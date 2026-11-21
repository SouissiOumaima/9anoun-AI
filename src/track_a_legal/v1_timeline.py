
"""Construction de la chronologie juridique DS4 v1."""

from __future__ import annotations

from datetime import date
from typing import Any


def _parse_event_date(value: Any, event_id: str) -> date:
    """Valider une date ISO stricte."""

    if not isinstance(value, str):
        raise ValueError(
            f"Invalid date type for event {event_id}"
        )

    try:
        parsed = date.fromisoformat(value)
    except ValueError as exc:
        raise ValueError(
            f"Invalid date for event {event_id}: {value}"
        ) from exc

    # Exiger une repr?sentation ISO canonique.
    if parsed.isoformat() != value:
        raise ValueError(
            f"Non-canonical date for event {event_id}: {value}"
        )

    return parsed


def build_v1_timeline(events: list[dict]) -> list[dict]:
    """Construire une timeline compatible avec les dates inconnues.

    Les ?v?nements dat?s sont class?s chronologiquement.
    Les ?v?nements sans date sont plac?s ? la fin, en conservant
    leur ordre initial.

    Les ?v?nements originaux ne sont jamais modifi?s.
    """

    # Refuser une collection incorrecte.
    if not isinstance(events, list):
        raise ValueError("events must be a list")

    normalized_events = []

    for index, event in enumerate(events):

        # V?rifier la structure de chaque ?v?nement.
        if not isinstance(event, dict):
            raise ValueError(
                f"Invalid event at index {index}"
            )

        event_id = event.get("event_id")

        if not isinstance(event_id, str) or not event_id.strip():
            raise ValueError(
                f"Missing event_id at index {index}"
            )

        description = event.get("description")

        if not isinstance(description, str) or not description.strip():
            raise ValueError(
                f"Missing description for event {event_id}"
            )

        source_ids = event.get("source_ids")

        if not isinstance(source_ids, list):
            raise ValueError(
                f"Invalid source_ids for event {event_id}"
            )

        # Lire la date sans modifier l'?v?nement original.
        event_date = event.get("date")

        normalized = dict(event)

        if event_date is None:

            # Une date inconnue exige une justification explicite.
            if event.get("date_precision") != "unknown":
                raise ValueError(
                    f"Unknown date precision for event {event_id}"
                )

            reason = event.get("date_reason")

            if not isinstance(reason, str) or not reason.strip():
                raise ValueError(
                    f"Missing date reason for event {event_id}"
                )

            normalized["date_precision"] = "unknown"

            # Les dates inconnues sont tri?es apr?s les dates connues.
            sort_key = (1, date.max)

        else:

            # Valider la date et v?rifier sa pr?cision.
            parsed_date = _parse_event_date(event_date, event_id)

            precision = event.get("date_precision")

            if precision is not None and precision != "exact":
                raise ValueError(
                    f"Invalid date precision for event {event_id}"
                )

            normalized["date_precision"] = "exact"
            normalized.setdefault("date_reason", None)

            sort_key = (0, parsed_date)

        # Conserver l'ordre initial en cas d'?galit?.
        normalized_events.append(
            (sort_key, index, normalized)
        )

    # sorted() est stable : les dates inconnues gardent
    # leur ordre initial, tout comme les dates identiques.
    ordered = sorted(
        normalized_events,
        key=lambda item: item[0],
    )

    return [
        item[2]
        for item in ordered
    ]
