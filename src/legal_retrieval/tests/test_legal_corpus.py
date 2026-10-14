"""DS2 corpus tests — synthetic Arabic texts only (no confidential data)."""

from __future__ import annotations

import json
from pathlib import Path

import pymupdf
import pytest

from src.legal_retrieval.corpus.ingest import run
from src.legal_retrieval.corpus.loaders import parse_pages, reversed_text_ratio
from src.legal_retrieval.corpus.normalize import normalize_arabic
from src.legal_retrieval.corpus.registry import match_source
from src.legal_retrieval.corpus.splitter import split_articles

SAMPLE = (
    "الاتفاقية المشتركة القطاعية للبنوك\n"
    "الفصل الأول : مجال التطبيق\nتنطبق هذه الاتفاقية على البنوك.\n"
    "الفصل ٢ - الانتداب\nيتم الانتداب حسب الشروط.\n"
    "الفصل 3 مكرر\nنص مضاف.\n"
)

# Exact file names of data/raw/pdf (as listed in the repo on 2026-10-08).
REAL_FILE_NAMES = {
    "أعوان مؤسسات الحراسة والسلامة ونقل العملة": "CCS-GARDIENNAGE",
    "الأجر الأدنى المضمون لمختلف المهن في القطاعات غير الفلاحية": "SMIG-GRILLE",
    "الاتفاقية المشتركة القطاعية  للبناء المعدني": "CCS-CONSTRUCTION-METALLIQUE",
    "الاتفاقية المشتركة القطاعية  للبناء والأشغال العامة": "CCS-BTP",
    "الاتفاقية المشتركة القطاعية للتأميـن": "CCS-ASSURANCE",
    "الاتفاقية المشتركة القطاعية للتعليم الخا ص": "CCS-ENSEIGNEMENT-PRIVE",
    "الاتفاقيّة المشتركة القطاعيّة لأعوان جمعيّات رعاية الأشخاص المعوّقيـن":
        "CCS-ASSOCIATIONS",
    "الاطارية": "CC-CADRE",
    "البنوك": "CCS-BANQUES",
}


# --- normalization -------------------------------------------------------
def test_normalize_removes_tatweel_diacritics_and_unifies_alef() -> None:
    assert normalize_arabic("للتأمـين") == normalize_arabic("للتامين")
    assert normalize_arabic("الاتفاقيّة") == "الاتفاقيه"
    assert normalize_arabic("الفصل ١٤") == "الفصل 14"


def test_normalize_turns_presentation_forms_into_letters() -> None:
    assert normalize_arabic("ﺍﻟﻔﺼﻞ") == "الفصل"  # glyphs seen in PDF extraction


# --- splitting -----------------------------------------------------------
def test_split_handles_ordinals_eastern_digits_and_bis() -> None:
    preamble, arts = split_articles(SAMPLE)
    assert preamble == "الاتفاقية المشتركة القطاعية للبنوك"
    assert [a.number for a in arts] == [1, 2, 3]
    assert arts[1].label.startswith("الفصل ٢")  # original digits kept
    assert "مكرر" in arts[2].label and arts[2].is_bis
    assert not arts[1].is_bis


def test_split_tolerates_tatweel_and_diacritics() -> None:
    _, arts = split_articles("الفصــل 1\nنص\nالفَصْل 2\nنص")
    assert [a.number for a in arts] == [1, 2]


def test_split_without_headers_returns_no_articles() -> None:
    preamble, arts = split_articles("نص بدون فصول")
    assert arts == [] and preamble == "نص بدون فصول"


# --- registry ------------------------------------------------------------
@pytest.mark.parametrize(("file_name", "source_id"), REAL_FILE_NAMES.items())
def test_registry_matches_every_real_file(file_name: str, source_id: str) -> None:
    entry = match_source(file_name)
    assert entry is not None and entry.source_id == source_id


def test_registry_rejects_unknown_file() -> None:
    assert match_source("ملف غير معروف") is None


# --- loaders -------------------------------------------------------------
def test_json_loader_accepts_known_shapes() -> None:
    assert parse_pages([{"page": 1, "text": "a"}])[0].number == 1
    assert parse_pages({"pages": [{"page_number": 2, "content": "b"}]})[0].text == "b"
    assert parse_pages({"text": "c"})[0].number is None
    assert "d" in parse_pages({"x": {"y": ["d"]}})[0].text


def test_reversed_text_ratio_detects_backwards_arabic() -> None:
    assert reversed_text_ratio("الفصل 1 الفصل 2") == 0.0
    assert reversed_text_ratio("1 لصفلا 2 لصفلا") == 1.0


# --- end-to-end ----------------------------------------------------------
def test_ingestion_from_json_end_to_end(tmp_path: Path) -> None:
    src = tmp_path / "txt"
    src.mkdir()
    pages = [{"page": 1, "text": SAMPLE[:60]}, {"page": 2, "text": SAMPLE[60:]}]
    (src / "البنوك.json").write_text(json.dumps(pages, ensure_ascii=False), "utf-8")

    reports = run(src, tmp_path / "out")
    lines = (tmp_path / "out" / "legal_articles.jsonl").read_text("utf-8").splitlines()
    first = json.loads(lines[0])
    assert reports[0]["articles"] == 3 and reports[0]["missing_numbers"] == []
    assert first["article_id"] == "CCS-BANQUES-ART-1-v1"
    assert first["sector"] == "banques" and first["page_start"] == 1


def _arabic_font() -> str | None:
    """A system font with Arabic glyphs (Windows: Arial, Linux: DejaVu)."""
    for candidate in ("C:/Windows/Fonts/arial.ttf",
                      "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
                      "/System/Library/Fonts/Supplemental/Arial.ttf"):
        if Path(candidate).exists():
            return candidate
    return None


def _make_pdf(path: Path, pages: list[list[str]], font: str | None = None) -> None:
    """Write a PDF with one list of lines per page."""
    doc = pymupdf.open()
    for lines in pages:
        page = doc.new_page()
        for i, line in enumerate(lines):
            if font:
                page.insert_text((72, 72 + 20 * i), line, fontfile=font, fontname="ar")
            else:
                page.insert_text((72, 72 + 20 * i), line)
    doc.save(path)


def test_ingestion_from_pdf_keeps_page_numbers(tmp_path: Path) -> None:
    src = tmp_path / "pdf"
    src.mkdir()
    # Latin text: tests the PDF -> pages -> articles chain without RTL effects
    _make_pdf(src / "البنوك.pdf", [["Article 1", "Champ d'application."],
                                   ["Article 2", "Periode d'essai."]])
    reports = run(src, tmp_path / "out")
    rows = [json.loads(x) for x in
            (tmp_path / "out" / "legal_articles.jsonl").read_text("utf-8").splitlines()]
    assert reports[0]["articles"] == 2 and reports[0]["empty_pages"] == 0
    assert [r["page_start"] for r in rows] == [1, 2]  # citation needs the page


@pytest.mark.skipif(_arabic_font() is None, reason="no Arabic font on this machine")
def test_reversed_arabic_pdf_is_flagged_in_report(tmp_path: Path) -> None:
    """Real pymupdf behaviour: this PDF comes back as "لصفلا" (reversed)."""
    src = tmp_path / "pdf"
    src.mkdir()
    _make_pdf(src / "البنوك.pdf", [["الفصل 1", "نص"]], font=_arabic_font())
    report = run(src, tmp_path / "out")[0]
    assert report["reversed_text_ratio"] == 1.0  # detector raises the flag
    assert report["articles"] == 0  # and nothing wrong was silently produced


def test_diagnose_reports_header_shapes(tmp_path: Path) -> None:
    from src.legal_retrieval.tools.diagnose_text_layer import diagnose

    _make_pdf(tmp_path / "x.pdf", [["Article 1", "texte"], ["Article 2", "texte"]])
    report = diagnose(tmp_path / "x.pdf")
    assert report["keyword_counts_normalized"]["article"] == 2  # type: ignore[index]
    assert ("Article #", 2) in report["line_starts_top20"]  # type: ignore[operator]


def test_decode_pua_cp1256_restores_arabic() -> None:
    from src.legal_retrieval.tools.diagnose_pua import _stats, decode_pua

    # "الفصل" in cp1256 bytes, shifted into the U+F0xx "symbol font" range
    pua = "".join(chr(0xF000 + b) for b in "الفصل 1".encode("cp1256"))
    decoded = decode_pua(pua, "cp1256")
    assert decoded == "الفصل 1"
    assert _stats(decoded)["fasl"] == 1 and _stats(decoded)["arabic_ratio"] == 1.0


def test_hybrid_ingestion_flags_ocr_numbers_missing_from_pdf(tmp_path: Path) -> None:
    """Text from OCR JSON; a wrong OCR figure is flagged against the PDF."""
    txt, pdf = tmp_path / "txt", tmp_path / "pdf"
    txt.mkdir()
    pdf.mkdir()
    ocr = [{"page": 1, "text": "الفصل 1\nالأجر 1500 دينار.\n"
                               "الفصل 2\nالأجر الأدنى 459.246 دينار.\n"}]  # OCR typo
    (txt / "البنوك.json").write_text(json.dumps(ocr, ensure_ascii=False), "utf-8")
    # PDF text layer: Arabic unusable, but digits are reliable (true value 459.264)
    _make_pdf(pdf / "البنوك.pdf", [["1  1500", "2  459.264"]])

    report = run(txt, tmp_path / "out", pdf_dir=pdf)[0]
    rows = [json.loads(x) for x in
            (tmp_path / "out" / "legal_articles.jsonl").read_text("utf-8").splitlines()]
    assert report["articles"] == 2 and report["numbers_checked_against_pdf"] is True
    assert rows[0]["numbers_unverified"] == []  # 1 and 1500 found in the PDF
    assert rows[1]["numbers_unverified"] == ["459.246"]  # OCR error caught
    assert rows[1]["text_source"] == "ocr_json"
    assert report["numbers_unverified"] == 1 and report["numbers_total"] == 4


def test_without_pdf_the_number_check_is_marked_not_run(tmp_path: Path) -> None:
    txt = tmp_path / "txt"
    txt.mkdir()
    (txt / "البنوك.json").write_text(json.dumps([{"page": 1, "text": SAMPLE}],
                                                 ensure_ascii=False), "utf-8")
    report = run(txt, tmp_path / "out", pdf_dir=tmp_path / "absent")[0]
    row = json.loads((tmp_path / "out" / "legal_articles.jsonl")
                     .read_text("utf-8").splitlines()[0])
    assert report["numbers_checked_against_pdf"] is False
    assert row["numbers_unverified"] is None  # None = not checked, never "OK"


def test_number_check_ignores_separators_and_rtl_digit_order() -> None:
    from src.legal_retrieval.corpus.ingest import _canonical, pdf_number_index

    index = pdf_number_index("0051 et 459,264")  # "1500" read backwards by RTL
    assert _canonical("1500") in index  # reversed digits accepted
    assert _canonical("459.264") in index  # "," vs "." accepted
    assert _canonical("459.246") not in index  # a real OCR error still caught


def test_bis_article_gets_its_own_id_not_a_duplicate(tmp_path: Path) -> None:
    txt = tmp_path / "txt"
    txt.mkdir()
    text = "الفصل 7\nنص\nالفصل 7 مكرر: تشغيل\nنص\nالفصل 8\nنص"
    (txt / "البنوك.json").write_text(json.dumps([{"page": 1, "text": text}],
                                                 ensure_ascii=False), "utf-8")
    report = run(txt, tmp_path / "out")[0]
    ids = [json.loads(x)["article_id"] for x in
           (tmp_path / "out" / "legal_articles.jsonl").read_text("utf-8").splitlines()]
    assert ids == ["CCS-BANQUES-ART-7-v1", "CCS-BANQUES-ART-7BIS-v1",
                   "CCS-BANQUES-ART-8-v1"]
    assert report["duplicate_ids"] == 0
