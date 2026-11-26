"""S8: structured and traceable preliminary legal report."""

from __future__ import annotations

from copy import deepcopy
from typing import Any


def _get_s7_content(
    deliverable_s7: dict[str, Any],
    section_id: str,
) -> list[dict[str, Any]]:
    """Retrieve a section from S7 without modifying its content."""

    matches = [
        section
        for section in deliverable_s7["sections"]
        if section.get("section_id") == section_id
    ]

    if len(matches) != 1:
        raise ValueError(f"Missing or duplicate S7 section: {section_id}")

    content = matches[0].get("content")

    if not isinstance(content, list):
        raise ValueError(f"Invalid S7 section content: {section_id}")

    return deepcopy(content)



def _reject_unauthorized_legal_conclusions(value: Any) -> None:
    """Reject non-null legal conclusions at any nesting level."""

    if isinstance(value, dict):
        for key, item in value.items():
            if key == "legal_conclusion" and item is not None:
                raise ValueError(
                    "Unauthorized legal conclusion in S7 input."
                )

            _reject_unauthorized_legal_conclusions(item)

    elif isinstance(value, list):
        for item in value:
            _reject_unauthorized_legal_conclusions(item)


def generate_legal_report_s8(
    request: dict[str, Any],
    analysis: dict[str, Any],
    deliverable_s7: dict[str, Any],
) -> dict[str, Any]:
    """Generate ten traceable sections without legal conclusions."""

    # Validate the three required input structures.
    if not all(
        isinstance(value, dict)
        for value in (request, analysis, deliverable_s7)
    ):
        raise ValueError("Invalid S8 input structures.")

    case_id = request.get("case_id")

    if not isinstance(case_id, str) or not case_id.strip():
        raise ValueError("Missing or invalid case_id.")

    # Prevent mixing information from different cases.
    if analysis.get("case_id") != case_id:
        raise ValueError("Analysis case_id mismatch.")

    if deliverable_s7.get("case_id") != case_id:
        raise ValueError("S7 case_id mismatch.")

    # Require the expected preparatory S7 deliverable.
    if deliverable_s7.get("lawyer_validated") is not False:
        raise ValueError("Unexpected S7 lawyer validation status.")

    # Reject unauthorized nested legal conclusions before copying S7.
    _reject_unauthorized_legal_conclusions(deliverable_s7)

    # Extract existing S7 sections without changing their content.
    facts = _get_s7_content(deliverable_s7, "S7-01")
    declarations = _get_s7_content(deliverable_s7, "S7-02")
    rules = _get_s7_content(deliverable_s7, "S7-03")
    interpretation = _get_s7_content(deliverable_s7, "S7-04")
    strategy = _get_s7_content(deliverable_s7, "S7-05")

    # Preserve original case information.
    parties = deepcopy(request.get("parties", []))
    evidence = deepcopy(request.get("evidence", []))
    timeline = deepcopy(analysis.get("timeline", []))

    # Preserve explicit event-evidence links only.
    evidence_ids = {
        item["evidence_id"]
        for item in evidence
        if isinstance(item, dict) and isinstance(item.get("evidence_id"), str)
    }

    evidence_traceability = []

    for event in request.get("events", []):
        if not isinstance(event, dict):
            continue

        for evidence_id in event.get("evidence_ids", []):
            if evidence_id in evidence_ids:
                evidence_traceability.append({
                    "event_id": event["event_id"],
                    "evidence_id": evidence_id,
                    "relation": "explicit_request_link",
                })

    # Collect diagnostics without inventing missing information.
    diagnostics = {
        "reference_errors": deepcopy(
            analysis.get("reference_errors", [])
        ),
        "legal_version_errors": deepcopy(
            analysis.get("legal_version_errors", [])
        ),
        "temporal_consistency_findings": deepcopy(
            analysis.get("temporal_consistency_findings", [])
        ),
        "missing_information": deepcopy(
            request.get("missing_information", [])
        ),
        "contradictions": deepcopy(
            request.get("contradictions", [])
        ),
    }

    # Build the ten report sections.
    sections = [
        {
            "section_id": "S8-01",
            "title": "Identification du dossier",
            "content": {
                "case_id": case_id,
                "request_id": request.get("request_id"),
                "contract_version": request.get("contract_version"),
                "lang": request.get("lang"),
            },
        },
        {
            "section_id": "S8-02",
            "title": "Resume general",
            "content": {
                "analysis_status": analysis.get("analysis_status"),
                "number_of_parties": len(parties),
                "number_of_events": len(request.get("events", [])),
                "number_of_claims": len(request.get("claims", [])),
                "number_of_evidence": len(evidence),
            },
        },
        {
            "section_id": "S8-03",
            "title": "Parties concernees",
            "content": parties,
        },
        {
            "section_id": "S8-04",
            "title": "Faits et elements documentaires",
            "content": facts,
        },
        {
            "section_id": "S8-05",
            "title": "Declarations et demandes",
            "content": declarations,
        },
        {
            "section_id": "S8-06",
            "title": "Chronologie des evenements",
            "content": timeline,
        },
        {
            "section_id": "S8-07",
            "title": "Preuves et tracabilite",
            "content": {
                "evidence": evidence,
                "explicit_event_evidence_links": evidence_traceability,
            },
        },
        {
            "section_id": "S8-08",
            "title": "Sources et regles juridiques",
            "content": rules,
        },
        {
            "section_id": "S8-09",
            "title": "Incertitudes et contradictions",
            "content": diagnostics,
        },
        {
            "section_id": "S8-10",
            "title": "Interpretation et strategie juridique",
            "content": {
                "interpretation": interpretation,
                "strategy": strategy,
                "legal_conclusion": None,
            },
        },
    ]

    # Return an independent preliminary report.
    return {
        "report_version": "track_a_legal_report_s8.v1",
        "case_id": case_id,
        "document_status": "preparatory",
        "lawyer_validated": False,
        "legal_conclusion": None,
        "sections": sections,
    }
