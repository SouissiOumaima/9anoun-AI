"""Vocabulary-backed extraction for DS1 → DS2 legal retrieval requests."""

from __future__ import annotations

from dataclasses import dataclass
import re
import unicodedata
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
    sector_choices_fr: tuple[str, ...] = ()
    sector_choices_ar: tuple[str, ...] = ()


_ARTICLE_ID_RE = re.compile(r"\b([A-Z][A-Z0-9-]*-(?:ART-[0-9]+(?:BIS|TER|QUATER|-[0-9]+)?|ANNEXE-[0-9]+)(?:-DUP[0-9]+)?(?:-v[0-9]+)?)\b")
_ARTICLE_RE = re.compile(r"(?:article|art\.?|الفصل)\s*([0-9]+(?:bis|ter|quater|-[0-9]+)?)\b", re.IGNORECASE)


def extract_legal_prompt(message: str) -> LegalPromptExtraction:
    """Extract only vocabulary values that are explicit in the user prompt."""

    lowered = message.casefold()
    vocabulary = load_vocabulary()
    choices, ambiguous = _sector_candidates(message, vocabulary)
    sector_item = choices[0] if len(choices) == 1 and not ambiguous else None
    sector = sector_item["code"] if sector_item else None
    source_id = sector_item["source_id"] if sector_item else None
    category = _find_worker_category(lowered, vocabulary["worker_categories"])
    article_id = _article_id(message)
    article = _article_number(message)
    if article_id is not None:
        source_id, article = None, None
    return LegalPromptExtraction(
        sector, category, source_id, article, article_id, ambiguous,
        tuple(s['label_fr'] for s in choices) if ambiguous else (),
        tuple(s['label_ar'] for s in choices) if ambiguous else (),
    )


def normalize_sector_text(text: str) -> str:
    """Comparable FR/AR text; keep matching independent of vocabulary order."""
    text = unicodedata.normalize('NFKD', text.casefold())
    text = ''.join(c for c in text if not unicodedata.combining(c))
    text = re.sub(r"[-‐‑–—]", ' ', text).replace('’', "'")
    return ' '.join(text.split())


def _term_spans(message: str, term: str):
    term = normalize_sector_text(term)
    if not term:
        return []
    return [m.span() for m in re.finditer(rf'(?<!\w){re.escape(term)}(?!\w)', message)]


def _sector_candidates(message: str, vocabulary: dict[str, Any]) -> tuple[list[dict[str, Any]], bool]:
    message = normalize_sector_text(message)
    # Protection-sociale expressions must never select assurance or gardiennage.
    message = re.sub(
        r'\b(?:securite sociale|assurance (?:sociale|maladie|sante))\b|'
        r'التامين (?:على المرض|الاجتماعي|الصحي)|الضمان الاجتماعي', ' ', message,
    )
    sectors = {s['code']: s for s in vocabulary['sectors']}
    if len(sectors) != len(vocabulary['sectors']):
        raise ValueError('D21 contains duplicate sector codes')
    matches = []
    for code, sector in sectors.items():
        terms = [code, sector['source_id'], sector['label_fr'], sector['label_ar'], *sector.get('aliases', [])]
        for term in terms:
            matches.extend((start, end, code) for start, end in _term_spans(message, term))
    # A specific designation suppresses only shorter aliases inside the same
    # phrase. Distinct mentions and shared aliases remain ambiguous.
    matches = [m for m in set(matches) if not any(
        other[0] <= m[0] and m[1] <= other[1] and other[1]-other[0] > m[1]-m[0]
        for other in matches
    )]
    codes = {m[2] for m in matches}
    ambiguous_rule = False
    for rule in vocabulary.get('sector_ambiguities', []):
        aliases = rule.get('aliases') or rule.get('alias', '').split('/')
        for term in aliases:
            for start, end in _term_spans(message, term.strip()):
                if any(m[0] <= start and end <= m[1] and m[1]-m[0] > end-start for m in matches):
                    continue
                ambiguous_rule = True
                unknown = set(rule['codes']) - sectors.keys()
                if unknown:
                    raise ValueError('D21 ambiguity references unknown sector codes')
                codes.update(rule['codes'])
    choices = [sectors[code] for code in sorted(codes)]
    return choices, ambiguous_rule or len(choices) > 1


def legal_sector_clarification(extracted: LegalPromptExtraction) -> tuple[str, str]:
    fr = ' ou '.join(extracted.sector_choices_fr)
    ar = ' أم '.join(extracted.sector_choices_ar)
    return (
        f'Le secteur est ambigu. Précisez le secteur concerné : {fr}.',
        f'القطاع غير محدد بوضوح. يرجى تحديد القطاع المعني: {ar}.',
    )


def _find_worker_category(message: str, categories: list[dict[str, Any]]) -> str | None:
    for category in categories:
        terms = [category["label_fr"], category["label_ar"], *category.get("corpus_terms_ar", [])]
        if any(term.casefold() in message for term in terms):
            return str(category["code"])
    return None


def _article_id(message: str) -> str | None:
    match = _ARTICLE_ID_RE.search(message.upper())
    return match.group(1) if match else None


def _article_number(message: str) -> str | None:
    match = _ARTICLE_RE.search(message)
    return match.group(1).upper() if match else None
