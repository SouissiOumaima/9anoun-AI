"""Tests de l'inventaire : on fabrique un faux PDF avec 4 types de pages."""

from __future__ import annotations

from pathlib import Path

import pymupdf
import pytest

from src.document_intelligence.reading.inventory import classify, export_images, inventory

LOREM = "Article 1. Le présent texte fixe les salaires minimums du secteur. " * 3


def _png_bytes(width: int = 400, height: int = 200) -> bytes:
    pix = pymupdf.Pixmap(pymupdf.csRGB, pymupdf.IRect(0, 0, width, height), False)
    pix.clear_with(200)
    return bytes(pix.tobytes("png"))


@pytest.fixture()
def sample_pdf(tmp_path: Path) -> Path:
    doc = pymupdf.open()
    img = _png_bytes()
    # page 1 : texte seulement
    doc.new_page().insert_textbox(pymupdf.Rect(50, 50, 550, 300), LOREM)
    # page 2 : scan (une image qui couvre la page, pas de texte)
    p2 = doc.new_page()
    p2.insert_image(p2.rect, stream=img, keep_proportion=False)  # un vrai scan couvre toute la page
    # page 3 : texte + tableau en image
    p3 = doc.new_page()
    p3.insert_textbox(pymupdf.Rect(50, 50, 550, 200), LOREM)
    p3.insert_image(pymupdf.Rect(50, 300, 450, 500), stream=img)
    # page 4 : vide
    doc.new_page()
    path = tmp_path / "loi_test.pdf"
    doc.save(path)
    doc.close()
    return path


def test_classify_rules() -> None:
    assert classify(500, 0, 0.0) == "texte"
    assert classify(26, 0, 0.0) == "texte"  # texte court, sans image
    assert classify(0, 0, 0.0) == "vide"
    assert classify(500, 1, 0.2) == "mixte"
    assert classify(0, 1, 0.95) == "image"  # scan pleine page
    assert classify(26, 1, 0.07) == "mixte"  # titre court + petit tableau en image


def test_short_title_above_table_image_is_mixte(tmp_path: Path) -> None:
    """Cas trouvé en testant essai.py : un titre de 26 caractères + un petit tableau en image."""
    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text((72, 80), "Grille des salaires n. 2 :", fontsize=12)
    page.insert_image(pymupdf.Rect(72, 100, 372, 210), stream=_png_bytes())
    path = tmp_path / "titre_court.pdf"
    doc.save(path)
    doc.close()
    assert inventory(path)[0].kind == "mixte"


def test_inventory_detects_each_page_kind(sample_pdf: Path) -> None:
    kinds = [p.kind for p in inventory(sample_pdf)]
    assert kinds == ["texte", "image", "mixte", "vide"]


def test_inventory_keeps_image_position(sample_pdf: Path) -> None:
    page3 = inventory(sample_pdf)[2]
    assert page3.images[0].bbox == (50.0, 300.0, 450.0, 500.0)


def test_export_only_what_needs_ocr(sample_pdf: Path, tmp_path: Path) -> None:
    out = tmp_path / "images"
    exported = export_images(sample_pdf, out, dpi=72)
    assert [(e.page, e.whole_page) for e in exported] == [(2, True), (3, False)]
    for e in exported:
        assert Path(e.path).is_file()


def test_export_resolution(sample_pdf: Path, tmp_path: Path) -> None:
    exported = export_images(sample_pdf, tmp_path / "hd", dpi=300)
    zone = exported[1]  # image de 400 x 200 points sur la page 3
    pix = pymupdf.Pixmap(zone.path)
    assert pix.width == pytest.approx(400 * 300 / 72, abs=2)
