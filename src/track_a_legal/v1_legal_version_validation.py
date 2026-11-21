"""Contr?les pr?liminaires du versionnement juridique DS2."""

from __future__ import annotations

from datetime import date
from typing import Any


def _parse_date(value: Any) -> tuple[date | None, bool]:
    """Lire une date ISO stricte ; None repr?sente l'inconnu."""

    if value is None:
        return None, True

    if not isinstance(value, str):
        return None, False

    # Refuser les formats non canoniques.
    if (
        len(value) != 10
        or value[4] != "-"
        or value[7] != "-"
        or not all(
            part.isascii() and part.isdigit()
            for part in (
                value[:4],
                value[5:7],
                value[8:],
            )
        )
    ):
        return None, False

    try:
        parsed = date.fromisoformat(value)
    except ValueError:
        return None, False

    return parsed, parsed.isoformat() == value


def validate_legal_versions(
    sources: list[dict[str, Any]],
    reference_date: str | None,
) -> list[dict[str, str]]:
    """Signaler les incoh?rences temporelles sans conclure en droit.

    Pr?condition : sources structur?es selon le sch?ma v1.
    """

    errors: list[dict[str, str]] = []

    reference, valid_reference = _parse_date(reference_date)

    if reference is None or not valid_reference:
        errors.append({
            "code": (
                "REFERENCE_DATE_MISSING"
                if reference_date is None
                else "INVALID_REFERENCE_DATE"
            ),
            "path": "reference_date",
        })

    # Suivre les versions explicitement d?clar?es applicables.
    applicable_groups: dict[str, str] = {}

    for index, source in enumerate(sources):
        path = f"legal_sources[{index}]"
        source_id = source.get("source_id", "")

        start, start_valid = _parse_date(
            source.get("effective_from")
        )

        end, end_valid = _parse_date(
            source.get("effective_to")
        )

        # V?rifier ind?pendamment chaque borne renseign?e.
        if not start_valid:
            errors.append({
                "code": "INVALID_EFFECTIVE_FROM",
                "path": f"{path}.effective_from",
            })

        if not end_valid:
            errors.append({
                "code": "INVALID_EFFECTIVE_TO",
                "path": f"{path}.effective_to",
            })

        # Refuser une p?riode chronologiquement invers?e.
        if start is not None and end is not None:
            if end < start:
                errors.append({
                    "code": "INVERTED_EFFECTIVE_PERIOD",
                    "path": path,
                })

        # Comparer les bornes ? la date du dossier.
        if reference is not None:
            if start is not None and start > reference:
                errors.append({
                    "code": "NOT_YET_EFFECTIVE",
                    "path": path,
                })

            if end is not None and end < reference:
                errors.append({
                    "code": "NO_LONGER_EFFECTIVE",
                    "path": path,
                })

        # Un indicateur inconnu n'autorise aucune conclusion.
        applicable = source.get(
            "applicable_at_reference_date"
        )

        if applicable is None:
            errors.append({
                "code": "APPLICABILITY_UNKNOWN",
                "path": (
                    f"{path}.applicable_at_reference_date"
                ),
            })

        # Contr?ler les versions du m?me groupe juridique.
        group = source.get("version_group")

        if applicable is True and isinstance(group, str) and group:
            if group in applicable_groups:
                errors.append({
                    "code": "MULTIPLE_APPLICABLE_VERSIONS",
                    "path": path,
                })
            else:
                applicable_groups[group] = source_id

    return errors
