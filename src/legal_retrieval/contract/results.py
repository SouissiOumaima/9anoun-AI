"""One corpus article -> one result item of legal_retrieval_search_response.v0.

Shared by `search` (BM25, D26) and `get_article` (D22): DS1 and DS4 parse ONE
result format, whatever operation produced it.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ..corpus.store import DATA_FILE, CorpusStore, version_group, version_of


def to_result(article: dict[str, Any], store: CorpusStore, score: float = 1.0) -> dict[str, Any]:
    """LegalArticle (corpus line) -> result item. `score` in [0, 1] (1.0 = exact reference)."""
    source = store.sources.get(article["source_id"], {})
    pdf = f"data/raw/pdf/{Path(source.get('file_name', article['source_id'])).stem}.pdf"
    citation = {"source_file": pdf, "page": article.get("page_start"),
                "article": article["article_label"], "data_file": DATA_FILE,
                "decision_ref": "D20"}  # the corpus itself comes from the D20 loader
    return {
        "article_id": article["article_id"],
        "source_id": article["source_id"],
        "source_title": source.get("title_ar", article["source_id"]),
        "article_number": article.get("article_number"),
        "hierarchy_path": article["hierarchy_path"],
        "text": article["text"],  # exact text, never the normalized one (D13)
        "page": article.get("page_start"),  # not in the Tradrly digest yet -> null
        "effective_from": article.get("effective_from"),
        "effective_to": article.get("effective_to"),
        "status": article["status"],
        "sector": article.get("sector"),
        "related": [],
        "score": score,
        "version_group": version_group(article["article_id"]),
        "version": version_of(article["article_id"]),
        # v0: the consolidated text in force; dated filter in Sprint 5
        "applicable_at_reference_date": article["status"] == "en_vigueur",
        "modified": bool(article.get("modified")),
        "amended_by": article.get("amended_by"),
        "previous_version_available": (False if article["status"] == "abroge"
                                       else article.get("previous_version_available", True)),
        "citation": citation,
    }
