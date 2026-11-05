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
from typing import Any, Mapping


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


def sector_clarification_labels(message: str) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """Return safe FR/AR choices for a sector clarification prompt.

    The labels are derived only from D30.  When a generic construction term
    has no unique table match, D30's two documented construction choices are
    offered; otherwise the choices are exactly the matched sectors.
    """

    matches = _clarification_sectors(message.casefold())
    return (
        tuple(_choice_label_fr(sector) for sector in matches),
        tuple(str(sector["label_ar"]) for sector in matches),
    )


def sector_clarification_messages(message: str) -> tuple[str, str]:
    """Return user-facing FR/AR wording that reflects the exact ambiguity.

    D30 has two different ambiguity rules.  A generic building term can name
    BTP or construction métallique, whereas *métallurgie* alone can only be
    clarified to construction métallique (or remains outside the DS5 corpus).
    The UI must not claim that several sectors were mentioned when the user
    supplied one ambiguous word.
    """

    lowered = message.casefold()
    matches = _matched_sectors(lowered)
    choices_fr, choices_ar = sector_clarification_labels(message)
    if len(matches) > 1:
        return (
            f"Plusieurs secteurs sont indiqués : {' ou '.join(choices_fr)} ?",
            f"تم ذكر أكثر من قطاع: {' أم '.join(choices_ar)}؟",
        )
    if _has_metallurgy_term(lowered):
        choice_fr, choice_ar = choices_fr[0], choices_ar[0]
        return (
            "Le terme « métallurgie » ne permet pas d'identifier automatiquement "
            f"un secteur DS5. Précisez s'il s'agit de {choice_fr}.",
            "مصطلح « المعادن » لا يحدد تلقائيا قطاعا لدى DS5. "
            f"يرجى توضيح ما إذا كان المقصود هو {choice_ar}.",
        )
    return (
        f"Ce terme peut correspondre à plusieurs secteurs : {' ou '.join(choices_fr)}. "
        "Précisez le secteur concerné.",
        f"قد يشير هذا المصطلح إلى عدة قطاعات: {' أم '.join(choices_ar)}. "
        "يرجى تحديد القطاع المعني.",
    )


def _clarification_sectors(message: str) -> list[dict[str, Any]]:
    """Get only the D30 choices applicable to the wording in ``message``."""

    matches = _matched_sectors(message)
    if len(matches) >= 2:
        return matches
    table = load_sector_table()["sectors"]
    if _has_metallurgy_term(message):
        return [sector for sector in table if sector["ds2_code"] == "construction_metallique"]
    return [
        sector for sector in table
        if sector["ds2_code"] in {"btp", "construction_metallique"}
    ]


def _matched_sectors(message: str) -> list[dict[str, Any]]:
    matches: list[dict[str, Any]] = []
    for sector in load_sector_table()["sectors"]:
        terms = (
            sector["ds2_code"], sector["label_fr"], sector["label_ar"],
            sector.get("ds5_code") or "", *sector.get("aliases", ()),
        )
        # D21 keeps the one-word alias "sécurité" for legal-retrieval
        # vocabulary, but it is too broad for DS1 payroll routing: it also
        # occurs in ordinary phrases such as "sécurité sociale".  Require a
        # specific gardiennage expression instead (for example "gardiennage",
        # "transport de fonds", or the existing "agent de sécurité" alias).
        if sector["ds2_code"] == "gardiennage_securite_transport_fonds":
            terms = tuple(term for term in terms if term.casefold() != "sécurité")
        if any(_matches_term(message, term) for term in terms if term):
            matches.append(sector)
    return matches


def _choice_label_fr(sector: Mapping[str, Any]) -> str:
    """Keep clarification choices short while retaining D30 terminology."""

    return "BTP" if sector["ds2_code"] == "btp" else str(sector["label_fr"])


def _matches_term(message: str, term: str) -> bool:
    """Match a whole Latin term, while retaining substring matching for Arabic."""

    normalized = term.casefold()
    if any("\u0600" <= char <= "\u06ff" for char in normalized):
        return normalized in message
    return re.search(rf"(?<!\w){re.escape(normalized)}(?!\w)", message) is not None


def _has_ambiguous_term(message: str) -> bool:
    return any(term in message for term in ("bâtiment", "batiment", "البناء", "construction", "métallurgie", "metallurgie", "المعادن"))


def _has_metallurgy_term(message: str) -> bool:
    return any(term in message for term in ("métallurgie", "metallurgie", "المعادن"))


def _has_unambiguous_sector_term(message: str) -> bool:
    table = load_sector_table()
    for sector in table["sectors"]:
        if sector["ds5_status"] != "actif":
            continue
        terms = (sector["ds2_code"], sector["label_fr"], sector["label_ar"], sector.get("ds5_code") or "", *sector.get("aliases", ()))
        if any(term and term.casefold() in message for term in terms):
            return True
    return False
