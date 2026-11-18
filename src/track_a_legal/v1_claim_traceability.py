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

        # A valid reference is not proof of a claim's truth.
        result.append({
            "claim_id": claim["claim_id"],
            "party_id": claim["party_id"],
            "text": claim["text"],
            "status": "unverified",
            "event_ids": event_ids,
            "evidence_ids": evidence_ids,
            "legal_source_ids": legal_source_ids,
        })

    return result
