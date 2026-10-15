"""D28 tests: embeddings + RRF fusion with a FAKE embedder (no network, no key used)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from src.legal_retrieval.contract.handler import handle
from src.legal_retrieval.corpus.ingest_sections import run
from src.legal_retrieval.corpus.normalize import normalize_arabic
from src.legal_retrieval.corpus.store import load_store
from src.legal_retrieval.search import bm25, embeddings

V0 = "legal_retrieval.v0"
# fake "meaning": one dimension per idea, whatever the word used (like a real embedding)
_IDEAS = {0: ("وفا", "توفي"), 1: ("نقل",), 2: ("عطل",), 3: ("منح",)}


class FakeEmbedder:
    """Counts ideas in the text: "توفي" and "الوفاة" land on the same dimension."""

    model = "fake-embedding"

    def __init__(self, fail_on_query: bool = False) -> None:
        self.fail_on_query = fail_on_query
        self.calls: list[str] = []

    def embed(self, texts: list[str], task: str) -> list[list[float]]:
        self.calls.append(task)
        if task == "query" and self.fail_on_query:
            raise ConnectionError("pas de réseau")
        return [[0.01 + sum(normalize_arabic(t).count(w) for w in words)
                 for _, words in sorted(_IDEAS.items())] for t in texts]


def _section(article: str, text: str) -> dict[str, Any]:
    heading = f"الفصل {article}"
    return {"source_article": article, "source_heading": heading, "title": heading,
            "content_type": None, "content": text, "paragraphs": [text]}


def _ingest(tmp_path: Path, death_text: str) -> Path:
    raw = tmp_path / "raw"
    raw.mkdir(parents=True, exist_ok=True)
    digest = {"sections": [
        _section("1", death_text),
        _section("2", "تصرف منحة النقل للعامل ومنحة شهرية ومنحة سنوية للعامل."),
        _section("3", "يتمتع العامل بعطلة سنوية خالصة الأجر."),
    ]}
    (raw / "الاتفاقية المشتركة القطاعية للبناء والأشغال العامة.json").write_text(
        json.dumps(digest, ensure_ascii=False), encoding="utf-8")
    out = tmp_path / "corpus"
    run(raw, out)
    return out


@pytest.fixture
def corpus(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    out = _ingest(tmp_path, "تسند منحة لعائلة العامل عند الوفاة.")
    monkeypatch.setenv("DS2_CORPUS_DIR", str(out))
    monkeypatch.setattr(bm25, "MIN_RAW", 0.0)  # tiny corpus: isolate the ranking from D27 abstention
    return out


def _groups(query: str) -> list[str]:
    response = handle({"contract_version": V0, "query": query, "sector": "btp"})
    seen: list[str] = []
    for r in response["results"]:
        if r["version_group"] not in seen:
            seen.append(r["version_group"])
    return seen


QUESTION = "ما هي المنحة للعامل إذا توفي"  # "توفي" never appears in the corpus


def test_rrf_rewards_documents_ranked_well_by_both() -> None:
    fused = embeddings.rrf([["a", "b", "c"], ["b", "c", "a"]])
    assert fused[0][0] == "b" and [g for g, _ in fused] == ["b", "a", "c"]


def test_without_cache_the_search_is_bm25_only(corpus: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    fake = FakeEmbedder()
    monkeypatch.setattr(embeddings, "_override", fake)
    store = load_store()
    assert store is not None
    assert embeddings.dense_scores(QUESTION, store, set(store.groups)) is None  # no cache built
    assert fake.calls == []  # nothing sent anywhere without a cache


def test_meaning_brings_the_right_article_first(corpus: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    bm25_only = _groups(QUESTION)  # words: the grant article (منحة x3) wins
    fake = FakeEmbedder()
    monkeypatch.setattr(embeddings, "_override", fake)
    store = load_store()
    assert store is not None
    path = embeddings.build(store, fake)
    assert path.name == "fake-embedding.json" and fake.calls == ["document"]
    hybrid = _groups(QUESTION)  # meaning: "توفي" ~ "الوفاة"
    assert bm25_only[0] == "CCS-BTP-ART-2"
    assert hybrid[0] == "CCS-BTP-ART-1"
    assert fake.calls[-1] == "query"  # only the QUESTION is embedded at search time


def test_stale_cache_is_never_used(corpus: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    fake = FakeEmbedder()
    monkeypatch.setattr(embeddings, "_override", fake)
    store = load_store()
    assert store is not None
    embeddings.build(store, fake)
    changed = _ingest(tmp_path / "v2", "نص مختلف تماما.")  # corpus changed after the build
    (changed / "embeddings").mkdir()
    (changed / "embeddings" / "fake-embedding.json").write_bytes(
        embeddings.cache_path(store, fake.model).read_bytes())
    monkeypatch.setenv("DS2_CORPUS_DIR", str(changed))
    new_store = load_store()
    assert new_store is not None and embeddings.load_dense(new_store) is None


def test_network_error_falls_back_to_bm25(corpus: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    store = load_store()
    assert store is not None
    embeddings.build(store, FakeEmbedder())
    monkeypatch.setattr(embeddings, "_override", FakeEmbedder(fail_on_query=True))
    response = handle({"contract_version": V0, "query": QUESTION, "sector": "btp"})
    assert response["status"] == "ok" and response["mode"] == "live"  # no erreur, BM25 answer


def test_key_is_read_from_env_never_required(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GEMINI_API_KEY", " test-key ")
    assert embeddings.api_key() == "test-key"
    monkeypatch.setenv("DS2_EMBED_MODEL", "gemini-embedding-2")
    assert embeddings.model_name() == "gemini-embedding-2"
