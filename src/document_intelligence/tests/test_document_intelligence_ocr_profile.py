"""Tests de `scripts/evaluer_donnees_reelles.py` (options --profile et --max-pages) sur des PDF FICTIFS.

Faux moteur d'OCR : aucun modèle n'est chargé. On vérifie surtout qu'aucun texte lu n'est affiché.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType

import pymupdf
import pytest

from src.document_intelligence.reading.ocr import Image3, OcrBox, OcrLang

SCRIPT = Path(__file__).resolve().parents[3] / "scripts" / "evaluer_donnees_reelles.py"
SECRET = "Salaire SECRET 999.999"


def _load_script() -> ModuleType:
    spec = importlib.util.spec_from_file_location("evaluer_donnees_reelles", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module  # nécessaire aux dataclasses du script
    spec.loader.exec_module(module)
    return module


class LatinEngine:
    """Lit toujours le même texte latin : le mode « auto » fait donc deux passes (ar puis fr)."""

    name = "fake"

    def recognize(self, image: Image3, lang: OcrLang) -> list[OcrBox]:
        return [OcrBox(SECRET, 0.9 if lang == "fr" else 0.8, (0, 0, image.shape[1] / 2, 30))]


def _png() -> bytes:
    pix = pymupdf.Pixmap(pymupdf.csRGB, pymupdf.IRect(0, 0, 600, 220), False)
    pix.clear_with(230)
    return bytes(pix.tobytes("png"))


@pytest.fixture()
def pdf_dir(tmp_path: Path) -> Path:
    """Un PDF fictif de 3 pages, une image (donc une zone en attente) par page."""
    folder = tmp_path / "pdfs"
    folder.mkdir()
    doc = pymupdf.open()
    for _ in range(3):
        doc.new_page().insert_image(pymupdf.Rect(72, 100, 372, 210), stream=_png())
    doc.save(folder / "fictif.pdf")
    doc.close()
    return folder


def test_profile_counts_zones_calls_and_pixels_with_max_pages(pdf_dir: Path, tmp_path: Path,
                                                               capsys: pytest.CaptureFixture[str]) -> None:
    script = _load_script()
    profile = script.Profile()
    totals = script.evaluate(pdf_dir, tmp_path / "out", None, max_pages=2, profile=profile, engine=LatinEngine())

    assert totals.pages == 2 and totals.zones_a_lire == 2 and totals.lignes_ocr == 2
    summary = profile.summary()
    assert summary["zones"] == 2
    assert (summary["appels_ocr_ar"], summary["appels_ocr_fr"], summary["zones_lues_deux_fois"]) == (2, 2, 2)
    assert summary["boites_total"] == 4  # 2 zones x 2 passes x 1 boîte
    assert summary["plus_grande_image_px"] == "1250x458" or summary["plus_grande_image_px"].startswith("1250x45")
    assert all(z.rendu_s >= 0 and z.ocr_s >= 0 for z in profile.zones)

    script.print_profile(profile)
    printed = capsys.readouterr().out
    assert "SECRET" not in printed and "fictif" not in printed  # ni texte lu, ni nom de fichier


def test_render_probe_is_removed_after_evaluation(pdf_dir: Path, tmp_path: Path) -> None:
    script = _load_script()
    from src.document_intelligence.reading import ocr

    original = ocr.render_zone
    script.evaluate(pdf_dir, tmp_path / "out", None, profile=script.Profile(), engine=LatinEngine())
    assert ocr.render_zone is original


def test_main_rejects_bad_max_pages_and_writes_no_text(pdf_dir: Path, tmp_path: Path,
                                                        capsys: pytest.CaptureFixture[str]) -> None:
    script = _load_script()
    assert script.main([str(pdf_dir), "--out", str(tmp_path / "o"), "--max-pages", "0"]) == 2
    out = tmp_path / "out"
    totals = script.evaluate(pdf_dir, out, 1, max_pages=1, engine=LatinEngine())
    assert totals.pages == 1
    summary = json.dumps(totals.summary())
    assert "SECRET" not in summary and "SECRET" not in capsys.readouterr().out
