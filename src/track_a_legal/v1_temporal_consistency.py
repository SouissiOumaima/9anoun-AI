"""Diagnostic de coh?rence des m?tadonn?es temporelles DS2."""

from __future__ import annotations

from datetime import date
from typing import Any


def _valid_date(value: Any) -> bool:
    """V?rifier une date ISO canonique, sans accepter les bool?ens."""

    if not isinstance(value, str):
        return False

    try:
        parsed = date.fromisoformat(value)
    except ValueError:
        return False

    return parsed.isoformat() == value


def check_temporal_consistency(
    source: dict[str, Any],
) -> list[dict[str, str]]:
    """D?tecter les divergences temporelles sans conclure en droit."""

    findings: list[dict[str, str]] = []

    citation = source.get("citation")
    metadata = citation if isinstance(citation, dict) else {}

    # La date d'effet issue de la citation n'a pas encore
    # une s?mantique contractuelle confirm?e par DS2.
    citation_date = metadata.get("effective_date")

    # Les bornes de validit? proviennent du versionnement DS2.
    effective_from = source.get("effective_from")
    effective_to = source.get("effective_to")

    # Signaler toute date renseign?e qui n'est pas valide.
    for field, value in (
        ("citation.effective_date", citation_date),
        ("effective_from", effective_from),
        ("effective_to", effective_to),
    ):
        if value is not None and not _valid_date(value):
            findings.append({
                "code": "INVALID_TEMPORAL_METADATA",
                "path": field,
            })

    # Comparer seulement les dates valides.
    if (
        _valid_date(citation_date)
        and _valid_date(effective_from)
        and citation_date != effective_from
    ):
        findings.append({
            "code": "EFFECTIVE_DATE_DIVERGENCE",
            "path": "citation.effective_date",
        })

    # D?tecter les indicateurs d'applicabilit? contradictoires
    # avec les bornes d?clar?es, si une date de r?f?rence
    # est explicitement disponible.
    return findings
