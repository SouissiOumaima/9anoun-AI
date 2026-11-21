"""Handler v1 for the DS4 Lawyer Track."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker

from src.track_a_legal.v1_case_analysis import analyze_case_v1


# Load the official response contract.
_SCHEMA_PATH = Path(__file__).resolve().parents[2] / "data/mock_cards/schemas/track_a_response.v1.schema.json"
_RESPONSE_SCHEMA = json.loads(
    _SCHEMA_PATH.read_text(encoding="utf-8-sig")
)
_RESPONSE_VALIDATOR = Draft202012Validator(
    _RESPONSE_SCHEMA,
    format_checker=FormatChecker(),
)


def handle_v1(request: dict[str, Any]) -> dict[str, Any]:
    """Convert a valid Request v1 into a schema-compliant response."""

    # Run the existing DS4 analysis engine.
    try:
        analysis = analyze_case_v1(request)
    except ValueError:
        # Preserve request_id only when it is a valid string.
        request_id = (
            request.get("request_id")
            if isinstance(request, dict)
            and isinstance(request.get("request_id"), str)
            else None
        )

        # Return a structured refusal without legal conclusions.
        response = {
            "contract_version": "track_a.v1",
            "request_id": request_id,
            "status": "refus",
            "result": None,
            "citations": [],
            "refus": {
                "code": "PARAM_INVALIDE",
                "message_fr": "Requete invalide.",
                "message_ar": "\u0637\u0644\u0628 \u063a\u064a\u0631 \u0635\u0627\u0644\u062d.",
            },
            "computed_by": "DS4_Lawyer_Track_v1",
        }

        # Validate the refusal against the official contract.
        _RESPONSE_VALIDATOR.validate(response)
        return response
    except Exception:
        # Do not expose internal exception messages or tracebacks.
        request_id = (
            request.get("request_id")
            if isinstance(request, dict)
            and isinstance(request.get("request_id"), str)
            else None
        )

        # Return a schema-compliant technical error.
        response = {
            "contract_version": "track_a.v1",
            "request_id": request_id,
            "status": "erreur",
            "result": None,
            "citations": [],
            "refus": None,
            "erreur": {
                "type": "INTERNAL_ERROR",
                "message_fr": "Erreur interne du traitement.",
                "message_ar": "\u062e\u0637\u0623 "
                              "\u062f\u0627\u062e\u0644\u064a "
                              "\u0641\u064a "
                              "\u0627\u0644\u0645\u0639\u0627\u0644\u062c\u0629.",
            },
            "computed_by": "DS4_Lawyer_Track_v1",
        }

        # Validate the technical error against Response v1.
        _RESPONSE_VALIDATOR.validate(response)
        return response

    # Build mappings only from explicit event-evidence links.
    # Never infer a relationship from text similarity.
    # POST_ANALYSIS_ERROR_GUARD_V1
    try:
        known_evidence_ids = {
            item["evidence_id"]
            for item in request["evidence"]
        }

        # Deduplicate links while preserving their original order.
        seen_links = set()
        evidence_mapping = []

        for event in request["events"]:
            for evidence_id in event.get("evidence_ids", []):
                link = (event["event_id"], evidence_id)

                # Ignore unknown references and duplicate links.
                if evidence_id not in known_evidence_ids:
                    continue

                if link in seen_links:
                    continue

                seen_links.add(link)

                evidence_mapping.append({
                    "event_id": event["event_id"],
                    "evidence_id": evidence_id,
                    "relation": "source",
                })

        # Build the response using only allowed contract fields.
        result = {
            "case_id": request["case_id"],
            "case_summary": {
                "number_of_parties": len(request["parties"]),
                "number_of_events": len(request["events"]),
                "number_of_claims": len(request["claims"]),
                "number_of_evidence": len(request["evidence"]),
            },
            "parties": request["parties"],
            "timeline": analysis["timeline"],
            "claims_analysis": [
                {
                    "claim_id": item["claim_id"],
                    "party_id": item["party_id"],
                    "text": item["text"],
                    "status": "unverified",
                }
                for item in request["claims"]
            ],
            "evidence": request["evidence"],
            "evidence_mapping": evidence_mapping,
            "contradictions": [],
            "missing_evidence": [],
            "legal_conclusion": None,
            "legal_sources_used": [
                source["article_id"]
                for source in request.get("legal_sources", [])
            ],
            "analysis_status": analysis["analysis_status"],
            "uncertain_information": [
                {
                    "reference_id": str(error["reference_id"]),
                    "reason": (
                        f"{error['code']} at {error['path']}"
                    ),
                }
                for error in analysis["reference_errors"]
            ],
        }

        # Do not invent legal citations.
        response = {
            "contract_version": "track_a.v1",
            "request_id": request["request_id"],
            "case_id": request["case_id"],
            "status": "ok",
            "result": result,
            "citations": [],
            "refus": None,
            "computed_by": "DS4_Lawyer_Track_v1",
        }

        # Fail explicitly if the response violates its JSON Schema.
        _RESPONSE_VALIDATOR.validate(response)

        return response

    except Exception:
        request_id = (
            request.get("request_id")
            if isinstance(request, dict)
            and isinstance(request.get("request_id"), str)
            else None
        )

        # Return a schema-compliant technical error.
        response = {
            "contract_version": "track_a.v1",
            "request_id": request_id,
            "status": "erreur",
            "result": None,
            "citations": [],
            "refus": None,
            "erreur": {
                "type": "INTERNAL_ERROR",
                "message_fr": "Erreur interne du traitement.",
                "message_ar": "\u062e\u0637\u0623 "
                              "\u062f\u0627\u062e\u0644\u064a "
                              "\u0641\u064a "
                              "\u0627\u0644\u0645\u0639\u0627\u0644\u062c\u0629.",
            },
            "computed_by": "DS4_Lawyer_Track_v1",
        }

        # Validate the technical error against Response v1.
        _RESPONSE_VALIDATOR.validate(response)
        return response
