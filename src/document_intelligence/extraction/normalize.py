"""Normalisation des valeurs lues sur un document (étape 2 de l'extracteur DS3).

Gemini recopie la valeur telle qu'elle est imprimée (« 424,100 », « 01/09/2019 », « 1 ب », « 208 h »).
Ce module la met au format du contrat ds3.v2 avec des règles fixes, écrites dans le code :
jamais par le modèle.

Règle commune : si la valeur ne peut pas être convertie sans deviner, la fonction renvoie None.
L'extracteur mettra alors le champ à null avec unreadable_reason = "valeur_incoherente".
"""

from __future__ import annotations

import re
from datetime import date
from typing import Final

# Chiffres arabes orientaux (٠-٩) et persans (۰-۹) -> chiffres latins ; virgule et séparateur arabes.
_DIGITS: Final = str.maketrans("٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹٫٬", "01234567890123456789, ")
_CURRENCY: Final = re.compile(r"(TND|DT|D\.T\.?|د\.ت\.?|دينار|dinars?)", re.IGNORECASE)
_SPACES: Final = re.compile(r"[\s  ]+")


def to_latin_digits(text: str) -> str:
    """Remplace les chiffres arabes par des chiffres latins (« ٤٢٤ » -> « 424 »)."""
    return text.translate(_DIGITS)


# ------------------------------------------------------------------ montants


def normalize_amount(raw: str) -> str | None:
    """Montant imprimé -> chaîne à 3 décimales.

    « 424,100 » -> "424.100" ; « 1 275,000 DT » -> "1275.000" ; « 1.275,000 » -> "1275.000" ;
    « 56 » -> "56.000" ; « ٤٢٤٫١٠٠ » -> "424.100".
    Un seul séparateur = séparateur décimal (les fiches de paie tunisiennes impriment les millimes).
    Ambigu (« 1.275.000 », plus de 3 décimales) -> None.
    """
    text = _SPACES.sub("", _CURRENCY.sub("", to_latin_digits(raw))).strip()
    sign = ""
    if text.startswith("-"):
        sign, text = "-", text[1:]
    if not text or not re.fullmatch(r"[0-9.,]+", text) or not text[0].isdigit():
        return None
    seps = [c for c in text if c in ".,"]
    if not seps:
        integer, decimals = text, ""
    elif len(set(seps)) == 2:
        # Deux séparateurs différents : le dernier est décimal, l'autre sépare les milliers.
        decimal_sep = seps[-1]
        thousands_sep = "." if decimal_sep == "," else ","
        if seps.count(decimal_sep) != 1:
            return None
        integer, decimals = text.split(decimal_sep)
        groups = integer.split(thousands_sep)
        if not all(len(g) == 3 for g in groups[1:]) or not 1 <= len(groups[0]) <= 3:
            return None
        integer = "".join(groups)
    elif len(seps) == 1:
        integer, decimals = re.split(r"[.,]", text)
    else:
        return None  # « 1.275.000 » : milliers ou décimales ? On ne devine pas.
    if not integer or (seps and not decimals) or len(decimals) > 3:
        return None
    return f"{sign}{int(integer)}.{decimals.ljust(3, '0')}"


# ------------------------------------------------------------------ dates

_MONTHS: Final[dict[str, int]] = {
    # français
    "janvier": 1, "février": 2, "fevrier": 2, "mars": 3, "avril": 4, "mai": 5, "juin": 6,
    "juillet": 7, "août": 8, "aout": 8, "septembre": 9, "octobre": 10, "novembre": 11,
    "décembre": 12, "decembre": 12,
    # arabe (noms utilisés en Tunisie)
    "جانفي": 1, "فيفري": 2, "مارس": 3, "أفريل": 4, "افريل": 4, "ماي": 5, "جوان": 6,
    "جويلية": 7, "أوت": 8, "اوت": 8, "سبتمبر": 9, "أكتوبر": 10, "اكتوبر": 10, "نوفمبر": 11,
    "ديسمبر": 12,
}


def _iso(year: int, month: int, day: int) -> str | None:
    try:
        return date(year, month, day).isoformat()
    except ValueError:
        return None  # ex. 31/02/2026


def normalize_date(raw: str) -> str | None:
    """Date imprimée -> "AAAA-MM-JJ".

    « 01/09/2019 », « 01-09-2019 », « 01.09.2019 », « 2019-09-01 », « ٠١/٠٩/٢٠١٩ » -> "2019-09-01".
    Ordre jour/mois/année (usage tunisien). Année sur 2 chiffres ou date impossible -> None.
    """
    text = to_latin_digits(raw).strip()
    if m := re.fullmatch(r"([0-9]{4})[-/.]([0-9]{1,2})[-/.]([0-9]{1,2})", text):
        return _iso(int(m[1]), int(m[2]), int(m[3]))
    if m := re.fullmatch(r"([0-9]{1,2})[-/.]([0-9]{1,2})[-/.]([0-9]{4})", text):
        return _iso(int(m[3]), int(m[2]), int(m[1]))
    return None


def month_period(raw: str) -> tuple[str, str] | None:
    """Mois de paie imprimé -> (premier jour, dernier jour).

    « Mars 2026 », « مارس 2026 », « 03/2026 » -> ("2026-03-01", "2026-03-31").
    """
    text = to_latin_digits(raw).strip().lower()
    month: int | None = None
    if m := re.fullmatch(r"([0-9]{1,2})[-/.]([0-9]{4})", text):
        month, year = int(m[1]), int(m[2])
    elif m := re.fullmatch(r"(\S+)\s+([0-9]{4})", text):
        month, year = _MONTHS.get(m[1]), int(m[2])
    if month is None or not 1 <= month <= 12:
        return None
    next_month = date(year + month // 12, month % 12 + 1, 1)
    last_day = date.fromordinal(next_month.toordinal() - 1)
    return date(year, month, 1).isoformat(), last_day.isoformat()


# ------------------------------------------------------------------ catégorie, heures, listes fermées

_AR_LETTERS: Final[dict[str, str]] = {"أ": "A", "ا": "A", "ب": "B", "ج": "C", "د": "D", "ه": "E", "هـ": "E"}


def normalize_category(raw: str) -> str | None:
    """Catégorie imprimée -> "3", "1B"…  (« 1 ب » -> "1B", « 1 أ » -> "1A", « 2b » -> "2B")."""
    text = _SPACES.sub("", to_latin_digits(raw)).replace("ـ", "")
    m = re.fullmatch(r"([0-9]{1,2})(.*)", text)
    if not m:
        return None
    letter = m[2]
    if letter == "":
        return m[1]
    letter = _AR_LETTERS.get(letter, letter.upper())
    return f"{m[1]}{letter}" if letter in {"A", "B", "C", "D", "E"} else None


def normalize_hours(raw: str) -> str | None:
    """Régime horaire imprimé -> heures par semaine ("40" ou "48").

    Mensuel : 208 h -> "48" ; 173,33 h -> "40". Hebdomadaire 40 ou 48 repris tel quel.
    Toute autre valeur -> None (pas de conversion inventée).
    """
    text = to_latin_digits(raw).lower()
    text = re.sub(r"(heures?|ساعة|h(?:00)?|س)", " ", text).strip()
    text = _SPACES.sub("", text).replace(",", ".")
    try:
        value = float(text)
    except ValueError:
        return None
    if abs(value - 208) < 0.01:
        return "48"
    if abs(value - 173.33) < 0.01 or abs(value - 173.3) < 0.01:
        return "40"
    if value in (40, 48):
        return str(int(value))
    return None


PAY_MODES: Final[dict[str, str]] = {
    "mensuel": "mensuel", "mensuelle": "mensuel", "شهري": "mensuel",
    "horaire": "horaire", "بالساعة": "horaire", "ساعي": "horaire",
}
EMPLOYMENT_STATUSES: Final[dict[str, str]] = {
    "permanent": "permanent", "titulaire": "permanent", "قار": "permanent",
    "temporaire": "temporaire", "وقتي": "temporaire",
    "occasionnel": "occasionnel", "عرضي": "occasionnel",
}


def normalize_enum(raw: str, vocabulary: dict[str, str]) -> str | None:
    """Mot imprimé -> valeur de la liste fermée, seulement s'il figure dans le vocabulaire.

    Pas de synonyme deviné : « CDD » n'est pas traduit en « temporaire » (c'est une interprétation).
    """
    return vocabulary.get(raw.strip().lower())
