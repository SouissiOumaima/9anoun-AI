"""Tests du lecteur de PDF natif et de la représentation intermédiaire."""

from __future__ import annotations

from pathlib import Path

import pymupdf
import pytest

from src.document_intelligence.intermediate import detect_language, is_unreadable_line
from src.document_intelligence.reading.pdf_natif import merge_rows, read_pdf


def _png_bytes() -> bytes:
    pix = pymupdf.Pixmap(pymupdf.csRGB, pymupdf.IRect(0, 0, 400, 200), False)
    pix.clear_with(200)
    return bytes(pix.tobytes("png"))


@pytest.fixture()
def loi_pdf(tmp_path: Path) -> Path:
    doc = pymupdf.open()
    p1 = doc.new_page()
    p1.insert_text((72, 100), "Article 1. Le salaire minimum est fixe par decret.", fontsize=12)
    p1.insert_text((72, 130), "Article 2. Il est revise chaque annee.", fontsize=12)
    p2 = doc.new_page()
    p2.insert_text((72, 80), "Grille des salaires n. 2 :", fontsize=12)
    p2.insert_image(pymupdf.Rect(72, 100, 372, 210), stream=_png_bytes())
    path = tmp_path / "loi.pdf"
    doc.save(path)
    doc.close()
    return path


def test_reads_native_lines_with_position(loi_pdf: Path) -> None:
    doc = read_pdf(loi_pdf)
    page1 = doc.pages[0]
    assert [line.text for line in page1.lines] == [
        "Article 1. Le salaire minimum est fixe par decret.",
        "Article 2. Il est revise chaque annee.",
    ]
    first = page1.lines[0]
    assert first.line_id == "p1_l1"
    assert first.source == "natif"
    assert first.confidence == 1.0
    assert first.language == "fr"
    assert first.bbox[0] == pytest.approx(72, abs=1)  # commence à 72 points du bord gauche


def test_image_zone_is_left_for_ocr(loi_pdf: Path) -> None:
    doc = read_pdf(loi_pdf)
    page2 = doc.pages[1]
    assert page2.kind == "mixte"
    assert [line.text for line in page2.lines] == ["Grille des salaires n. 2 :"]
    assert len(page2.pending_zones) == 1
    assert page2.pending_zones[0].zone_id == "p2_z1"
    assert any("OCR" in w for w in doc.warnings)


def test_full_text_keeps_line_ids(loi_pdf: Path) -> None:
    text = read_pdf(loi_pdf).full_text()
    assert "=== Page 1 ===" in text
    assert "[p1_l1] Article 1." in text
    assert "[p2_z1] <zone image non lue" in text


def test_find_line_gives_back_position(loi_pdf: Path) -> None:
    doc = read_pdf(loi_pdf)
    line = doc.find_line("p2_l1")
    assert line is not None and line.page == 2
    assert doc.find_line("p9_l9") is None


def test_round_trip_json(loi_pdf: Path) -> None:
    doc = read_pdf(loi_pdf)
    again = type(doc).model_validate_json(doc.model_dump_json())
    assert again == doc


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Le salaire de base", "fr"),
        ("الأجر الأدنى المضمون", "ar"),
        ("Article 43 الفصل", "mixte"),
        ("344.500", "inconnu"),
    ],
)
def test_detect_language(text: str, expected: str) -> None:
    assert detect_language(text) == expected


# Une police TrueType sans glyphes « Private Use » (Linux ou Windows).
_FONT_CANDIDATES = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "C:/Windows/Fonts/arial.ttf",
    "/Library/Fonts/Arial.ttf",
]
FONT = next((f for f in _FONT_CANDIDATES if Path(f).exists()), "")
# Caractères « Private Use » comme l'arabe du corpus Tradrly. Insérés avec une police qui n'a pas
# ces glyphes, ils ressortent sans code (U+0000) : une couche texte cassée, comme dans le corpus.
PUA_TEXT = "\uf2a1\uf2b3\uf2c4 \uf2d5\uf2e6 43"


def _pdf_with_lines(tmp_path: Path, lines: list[str], name: str) -> Path:
    doc = pymupdf.open()
    page = doc.new_page()
    for i, text in enumerate(lines):
        if text == PUA_TEXT:
            page.insert_text((72, 100 + i * 30), text, fontsize=12, fontfile=FONT, fontname="ttf")
        else:
            page.insert_text((72, 100 + i * 30), text, fontsize=12)
    path = tmp_path / name
    doc.save(path)
    doc.close()
    return path


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Article 1. Le salaire minimum", False),
        ("الأجر الأدنى المضمون", False),
        ("344.500", False),
        ("", False),
        ("\uf2a1\uf2b3\uf2c4 \uf2d5 43", True),  # arabe en Private Use (corpus Tradrly)
        ("\x00\x00\x00 \x00\x00 43", True),  # glyphes sans code
        ("abc\ufffd", True),  # caractère de remplacement
    ],
)
def test_is_unreadable_line(text: str, expected: bool) -> None:
    assert is_unreadable_line(text) is expected


@pytest.mark.skipif(not FONT, reason="aucune police TrueType trouvée")
def test_unreadable_line_goes_to_ocr(tmp_path: Path) -> None:
    path = _pdf_with_lines(
        tmp_path, ["Article 1. Texte lisible.", PUA_TEXT, "Article 2. Texte lisible.", "Article 3."], "un.pdf"
    )
    doc = read_pdf(path)
    page = doc.pages[0]
    assert [line.text for line in page.lines] == [
        "Article 1. Texte lisible.",
        "Article 2. Texte lisible.",
        "Article 3.",
    ]
    zones = [z for z in page.pending_zones if z.reason == "texte_illisible"]
    assert [z.zone_id for z in zones] == ["p1_u1"]
    assert any("illisible" in w for w in doc.warnings)
    assert "[p1_u1] <texte natif illisible" in doc.full_text()


@pytest.mark.skipif(not FONT, reason="aucune police TrueType trouvée")
def test_mostly_unreadable_page_goes_entirely_to_ocr(tmp_path: Path) -> None:
    path = _pdf_with_lines(tmp_path, [PUA_TEXT, PUA_TEXT, "Article 1."], "beaucoup.pdf")
    page = read_pdf(path).pages[0]
    assert page.lines == []
    assert len(page.pending_zones) == 1
    zone = page.pending_zones[0]
    assert zone.reason == "texte_illisible"
    assert zone.bbox == (0.0, 0.0, 595.0, 842.0)


# ------------------------------------------------------------ lignes visuelles (v0.3)


def test_label_and_amount_in_two_columns_become_one_line(tmp_path: Path) -> None:
    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text((72, 100), "Salaire de base", fontsize=10)
    page.insert_text((420, 100), "424,100", fontsize=10)
    page.insert_text((72, 120), "Prime de transport", fontsize=10)
    page.insert_text((420, 120), "56,000", fontsize=10)
    path = tmp_path / "colonnes.pdf"
    doc.save(path)
    lines = read_pdf(path).pages[0].lines
    assert [line.text for line in lines] == ["Salaire de base  424,100", "Prime de transport  56,000"]
    assert lines[0].bbox[0] == pytest.approx(72, abs=1) and lines[0].bbox[2] > 420


def test_merge_rows_reads_arabic_rows_right_to_left() -> None:
    parts = [("424,100", (72.0, 100.0, 110.0, 112.0)), ("الأجر الأساسي", (400.0, 100.0, 480.0, 112.0))]
    assert merge_rows(parts) == [("الأجر الأساسي  424,100", (72.0, 100.0, 480.0, 112.0))]


def test_merge_rows_keeps_separate_lines_apart() -> None:
    parts = [("Ligne 2", (72.0, 130.0, 120.0, 142.0)), ("Ligne 1", (72.0, 100.0, 120.0, 112.0))]
    assert [text for text, _ in merge_rows(parts)] == ["Ligne 1", "Ligne 2"]


@pytest.mark.skipif(not FONT, reason="aucune police TrueType trouvée")
def test_arabic_presentation_forms_are_turned_into_normal_letters(tmp_path: Path) -> None:
    # « الصنف » écrit en formes de présentation (U+FExx) et posé dans l'ordre visuel
    # (de gauche à droite à l'écran), comme dans beaucoup de vrais PDF arabes.
    visual = "ﻒﻨﺼﻟﺍ"
    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text((72, 100), visual, fontsize=12, fontfile=FONT, fontname="ttf")
    path = tmp_path / "formes.pdf"
    doc.save(path)
    lines = read_pdf(path).pages[0].lines
    assert lines and lines[0].text == "الصنف" and lines[0].language == "ar"
