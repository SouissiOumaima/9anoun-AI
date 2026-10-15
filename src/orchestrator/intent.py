"""Deterministic FR/AR intent and entity baseline for DS1.

This intentionally modest parser is a safe first routing layer. It never
creates facts, permissions, or card identifiers; a future model-backed parser
must preserve the same ``ParsedRequest`` contract and be evaluated separately.
"""

from __future__ import annotations

import re
from collections.abc import Iterable

from .models import Intent, ParsedRequest

_ARABIC_RE = re.compile(r"[\u0600-\u06ff]")
_DATE_RE = re.compile(r"\b\d{4}-\d{2}(?:-\d{2})?\b")
_AMOUNT_RE = re.compile(r"\b\d+(?:[.,]\d+)?\s*(?:dt|tnd|دينار)\b", re.IGNORECASE)
_ARTICLE_RE = re.compile(r"(?:article|art\.?|الفصل)\s*\d+", re.IGNORECASE)

_INTENT_KEYWORDS: tuple[tuple[Intent, tuple[str, ...]], ...] = (
    (Intent.GENERATE_DELIVERABLE, ("rédige", "redige", "génère", "genere", "contrat", "avenant", "lettre", "rapport", "حرر", "اكتب", "أنشئ")),
    (Intent.DOCUMENT_ANALYSIS, ("pdf", "document", "facture", "fichier", "scan", "وثيقة", "فاتورة", "ملف")),
    (Intent.PAYROLL_CALCULATION, ("salaire", "paie", "smig", "smag", "cnss", "cotisation", "prime", "راتب", "أجر", "منحة", "ضمان اجتماعي")),
    (Intent.CASE_ANALYSIS, ("dossier", "litige", "preuve", "partie", "affaire", "قضية", "نزاع", "دليل")),
    (Intent.LEGAL_RESEARCH, ("loi", "code", "article", "juridique", "préavis", "قانون", "مجلة", "فصل", "إشعار")),
)


def detect_language(message: str) -> str:
    """Choose Arabic only when Arabic script is present; otherwise French."""

    return "ar" if _ARABIC_RE.search(message) else "fr"


def _matches(message: str, keywords: Iterable[str]) -> tuple[str, ...]:
    lowered = message.lower()
    return tuple(keyword for keyword in keywords if keyword in lowered)


def extract_entities(message: str) -> dict[str, tuple[str, ...]]:
    """Extract only explicit, low-risk entities from the message text."""

    entities: dict[str, tuple[str, ...]] = {}
    for key, pattern in (("dates", _DATE_RE), ("amounts", _AMOUNT_RE), ("articles", _ARTICLE_RE)):
        values = tuple(match.group(0) for match in pattern.finditer(message))
        if values:
            entities[key] = values
    return entities


def parse_message(message: str) -> ParsedRequest:
    """Classify one non-empty message into a safe routing intent.

    Ties deliberately request clarification instead of picking a specialist at
    random. The highest-priority match only applies when it is unique.
    """

    if not message.strip():
        raise ValueError("message is required")

    language = detect_language(message)
    matches = [(intent, _matches(message, keywords)) for intent, keywords in _INTENT_KEYWORDS]
    matched = [(intent, words) for intent, words in matches if words]

    if not matched:
        return ParsedRequest(Intent.CLARIFICATION_REQUIRED, language, extract_entities(message), 0.0, True)

    top_intent, top_words = matched[0]
    has_conflict = len(matched) > 1 and len(top_words) == len(matched[1][1])
    if has_conflict:
        return ParsedRequest(Intent.CLARIFICATION_REQUIRED, language, extract_entities(message), 0.4, True)

    confidence = min(0.9, 0.6 + 0.1 * len(top_words))
    return ParsedRequest(top_intent, language, extract_entities(message), confidence, False)
