"""Resolve explicit DS1 sector wording through the shared DS2 ↔ DS5 table.

The shared table is the authority for a DS2 sector's availability in DS5.
This module deliberately does not guess from generic construction or
metallurgy wording: those terms are documented as ambiguous in D30.
"""

from __future__ import annotations

from functools import lru_cache
import json
from pathlib import Path
import re
from typing import Any


_TABLE_PATH = Path(__file__).resolve().parents[1] / "shared" / "sectors" / "sectors.v0.json"


@lru_cache(maxsize=1)
def load_sector_table() -> dict[str, Any]:
    """Load the versioned common sector table shipped with the repository."""

    with _TABLE_PATH.open(encoding="utf-8") as file:
        return json.load(file)


def resolve_active_ds5_sector(message: str) -> str | None:
    """Return a DS5 code only for an explicit, active sector in D30.

    A direct DS5 code is accepted as explicit input. Otherwise, matching uses
    only the labels, aliases and DS2 codes recorded in the common table. A
    sector with no active DS5 grid deliberately returns ``None`` so DS1 will
    request clarification instead of invoking Track B.
    """

    matches = _matched_sectors(message.casefold())
    if len(matches) != 1:
        return None
    sector = matches[0]
    return sector["ds5_code"] if sector["ds5_status"] == "actif" else None


def is_active_ds5_sector(ds5_code: str | None) -> bool:
    """Whether a DS5 code is explicitly active in the common D30 table."""

    return isinstance(ds5_code, str) and any(
        sector["ds5_status"] == "actif" and sector.get("ds5_code") == ds5_code
        for sector in load_sector_table()["sectors"]
    )


def needs_sector_clarification(message: str) -> bool:
    """True for D30 ambiguities or more than one sector in the same message."""

    lowered = message.casefold()
    return len(_matched_sectors(lowered)) > 1 or (
        _has_ambiguous_term(lowered) and not _has_unambiguous_sector_term(lowered)
    )


def _matched_sectors(message: str) -> list[dict[str, Any]]:
    matches: list[dict[str, Any]] = []
    for sector in load_sector_table()["sectors"]:
        terms = (
            sector["ds2_code"], sector["label_fr"], sector["label_ar"],
            sector.get("ds5_code") or "", *sector.get("aliases", ()),
        )
        if any(_matches_term(message, term) for term in terms if term):
            matches.append(sector)
    return matches


def _matches_term(message: str, term: str) -> bool:
    """Match a whole Latin term, while retaining substring matching for Arabic."""

    normalized = term.casefold()
    if any("\u0600" <= char <= "\u06ff" for char in normalized):
        return normalized in message
    return re.search(rf"(?<!\w){re.escape(normalized)}(?!\w)", message) is not None


def _has_ambiguous_term(message: str) -> bool:
    return any(term in message for term in ("bâtiment", "batiment", "البناء", "construction", "métallurgie", "metallurgie", "المعادن"))


def _has_unambiguous_sector_term(message: str) -> bool:
    table = load_sector_table()
    for sector in table["sectors"]:
        if sector["ds5_status"] != "actif":
            continue
        terms = (sector["ds2_code"], sector["label_fr"], sector["label_ar"], sector.get("ds5_code") or "", *sector.get("aliases", ()))
        if any(term and term.casefold() in message for term in terms):
            return True
    return False
