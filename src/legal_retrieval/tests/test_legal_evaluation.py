"""D27 tests: golden set file is well formed; metrics computed on a synthetic live corpus."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from src.legal_retrieval.contract.vocabulary import load_vocabulary
from src.legal_retrieval.corpus.ingest_sections import run
from src.legal_retrieval.corpus.store import load_store
from src.legal_retrieval.evaluation.metrics import evaluate, load_golden

KINDS = {"sujet", "dialecte", "francais", "numero", "hors_perimetre"}


def test_golden_set_is_well_formed() -> None:
    golden = load_golden()
    ids = [q["id"] for q in golden["questions"]]
    assert len(ids) == len(set(ids))  # unique ids
    sectors = {s["code"] for s in load_vocabulary()["sectors"]}
    for q in golden["questions"]:
        assert q["kind"] in KINDS and q["status"] in {"a_completer", "complet"}
        assert q["sector"] is None or q["sector"] in sectors, q["id"]  # D21 codes only
        if q["kind"] == "hors_perimetre":
            assert q["expected"] == [] and q["status"] == "complet"
        if q["status"] == "complet" and q["kind"] != "hors_perimetre":
            assert q["expected"], f"{q['id']} complet sans article attendu"
            assert all("-ART-" in g or "-ANNEXE-" in g for g in q["expected"])
            assert not any(g.endswith(("-v1", "-v2")) for g in q["expected"])  # version_group


def _section(article: str, text: str) -> dict[str, Any]:
    heading = f"الفصل {article}"
    return {"source_article": article, "source_heading": heading, "title": heading,
            "content_type": None, "content": text, "paragraphs": [text]}


@pytest.fixture
def live_store(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Any:
    raw = tmp_path / "raw"
    raw.mkdir()
    digest = {"sections": [_section("1", "يتمتع العامل بعطلة سنوية خالصة الأجر."),
                           _section("2", "تصرف منحة النقل شهريا لكل عامل.")]}
    (raw / "الاتفاقية المشتركة القطاعية للبناء والأشغال العامة.json").write_text(
        json.dumps(digest, ensure_ascii=False), encoding="utf-8")
    run(raw, tmp_path / "corpus")
    monkeypatch.setenv("DS2_CORPUS_DIR", str(tmp_path / "corpus"))
    return load_store()


def _q(i: str, kind: str, question: str, expected: list[str], status: str = "complet") -> dict[str, Any]:
    return {"id": i, "kind": kind, "question": question, "sector": "btp",
            "reference_date": None, "expected": expected, "status": status, "note": ""}


def test_metrics_on_a_synthetic_corpus(live_store: Any) -> None:
    golden = {"golden_set_version": "test", "questions": [
        _q("A", "sujet", "كم يوما من العطلة السنوية؟", ["CCS-BTP-ART-1"]),
        _q("B", "numero", "الفصل 2", ["CCS-BTP-ART-2"]),
        _q("C", "sujet", "منحة النقل", ["CCS-BTP-ART-99"]),  # wrong on purpose: missed
        _q("H", "hors_perimetre", "ما هي عاصمة فرنسا؟", []),
        _q("X", "sujet", "سؤال", [], status="a_completer"),
    ]}
    report = evaluate(golden, live_store)
    s = report["summary"]
    assert report["skipped_a_completer"] == ["X"]
    assert s["core"]["n"] == 3 and s["core"]["recall@1"] == pytest.approx(2 / 3)
    assert s["missed@10"] == ["C"] and s["abstention"] == 1.0
    rows = {r["id"]: r for r in report["rows"]}
    assert rows["B"]["article_number_asked"] is True and rows["H"]["raw_top"] == 0.0
    # question in scope: a good part of it is found ; out of scope: nothing
    assert rows["A"]["coverage"] > 0.3 and rows["H"]["coverage"] == 0.0
    # threshold 0.0 refuses nothing more than the engine already does
    assert s["threshold_study"][0]["threshold"] == 0.0
    assert s["threshold_study"][0]["recall@10"] == pytest.approx(2 / 3)
    assert s["coverage_study"][0]["threshold"] == 0.0
