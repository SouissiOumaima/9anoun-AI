"""Tests de l'inventaire couche texte (PDF générés en mémoire, jamais data/raw/).
Lancer depuis la racine du dépôt : pytest src/track_b_accounting/tests/test_inventory.py
"""

import sys
from pathlib import Path

import pymupdf

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from inventory_pdf_text_layer import analyse_text, inventory_pdf, render_markdown  # noqa: E402

LONG_TEXT = "Salaire de base categorie 5 : 459.264 TND, prime 81.435 TND, conge 2.208 TND par heure."


def _make_pdf(tmp_path: Path) -> Path:
    doc = pymupdf.open()
    doc.new_page().insert_text((72, 72), "Couverture")  # p1 : < 50 car.
    doc.new_page().insert_text((72, 72), LONG_TEXT)  # p2 : texte
    page = doc.new_page()  # p3 : image seule
    pix = pymupdf.Pixmap(pymupdf.csRGB, pymupdf.IRect(0, 0, 20, 20), False)
    pix.clear_with(200)
    page.insert_image(pymupdf.Rect(72, 72, 300, 300), pixmap=pix)
    doc.new_page()  # p4 : vide
    path = tmp_path / "mini.pdf"
    doc.save(path)
    return path


def test_seuil_texte():
    assert analyse_text("x" * 50)["statut"] == "scan"
    assert analyse_text("x" * 51)["statut"] == "texte"
    assert analyse_text("   \n" + "x" * 50 + "\n  ")["statut"] == "scan"


def test_encodage():
    assert analyse_text("الأجر الأدنى المضمون")["encodage"] == "unicode"
    assert analyse_text("  30")["encodage"] == "pua"
    assert analyse_text("Salaire 459.264")["encodage"] == "sans_arabe"


def test_montants():
    assert analyse_text("459.264 et 49,500 mais pas 30 ni 2.5")["n_montants"] == 2


def test_mots_cles_formes_de_presentation():
    # "جدول" écrit en formes de présentation (ﺟﺪﻭﻝ) doit être retrouvé après NFKC.
    assert analyse_text("ﺟﺪﻭﻝ")["mots_cles"] == ["جدول"]
    assert analyse_text("منحة النقل و جدول الأجور")["mots_cles"] == ["جدول", "الأجور", "منحة"]


def test_inventory_pdf(tmp_path):
    r = inventory_pdf(_make_pdf(tmp_path))
    assert r["nb_pages"] == 4
    assert [p["statut"] for p in r["pages"]] == ["scan", "texte", "scan", "scan"]
    assert r["nb_pages_texte"] == 1 and r["nb_pages_scan"] == 3
    assert r["pages_scan_hors_couverture"] == [3, 4]
    assert r["pages_montants"] == [2]


def test_render_markdown_classement(tmp_path):
    r = inventory_pdf(_make_pdf(tmp_path))
    md = render_markdown([r])
    assert "| mini.pdf | 4 | 1 | 3 | 1, 3, 4 |" in md
    assert "| 1 | mini.pdf | 3, 4 | 2 |" in md
