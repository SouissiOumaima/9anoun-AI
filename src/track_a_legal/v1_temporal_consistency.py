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

    # Read temporal metadata from the legal source (Request v1).
    source_date = source.get("effective_date")

    # Les bornes de validit? proviennent du versionnement DS2.
    effective_from = source.get("effective_from")
    effective_to = source.get("effective_to")

    # Signaler toute date renseign?e qui n'est pas valide.
    for field, value in (
        ("effective_date", source_date),
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
        _valid_date(source_date)
        and _valid_date(effective_from)
        and source_date != effective_from
    ):
        findings.append({
            "code": "EFFECTIVE_DATE_DIVERGENCE",
            "path": "effective_date",
        })

    # D?tecter les indicateurs d'applicabilit? contradictoires
    # avec les bornes d?clar?es, si une date de r?f?rence
    # est explicitement disponible.
    return findings
