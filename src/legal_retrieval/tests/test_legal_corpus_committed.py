"""D25: the committed corpus must equal a fresh ingestion of data/raw (no drift)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.legal_retrieval.corpus.ingest_sections import run

_ROOT = Path(__file__).resolve().parents[3]
_RAW_TXT = _ROOT / "data" / "raw" / "txt"
_RAW_PDF = _ROOT / "data" / "raw" / "pdf"
_COMMITTED = _ROOT / "data" / "processed" / "legal_corpus"
_FILES = ("legal_articles.jsonl", "legal_sources.json", "avenants.json")


@pytest.mark.skipif(not _RAW_TXT.exists() or not (_COMMITTED / _FILES[0]).exists(),
                    reason="raw sources or committed corpus not present")
def test_committed_corpus_equals_a_fresh_ingestion(tmp_path: Path) -> None:
    run(_RAW_TXT, tmp_path, _RAW_PDF if _RAW_PDF.exists() else None)
    for name in _FILES:
        fresh = (tmp_path / name).read_text(encoding="utf-8").splitlines()
        committed = (_COMMITTED / name).read_text(encoding="utf-8").splitlines()
        assert committed == fresh, (
            f"{name} n'est plus à jour : relancer "
            "python -m src.legal_retrieval.corpus.ingest_sections puis commiter")


@pytest.mark.skipif(not (_COMMITTED / _FILES[0]).exists(), reason="corpus not committed")
def test_committed_corpus_is_the_reference_size() -> None:
    """466 articles + 2 annexes (D20) ; change only with a decision."""
    lines = (_COMMITTED / _FILES[0]).read_text(encoding="utf-8").splitlines()
    origins = [json.loads(line).get("origin") for line in lines]
    assert len(lines) == 468 and origins.count("annex") == 2
