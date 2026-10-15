"""DS1 validation rules for a structured Case Card proposal.

The JSON Schema checks field shapes.  These checks validate cross-references
that JSON Schema cannot express: each proof must cite a known document and
each fact reference must point to a known event or claim.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any


class CaseCardValidationError(ValueError):
    """Raised when a Case Card has dangling or duplicate identifiers."""


def validate_case_card_references(card: Mapping[str, Any]) -> None:
    """Validate semantic references in a schema-valid DS1 Case Card.

    This function deliberately does not infer or add facts.  It only confirms
    that every declared relation can be resolved inside the active card.
    """

    if card.get("card_type") != "case" or not isinstance(card.get("data"), Mapping):
        raise CaseCardValidationError("a Case Card with data is required")
    data = card["data"]
    documents = _ids(data.get("documents"), "document_id", "document")
    parties = _ids(data.get("parties"), "party_id", "party")
    events = _ids(data.get("events"), "event_id", "event")
    claims = _ids(data.get("claims"), "claim_id", "claim")
    evidence = _ids(data.get("evidence"), "evidence_id", "evidence")

    for event in _records(data.get("events"), "event"):
        _known_ids(event.get("evidence_ids"), evidence, "event evidence_ids")

    for claim in _records(data.get("claims"), "claim"):
        party_id = claim.get("party_id")
        if party_id not in parties:
            raise CaseCardValidationError(f"claim references unknown party_id: {party_id!r}")
        _known_ids(claim.get("event_ids"), events, "claim event_ids")
        _known_ids(claim.get("evidence_ids"), evidence, "claim evidence_ids")

    for item in _records(data.get("evidence"), "evidence"):
        evidence_id = item.get("evidence_id")
        document_id = item.get("document_id")
        if document_id not in documents:
            raise CaseCardValidationError(f"evidence references unknown document_id: {document_id!r}")
        for reference in _records(item.get("supports"), "evidence supports"):
            target = events if reference.get("fact_type") == "event" else claims
            fact_id = reference.get("fact_id")
            if fact_id not in target:
                raise CaseCardValidationError(
                    f"evidence references unknown {reference.get('fact_type')!r}: {fact_id!r}"
                )
            fact = next(record for record in _records(data[f"{reference['fact_type']}s"], reference["fact_type"])
                        if record[f"{reference['fact_type']}_id"] == fact_id)
            if evidence_id not in fact["evidence_ids"]:
                raise CaseCardValidationError(
                    f"evidence support is not reciprocally declared by {reference['fact_type']}: {fact_id!r}"
                )


def _records(value: Any, label: str) -> Iterable[Mapping[str, Any]]:
    if not isinstance(value, list) or not all(isinstance(item, Mapping) for item in value):
        raise CaseCardValidationError(f"{label} must be an array of objects")
    return value


def _ids(value: Any, key: str, label: str) -> set[str]:
    records = _records(value, label)
    identifiers = [item.get(key) for item in records]
    if not all(isinstance(identifier, str) and identifier for identifier in identifiers):
        raise CaseCardValidationError(f"every {label} requires a non-empty {key}")
    if len(identifiers) != len(set(identifiers)):
        raise CaseCardValidationError(f"duplicate {label} identifier")
    return set(identifiers)


def _known_ids(value: Any, known: set[str], label: str) -> None:
    if not isinstance(value, list):
        raise CaseCardValidationError(f"{label} must be an array")
    unknown = [identifier for identifier in value if identifier not in known]
    if unknown:
        raise CaseCardValidationError(f"{label} references unknown ids: {unknown!r}")
