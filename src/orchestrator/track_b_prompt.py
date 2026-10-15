"""Safe extraction of explicit DS5 parameters from a user prompt.

This module is deliberately rule-based: it standardizes only wording that is
present in the message and never fills a payroll value from a guess or a Card.
The resulting parameters are still validated by the Track B JSON schema.
"""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any, Mapping


@dataclass(frozen=True, slots=True)
class TrackBPromptExtraction:
    """One operation and its explicit parameters, ready for contract validation."""

    operation: str | None
    params: Mapping[str, Any]
    missing: tuple[str, ...]


_DATE_RE = re.compile(r"\b\d{4}-\d{2}-\d{2}\b")
_CATEGORY_RE = re.compile(r"\bcat(?:é|e)gorie\s*(?:n[°o.]?\s*)?([0-9]+[a-zA-Z]?)\b", re.IGNORECASE)
_SENIORITY_RE = re.compile(r"\b(\d+(?:[.,]\d+)?)\s*ans?\s*(?:d(?:['’]\s*|\s+))?anciennet(?:é|e)\b", re.IGNORECASE)
_SUBCATEGORY_RE = re.compile(r"\bsous[ -]cat(?:é|e)gorie\s*(?:n[°o.]?\s*)?([0-9a-zA-Z_-]+)\b", re.IGNORECASE)


def extract_track_b_prompt(message: str) -> TrackBPromptExtraction:
    """Extract explicit v0 values for SMIG, salary base, or a prime request."""

    lowered = message.casefold()
    operation = _operation(lowered)
    if operation is None:
        return TrackBPromptExtraction(None, {}, ("operation",))

    date = _first_date(message)
    if operation == "smig":
        params: dict[str, Any] = {}
        if "mensuel" in lowered or "شهري" in lowered:
            params["mode"] = "mensuel"
        elif "horaire" in lowered or "بالساعة" in lowered:
            params["mode"] = "horaire"
        regime = re.search(r"\b(40|48)\s*h(?:eures?)?\b", lowered)
        if regime:
            params["regime_heures"] = int(regime.group(1))
        if date:
            params["date"] = date
        return TrackBPromptExtraction("smig", params, _missing(params, "mode", "regime_heures", "date"))

    secteur = _secteur(lowered)
    if operation == "salaire_base":
        population = _population(lowered, secteur)
        categorie = _match_group(_CATEGORY_RE, message)
        params = _without_none({
            "secteur": secteur,
            "population": population,
            "categorie": categorie,
            "sous_categorie": _match_group(_SUBCATEGORY_RE, message),
            "anciennete_annees": _seniority(message),
            "date": date,
        })
        required = ["secteur", "population", "categorie", "date"]
        if not (secteur == "BATIMENT_TRAVAUX_PUBLICS" and population == "ouvriers_occasionnels"):
            required.append("anciennete_annees")
        if secteur == "BATIMENT_TRAVAUX_PUBLICS" and population == "ouvriers_occasionnels" and categorie in {"6", "7"}:
            required.append("sous_categorie")
        return TrackBPromptExtraction(
            "salaire_base", params,
            _missing(params, *required),
        )

    params = _without_none({
        "secteur": secteur,
        "code": _prime_code(lowered),
        "date": date,
        "groupe": _group(lowered),
        "transport_assure": _transport_assure(lowered),
        "condition_remplie": _condition_remplie(lowered),
    })
    return TrackBPromptExtraction("prime", params, _missing(params, "secteur", "code", "date"))


def _operation(message: str) -> str | None:
    if "smig" in message:
        return "smig"
    if "salaire de base" in message or "salaire base" in message:
        return "salaire_base"
    if "prime" in message or "منحة" in message:
        return "prime"
    return None


def _secteur(message: str) -> str | None:
    if "metallurgie_batiment" in message or "métallurgie_bâtiment" in message:
        return "METALLURGIE_BATIMENT"
    if "métallurgie" in message or "metallurgie" in message or "bâtiment métallique" in message or "batiment metallique" in message:
        return "METALLURGIE_BATIMENT"
    if re.search(r"\bbtp\b", message) or "bâtiment travaux publics" in message or "batiment travaux publics" in message:
        return "BATIMENT_TRAVAUX_PUBLICS"
    return None


def _population(message: str, _secteur: str | None) -> str | None:
    """Accept only a population code explicitly supplied by the user.

    Job titles such as ``technicien`` are not population codes: their meaning
    changes with the sector and must be proposed/confirmed in the UI.
    """

    match = re.search(r"\bpopulation\s*(?:=|:)?\s*([a-z][a-z0-9_-]*)", message, re.IGNORECASE)
    return match.group(1).replace("-", "_") if match else None


def _prime_code(message: str) -> str | None:
    codes = {
        "transport": "prime_transport",
        "panier": "prime_panier_qefa",
        "logement": "prime_logement",
        "présence": "prime_presence",
        "presence": "prime_presence",
        "déplacement": "prime_deplacement_chantier",
        "deplacement": "prime_deplacement_chantier",
        "hauteur": "prime_travail_en_hauteur",
    }
    return next((code for term, code in codes.items() if term in message), None)


def _group(message: str) -> str | None:
    if "cadres" in message or "cadre" in message:
        return "cadres"
    if "exécution et maîtrise" in message or "execution et maitrise" in message:
        return "execution_et_maitrise"
    return None


def _transport_assure(message: str) -> bool | None:
    if "transport non assuré" in message or "transport non assure" in message:
        return False
    if "transport assuré" in message or "transport assure" in message:
        return True
    return None


def _condition_remplie(message: str) -> bool | None:
    if "condition non remplie" in message:
        return False
    if "condition remplie" in message:
        return True
    return None


def _first_date(message: str) -> str | None:
    match = _DATE_RE.search(message)
    return match.group(0) if match else None


def _match_group(pattern: re.Pattern[str], message: str) -> str | None:
    match = pattern.search(message)
    return match.group(1) if match else None


def _seniority(message: str) -> int | float | None:
    value = _match_group(_SENIORITY_RE, message)
    if value is None:
        return None
    number = value.replace(",", ".")
    return float(number) if "." in number else int(number)


def _without_none(values: Mapping[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in values.items() if value is not None}


def _missing(values: Mapping[str, Any], *required: str) -> tuple[str, ...]:
    return tuple(key for key in required if key not in values)
