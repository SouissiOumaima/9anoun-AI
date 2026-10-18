"""Search by meaning: Gemini embeddings + RRF fusion with BM25 (Sprint 4 CORE, D28).

    python -m src.legal_retrieval.search.embeddings --build       # vectors of the corpus, once
    python -m src.legal_retrieval.search.embeddings --build --model gemini-embedding-2

- Gemini is the ONLY external service allowed for the confidential data (Tradrly);
  the key is read from the GEMINI_API_KEY environment variable or from the .env file
  at the repo root (ignored by Git), never from the code.
- Article vectors are computed ONCE and kept locally in
  data/processed/legal_corpus/embeddings/<model>.json (ignored by Git, like the graph).
  The file carries a fingerprint of the corpus: a stale cache is never used.
- At search time only the QUESTION is sent to Gemini.
- No key, no cache, no network -> None: the search stays BM25 only (nothing breaks).
Pure Python (no numpy): 468 vectors, cosine in a few milliseconds.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import sys
from dataclasses import dataclass, field
from functools import cache
from pathlib import Path
from typing import Any, Protocol

from ..corpus.store import CorpusStore, load_store, version_group

DEFAULT_MODEL = "gemini-embedding-001"
DIMENSION = 768  # reduced output size: smaller cache, enough for 468 articles
BATCH = 100  # texts per Gemini call
RRF_K = 60  # usual Reciprocal Rank Fusion constant

# embeddings.py -> search -> legal_retrieval -> src -> <repo root>
_REPO_ROOT = Path(__file__).resolve().parents[3]


class Embedder(Protocol):
    """Anything that turns texts into vectors (Gemini in production, a fake in tests)."""

    model: str

    def embed(self, texts: list[str], task: str) -> list[list[float]]:
        """task = "document" (corpus) or "query" (question)."""
        ...


def model_name() -> str:
    """Embedding model: env DS2_EMBED_MODEL, else gemini-embedding-001 (compared in D28)."""
    return os.environ.get("DS2_EMBED_MODEL") or DEFAULT_MODEL


def api_key() -> str | None:
    """GEMINI_API_KEY from the environment, else from <repo>/.env ; None if absent."""
    if os.environ.get("GEMINI_API_KEY"):
        return os.environ["GEMINI_API_KEY"].strip()
    env_file = _REPO_ROOT / ".env"
    if env_file.exists():
        for line in env_file.read_text(encoding="utf-8").splitlines():
            name, _, value = line.partition("=")
            if name.strip() == "GEMINI_API_KEY" and value.strip():
                return value.strip()
    return None


class GeminiEmbedder:
    """Gemini embeddings through the official client (google-genai)."""

    def __init__(self, model: str, key: str) -> None:
        # imported here: tests and BM25-only machines do not need google-genai
        from google import genai

        self.model = model
        self._client = genai.Client(api_key=key)

    def embed(self, texts: list[str], task: str) -> list[list[float]]:
        from google.genai import types

        config = types.EmbedContentConfig(
            task_type="RETRIEVAL_DOCUMENT" if task == "document" else "RETRIEVAL_QUERY",
            output_dimensionality=DIMENSION)
        vectors: list[list[float]] = []
        for start in range(0, len(texts), BATCH):
            result = self._client.models.embed_content(
                model=self.model, contents=texts[start:start + BATCH], config=config)
            vectors += [list(e.values or []) for e in result.embeddings or []]
        return vectors


_override: Embedder | None = None  # tests put a fake embedder here (no network)


def query_embedder() -> Embedder | None:
    """The embedder for questions: test override, else Gemini if a key exists, else None."""
    if _override is not None:
        return _override
    key = api_key()
    if key is None:
        return None
    try:
        return GeminiEmbedder(model_name(), key)
    except ImportError:  # google-genai not installed on this machine: BM25 only
        return None


def fingerprint(store: CorpusStore) -> str:
    """SHA-256 of every article id + text: changes as soon as the corpus changes."""
    digest = hashlib.sha256()
    for group in sorted(store.groups):
        for article in sorted(store.groups[group], key=lambda a: a["article_id"]):
            digest.update(f"{article['article_id']}\n{article['text']}\n".encode())
    return digest.hexdigest()


def cache_path(store: CorpusStore, model: str) -> Path:
    return store.folder / "embeddings" / f"{model}.json"


def build(store: CorpusStore, embedder: Embedder) -> Path:
    """Embed every article version (exact text) and write the cache. Returns its path."""
    articles = [a for g in sorted(store.groups) for a in store.groups[g]]
    vectors = embedder.embed([a["text"] for a in articles], "document")
    if len(vectors) != len(articles):
        raise RuntimeError(f"{len(vectors)} vecteurs pour {len(articles)} articles")
    path = cache_path(store, embedder.model)
    path.parent.mkdir(parents=True, exist_ok=True)
    data = {"model": embedder.model, "dimension": len(vectors[0]) if vectors else 0,
            "fingerprint": fingerprint(store),
            "vectors": {a["article_id"]: [round(x, 6) for x in v]
                        for a, v in zip(articles, vectors, strict=True)}}
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


@dataclass
class DenseIndex:
    """Unit vectors of every article version, with their version_group."""

    groups: list[str] = field(default_factory=list)
    vectors: list[list[float]] = field(default_factory=list)


def _unit(vector: list[float]) -> list[float]:
    norm = math.sqrt(sum(x * x for x in vector)) or 1.0
    return [x / norm for x in vector]


@cache
def _load(path: Path, mtime: float, expected: str) -> DenseIndex | None:
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("fingerprint") != expected:  # stale cache: never mix two corpora
        return None
    index = DenseIndex()
    for article_id, vector in sorted(data["vectors"].items()):
        index.groups.append(version_group(article_id))
        index.vectors.append(_unit(vector))
    return index


def load_dense(store: CorpusStore) -> DenseIndex | None:
    """The cached vectors of the current model, if they match the corpus; else None."""
    path = cache_path(store, model_name() if _override is None else _override.model)
    if not path.exists():
        return None
    return _load(path, path.stat().st_mtime, fingerprint(store))


def dense_scores(question: str, store: CorpusStore, allowed: set[str]) -> dict[str, float] | None:
    """Cosine of the question with every allowed article (max over versions), or None."""
    index = load_dense(store)
    embedder = query_embedder() if index is not None else None
    if index is None or embedder is None:
        return None
    try:
        query = _unit(embedder.embed([question], "query")[0])
    except Exception:  # noqa: BLE001 - network or quota problem: fall back to BM25, never fail
        return None
    best: dict[str, float] = {}
    for group, vector in zip(index.groups, index.vectors, strict=True):
        if group in allowed:
            cosine = sum(q * v for q, v in zip(query, vector, strict=True))
            best[group] = max(best.get(group, -1.0), cosine)
    return best


def rrf(rankings: list[list[str]], k: int = RRF_K) -> list[tuple[str, float]]:
    """Reciprocal Rank Fusion: sum of 1 / (k + rank) ; ties broken by id (stable order)."""
    fused: dict[str, float] = {}
    for ranking in rankings:
        for rank, group in enumerate(ranking, start=1):
            fused[group] = fused.get(group, 0.0) + 1.0 / (k + rank)
    return sorted(fused.items(), key=lambda item: (-item[1], item[0]))


def main() -> None:
    parser = argparse.ArgumentParser(description="DS2 embeddings (Gemini) for the corpus")
    parser.add_argument("--build", action="store_true", help="embed the corpus (sends it to Gemini)")
    parser.add_argument("--model", help="ex. gemini-embedding-001, gemini-embedding-2")
    args = parser.parse_args()
    if args.model:
        os.environ["DS2_EMBED_MODEL"] = args.model
    store, key = load_store(), api_key()
    if store is None or key is None:
        raise SystemExit("Corpus ou GEMINI_API_KEY absent : rien n'est envoyé.")
    if not args.build:
        raise SystemExit("Ajouter --build pour envoyer le corpus à Gemini (accord Tradrly requis).")
    path = build(store, GeminiEmbedder(model_name(), key))
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]  # Windows console
    data: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    print(f"{len(data['vectors'])} vecteurs, dimension {data['dimension']}, modèle {data['model']}")
    print(f"-> {path}")


if __name__ == "__main__":
    main()
