"""Resolve explicit DS1 sector wording through the shared DS2 ↔ DS5 table.

The shared table is the authority for a DS2 sector's availability in DS5.
This module deliberately does not guess from generic construction or
metallurgy wording: those terms are documented as ambiguous in D30.
"""

from __future__ import annotations

from functools import lru_cache
import json
from pathlib import Path
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

    lowered = message.casefold()
    if _has_ambiguous_term(lowered) and not _has_unambiguous_sector_term(lowered):
        return None

    for sector in load_sector_table()["sectors"]:
        terms = (
            sector["ds2_code"],
            sector["label_fr"],
            sector["label_ar"],
            sector.get("ds5_code") or "",
            *sector.get("aliases", ()),
        )
        if any(term and term.casefold() in lowered for term in terms):
            if sector["ds5_status"] == "actif":
                return sector["ds5_code"]
            return None
    return None


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
