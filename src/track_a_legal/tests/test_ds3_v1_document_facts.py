"""Tests de conversion DS3 LIVE vers DS4 v1."""

import copy
import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from src.document_intelligence.tests import (
    test_document_intelligence_service as ds3_fixtures,
)
from src.track_a_legal.tools.ds3_v1_document_facts import (
    convert_ds3_facts_to_v1,
)
from src.track_a_legal.v1_document_fact_validation import (
    assess_document_fact,
)


@pytest.fixture
def live_response(tmp_path):
    """Produire une r?ponse DS3 LIVE sans appel Gemini r?el."""

    # Pr?parer le PDF fictif officiel dans le dossier temporaire.
    storage = ds3_fixtures.storage.__wrapped__(tmp_path)

    # Injecter explicitement le client fictif.
    response = ds3_fixtures._call(
        ds3_fixtures._request(),
        storage,
        client=ds3_fixtures._client(),
    )

    assert response["status"] == "ok"
    assert response["mode"] == "live"

    return response


def convert(response, links=None):
    """Convertir avec une preuve DS4 d?clar?e explicitement."""

    document_id = response["document_id"]

    if links is None:
        links = {document_id: "EV-001"}

    return convert_ds3_facts_to_v1(
        ds3_response=response,
        subject_id="P1",
        evidence=[{
            "evidence_id": "EV-001",
            "type": "document",
            "description": "Fiche de paie fictive",
            "source": "Fixture DS3",
        }],
        document_links=links,
    )


def test_live_conversion_preserves_three_monetary_facts(live_response):
    """Conserver les trois montants extraits et leurs citations."""

    facts = convert(live_response)

    assert len(facts) == 3

    values = {
        fact["field_name"]: fact["value"]
        for fact in facts
    }

    assert values == {
        "base_salary": "424.100",
        "gross_salary": "516.100",
        "cnss_employee": "47.378",
    }

    assert all(fact["citation"] for fact in facts)
    assert all(fact["evidence_id"] == "EV-001" for fact in facts)


@pytest.mark.parametrize("mode", ["mock", None, ""])
def test_non_live_response_never_becomes_v1_document_facts(live_response, mode):
    """Reject simulated or missing provenance even with valid citations and links."""
    response = copy.deepcopy(live_response)
    response["mode"] = mode
    assert convert(response) == []


@pytest.mark.parametrize("confidence", [0.0, 0.42, 0.896, 0.89999])
def test_low_confidence_visible_but_confirmation_cannot_establish_fact(live_response, confidence):
    response = copy.deepcopy(live_response)
    response["result"]["fields"]["base_salary"]["confidence"] = confidence
    fact = next(f for f in convert(response) if f["field_name"] == "base_salary")
    assert fact["confidence"] == confidence
    assert fact["user_confirmed"] is False
    assert "LOW_OR_MISSING_CONFIDENCE" in fact["warnings"]
    assessment = assess_document_fact({**fact, "user_confirmed": True})
    assert assessment["eligible_for_established_fact"] is False
    assert "LOW_OR_MISSING_CONFIDENCE" in assessment["reasons"]


@pytest.mark.parametrize("confidence", [0.90, 1.0])
def test_confidence_at_threshold_still_requires_explicit_confirmation(live_response, confidence):
    response = copy.deepcopy(live_response)
    response["result"]["fields"]["base_salary"]["confidence"] = confidence
    fact = next(f for f in convert(response) if f["field_name"] == "base_salary")
    assert "LOW_OR_MISSING_CONFIDENCE" not in fact["warnings"]
    assert "USER_CONFIRMATION_REQUIRED" in fact["warnings"]
    assert not assess_document_fact(fact)["eligible_for_established_fact"]
    assert assess_document_fact({**fact, "user_confirmed": True})["eligible_for_established_fact"]


@pytest.mark.parametrize("currency", [None, "", " ", 42, "tnd", "TND/mois"])
def test_missing_or_invalid_currency_cannot_become_document_fact(live_response, currency):
    response = copy.deepcopy(live_response)
    response["result"]["fields"]["base_salary"]["currency"] = currency
    assert all(f["field_name"] != "base_salary" for f in convert(response))


def test_currency_is_copied_from_each_ds3_field(live_response):
    from src.track_a_legal.tools.document_facts_adapter import extract_document_facts

    response = copy.deepcopy(live_response)
    response["result"]["fields"]["base_salary"]["currency"] = "EUR"
    facts = extract_document_facts(response, "P1")
    assert next(f for f in facts if f["property"] == "base_salary")["unit"] == "EUR"
    assert next(f for f in facts if f["property"] == "gross_salary")["unit"] == "TND"


def test_absent_currency_is_not_defaulted(live_response):
    response = copy.deepcopy(live_response)
    response["result"]["fields"]["base_salary"].pop("currency")
    assert all(f["field_name"] != "base_salary" for f in convert(response))


def test_converted_facts_match_ds4_v1_schema(live_response):
    """Valider chaque fait contre le contrat officiel DS4 v1."""

    schema_path = Path(
        "data/mock_cards/schemas/"
        "track_a_request.v1.schema.json"
    )

    schema = json.loads(
        schema_path.read_text(encoding="utf-8")
    )

    fact_schema = schema["properties"]["document_facts"]["items"]
    validator = Draft202012Validator(fact_schema)

    for fact in convert(live_response):
        assert list(validator.iter_errors(fact)) == []


def test_no_automatic_human_confirmation(live_response):
    """Une extraction ne constitue jamais une confirmation humaine."""

    for fact in convert(live_response):
        assert fact["user_confirmed"] is False

        assessment = assess_document_fact(fact)

        assert assessment["eligible_for_established_fact"] is False
        assert "USER_NOT_CONFIRMED" in assessment["reasons"]


def test_mock_response_is_rejected(live_response):
    """Refuser les r?ponses DS3 en mode mock."""

    response = copy.deepcopy(live_response)
    response["mode"] = "mock"

    assert convert(response) == []


def test_missing_explicit_link_is_rejected(live_response):
    """Ne jamais inventer une association document-preuve."""

    assert convert(live_response, links={}) == []


def test_wrong_evidence_link_is_rejected(live_response):
    """Refuser une association vers une preuve inconnue."""

    links = {live_response["document_id"]: "EV-999"}

    assert convert(live_response, links=links) == []


def test_missing_citations_are_rejected(live_response):
    """Refuser les r?ponses sans citations documentaires."""

    response = copy.deepcopy(live_response)
    response["citations"] = []

    assert convert(response) == []


def test_original_response_is_not_modified(live_response):
    """Garantir l'absence de mutation des donn?es DS3."""

    original = copy.deepcopy(live_response)

    convert(live_response)

    assert live_response == original


@pytest.mark.parametrize("currency", ["EUR", "USD"])
def test_v1_rejects_foreign_currency(live_response, currency):
    """Track A v1 ne doit pas perdre une devise etrangere."""
    response = copy.deepcopy(live_response)
    response["result"]["fields"]["base_salary"]["currency"] = currency

    facts = convert(response)

    # Exclure le montant etranger et conserver les autres faits TND.
    assert {fact["field_name"] for fact in facts} == {
        "gross_salary",
        "cnss_employee",
    }
