"""Explicit claim traceability for the DS4 Lawyer Track v1."""

from __future__ import annotations

from typing import Any


def build_claim_traceability(
    request: dict[str, Any],
) -> list[dict[str, Any]]:
    """Preserve valid explicit links without verifying legal claims.

    The caller must first validate the Request v1 JSON Schema.
    Unknown references are excluded, never inferred or replaced.
    """

    # Build identifier sets from the supplied case.
    known_events = {
        item["event_id"]
        for item in request.get("events", [])
    }
    known_evidence = {
        item["evidence_id"]
        for item in request.get("evidence", [])
    }
    known_legal_sources = {
        item["source_id"]
        for item in request.get("legal_sources", [])
    }

    result: list[dict[str, Any]] = []

    # Preserve the original order of claims.
    for claim in request.get("claims", []):

        # Keep only explicitly declared and existing references.
        event_ids = [
            identifier
            for identifier in claim.get("event_ids", [])
            if identifier in known_events
        ]
        evidence_ids = [
            identifier
            for identifier in claim.get("evidence_ids", [])
            if identifier in known_evidence
        ]
        legal_source_ids = [
            identifier
            for identifier in claim.get("legal_source_ids", [])
            if identifier in known_legal_sources
        ]

        # Describe explicit reference coverage without assessing truth.
        missing_link_types = []

        if not event_ids:
            missing_link_types.append("events")

        if not evidence_ids:
            missing_link_types.append("evidence")

        if not legal_source_ids:
            missing_link_types.append("legal_sources")

        reference_coverage = {
            "has_event_links": bool(event_ids),
            "has_evidence_links": bool(evidence_ids),
            "has_legal_source_links": bool(legal_source_ids),
            "missing_link_types": missing_link_types,
        }

        # A valid reference is not proof of a claim's truth.
        result.append({
            "reference_coverage": reference_coverage,
            "claim_id": claim["claim_id"],
            "party_id": claim["party_id"],
            "text": claim["text"],
            "status": "unverified",
            "event_ids": event_ids,
            "evidence_ids": evidence_ids,
            "legal_source_ids": legal_source_ids,
        })

    return result
