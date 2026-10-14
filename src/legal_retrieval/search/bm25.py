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
Not yet: dense embeddings + RRF fusion (need a model validated by Tradrly),
worker_category filter (no category metadata per article), dated versions (S5).
"""

from __future__ import annotations

import math
import re
from collections import Counter
from dataclasses import dataclass, field
from typing import Any

from ..contract.results import to_result
from ..corpus.store import CorpusStore
from .text import article_refs, terms, without_refs

K1, B = 1.5, 0.75  # usual BM25 values; to tune with the golden set (Recall@10)


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


def _exact_groups(store: CorpusStore, question: str, sector: str | None) -> list[str]:
    """Groups whose article number is asked, sectoral sources before general ones."""
    found: list[str] = []
    for number, suffix in article_refs(question):
        pattern = re.compile(rf"-ART-{re.escape(number)}{suffix}(-DUP\d+)?$")
        for group in sorted(store.groups):
            article = store.groups[group][0]
            if pattern.search(group) and _sector_ok(article.get("sector"), sector) \
                    and group not in found:
                found.append(group)
    sectors = {g: store.groups[g][0].get("sector") for g in found}
    return sorted(found, key=lambda g: sectors[g] is None)  # stable: sectoral first


def ranked_groups(request: dict[str, Any], store: CorpusStore) -> list[tuple[str, float]]:
    """(version_group, score in [0, 1]) best first, filters applied, not yet cut to top_k."""
    question, sector = request["query"], request.get("sector")
    ranked = [(g, 1.0) for g in _exact_groups(store, question, sector)]
    index = index_for(store)
    allowed = {g for g, s in zip(index.groups, index.sectors, strict=True) if _sector_ok(s, sector)}
    bm25 = {g: s for g, s in index.scores(terms(without_refs(question))).items()
            if g in allowed and g not in dict(ranked)}
    if bm25:
        top = max(bm25.values())
        # ties broken by id so that the same question always gives the same order
        ranked += [(g, round(s / top, 4)) for g, s in
                   sorted(bm25.items(), key=lambda item: (-item[1], item[0]))]
    return ranked


def search_live(request: dict[str, Any], store: CorpusStore) -> list[dict[str, Any]]:
    """Result items of the response: top_k articles, each with all its versions."""
    results: list[dict[str, Any]] = []
    for group, score in ranked_groups(request, store)[: request.get("top_k", 10)]:
        results += [to_result(a, store, score) for a in store.find_group(group)]
    return results

