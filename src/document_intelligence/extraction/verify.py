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

import re
from dataclasses import dataclass, field
from typing import Final

from pydantic import BaseModel, ConfigDict

from src.document_intelligence.contract.v2.models import UnreadableReason
from src.document_intelligence.extraction.normalize import to_latin_digits
from src.document_intelligence.intermediate import (
    IntermediateDocument,
    PendingZone,
    TextLine,
    is_unreadable_line,
)

_SPACES: Final = re.compile(r"[\s  ]+")


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


def canon(text: str) -> str:
    """Forme comparable d'un texte : chiffres latins, sans espaces, sans tatweel, en minuscules.

    « Salaire de base 424,100 » et « salaire  de base ٤٢٤٫١٠٠ » donnent la même chose.
    """
    return _SPACES.sub("", to_latin_digits(text)).replace("ـ", "").casefold()


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


def contains_value(line_text: str, raw: str) -> bool:
    """La valeur recopiée figure-t-elle dans la ligne, en entier ?

    Comparaison sur les formes canoniques. Un nombre doit apparaître entier : « 3 » n'est pas trouvé
    dans « 2023 », ni « 275,000 » dans « 1.275,000 ».
    """
    hay, needle = canon(line_text), canon(raw)
    if not needle:
        return False
    start = hay.find(needle)
    while start != -1:
        end = start + len(needle)
        cut_before = needle[0].isdigit() and _inside_number(hay, start - 1, -1)
        cut_after = needle[-1].isdigit() and _inside_number(hay, end, 1)
        if not cut_before and not cut_after:
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
