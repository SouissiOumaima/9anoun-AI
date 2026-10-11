"""Read access to the ingested corpus (output of corpus/ingest_sections.py).

The corpus lives in data/processed/legal_corpus/ (NOT in git: confidential).
`DS2_CORPUS_DIR` can point elsewhere (tests). When the folder or its
legal_articles.jsonl is missing, `load_store()` returns None and callers fall
back to mock mode: a machine without the corpus never invents articles.
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from functools import cache
from pathlib import Path
from typing import Any

# store.py -> corpus -> legal_retrieval -> src -> <repo root>
DEFAULT_CORPUS_DIR = Path(__file__).resolve().parents[3] / "data" / "processed" / "legal_corpus"
DATA_FILE = "data/processed/legal_corpus/legal_articles.jsonl"  # citation.data_file

_VERSION = re.compile(r"-v(\d+)$")


def version_group(article_id: str) -> str:
    """"CCS-BTP-ART-39-v1" -> "CCS-BTP-ART-39" (same for every version)."""
    return _VERSION.sub("", article_id)


def version_of(article_id: str) -> int:
    """"...-v2" -> 2 ; no suffix -> 1."""
    match = _VERSION.search(article_id)
    return int(match.group(1)) if match else 1


@dataclass
class CorpusStore:
    """Articles grouped by version_group, plus source titles."""

    folder: Path
    groups: dict[str, list[dict[str, Any]]] = field(default_factory=dict)
    sources: dict[str, dict[str, Any]] = field(default_factory=dict)

    def find_group(self, group: str) -> list[dict[str, Any]]:
        """All versions of one article, NEWEST first like search ([] if unknown)."""
        return sorted(self.groups.get(group, []), key=lambda a: -version_of(a["article_id"]))

    def find_by_number(self, source_id: str, article: str) -> list[list[dict[str, Any]]]:
        """Every article "<source>[-P<n>]-ART-<article>[-DUP<k>]" (several texts per file)."""
        pattern = re.compile(
            rf"^{re.escape(source_id)}(-P\d+)?-ART-{re.escape(article)}(-DUP\d+)?$")
        return [self.find_group(g) for g in sorted(self.groups) if pattern.match(g)]


def corpus_dir() -> Path:
    """Folder of the ingested corpus (env DS2_CORPUS_DIR first)."""
    return Path(os.environ.get("DS2_CORPUS_DIR") or DEFAULT_CORPUS_DIR)


@cache
def _load(folder: Path, mtime: float) -> CorpusStore:
    """Parse the corpus once per (folder, file modification time)."""
    store = CorpusStore(folder)
    for line in (folder / "legal_articles.jsonl").read_text(encoding="utf-8").splitlines():
        if line.strip():
            article = json.loads(line)
            store.groups.setdefault(version_group(article["article_id"]), []).append(article)
    sources_file = folder / "legal_sources.json"
    if sources_file.exists():
        for source in json.loads(sources_file.read_text(encoding="utf-8")):
            store.sources[source["source_id"]] = source
    return store


def load_store() -> CorpusStore | None:
    """The corpus if it was ingested on this machine, else None (mock mode)."""
    articles = corpus_dir() / "legal_articles.jsonl"
    if not articles.exists():
        return None
    return _load(corpus_dir(), articles.stat().st_mtime)  # re-read after a new ingestion
