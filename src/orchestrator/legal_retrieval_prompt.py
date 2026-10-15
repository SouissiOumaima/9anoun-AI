"""Vocabulary-backed extraction for DS1 → DS2 legal retrieval requests."""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any

from src.legal_retrieval.contract.vocabulary import load_vocabulary


@dataclass(frozen=True, slots=True)
class LegalPromptExtraction:
    sector: str | None
    worker_category: str | None
    source_id: str | None
    article: str | None
    article_id: str | None
    sector_ambiguous: bool


_ARTICLE_ID_RE = re.compile(r"\b([A-Z][A-Z0-9-]*-(?:ART-[0-9]+(?:BIS|TER|QUATER|-[0-9]+)?|ANNEXE-[0-9]+)(?:-DUP[0-9]+)?(?:-v[0-9]+)?)\b")
_ARTICLE_RE = re.compile(r"(?:article|art\.?|الفصل)\s*([0-9]+(?:bis|ter|quater|-[0-9]+)?)\b", re.IGNORECASE)


def extract_legal_prompt(message: str) -> LegalPromptExtraction:
    """Extract only vocabulary values that are explicit in the user prompt."""

    lowered = message.casefold()
    vocabulary = load_vocabulary()
    ambiguous = _is_ambiguous_construction(lowered)
    sector_item = None if ambiguous else _find_sector(lowered, vocabulary["sectors"])
    sector = sector_item["code"] if sector_item else None
    source_id = sector_item["source_id"] if sector_item else None
    category = _find_worker_category(lowered, vocabulary["worker_categories"])
    article_id = _article_id(message)
    article = _article_number(message)
    if article_id is not None:
        source_id, article = None, None
    return LegalPromptExtraction(
        sector, category, source_id, article, article_id, ambiguous,
    )


def _find_sector(message: str, sectors: list[dict[str, Any]]) -> dict[str, Any] | None:
    for sector in sectors:
        terms = [sector["label_fr"], sector["label_ar"], *sector.get("aliases", [])]
        if any(term.casefold() in message for term in terms):
            return sector
    return None


def _find_worker_category(message: str, categories: list[dict[str, Any]]) -> str | None:
    for category in categories:
        terms = [category["label_fr"], category["label_ar"], *category.get("corpus_terms_ar", [])]
        if any(term.casefold() in message for term in terms):
            return str(category["code"])
    return None


def _is_ambiguous_construction(message: str) -> bool:
    french_ambiguous = "construction" in message and "construction métallique" not in message and "construction metallique" not in message
    arabic_ambiguous = "البناء" in message and "البناء المعدني" not in message and "الأشغال العامة" not in message
    return french_ambiguous or arabic_ambiguous


def _article_id(message: str) -> str | None:
    match = _ARTICLE_ID_RE.search(message.upper())
    return match.group(1) if match else None


def _article_number(message: str) -> str | None:
    match = _ARTICLE_RE.search(message)
    return match.group(1).upper() if match else None
