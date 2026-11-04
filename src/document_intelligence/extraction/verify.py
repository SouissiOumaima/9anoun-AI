"""Vérification des réponses de Gemini (étape 3 de l'extracteur DS3) : la barrière contre l'invention.

Pour chaque champ, Gemini renvoie seulement :
- raw     : la valeur recopiée telle qu'elle est imprimée (ou null s'il ne la trouve pas) ;
- line_id : l'identifiant de la ligne où il l'a lue (ex. "p1_l7").

Ce module contrôle, avec du code, que la valeur existe vraiment dans le document :
1. la ligne citée existe ;
2. la ligne est lisible (pas de texte cassé) ;
3. la valeur recopiée se trouve bien dans le texte de cette ligne.

Si un contrôle échoue, la valeur est rejetée (null) : « citation ou silence ».
"""

from __future__ import annotations

from dataclasses import dataclass, field

from pydantic import BaseModel, ConfigDict

from src.document_intelligence.contract.v2.models import UnreadableReason
from src.document_intelligence.extraction.normalize import to_latin_digits
from src.document_intelligence.intermediate import (
    IntermediateDocument,
    PendingZone,
    TextLine,
    is_unreadable_line,
)


class RawField(BaseModel):
    """Ce que Gemini répond pour un champ."""

    model_config = ConfigDict(extra="forbid")

    raw: str | None
    line_id: str | None


@dataclass(frozen=True)
class VerifiedField:
    """Résultat de la vérification d'un champ.

    - accepté : raw et line sont remplis, reason = None ;
    - rejeté ou absent : raw = None, line = None, reason dit pourquoi.
    """

    raw: str | None
    line: TextLine | None
    reason: UnreadableReason | None
    warnings: list[str] = field(default_factory=list)


def _is_space(ch: str) -> bool:
    return ch.isspace() or ch in "\u00a0\u202f"


def _canon_with_positions(text: str) -> tuple[str, list[int]]:
    """Forme canonique (voir canon) et, pour chacun de ses caractères, sa position dans le texte d'origine."""
    latin = to_latin_digits(text)
    chars: list[str] = []
    positions: list[int] = []
    for i, ch in enumerate(latin):
        if _is_space(ch) or ch == "ـ":
            continue
        for folded in ch.casefold():
            chars.append(folded)
            positions.append(i)
    return "".join(chars), positions


def canon(text: str) -> str:
    """Forme comparable d'un texte : chiffres latins, sans espaces, sans tatweel, en minuscules.

    « Salaire de base 424,100 » et « salaire  de base ٤٢٤٫١٠٠ » donnent la même chose.
    """
    return _canon_with_positions(text)[0]


def _inside_number(text: str, i: int, step: int) -> bool:
    """Le caractère à la position i (et au-delà, dans la direction step) continue-t-il un nombre ?

    Vrai pour un chiffre, ou pour un séparateur « . » / « , » suivi d'un chiffre.
    """
    if not 0 <= i < len(text):
        return False
    if text[i].isdigit():
        return True
    j = i + step
    return text[i] in ".," and 0 <= j < len(text) and text[j].isdigit()


def _digit_run_left(text: str, end: int) -> int:
    """Début de la suite de chiffres qui se termine juste avant la position end."""
    start = end
    while start > 0 and text[start - 1].isdigit():
        start -= 1
    return start


def _is_integer_group(text: str, start: int, end: int) -> bool:
    """text[start:end] est-il un groupe de 1 à 3 chiffres qui peut commencer un nombre écrit « 1 156,013 » ?

    Non si c'est la partie décimale d'un nombre (« 9.18 ») ou un morceau d'un nombre plus long.
    """
    if not 1 <= end - start <= 3 or not text[start:end].isdigit():
        return False
    return not _inside_number(text, start - 1, -1)


def _is_thousands_group(text: str, start: int) -> bool:
    """text[start:] commence-t-il par exactement 3 chiffres qui peuvent suivre un espace des milliers ?

    Convention des fiches tunisiennes : « 1 156,013 » (espace des milliers, virgule décimale) ou « 1 156 ».
    Après un point (« 200 210.496 »), l'espace sépare deux nombres : ce n'est pas un groupe des milliers.
    """
    group = text[start:start + 3]
    if len(group) != 3 or not group.isdigit():
        return False
    after = start + 3
    if after < len(text) and text[after].isdigit():
        return False
    return not (text[after:after + 1] == "." and _inside_number(text, after, 1))


def _thousands_space(text: str, i: int) -> bool:
    """L'espace simple à la position i peut-il être un séparateur des milliers (« 1 156,013 ») ?"""
    if not (0 < i < len(text) - 1 and _is_space(text[i])):
        return False
    if _is_space(text[i - 1]) or _is_space(text[i + 1]):
        return False  # deux espaces ou plus : séparation entre colonnes
    return _is_integer_group(text, _digit_run_left(text, i), i) and _is_thousands_group(text, i + 1)


def _whole_number_span(text: str, start: int, end: int) -> bool:
    """Le passage text[start:end] du texte d'origine est-il pris en entier, sans couper un nombre ?

    Les frontières sont vérifiées sur le texte d'origine, avec ses espaces : dans « 9.18 122.093 »,
    l'espace sépare deux nombres et « 122.093 » est accepté. Un espace qui peut être un séparateur
    des milliers (« 1 156,013 ») compte comme l'intérieur d'un nombre : « 156,013 » n'y est pas accepté.
    """
    first, last = text[start], text[end - 1]
    if first.isdigit() and (_inside_number(text, start - 1, -1) or _thousands_space(text, start - 1)):
        return False
    if last.isdigit() and (_inside_number(text, end, 1) or _thousands_space(text, end)):
        return False
    # À l'intérieur du passage, un espace entre deux chiffres doit être un séparateur des milliers :
    # sinon le passage colle deux nombres différents (« 200 210.496 »).
    i = start + 1
    while i < end - 1:
        if not _is_space(text[i]):
            i += 1
            continue
        gap_end = i
        while gap_end < end and _is_space(text[gap_end]):
            gap_end += 1
        between_digits = text[i - 1].isdigit() and gap_end < end and text[gap_end].isdigit()
        if between_digits and not (gap_end == i + 1 and _thousands_space(text, i)):
            return False
        i = gap_end
    return True


def contains_value(line_text: str, raw: str) -> bool:
    """La valeur recopiée figure-t-elle dans la ligne, en entier ?

    Comparaison sur les formes canoniques (espaces, chiffres arabes et majuscules ignorés), puis contrôle
    des frontières sur le texte d'origine. Un nombre doit apparaître entier : « 3 » n'est pas trouvé
    dans « 2023 », ni « 275,000 » dans « 1.275,000 » ou dans « 1 275,000 ».
    """
    needle = canon(raw)
    if not needle:
        return False
    latin = to_latin_digits(line_text)
    hay, positions = _canon_with_positions(line_text)
    start = hay.find(needle)
    while start != -1:
        if _whole_number_span(latin, positions[start], positions[start + len(needle) - 1] + 1):
            return True
        start = hay.find(needle, start + 1)
    return False


def _find_zone(doc: IntermediateDocument, zone_id: str) -> PendingZone | None:
    for page in doc.pages:
        for zone in page.pending_zones:
            if zone.zone_id == zone_id:
                return zone
    return None


def _absent() -> VerifiedField:
    return VerifiedField(None, None, "absent_du_document")


def _rejected(name: str, why: str) -> VerifiedField:
    return VerifiedField(None, None, "valeur_incoherente", [f"{name} : valeur de Gemini rejetée ({why})."])


def verify_field(name: str, answer: RawField, doc: IntermediateDocument) -> VerifiedField:
    """Vérifie un champ renvoyé par Gemini contre le document."""
    raw = (answer.raw or "").strip() or None  # "" ou "  " = rien trouvé (sinon "" serait « dans » toute ligne)
    line_id = answer.line_id

    # Gemini cite une zone pas encore lue (image, arabe cassé) : la valeur existe peut-être, mais illisible.
    if line_id is not None and (zone := _find_zone(doc, line_id)) is not None:
        return VerifiedField(None, None, "zone_illisible",
                             [f"{name} : page {zone.page}, zone non lue ({zone.reason})."])
    if raw is None:
        return _absent()
    if line_id is None:
        return _rejected(name, "aucune ligne citée")
    line = doc.find_line(line_id)
    if line is None:
        return _rejected(name, f"la ligne {line_id} n'existe pas")
    if is_unreadable_line(line.text):
        return VerifiedField(None, None, "zone_illisible",
                             [f"{name} : page {line.page}, ligne {line_id} illisible."])
    if not contains_value(line.text, raw):
        return _rejected(name, f"« {raw} » ne figure pas dans la ligne {line_id}")
    return VerifiedField(raw, line, None)


def verify_all(answers: dict[str, RawField], doc: IntermediateDocument,
               expected: list[str]) -> tuple[dict[str, VerifiedField], list[str]]:
    """Vérifie tous les champs attendus.

    - un champ attendu que Gemini n'a pas renvoyé est absent ;
    - un champ renvoyé mais non attendu est ignoré, avec un avertissement.
    Renvoie les champs vérifiés et la liste des avertissements.
    """
    results: dict[str, VerifiedField] = {}
    warnings: list[str] = []
    for name in expected:
        answer = answers.get(name)
        result = verify_field(name, answer, doc) if answer is not None else _absent()
        results[name] = result
        warnings.extend(result.warnings)
    for extra in sorted(set(answers) - set(expected)):
        warnings.append(f"Champ inconnu renvoyé par Gemini, ignoré : {extra}.")
    return results, warnings
