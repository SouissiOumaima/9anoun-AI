"""Sprint 3 tests: references found in article texts (forms seen in the real corpus)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.legal_retrieval.graph.references import find_references
from src.legal_retrieval.tools.diagnose_references import diagnose


@pytest.mark.parametrize(("text", "expected"), [
    ("المنصوص عليها بالفصل 51 فقرة (ب) وتسدد", [("article", "same_source", ("51",))]),
    ("عملا بأحكام الفصلين الأول و2 من هذا الأمر", [("article", "same_source", ("1", "2"))]),
    ("الفصل 5 من الاتفاقية المشتركة الإطارية", [("article", "CC-CADRE", ("5",))]),
    ("بالفصل 5 من الأمر المؤرخ في 8 جانفي 1948", [("article", "external_text", ("5",))]),
    ("طبقا للفصل 14 من مجلة الشغل", [("article", "code_travail", ("14",)),
                                    ("external", "text", ())]),
    ("حسب الفصل 7 مكرر من هذه الاتفاقية", [("article", "same_source", ("7BIS",))]),
    # real forms (diagnostic 2026-10-11): OCR "مجل الشغل", and "... الفصل 143 منها"
    ("تنسحب احكام الفصل 166 جديد من مجل الشغل علي", [("article", "code_travail", ("166",)),
                                                    ("external", "text", ())]),
    ("مقتضيات مجل الشغل وخاص الفصل 143 منها، واذا", [("article", "code_travail", ("143",)),
                                                   ("external", "text", ())]),
    ("حسب الفصل 333 من مجله الشغل والفصل 44 من الاتفاقيه المشتركه الاطاريه",
     [("article", "code_travail", ("333",)), ("article", "CC-CADRE", ("44",)),
      ("external", "text", ())]),
])
def test_article_references(text: str, expected: list[tuple[str, str, tuple[str, ...]]]) -> None:
    assert [(r.kind, r.target, r.numbers) for r in find_references(text)] == expected


@pytest.mark.parametrize("text", [
    "إلفصل 51 (جديد): منح القفة والتنقل",          # an article header (R4), not a citation
    "الفصل56: الانتداب",                            # header without space (R1)
    "الفصول 38-39-40-41 : (ألغيت بمقتضى …",          # a repeal list (R2)
])
def test_headers_and_repeal_lists_are_not_citations(text: str) -> None:
    assert [r for r in find_references(text) if r.kind == "article"] == []


def test_avenant_and_external_texts() -> None:
    refs = find_references("حسب الملحق التعديلي عدد 3 والأمر عدد 1112 لسنة 1975")
    assert [(r.kind, r.numbers) for r in refs] == [("avenant", ("3",)), ("external", ())]
    assert refs[1].span == "الامر عدد 1112 لسنه 1975"


def test_diagnose_resolves_targets(tmp_path: Path) -> None:
    rows = [
        {"article_id": "CCS-BTP-ART-1-v1", "source_id": "CCS-BTP", "text": "تطبق أحكام الفصل 2."},
        {"article_id": "CCS-BTP-ART-2-v1", "source_id": "CCS-BTP",
         "text": "حسب الفصل 99 والملحق التعديلي عدد 5 والفصل 5 من الاتفاقية الإطارية"},
        {"article_id": "CC-CADRE-ART-5-v1", "source_id": "CC-CADRE", "text": "نص"},
    ]
    (tmp_path / "legal_articles.jsonl").write_text(
        "\n".join(json.dumps(r, ensure_ascii=False) for r in rows), encoding="utf-8")
    (tmp_path / "avenants.json").write_text(json.dumps(
        [{"source_id": "CCS-BTP", "avenants": [{"number": 5}]}]), encoding="utf-8")
    report = diagnose(tmp_path)
    assert report["resolution"] == {"article_ok": 2, "article_missing": 1, "avenant_ok": 1}
    assert report["articles_with_references"] == 2
