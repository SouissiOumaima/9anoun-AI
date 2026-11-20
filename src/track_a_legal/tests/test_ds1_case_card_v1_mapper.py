from copy import deepcopy
from pathlib import Path

import pytest

from src.track_a_legal.tools.ds1_case_card_v1_mapper import (
    CaseCardV1MappingError,
    map_case_card_to_track_a_v1,
)


def build_case_card():
    """Créer une Case Card DS1 fictive et cohérente."""

    return {
        "card_id": "case-mapper-001",
        "organization_id": "org-test",
        "card_type": "case",
        "data": {
            "title": "Affaire fictive",
            "jurisdiction": "TN",
            "documents": [
                {
                    "document_id": "doc-001",
                    "label": "Contrat",
                    "file_name": "contrat.pdf",
                    "mime_type": "application/pdf",
                    "storage_ref": (
                        "tradrly://cards/case-mapper-001/documents/doc-001"
                    ),
                }
            ],
            "parties": [
                {
                    "party_id": "party-001",
                    "name": "Ahmed Ben Ali",
                    "role": "employee",
                    "party_type": "physical_person",
                }
            ],
            "events": [
                {
                    "event_id": "event-001",
                    "date": "2024-01-01",
                    "date_precision": "exact",
                    "description": "Début du contrat.",
                    "evidence_ids": ["evidence-001"],
                    "confidence": 0.98,
                },
                {
                    "event_id": "event-002",
                    "date": "2024-02",
                    "date_precision": "month",
                    "description": "Événement situé en février 2024.",
                    "evidence_ids": [],
                    "confidence": 0.80,
                },
            ],
            "claims": [
                {
                    "claim_id": "claim-001",
                    "party_id": "party-001",
                    "text": "Le salarié formule une déclaration.",
                    "claim_type": "declaration",
                    "event_ids": ["event-001"],
                    "evidence_ids": ["evidence-001"],
                    "confidence": 0.60,
                }
            ],
            "evidence": [
                {
                    "evidence_id": "evidence-001",
                    "document_id": "doc-001",
                    "type": "employment_contract",
                    "description": "Clause relative au début du contrat.",
                    "citation": {
                        "citation_id": "citation-001",
                        "page": 1,
                        "excerpt": "Le contrat prend effet le 1er janvier 2024.",
                    },
                    "confidence": 0.98,
                    "supports": [
                        {
                            "fact_type": "event",
                            "fact_id": "event-001",
                        },
                        {
                            "fact_type": "claim",
                            "fact_id": "claim-001",
                        },
                    ],
                }
            ],
        },
    }


def test_maps_case_card_to_valid_track_a_v1():
    """Vérifier le mapping complet et le contrat final."""

    result = map_case_card_to_track_a_v1(
        build_case_card(),
        request_id="request-test-001",
        language="fr",
    )

    assert result["contract_version"] == "track_a.v1"
    assert result["case_id"] == "case-mapper-001"
    assert result["parties"][0]["party_id"] == "party-001"
    assert result["claims"][0]["claim_id"] == "claim-001"
    assert result["events"][0]["date"] == "2024-01-01"


def test_preserves_explicit_evidence_references():
    """Vérifier que les relations explicites sont conservées."""

    result = map_case_card_to_track_a_v1(
        build_case_card(),
        request_id="request-test-002",
        language="fr",
    )

    event = result["events"][0]

    assert event["source_ids"] == ["evidence-001"]
    assert event["evidence_ids"] == ["evidence-001"]

    evidence_source = result["evidence"][0]["source"]

    assert "citation-001" in evidence_source
    assert "page=1" in evidence_source


def test_partial_date_is_not_converted_to_exact_date():
    """Une date mensuelle ne doit jamais devenir une date exacte."""

    result = map_case_card_to_track_a_v1(
        build_case_card(),
        request_id="request-test-003",
        language="fr",
    )

    event = result["events"][1]

    assert event["date"] is None
    assert event["date_precision"] == "unknown"
    assert "month" in event["date_reason"]
    assert "2024-02" in event["date_reason"]


def test_rejects_unknown_event_evidence_reference():
    """Refuser une preuve absente de la Case Card."""

    card = build_case_card()
    card["data"]["events"][0]["evidence_ids"] = ["evidence-999"]

    with pytest.raises(CaseCardV1MappingError, match="Unknown references"):
        map_case_card_to_track_a_v1(
            card,
            request_id="request-test-004",
            language="fr",
        )


def test_rejects_unknown_document_reference():
    """Refuser une preuve associée à un document inexistant."""

    card = build_case_card()
    card["data"]["evidence"][0]["document_id"] = "doc-999"

    with pytest.raises(CaseCardV1MappingError, match="document_id"):
        map_case_card_to_track_a_v1(
            card,
            request_id="request-test-005",
            language="fr",
        )


def test_mapping_does_not_modify_original_case_card():
    """Garantir l'absence de mutation des données DS1."""

    card = build_case_card()
    original = deepcopy(card)

    map_case_card_to_track_a_v1(
        card,
        request_id="request-test-006",
        language="fr",
    )

    assert card == original
