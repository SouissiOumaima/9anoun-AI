"""Tests du pipeline combin? DS2 + DS3 + DS4 v1."""

from copy import deepcopy

import pytest

from src.document_intelligence.tests import (
    test_document_intelligence_service as ds3_fixtures,
)
from src.track_a_legal.tests.test_ds2_v1_pipeline import (
    make_valid_request,
)
from src.track_a_legal.tools import ds2_v1_pipeline
from src.track_a_legal.tools.ds2_ds3_v1_pipeline import (
    run_ds2_ds3_ds4_v1_pipeline,
)


@pytest.fixture
def pipeline_inputs(tmp_path):
    """Pr?parer des donn?es fictives officielles DS3 et DS4."""

    # G?n?rer la r?ponse DS3 avec un client Gemini fictif.
    storage = ds3_fixtures.storage.__wrapped__(tmp_path)

    ds3_response = ds3_fixtures._call(
        ds3_fixtures._request(),
        storage,
        client=ds3_fixtures._client(),
    )

    assert ds3_response["status"] == "ok"
    assert ds3_response["mode"] == "live"

    # Pr?parer une preuve documentaire explicitement d?clar?e.
    ds4_request = make_valid_request()
    evidence_id = "EV-DS3-001"

    ds4_request["evidence"].append({
        "evidence_id": evidence_id,
        "type": "document",
        "description": "Fiche de paie fictive",
        "source": "Fixture DS3",
    })

    return {
        "ds4_request": ds4_request,
        "ds2_request": {"query": "test"},
        "ds3_response": ds3_response,
        "subject_id": "P1",
        "document_links": {
            ds3_response["document_id"]: evidence_id,
        },
    }


def test_combined_pipeline_success(
    pipeline_inputs,
    valid_ds2_response,
    monkeypatch,
):
    """V?rifier les sources, la conclusion et l'immuabilit?."""

    # Injecter la r?ponse DS2 synth?tique officielle.
    def fake_ds2_handle(request, *, live=True):
        assert live is True
        return deepcopy(valid_ds2_response)

    monkeypatch.setattr(
        ds2_v1_pipeline,
        "ds2_handle",
        fake_ds2_handle,
    )

    original = deepcopy(pipeline_inputs)

    # Ex?cuter les trois composants.
    response = run_ds2_ds3_ds4_v1_pipeline(
        **pipeline_inputs
    )

    assert response["status"] == "ok"
    assert response["result"]["legal_conclusion"] is None
    assert response["citations"] == []

    # Conserver les r?f?rences DS2 attendues.
    expected_ids = [
        article["article_id"]
        for article in valid_ds2_response["results"]
    ]

    assert response["result"]["legal_sources_used"] == expected_ids

    # Aucune mutation des entr?es.
    assert pipeline_inputs == original


@pytest.mark.parametrize(
    "scenario",
    [
        "existing_facts",
        "mock_response",
        "missing_link",
        "unknown_evidence",
    ],
)
def test_combined_pipeline_rejects_unsafe_inputs(
    pipeline_inputs,
    monkeypatch,
    scenario,
):
    """Refuser les donn?es non exploitables avant DS2."""

    # DS2 ne doit jamais ?tre appel? dans ces sc?narios.
    def forbidden_ds2_handle(*args, **kwargs):
        raise AssertionError("DS2_SHOULD_NOT_BE_CALLED")

    monkeypatch.setattr(
        ds2_v1_pipeline,
        "ds2_handle",
        forbidden_ds2_handle,
    )

    inputs = deepcopy(pipeline_inputs)

    if scenario == "existing_facts":
        # Emp?cher l'?crasement des faits d?j? pr?sents.
        inputs["ds4_request"]["document_facts"] = [
            {"fact_id": "EXISTING"}
        ]

    elif scenario == "mock_response":
        # Refuser les extractions DS3 simul?es.
        inputs["ds3_response"]["mode"] = "mock"

    elif scenario == "missing_link":
        # Ne pas inventer d'association documentaire.
        inputs["document_links"] = {}

    elif scenario == "unknown_evidence":
        # Refuser une preuve absente du dossier.
        document_id = inputs["ds3_response"]["document_id"]
        inputs["document_links"] = {
            document_id: "EV-UNKNOWN"
        }

    # Tous les sc?narios doivent produire un refus explicite.
    with pytest.raises(ValueError):
        run_ds2_ds3_ds4_v1_pipeline(**inputs)


def test_pipeline_provenance_complete(
    pipeline_inputs,
    valid_ds2_response,
    monkeypatch,
):
    """Preserve documentary metadata and explicit evidence links."""

    monkeypatch.setattr(
        ds2_v1_pipeline,
        "ds2_handle",
        lambda request, *, live=True: deepcopy(valid_ds2_response),
    )

    original = deepcopy(pipeline_inputs)

    result = run_ds2_ds3_ds4_v1_pipeline(
        **pipeline_inputs,
        include_provenance=True,
    )

    analysis = result["analysis"]
    provenance = result["document_provenance"]

    assert analysis["status"] == "ok"
    assert analysis["result"]["legal_conclusion"] is None
    assert len(provenance) == 3

    document_id = pipeline_inputs["ds3_response"]["document_id"]
    fields = pipeline_inputs["ds3_response"]["result"]["fields"]

    expected_ids = {
        f"{document_id}:{name}"
        for name in ("base_salary", "gross_salary", "cnss_employee")
    }

    assert set(provenance) == expected_ids

    for item in provenance.values():
        assert item["document_id"] == document_id
        assert item["evidence_id"] == "EV-DS3-001"
        assert item["subject_id"] == "P1"
        assert item["currency"] == "TND"
        assert item["user_confirmed"] is False
        assert item["official_authenticity_confirmed"] is False

        assert item["period_start_source"]["field"] == fields["period_start"]
        assert item["period_end_source"]["field"] == fields["period_end"]

    # Preserve all original inputs.
    assert pipeline_inputs == original


def test_pipeline_provenance_backward_compatibility(
    pipeline_inputs,
    valid_ds2_response,
    monkeypatch,
):
    """Keep the official response unchanged by default."""

    from src.track_a_legal.v1_handler import _RESPONSE_VALIDATOR

    monkeypatch.setattr(
        ds2_v1_pipeline,
        "ds2_handle",
        lambda request, *, live=True: deepcopy(valid_ds2_response),
    )

    default = run_ds2_ds3_ds4_v1_pipeline(**pipeline_inputs)

    enriched = run_ds2_ds3_ds4_v1_pipeline(
        **pipeline_inputs,
        include_provenance=True,
    )

    assert default == enriched["analysis"]
    assert "document_provenance" not in default

    # Validate the official response, not the internal envelope.
    _RESPONSE_VALIDATOR.validate(default)
    _RESPONSE_VALIDATOR.validate(enriched["analysis"])


@pytest.mark.parametrize(
    "scenario",
    ["missing_link", "unknown_evidence", "mock_response"],
)
def test_pipeline_provenance_rejects_unsafe_inputs(
    pipeline_inputs,
    monkeypatch,
    scenario,
):
    """Never preserve provenance for rejected documentary inputs."""

    def forbidden_ds2_handle(*args, **kwargs):
        pytest.fail("DS2 must not be called.")

    monkeypatch.setattr(
        ds2_v1_pipeline,
        "ds2_handle",
        forbidden_ds2_handle,
    )

    inputs = deepcopy(pipeline_inputs)

    if scenario == "missing_link":
        inputs["document_links"] = {}

    elif scenario == "unknown_evidence":
        document_id = inputs["ds3_response"]["document_id"]
        inputs["document_links"] = {document_id: "EV-UNKNOWN"}

    elif scenario == "mock_response":
        inputs["ds3_response"]["mode"] = "mock"

    with pytest.raises(ValueError):
        run_ds2_ds3_ds4_v1_pipeline(
            **inputs,
            include_provenance=True,
        )


def test_pipeline_provenance_rejects_inconsistent_ids(
    pipeline_inputs,
    monkeypatch,
):
    """Reject provenance that does not match converted fact IDs."""

    from src.track_a_legal.tools import ds2_ds3_v1_pipeline

    monkeypatch.setattr(
        ds2_ds3_v1_pipeline,
        "build_document_provenance",
        lambda *args, **kwargs: {"UNKNOWN-FACT": {}},
    )

    def forbidden_ds2_handle(*args, **kwargs):
        pytest.fail("DS2 must not be called.")

    monkeypatch.setattr(
        ds2_v1_pipeline,
        "ds2_handle",
        forbidden_ds2_handle,
    )

    with pytest.raises(
        ValueError,
        match="Inconsistent document provenance",
    ):
        run_ds2_ds3_ds4_v1_pipeline(
            **pipeline_inputs,
            include_provenance=True,
        )
