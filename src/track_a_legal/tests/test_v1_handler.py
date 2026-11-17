"""Contract tests for the DS4 Handler v1."""

from __future__ import annotations

import json
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker

from src.track_a_legal.v1_handler import handle_v1


# Load the official Response v1 contract.
SCHEMA_PATH = Path(
    "data/mock_cards/schemas/track_a_response.v1.schema.json"
)
RESPONSE_SCHEMA = json.loads(
    SCHEMA_PATH.read_text(encoding="utf-8-sig")
)
RESPONSE_VALIDATOR = Draft202012Validator(
    RESPONSE_SCHEMA,
    format_checker=FormatChecker(),
)


def test_handler_v1_minimal_valid_request() -> None:
    """A minimal Request v1 produces a valid preparatory response."""

    # Build a fictitious case without legal evidence.
    request = {
        "contract_version": "track_a.v1",
        "request_id": "REQ-HANDLER-001",
        "case_id": "CASE-HANDLER-001",
        "lang": "fr",
        "reference_date": "2026-11-17",
        "parties": [],
        "events": [],
        "claims": [],
        "evidence": [],
    }

    # Execute the Handler v1.
    response = handle_v1(request)

    # Validate the full official response contract.
    RESPONSE_VALIDATOR.validate(response)

    # Check the expected safe preparatory state.
    assert response["status"] == "ok"
    assert response["request_id"] == request["request_id"]
    assert response["case_id"] == request["case_id"]
    assert response["result"]["analysis_status"] == "preparatory"
    assert response["result"]["legal_conclusion"] is None
    assert response["citations"] == []
    assert response["refus"] is None

    # Verify the summary of an empty case.
    assert response["result"]["case_summary"] == {
        "number_of_parties": 0,
        "number_of_events": 0,
        "number_of_claims": 0,
        "number_of_evidence": 0,
    }


def test_handler_v1_explicit_evidence_mapping() -> None:
    """Preserve explicit event-evidence links without inventing citations."""

    # Create a valid fictitious Request v1.
    request = {
        "contract_version": "track_a.v1",
        "request_id": "REQ-MAPPING-001",
        "case_id": "CASE-MAPPING-001",
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
                "date": "2026-10-10",
                "description": "Evenement fictif.",
                "source_ids": ["EVD-001"],
                "evidence_ids": ["EVD-001"],
            }
        ],
        "claims": [
            {
                "claim_id": "CL-001",
                "party_id": "P-001",
                "text": "Declaration fictive.",
                "event_ids": ["EV-001"],
                "evidence_ids": ["EVD-001"],
            }
        ],
        "evidence": [
            {
                "evidence_id": "EVD-001",
                "type": "document",
                "description": "Document fictif.",
                "source": "test_document.pdf",
            }
        ],
    }

    # Execute the Handler and validate the official response contract.
    response = handle_v1(request)
    RESPONSE_VALIDATOR.validate(response)

    # Verify the exact event-evidence relationship.
    assert response["result"]["evidence_mapping"] == [
        {
            "event_id": "EV-001",
            "evidence_id": "EVD-001",
            "relation": "source",
        }
    ]

    # Preserve the legal safety constraints.
    assert response["result"]["legal_conclusion"] is None
    assert response["citations"] == []
    assert response["result"]["claims_analysis"][0]["status"] == "unverified"


def test_handler_v1_unknown_evidence_reference() -> None:
    """Report unknown evidence references without inventing mappings."""

    # Build a fictitious case with an invalid evidence reference.
    request = {
        "contract_version": "track_a.v1",
        "request_id": "REQ-INVALID-REF-001",
        "case_id": "CASE-INVALID-REF-001",
        "lang": "fr",
        "reference_date": "2026-11-17",
        "parties": [],
        "events": [
            {
                "event_id": "EV-001",
                "date": "2026-10-10",
                "description": "Evenement fictif.",
                "source_ids": [],
                "evidence_ids": ["EVD-UNKNOWN"],
            }
        ],
        "claims": [],
        "evidence": [],
    }

    # Execute the Handler and validate the official Response v1 schema.
    response = handle_v1(request)
    RESPONSE_VALIDATOR.validate(response)

    # Distinguish technical success from insufficient evidence.
    assert response["status"] == "ok"
    assert response["result"]["analysis_status"] == "insufficient_evidence"

    # Verify that the invalid reference remains traceable.
    assert response["result"]["uncertain_information"] == [
        {
            "reference_id": "EVD-UNKNOWN",
            "reason": "UNKNOWN_REFERENCE at events/0/evidence_ids/0",
        }
    ]

    # Never fabricate evidence relationships or legal conclusions.
    assert response["result"]["evidence_mapping"] == []
    assert response["result"]["legal_conclusion"] is None
    assert response["citations"] == []


def test_handler_v1_invalid_request_refusal() -> None:
    """Return a schema-valid refusal for an invalid Request v1."""

    # Deliberately omit the required case_id.
    request = {
        "contract_version": "track_a.v1",
        "request_id": "REQ-INVALID-001",
        "lang": "fr",
        "reference_date": "2026-11-17",
        "parties": [],
        "events": [],
        "claims": [],
        "evidence": [],
    }

    # Execute the Handler and validate its response contract.
    response = handle_v1(request)
    RESPONSE_VALIDATOR.validate(response)

    # Check the exact refusal structure.
    assert response["status"] == "refus"
    assert response["request_id"] == "REQ-INVALID-001"
    assert response["result"] is None
    assert response["citations"] == []
    assert response["refus"]["code"] == "PARAM_INVALIDE"
    assert response["refus"]["message_fr"] == "Requete invalide."

    # Verify the actual Arabic Unicode text.
    expected_ar = (
        "\u0637\u0644\u0628 "
        "\u063a\u064a\u0631 "
        "\u0635\u0627\u0644\u062d."
    )
    assert response["refus"]["message_ar"] == expected_ar

    # A refusal must not include an error object.
    assert "erreur" not in response


def test_handler_v1_internal_error_response() -> None:
    """Return a safe, schema-valid response for unexpected failures."""
    import json
    from unittest.mock import patch

    # Use a valid fictitious Request v1.
    request = {
        "contract_version": "track_a.v1",
        "request_id": "REQ-ERROR-001",
        "case_id": "CASE-ERROR-001",
        "lang": "fr",
        "parties": [],
        "events": [],
        "claims": [],
        "evidence": [],
    }

    # Simulate a technical exception inside the analysis engine.
    with patch(
        "src.track_a_legal.v1_handler.analyze_case_v1",
        side_effect=RuntimeError("SIMULATED_INTERNAL_FAILURE"),
    ):
        response = handle_v1(request)

    # Validate the official Response v1 contract.
    RESPONSE_VALIDATOR.validate(response)

    # Check the structured technical error.
    assert response["status"] == "erreur"
    assert response["request_id"] == "REQ-ERROR-001"
    assert response["result"] is None
    assert response["citations"] == []
    assert response["refus"] is None
    assert response["erreur"]["type"] == "INTERNAL_ERROR"
    assert response["erreur"]["message_fr"] == (
        "Erreur interne du traitement."
    )

    # Verify the actual Arabic Unicode characters.
    expected_ar = (
        "\u062e\u0637\u0623 "
        "\u062f\u0627\u062e\u0644\u064a "
        "\u0641\u064a "
        "\u0627\u0644\u0645\u0639\u0627\u0644\u062c\u0629."
    )
    assert response["erreur"]["message_ar"] == expected_ar

    # Never expose internal exception details to callers.
    serialized = json.dumps(response, ensure_ascii=True)
    assert "SIMULATED_INTERNAL_FAILURE" not in serialized
    assert "RuntimeError" not in serialized


def test_handler_v1_post_analysis_error_response() -> None:
    """Return a safe error if response construction fails."""
    import json
    from unittest.mock import patch

    # Use a valid fictitious Request v1.
    request = {
        "contract_version": "track_a.v1",
        "request_id": "REQ-POST-ERROR-001",
        "case_id": "CASE-POST-ERROR-001",
        "lang": "fr",
        "parties": [],
        "events": [],
        "claims": [],
        "evidence": [],
    }

    # Simulate incomplete analysis output.
    # The missing reference_errors field causes a KeyError
    # during response construction.
    incomplete_analysis = {
        "timeline": [],
        "analysis_status": "preparatory",
    }

    with patch(
        "src.track_a_legal.v1_handler.analyze_case_v1",
        return_value=incomplete_analysis,
    ):
        response = handle_v1(request)

    # Validate the complete official Response v1 contract.
    RESPONSE_VALIDATOR.validate(response)

    # Check the structured technical error response.
    assert response["status"] == "erreur"
    assert response["request_id"] == "REQ-POST-ERROR-001"
    assert response["result"] is None
    assert response["citations"] == []
    assert response["refus"] is None
    assert response["erreur"]["type"] == "INTERNAL_ERROR"

    # Ensure implementation details are never exposed.
    serialized = json.dumps(response, ensure_ascii=True)
    assert "KeyError" not in serialized
    assert "reference_errors" not in serialized
