"""End-to-end contract tests for DS4 Lawyer Track v1."""

import json
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker

from src.track_a_legal.v1_handler import handle_v1


SCHEMA_DIR = Path("data/mock_cards/schemas")


def test_v1_e2e_valid_case_with_evidence_mapping() -> None:
    """Validate a fictitious case through Request and Response v1."""

    # Load both official JSON Schema contracts.
    request_schema = json.loads(
        (SCHEMA_DIR / "track_a_request.v1.schema.json").read_text(
            encoding="utf-8-sig"
        )
    )
    response_schema = json.loads(
        (SCHEMA_DIR / "track_a_response.v1.schema.json").read_text(
            encoding="utf-8-sig"
        )
    )

    request_validator = Draft202012Validator(
        request_schema,
        format_checker=FormatChecker(),
    )
    response_validator = Draft202012Validator(
        response_schema,
        format_checker=FormatChecker(),
    )

    # Use fictitious data with an explicit event-evidence link.
    request = {
        "contract_version": "track_a.v1",
        "request_id": "REQ-E2E-001",
        "case_id": "CASE-E2E-001",
        "lang": "fr",
        "reference_date": "2026-11-17",
        "parties": [
            {
                "party_id": "P-001",
                "name": "Personne fictive",
                "role": "demandeur",
            }
        ],
        "events": [
            {
                "event_id": "EV-001",
                "date": "2026-10-15",
                "description": "Reception d'un document fictif.",
                "source_ids": ["SRC-001"],
                "evidence_ids": ["EVD-001"],
            }
        ],
        "claims": [
            {
                "claim_id": "CL-001",
                "party_id": "P-001",
                "text": "Reception du document declaree.",
                "event_ids": ["EV-001"],
                "evidence_ids": ["EVD-001"],
            }
        ],
        "evidence": [
            {
                "evidence_id": "EVD-001",
                "type": "document",
                "description": "Document fictif de reception.",
                "source": "SRC-001",
            }
        ],
    }

    # Validate the input contract.
    request_validator.validate(request)

    # Execute the complete v1 pipeline.
    response = handle_v1(request)

    # Validate the output contract.
    response_validator.validate(response)

    # Verify identity, status, and explicit evidence traceability.
    assert response["status"] == "ok"
    assert response["request_id"] == "REQ-E2E-001"
    assert response["result"]["case_id"] == "CASE-E2E-001"
    assert response["result"]["analysis_status"] == "preparatory"

    assert response["result"]["evidence_mapping"] == [
        {
            "event_id": "EV-001",
            "evidence_id": "EVD-001",
            "relation": "source",
        }
    ]

    # The preparatory track must not invent legal conclusions.
    assert response["result"]["legal_conclusion"] is None
    assert response["citations"] == []



def test_v1_e2e_invalid_request_refusal() -> None:
    """Reject an invalid Request v1 with a schema-valid refusal."""

    # Load the official input and output contracts.
    request_schema = json.loads(
        (SCHEMA_DIR / "track_a_request.v1.schema.json").read_text(
            encoding="utf-8-sig"
        )
    )
    response_schema = json.loads(
        (SCHEMA_DIR / "track_a_response.v1.schema.json").read_text(
            encoding="utf-8-sig"
        )
    )

    request_validator = Draft202012Validator(
        request_schema,
        format_checker=FormatChecker(),
    )
    response_validator = Draft202012Validator(
        response_schema,
        format_checker=FormatChecker(),
    )

    # Deliberately omit the mandatory case_id.
    request = {
        "contract_version": "track_a.v1",
        "request_id": "REQ-E2E-INVALID-001",
        "lang": "fr",
        "parties": [],
        "events": [],
        "claims": [],
        "evidence": [],
    }

    # Confirm that the official Request schema rejects the input.
    assert list(request_validator.iter_errors(request))

    # Execute the full DS4 Handler.
    response = handle_v1(request)

    # The refusal must satisfy the official Response schema.
    response_validator.validate(response)

    assert response["status"] == "refus"
    assert response["request_id"] == "REQ-E2E-INVALID-001"
    assert response["result"] is None
    assert response["citations"] == []
    assert response["refus"]["code"] == "PARAM_INVALIDE"
    assert "erreur" not in response



def test_v1_e2e_explicit_contradiction() -> None:
    """Flag declared contradictions without inventing conclusions."""

    # Load the official Request and Response v1 contracts.
    request_schema = json.loads(
        (SCHEMA_DIR / "track_a_request.v1.schema.json").read_text(
            encoding="utf-8-sig"
        )
    )
    response_schema = json.loads(
        (SCHEMA_DIR / "track_a_response.v1.schema.json").read_text(
            encoding="utf-8-sig"
        )
    )

    request_validator = Draft202012Validator(
        request_schema,
        format_checker=FormatChecker(),
    )
    response_validator = Draft202012Validator(
        response_schema,
        format_checker=FormatChecker(),
    )

    # Use a fictitious case with an explicitly declared contradiction.
    request = {
        "contract_version": "track_a.v1",
        "request_id": "REQ-CONTRA-001",
        "case_id": "CASE-CONTRA-001",
        "lang": "fr",
        "parties": [],
        "events": [],
        "claims": [],
        "evidence": [],
        "contradictions": [
            {
                "contradiction_id": "CONTRA-001",
                "description": (
                    "Deux sources indiquent des dates differentes."
                ),
                "source_ids": ["SRC-001", "SRC-002"],
            }
        ],
    }

    # Validate the incoming Request.
    request_validator.validate(request)

    # Execute the complete DS4 v1 pipeline.
    response = handle_v1(request)

    # Validate the outgoing Response.
    response_validator.validate(response)

    # Confirm explicit contradictions are reflected in the status.
    assert response["status"] == "ok"
    assert response["result"]["analysis_status"] == (
        "contradictory_evidence"
    )

    # Respect the official Response v1 restrictions.
    assert response["result"]["contradictions"] == []
    assert response["result"]["legal_conclusion"] is None
    assert response["citations"] == []
