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
