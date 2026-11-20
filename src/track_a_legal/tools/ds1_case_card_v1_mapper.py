"""Mapping sécurisé d'une Case Card DS1 vers Track A v1."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Any, Mapping
from urllib.parse import urlencode, urlsplit, urlunsplit

from jsonschema import Draft202012Validator, FormatChecker


class CaseCardV1MappingError(ValueError):
    """Erreur de validation ou de conversion DS1 vers DS4 v1."""


def _records(value: Any, label: str) -> list[Mapping[str, Any]]:
    """Vérifier qu'une collection contient uniquement des objets."""
    if not isinstance(value, list):
        raise CaseCardV1MappingError(f"{label} must be a list")

    if not all(isinstance(item, Mapping) for item in value):
        raise CaseCardV1MappingError(f"{label} must contain objects")

    return value


def _unique_ids(
    records: list[Mapping[str, Any]],
    field: str,
    label: str,
) -> set[str]:
    """Contrôler la présence et l'unicité des identifiants."""
    identifiers = [item.get(field) for item in records]

    if not all(
        isinstance(value, str) and value.strip()
        for value in identifiers
    ):
        raise CaseCardV1MappingError(f"Invalid {label} identifier")

    if len(identifiers) != len(set(identifiers)):
        raise CaseCardV1MappingError(f"Duplicate {label} identifier")

    return set(identifiers)


def _check_references(
    references: Any,
    known_ids: set[str],
    label: str,
) -> None:
    """Refuser les références vers des objets inexistants."""
    if not isinstance(references, list):
        raise CaseCardV1MappingError(f"{label} must be a list")

    unknown = [
        value for value in references
        if not isinstance(value, str) or value not in known_ids
    ]

    if unknown:
        raise CaseCardV1MappingError(
            f"Unknown references in {label}: {unknown!r}"
        )


def _validate_case_card(card: Mapping[str, Any]) -> None:
    """Valider les références sémantiques de la Case Card DS1."""

    if card.get("card_type") != "case":
        raise CaseCardV1MappingError("A Case Card is required")

    data = card.get("data")

    if not isinstance(data, Mapping):
        raise CaseCardV1MappingError("Invalid Case Card data")

    documents = _records(data.get("documents"), "documents")
    parties = _records(data.get("parties"), "parties")
    events = _records(data.get("events"), "events")
    claims = _records(data.get("claims"), "claims")
    evidence = _records(data.get("evidence"), "evidence")

    document_ids = _unique_ids(documents, "document_id", "document")
    party_ids = _unique_ids(parties, "party_id", "party")
    event_ids = _unique_ids(events, "event_id", "event")
    claim_ids = _unique_ids(claims, "claim_id", "claim")
    evidence_ids = _unique_ids(evidence, "evidence_id", "evidence")

    # Vérifier les références des événements.
    for event in events:
        _check_references(
            event.get("evidence_ids"),
            evidence_ids,
            "event evidence_ids",
        )

    # Vérifier les références des affirmations.
    for claim in claims:
        if claim.get("party_id") not in party_ids:
            raise CaseCardV1MappingError("Unknown claim party_id")

        _check_references(
            claim.get("event_ids"),
            event_ids,
            "claim event_ids",
        )

        _check_references(
            claim.get("evidence_ids"),
            evidence_ids,
            "claim evidence_ids",
        )

    # Vérifier les preuves et leurs relations réciproques.
    for item in evidence:
        evidence_id = item.get("evidence_id")
        document_id = item.get("document_id")

        if document_id not in document_ids:
            raise CaseCardV1MappingError("Unknown evidence document_id")

        supports = _records(
            item.get("supports"),
            "evidence supports",
        )

        for reference in supports:
            fact_type = reference.get("fact_type")
            fact_id = reference.get("fact_id")

            if fact_type == "event":
                target_records = events
                target_ids = event_ids
                target_field = "evidence_ids"

            elif fact_type == "claim":
                target_records = claims
                target_ids = claim_ids
                target_field = "evidence_ids"

            else:
                raise CaseCardV1MappingError(
                    f"Unsupported evidence fact_type: {fact_type!r}"
                )

            if fact_id not in target_ids:
                raise CaseCardV1MappingError(
                    f"Unknown evidence support reference: {fact_id!r}"
                )

            target = next(
                record for record in target_records
                if record[
                    "event_id" if fact_type == "event" else "claim_id"
                ] == fact_id
            )

            if evidence_id not in target[target_field]:
                raise CaseCardV1MappingError(
                    f"Non-reciprocal evidence support: {fact_id!r}"
                )


def _build_evidence_source(
    storage_ref: str,
    citation: Mapping[str, Any],
) -> str:
    """Préserver la référence documentaire et les données de citation."""

    if not isinstance(storage_ref, str) or not storage_ref.strip():
        raise CaseCardV1MappingError("Invalid document storage_ref")

    citation_id = citation.get("citation_id")
    page = citation.get("page")
    excerpt = citation.get("excerpt")

    if (
        not isinstance(citation_id, str)
        or not citation_id.strip()
        or not isinstance(page, int)
        or isinstance(page, bool)
        or page < 1
        or not isinstance(excerpt, str)
        or not excerpt.strip()
    ):
        raise CaseCardV1MappingError("Invalid evidence citation")

    # Conserver les informations de citation dans le fragment URI.
    parsed = urlsplit(storage_ref)

    metadata = urlencode({
        "citation": citation_id,
        "page": page,
        "excerpt": excerpt,
    })

    fragment = (
        f"{parsed.fragment}&{metadata}"
        if parsed.fragment
        else metadata
    )

    return urlunsplit((
        parsed.scheme,
        parsed.netloc,
        parsed.path,
        parsed.query,
        fragment,
    ))


def map_case_card_to_track_a_v1(
    case_card: Mapping[str, Any],
    *,
    request_id: str,
    language: str,
) -> dict[str, Any]:
    """Transformer une Case Card DS1 en requête Track A v1."""

    if not isinstance(case_card, Mapping):
        raise CaseCardV1MappingError("Invalid Case Card")

    if not isinstance(request_id, str) or not request_id.strip():
        raise CaseCardV1MappingError("Invalid request_id")

    if language not in {"fr", "ar"}:
        raise CaseCardV1MappingError("Language must be fr or ar")

    case_id = case_card.get("card_id")

    if not isinstance(case_id, str) or not case_id.strip():
        raise CaseCardV1MappingError("Invalid case_id")

    _validate_case_card(case_card)

    data = case_card["data"]

    # Indexer les documents pour retrouver leurs références de stockage.
    documents = {
        item["document_id"]: item
        for item in data["documents"]
    }

    # Mapper les parties sans inventer de nouveaux attributs.
    parties = [
        {
            "party_id": item["party_id"],
            "name": item["name"],
            "role": item["role"],
        }
        for item in data["parties"]
    ]

    # Mapper les événements en conservant les références explicites.
    events = []

    for item in data["events"]:
        original_date = item.get("date")
        precision = item.get("date_precision")

        if precision not in {"exact", "month", "year", "unknown"}:
            raise CaseCardV1MappingError(
                f"Unsupported date precision: {precision!r}"
            )

        if precision == "exact":
            if not isinstance(original_date, str):
                raise CaseCardV1MappingError(
                    f"Missing exact date: {item['event_id']}"
                )

            try:
                parsed_date = date.fromisoformat(original_date)
            except ValueError as error:
                raise CaseCardV1MappingError(
                    f"Invalid event date: {item['event_id']}"
                ) from error

            if parsed_date.isoformat() != original_date:
                raise CaseCardV1MappingError(
                    f"Non-canonical event date: {item['event_id']}"
                )

            mapped_date = original_date
            mapped_precision = "exact"
            date_reason = None

        else:
            # Ne jamais transformer une date partielle en date exacte.
            mapped_date = None
            mapped_precision = "unknown"

            original_reason = item.get("date_reason")

            date_reason = (
                original_reason
                if isinstance(original_reason, str) and original_reason.strip()
                else (
                    f"Original DS1 date precision: {precision}; "
                    f"original date value: {original_date!r}"
                )
            )

        evidence_ids = list(item["evidence_ids"])

        events.append({
            "event_id": item["event_id"],
            "date": mapped_date,
            "description": item["description"],
            "source_ids": evidence_ids.copy(),
            "date_precision": mapped_precision,
            "date_reason": date_reason,
            "evidence_ids": evidence_ids,
        })

    # Mapper les affirmations en préservant leurs références.
    claims = []

    for item in data["claims"]:
        mapped_claim = {
            "claim_id": item["claim_id"],
            "party_id": item["party_id"],
            "text": item["text"],
        }

        # Préserver les champs facultatifs lorsqu'ils sont présents.
        if "event_ids" in item:
            mapped_claim["event_ids"] = list(item["event_ids"])

        if "evidence_ids" in item:
            mapped_claim["evidence_ids"] = list(item["evidence_ids"])

        claims.append(mapped_claim)

    # Mapper les preuves et préserver leur provenance documentaire.
    evidence = []

    for item in data["evidence"]:
        document = documents[item["document_id"]]

        evidence.append({
            "evidence_id": item["evidence_id"],
            "type": item["type"],
            "description": item["description"],
            "source": _build_evidence_source(
                document["storage_ref"],
                item["citation"],
            ),
        })

    # Construire exactement le contrat d'entrée DS4 v1.
    request = {
        "contract_version": "track_a.v1",
        "request_id": request_id,
        "case_id": case_id,
        "lang": language,
        "parties": parties,
        "events": events,
        "claims": claims,
        "evidence": evidence,
    }

    # Valider la requête finale avec le schéma officiel DS4.
    root = Path(__file__).resolve().parents[3]

    schema_path = (
        root
        / "data"
        / "mock_cards"
        / "schemas"
        / "track_a_request.v1.schema.json"
    )

    if not schema_path.is_file():
        raise CaseCardV1MappingError(
            "Official Track A v1 request schema not found"
        )

    schema = json.loads(schema_path.read_text(encoding="utf-8-sig"))

    validator = Draft202012Validator(
        schema,
        format_checker=FormatChecker(),
    )

    errors = sorted(
        validator.iter_errors(request),
        key=lambda error: list(error.path),
    )

    if errors:
        first = errors[0]
        location = "/".join(str(part) for part in first.path)

        raise CaseCardV1MappingError(
            f"Generated Track A v1 request is invalid at "
            f"{location}: {first.message}"
        )

    return request
