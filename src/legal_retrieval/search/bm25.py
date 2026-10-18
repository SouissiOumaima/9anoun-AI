"""Real search on the ingested corpus: article reference + BM25 (Sprint 4 CORE, D26).

    from src.legal_retrieval.search.bm25 import search_live
    search_live(request, load_store())

Order of the answer:
1. articles whose NUMBER is asked ("الفصل 42 مكرر") -> score 1.0, sectoral first;
2. then BM25 on the normalized text (k1 = 1.5, b = 0.75), score / best score.
Filters: sector (an article applies to its sector or to all, sector = null).
top_k counts ARTICLES; every article comes with ALL its versions (D17).
No term in common with the corpus -> [] -> refus SOURCE_MANQUANTE (Citation ou Silence).

Pure Python, no extra dependency, nothing sent outside (confidential corpus).
With Gemini embeddings available (search/embeddings.py, D28), steps 2 becomes the
RRF fusion of the BM25 ranking and the meaning (cosine) ranking; without key, cache
or network it stays BM25 only. The abstention rule (D27) is unchanged.
Not yet: worker_category filter (no category metadata per article), dated versions (S5).
"""

from __future__ import annotations

import math
import re
from collections import Counter
from dataclasses import dataclass, field
from typing import Any

from ..contract.results import to_result
from ..corpus.normalize import normalize_arabic
from ..corpus.registry import REGISTRY
from ..corpus.store import CorpusStore
from .embeddings import dense_scores, rrf
from .text import article_refs, terms, without_refs

K1, B = 1.5, 0.75  # usual BM25 values; to tune with the golden set (Recall@10)
# Abstention (D27, golden set 2026-10-14): refuse when the best match is BOTH weak
# (raw < 8.0) AND partial (coverage < 0.5), unless an article number is asked.
# 8.0 lies between the strongest refusable out-of-scope question (7.45) and the
# weakest in-scope one (9.17); coverage protects short complete questions.
MIN_RAW, MIN_COVERAGE = 8.0, 0.5


@dataclass
class Bm25Index:
    """One document per article VERSION; scores are kept per version_group."""

    groups: list[str] = field(default_factory=list)  # version_group of each document
    sectors: list[str | None] = field(default_factory=list)
    tfs: list[Counter[str]] = field(default_factory=list)  # term counts per document
    lengths: list[int] = field(default_factory=list)
    df: Counter[str] = field(default_factory=Counter)  # documents containing a term
    avgdl: float = 1.0

    def idf(self, term: str) -> float:
        n, df = len(self.tfs), self.df[term]
        return math.log(1 + (n - df + 0.5) / (df + 0.5))  # always > 0

    def scores(self, query_terms: list[str]) -> dict[str, float]:
        """BM25 score of every version_group sharing at least one term (max over versions)."""
        best: dict[str, float] = {}
        unique = set(query_terms)
        for doc, tf in enumerate(self.tfs):
            shared = unique & tf.keys()
            if not shared:
                continue
            norm = K1 * (1 - B + B * self.lengths[doc] / self.avgdl)
            score = sum(self.idf(t) * tf[t] * (K1 + 1) / (tf[t] + norm) for t in shared)
            group = self.groups[doc]
            best[group] = max(best.get(group, 0.0), score)
        return best

    def best_match(self, query_terms: list[str], allowed: set[str]) -> tuple[float, float]:
        """(raw BM25 score, coverage) of the best allowed document.

        coverage = idf weight of the question terms found in that document / idf
        weight of all question terms (0..1). A question sharing ONE rare word with
        an article gets a high raw score but a low coverage (abstention study, D27).
        """
        unique = set(query_terms)
        total = sum(self.idf(t) for t in unique)
        raw, coverage = 0.0, 0.0
        for doc, tf in enumerate(self.tfs):
            shared = unique & tf.keys()
            if not shared or self.groups[doc] not in allowed:
                continue
            norm = K1 * (1 - B + B * self.lengths[doc] / self.avgdl)
            score = sum(self.idf(t) * tf[t] * (K1 + 1) / (tf[t] + norm) for t in shared)
            if score > raw:
                raw, coverage = score, sum(self.idf(t) for t in shared) / total
        return raw, coverage


def build_index(store: CorpusStore) -> Bm25Index:
    """Index every version of every article (text_normalized when present)."""
    index = Bm25Index()
    for group in sorted(store.groups):
        for article in store.groups[group]:
            words = terms(article.get("text_normalized") or article["text"])
            index.groups.append(group)
            index.sectors.append(article.get("sector"))
            index.tfs.append(Counter(words))
            index.lengths.append(len(words))
            index.df.update(set(words))
    index.avgdl = sum(index.lengths) / len(index.lengths) if index.lengths else 1.0
    return index


_cache: tuple[CorpusStore, Bm25Index] | None = None


def index_for(store: CorpusStore) -> Bm25Index:
    """Build the index once per loaded corpus (store is re-loaded after a new ingestion)."""
    global _cache
    if _cache is None or _cache[0] is not store:
        _cache = (store, build_index(store))
    return _cache[1]


def _sector_ok(article_sector: str | None, wanted: str | None) -> bool:
    return wanted is None or article_sector in (None, wanted)


def named_sources(question: str) -> list[str]:
    """Sources named in the question ("الاتفاقية الإطارية" -> CC-CADRE), registry keywords."""
    text = normalize_arabic(question)
    return [e.source_id for e in REGISTRY if normalize_arabic(e.keyword) in text]


def _exact_groups(store: CorpusStore, question: str, sector: str | None) -> list[str]:
    """Groups whose article number is asked, sectoral sources before general ones.

    When the question names a convention that HAS this article ("الفصل 39 من
    الاتفاقية الإطارية"), only that convention's article is kept.
    """
    found: list[str] = []
    for number, suffix in article_refs(question):
        pattern = re.compile(rf"-ART-{re.escape(number)}{suffix}(-DUP\d+)?$")
        for group in sorted(store.groups):
            article = store.groups[group][0]
            if pattern.search(group) and _sector_ok(article.get("sector"), sector) \
                    and group not in found:
                found.append(group)
    named = named_sources(question)
    in_named = [g for g in found if store.groups[g][0]["source_id"] in named]
    if in_named:
        return in_named
    sectors = {g: store.groups[g][0].get("sector") for g in found}
    return sorted(found, key=lambda g: sectors[g] is None)  # stable: sectoral first


def ranked_groups(request: dict[str, Any], store: CorpusStore) -> list[tuple[str, float]]:
    """(version_group, score in [0, 1]) best first, filters applied, not yet cut to top_k."""
    question, sector = request["query"], request.get("sector")
    ranked = [(g, 1.0) for g in _exact_groups(store, question, sector)]
    index = index_for(store)
    allowed = {g for g, s in zip(index.groups, index.sectors, strict=True) if _sector_ok(s, sector)}
    query_terms = terms(without_refs(question))
    if not ranked:  # no article number asked: Citation ou Silence on weak AND partial matches
        raw, coverage = index.best_match(query_terms, allowed)
        if raw < MIN_RAW and coverage < MIN_COVERAGE:
            return []
    exact = dict(ranked)
    bm25 = {g: s for g, s in index.scores(query_terms).items() if g in allowed and g not in exact}
    # ties broken by id so that the same question always gives the same order
    by_bm25 = sorted(bm25.items(), key=lambda item: (-item[1], item[0]))
    dense = dense_scores(without_refs(question), store, allowed)  # None = BM25 only
    if dense:  # D28: fuse the word ranking and the meaning ranking
        by_dense = [g for g, _ in sorted(dense.items(), key=lambda item: (-item[1], item[0]))
                    if g not in exact]
        fused = rrf([[g for g, _ in by_bm25], by_dense])
        top = fused[0][1] if fused else 1.0
        return ranked + [(g, round(s / top, 4)) for g, s in fused]
    if by_bm25:
        top = by_bm25[0][1]
        ranked += [(g, round(s / top, 4)) for g, s in by_bm25]
    return ranked


def top_signals(request: dict[str, Any], store: CorpusStore) -> dict[str, Any]:
    """Signals of the best BM25 match, for the abstention study (evaluation/metrics.py).

    The normalized score is always 1.0 for the first result, so it cannot decide
    "nothing relevant": the raw score and the coverage can (threshold, D27).
    """
    question, sector = request["query"], request.get("sector")
    index = index_for(store)
    allowed = {g for g, s in zip(index.groups, index.sectors, strict=True) if _sector_ok(s, sector)}
    raw, coverage = index.best_match(terms(without_refs(question)), allowed)
    dense = dense_scores(without_refs(question), store, allowed)
    return {"raw": raw, "coverage": coverage,
            "cosine": max(dense.values()) if dense else None,  # D28 signal, None = BM25 only
            "number_asked": bool(_exact_groups(store, question, sector))}


def search_live(request: dict[str, Any], store: CorpusStore) -> list[dict[str, Any]]:
    """Result items of the response: top_k articles, each with all its versions."""
    results: list[dict[str, Any]] = []
    for group, score in ranked_groups(request, store)[: request.get("top_k", 10)]:
        results += [to_result(a, store, score) for a in store.find_group(group)]
    return results

