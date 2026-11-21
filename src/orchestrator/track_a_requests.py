"""Construction sûre des requêtes DS1 vers le contrat DS4 Track A v0."""

from __future__ import annotations

from typing import Any, Mapping
from copy import deepcopy

from .case_card import validate_case_card_references


def build_track_a_request(*, request_id: str, case_id: str, language: str) -> dict[str, Any]:
    """Build the smallest valid Track A request without inventing case facts.

    The current local Card model only authorizes a case identifier.  It does
    not yet expose structured parties, events, claims, or evidence, so DS1
    deliberately sends empty collections instead of guessing their content.
    A future Case Card connector can populate these fields from verified data.
    """

    if language not in {"fr", "ar"}:
        raise ValueError("Track A language must be fr or ar")
    if not request_id or not case_id:
        raise ValueError("Track A requires request_id and case_id")
    return {
        "contract_version": "track_a.v0",
        "request_id": request_id,
        "case_id": case_id,
        "lang": language,
        "parties": [],
        "events": [],
        "claims": [],
        "evidence": [],
    }


def build_track_a_request_from_case_card(
    *, request_id: str, case_id: str, language: str, case_card: Mapping[str, Any],
    contract_version: str = "track_a.v0",
) -> dict[str, Any]:
    """Map a validated DS1 Case Card into the accepted DS4 v0 request.

    DS4 v0 cannot carry confidence scores or rich citation objects. DS1 keeps
    those values in the Case Card and transports each evidence item through a
    stable, reviewable ``source`` reference. No fact is inferred here.
    """

    if contract_version not in {"track_a.v0", "track_a.v1"}:
        raise ValueError("Unsupported Track A contract version")
    if language not in {"fr", "ar"} or not request_id or not case_id:
        raise ValueError("Track A requires valid identifiers and language")
    if case_card.get("card_id") != case_id:
        raise ValueError("Case Card id must match the active case_id")
    validate_case_card_references(case_card)
    data = case_card["data"]

    events: list[dict[str, Any]] = []
    for event in data["events"]:
        date = event["date"]
        if not isinstance(date, str):
            raise ValueError(f"event {event['event_id']} has no exact date for Track A v0")
        events.append({
            "event_id": event["event_id"], "date": date, "description": event["description"],
            "source_ids": list(event["evidence_ids"]),
        })

    evidence: list[dict[str, Any]] = []
    for item in data["evidence"]:
        citation = item["citation"]
        source = (
            f"case://{case_id}/documents/{item['document_id']}"
            f"#citation={citation['citation_id']}&page={citation['page']}"
        )
        evidence.append({
            "evidence_id": item["evidence_id"], "type": item["type"],
            "description": item["description"], "source": source,
        })

    request = {
        "contract_version": contract_version, "request_id": request_id,
        "case_id": case_id, "lang": language,
        "parties": [
            {"party_id": party["party_id"], "name": party["name"], "role": party["role"]}
            for party in data["parties"]
        ],
        "events": events,
        "claims": [
            {"claim_id": claim["claim_id"], "party_id": claim["party_id"], "text": claim["text"]}
            for claim in data["claims"]
        ],
        "evidence": evidence,
    }
    if contract_version == "track_a.v1":
        for mapped, original in zip(request["events"], data["events"]):
            mapped["evidence_ids"] = list(original["evidence_ids"])
        for mapped, original in zip(request["claims"], data["claims"]):
            mapped["event_ids"] = list(original["event_ids"])
            mapped["evidence_ids"] = list(original["evidence_ids"])
        # No DS3 confirmation or DS2 reference is invented by the mapper.
        for name in ("document_facts", "legal_sources", "missing_information", "contradictions", "reference_date"):
            if name in data:
                request[name] = deepcopy(data[name])
    return request
