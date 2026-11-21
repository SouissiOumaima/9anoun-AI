"""Tests de l'OCR (partie A) sur des documents FICTIFS générés dans les tests.

- tests unitaires avec un faux moteur : logique des zones, bbox, numérotation, ordre RTL ;
- tests d'intégration avec PaddleOCR (ignorés si paddleocr n'est pas installé).
"""

from __future__ import annotations

import importlib.util
import subprocess
import sys
from collections.abc import Iterator
from pathlib import Path

import numpy as np
import pymupdf
import pytest
from PIL import Image

from src.document_intelligence.intermediate import IntermediateDocument
from src.document_intelligence.reading.ocr import (
    DET_MODEL,
    READER_SUFFIX,
    Image3,
    OcrBox,
    OcrLang,
    PaddleEngine,
    clean_boxes,
    group_rows,
    ocr_pending_zones,
    read_image,
    read_zone_boxes,
    to_pdf_bbox,
)
from src.document_intelligence.reading.pdf_natif import read_pdf


class FakeEngine:
    """Renvoie des boîtes préparées, une liste par appel, et garde la trace des appels."""

    name = "fake"

    def __init__(self, answers: list[list[OcrBox]]) -> None:
        self._answers: Iterator[list[OcrBox]] = iter(answers)
        self.calls: list[tuple[tuple[int, ...], OcrLang]] = []

    def recognize(self, image: Image3, lang: OcrLang) -> list[OcrBox]:
        self.calls.append((image.shape, lang))
        return next(self._answers, [])


def _png_bytes(width: int = 600, height: int = 220) -> bytes:
    """Image grise ; même rapport largeur/hauteur que le cadre 300 x 110 (insert_image garde le rapport)."""
    pix = pymupdf.Pixmap(pymupdf.csRGB, pymupdf.IRect(0, 0, width, height), False)
    pix.clear_with(230)
    return bytes(pix.tobytes("png"))


@pytest.fixture()
def mixed_pdf(tmp_path: Path) -> Path:
    """Page 1 : 2 lignes natives + 2 images (zones p1_z1 et p1_z2)."""
    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text((72, 60), "Fiche de paie fictive", fontsize=12)
    page.insert_text((72, 80), "Mois : mars 2026", fontsize=12)
    page.insert_image(pymupdf.Rect(72, 100, 372, 210), stream=_png_bytes())
    page.insert_image(pymupdf.Rect(72, 300, 372, 410), stream=_png_bytes())
    path = tmp_path / "fiche.pdf"
    doc.save(path)
    doc.close()
    return path


def test_to_pdf_bbox_converts_pixels_to_points() -> None:
    assert to_pdf_bbox((72.0, 100.0, 372.0, 210.0), (0.0, 0.0, 300.0, 60.0), 300) == (72.0, 100.0, 144.0, 114.4)


def test_zones_are_read_numbering_continues_and_input_is_unchanged(mixed_pdf: Path) -> None:
    doc = read_pdf(mixed_pdf)
    before = doc.model_dump_json()
    engine = FakeEngine(
        [
            [OcrBox("Salaire de base", 0.97, (0, 0, 600, 60)), OcrBox("424.100", 0.91, (900, 5, 1150, 60))],
            [OcrBox("Prime de transport 56.000", 0.88, (0, 100, 900, 160))],
        ]
    )
    out = ocr_pending_zones(doc, mixed_pdf, engine=engine, lang="fr")

    assert doc.model_dump_json() == before  # l'entrée n'est pas modifiée
    page = out.pages[0]
    assert [line.line_id for line in page.lines] == ["p1_l1", "p1_l2", "p1_l3", "p1_l4"]
    ocr = [line for line in page.lines if line.source == "ocr"]
    assert [line.text for line in ocr] == ["Salaire de base  424.100", "Prime de transport 56.000"]
    assert ocr[0].confidence == pytest.approx(0.91)  # minimum des morceaux de la ligne
    assert ocr[0].language == "fr"
    assert ocr[0].bbox == (72.0, 100.0, 348.0, 114.4)
    assert ocr[1].bbox[1] == pytest.approx(300 + 100 * 72 / 300, abs=0.1)
    assert page.pending_zones == []
    assert out.reader == f"{doc.reader}+{READER_SUFFIX}"
    assert any("2 zone(s) lue(s), 2 ligne(s)" in w for w in out.warnings)
    # rendu à 300 DPI : une zone de 300 x 110 points -> 1250 x 458 pixels (arrondi de MuPDF : ±1)
    height_px, width_px = engine.calls[0][0][:2]
    assert width_px == 1250 and abs(height_px - 458) <= 1
    assert len({line.line_id for line in page.lines}) == len(page.lines)


def test_empty_zone_stays_pending_with_warning(mixed_pdf: Path) -> None:
    doc = read_pdf(mixed_pdf)
    engine = FakeEngine([[], [OcrBox("Total 480.100", 0.95, (0, 0, 500, 50))]])
    out = ocr_pending_zones(doc, mixed_pdf, engine=engine, lang="fr")
    page = out.pages[0]
    assert [z.zone_id for z in page.pending_zones] == ["p1_z1"]
    assert [line.text for line in page.lines if line.source == "ocr"] == ["Total 480.100"]
    assert any("p1_z1" in w and "rien n'est deviné" in w for w in out.warnings)
    assert "[p1_z1] <zone image non lue" in out.full_text()


def test_whitespace_only_text_is_not_a_line(mixed_pdf: Path) -> None:
    out = ocr_pending_zones(read_pdf(mixed_pdf), mixed_pdf, engine=FakeEngine([[OcrBox("   ", 0.9, (0, 0, 9, 9))]]))
    assert all(line.source == "natif" for line in out.pages[0].lines)
    assert len(out.pages[0].pending_zones) == 2


def test_engine_failure_keeps_zone(mixed_pdf: Path) -> None:
    class Broken(FakeEngine):
        def recognize(self, image: Image3, lang: OcrLang) -> list[OcrBox]:
            raise RuntimeError("panne")

    out = ocr_pending_zones(read_pdf(mixed_pdf), mixed_pdf, engine=Broken([]), lang="fr")
    assert len(out.pages[0].pending_zones) == 2
    assert any("échec" in w for w in out.warnings)


def test_numbering_never_duplicates_existing_ids(mixed_pdf: Path) -> None:
    doc = read_pdf(mixed_pdf)
    page = doc.pages[0]
    page.lines[1] = page.lines[1].model_copy(update={"line_id": "p1_l7"})  # trou dans la numérotation
    out = ocr_pending_zones(doc, mixed_pdf, engine=FakeEngine([[OcrBox("x 1.000", 0.9, (0, 0, 50, 20))]]), lang="fr")
    assert [line.line_id for line in out.pages[0].lines] == ["p1_l1", "p1_l7", "p1_l8"]


def test_document_without_pending_zone_is_returned_unchanged(tmp_path: Path) -> None:
    doc = pymupdf.open()
    doc.new_page().insert_text((72, 72), "Texte natif seulement", fontsize=12)
    path = tmp_path / "natif.pdf"
    doc.save(path)
    natif = read_pdf(path)
    engine = FakeEngine([])
    out = ocr_pending_zones(natif, path, engine=engine)
    assert out == natif and engine.calls == []


def test_arabic_row_is_read_right_to_left() -> None:
    boxes = [
        OcrBox("424.100", 1.0, (42, 350, 387, 436)),
        OcrBox("الأجر", 0.99, (667, 337, 896, 459)),
        OcrBox("الأساسي", 0.98, (387, 325, 725, 472)),
    ]
    rows = group_rows(boxes)
    assert [r.text for r in rows] == ["الأجر  الأساسي  424.100"]
    assert rows[0].confidence == pytest.approx(0.98)


def test_french_rows_are_read_left_to_right_top_to_bottom() -> None:
    boxes = [
        OcrBox("Ligne 2", 0.9, (0, 100, 100, 130)),
        OcrBox("424.100", 0.9, (300, 0, 400, 30)),
        OcrBox("Salaire", 0.9, (0, 0, 100, 30)),
    ]
    assert [r.text for r in group_rows(boxes)] == ["Salaire  424.100", "Ligne 2"]


def test_fragments_inside_a_word_are_removed() -> None:
    # La hamza « ء » détectée seule au-dessus d'un mot déjà lu (vu sur PP-OCRv5) : doublon ignoré.
    boxes = [OcrBox("الأجر", 0.99, (667, 337, 896, 459)), OcrBox("ء", 0.33, (799, 351, 821, 373))]
    assert [b.text for b in clean_boxes(boxes)] == ["الأجر"]


def test_auto_mode_rereads_latin_text_with_french_model(mixed_pdf: Path) -> None:
    doc = read_pdf(mixed_pdf)
    engine = FakeEngine(
        [
            [OcrBox("Indemnite", 0.80, (0, 0, 300, 50))],  # zone 1, passe arabe : texte latin, sans accent
            [OcrBox("Indemnité", 0.97, (0, 0, 300, 50))],  # zone 1, passe latine, plus sûre : gardée → document « fr »
            [OcrBox("Alsnf", 0.41, (0, 0, 300, 50))],  # zone 2 lue d'abord en latin : charabia peu sûr
            [OcrBox("الصنف", 0.9, (0, 0, 300, 50))],  # zone 2 relue en arabe : l'autre langue gagne
        ]
    )
    out = ocr_pending_zones(doc, mixed_pdf, engine=engine, lang="auto")
    assert [lang for _, lang in engine.calls] == ["ar", "fr", "fr", "ar"]
    ocr = [line for line in out.pages[0].lines if line.source == "ocr"]
    assert [(line.text, line.language) for line in ocr] == [("Indemnité", "fr"), ("الصنف", "ar")]
    assert any("langue retenue pour le document : fr" in w for w in out.warnings)


# ------------------------------------------------------------ langue retenue une fois par document


class ZoneLanguageEngine:
    """Faux moteur qui connaît la vraie langue de chaque zone (reconnue à la hauteur de l'image) et répond
    comme les vrais modèles mesurés : le modèle arabe lit aussi le latin (sans accents) ; le modèle latin écrit
    du charabia sur une zone arabe, avec une confiance réglable."""

    name = "fake-langues"

    def __init__(self, zones: dict[int, str], junk: tuple[str, float] = ("Alsnf", 0.45)) -> None:
        self.zones = zones  # hauteur en points du cadre de la zone -> "fr", "ar" ou "vide"
        self.junk = junk
        self.calls: list[tuple[str, OcrLang]] = []

    def recognize(self, image: Image3, lang: OcrLang) -> list[OcrBox]:
        height_pt = round(image.shape[0] * 72 / 300)
        truth = self.zones[min(self.zones, key=lambda h: abs(h - height_pt))]
        self.calls.append((truth, lang))
        box = (0.0, 0.0, 300.0, 40.0)
        if truth == "vide":
            return []
        if truth == "fr":
            return [OcrBox("Échelon 5", 0.99, box)] if lang == "fr" else [OcrBox("Echelon 5", 0.90, box)]
        return [OcrBox("الدرجة 5", 0.92, box)] if lang == "ar" else [OcrBox(self.junk[0], self.junk[1], box)]


def _zones_pdf(tmp_path: Path, heights: list[int]) -> Path:
    """Une page FICTIVE avec une image par zone, de hauteurs différentes (pour que le faux moteur les reconnaisse)."""
    doc = pymupdf.open()
    page = doc.new_page()
    y = 60
    for h in heights:
        pix = pymupdf.Pixmap(pymupdf.csRGB, pymupdf.IRect(0, 0, 1200, round(h * 300 / 72)), False)
        pix.clear_with(230)
        page.insert_image(pymupdf.Rect(72, y, 360, y + h), stream=bytes(pix.tobytes("png")))
        y += h + 40
    path = tmp_path / "zones.pdf"
    doc.save(path)
    doc.close()
    return path


def _ocr_texts(doc: IntermediateDocument) -> list[str]:
    return [line.text for page in doc.pages for line in page.lines if line.source == "ocr"]


def test_french_document_is_read_twice_only_on_its_first_zone(tmp_path: Path) -> None:
    path = _zones_pdf(tmp_path, [40, 60, 80])
    engine = ZoneLanguageEngine({40: "fr", 60: "fr", 80: "fr"})
    out = ocr_pending_zones(read_pdf(path), path, engine=engine)
    assert [lang for _, lang in engine.calls] == ["ar", "fr", "fr", "fr"]  # 4 lectures au lieu de 6
    assert _ocr_texts(out) == ["Échelon 5"] * 3


def test_arabic_document_keeps_one_reading_per_zone(tmp_path: Path) -> None:
    path = _zones_pdf(tmp_path, [40, 60, 80])
    engine = ZoneLanguageEngine({40: "ar", 60: "ar", 80: "ar"})
    out = ocr_pending_zones(read_pdf(path), path, engine=engine)
    assert [lang for _, lang in engine.calls] == ["ar", "ar", "ar"]
    assert _ocr_texts(out) == ["الدرجة 5"] * 3
    assert any("langue retenue pour le document : ar" in w for w in out.warnings)


@pytest.mark.parametrize(
    "junk",
    [("Alsnf", 0.45), ("$$ 12", 0.70), ("Aldrjt", 0.90)],  # le dernier : détecté « fr », confiance sous LATIN_SURE
)
def test_a_zone_of_the_other_language_is_reread_with_the_arabic_model(tmp_path: Path, junk: tuple[str, float]) -> None:
    path = _zones_pdf(tmp_path, [40, 60, 80])
    engine = ZoneLanguageEngine({40: "fr", 60: "ar", 80: "fr"}, junk=junk)
    out = ocr_pending_zones(read_pdf(path), path, engine=engine)
    assert [(truth, lang) for truth, lang in engine.calls] == [
        ("fr", "ar"), ("fr", "fr"),  # zone 1 : double lecture, document retenu « fr »
        ("ar", "fr"), ("ar", "ar"),  # zone 2 arabe : latin peu sûr → relue en arabe, l'arabe gagne
        ("fr", "fr"),  # zone 3 : une seule lecture
    ]
    assert _ocr_texts(out) == ["Échelon 5", "الدرجة 5", "Échelon 5"]  # aucun charabia gardé


def test_language_is_retained_on_the_first_zone_with_text(tmp_path: Path) -> None:
    path = _zones_pdf(tmp_path, [40, 60, 80])
    engine = ZoneLanguageEngine({40: "vide", 60: "fr", 80: "fr"})
    out = ocr_pending_zones(read_pdf(path), path, engine=engine)
    # zone vide : arabe seulement (rien de latin à relire), puis la langue est retenue sur la zone 2
    assert [(truth, lang) for truth, lang in engine.calls] == [("vide", "ar"), ("fr", "ar"), ("fr", "fr"), ("fr", "fr")]
    assert [z.zone_id for z in out.pages[0].pending_zones] == ["p1_z1"]  # zone vide gardée : rien n'est deviné


def test_explicit_language_is_never_switched(tmp_path: Path) -> None:
    path = _zones_pdf(tmp_path, [40, 60])
    engine = ZoneLanguageEngine({40: "fr", 60: "ar"})
    out = ocr_pending_zones(read_pdf(path), path, engine=engine, lang="fr")
    assert [lang for _, lang in engine.calls] == ["fr", "fr"]
    assert not any("langue retenue" in w for w in out.warnings)


def test_read_zone_boxes_keeps_its_former_behaviour() -> None:
    engine = FakeEngine([[OcrBox("Indemnite", 0.80, (0, 0, 9, 9))], [OcrBox("Indemnité", 0.97, (0, 0, 9, 9))]])
    image: Image3 = np.zeros((20, 40, 3), dtype=np.uint8)
    assert [b.text for b in read_zone_boxes(engine, image, "auto")] == ["Indemnité"]
    assert [lang for _, lang in engine.calls] == ["ar", "fr"]


def test_read_image_uses_dpi_for_points(tmp_path: Path) -> None:
    path = tmp_path / "scan.png"
    Image.fromarray(np.full((300, 600, 3), 255, dtype=np.uint8)).save(path, dpi=(150, 150))
    engine = FakeEngine([[OcrBox("Catégorie 3", 0.93, (150, 30, 450, 60))]])
    doc = read_image(path, engine=engine, lang="fr")
    page = doc.pages[0]
    assert (page.width, page.height, page.kind) == (288.0, 144.0, "image")
    assert page.lines[0].line_id == "p1_l1"
    assert page.lines[0].bbox == (72.0, 14.4, 216.0, 28.8)
    assert page.pending_zones == []
    assert doc.page_count == 1 and doc.reader.startswith("ocr_image")
    assert IntermediateDocument.model_validate_json(doc.model_dump_json()) == doc


def test_read_image_empty_keeps_zone(tmp_path: Path) -> None:
    path = tmp_path / "blanc.jpg"
    Image.fromarray(np.full((100, 100, 3), 255, dtype=np.uint8)).save(path)
    doc = read_image(path, engine=FakeEngine([[]]), lang="ar")
    assert doc.pages[0].lines == [] and len(doc.pages[0].pending_zones) == 1
    assert doc.pages[0].width == pytest.approx(24.0)  # 100 px à 300 DPI par défaut


def test_read_image_rejects_other_extensions(tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        read_image(tmp_path / "doc.tiff", engine=FakeEngine([]))


# ------------------------------------------------------------ intégration PaddleOCR (modèles réels)

HAS_PADDLE = importlib.util.find_spec("paddleocr") is not None


def _cer(ref: str, hyp: str) -> float:
    prev = list(range(len(hyp) + 1))
    for i, a in enumerate(ref, 1):
        cur = [i]
        for j, b in enumerate(hyp, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (a != b)))
        prev = cur
    return prev[-1] / max(1, len(ref))


def _rendered_line_png(html: str) -> bytes:
    """Image d'une ligne de texte (rendu HTML de pymupdf, qui met en forme l'arabe)."""
    doc = pymupdf.open()
    page = doc.new_page(width=400, height=60)
    page.insert_htmlbox(pymupdf.Rect(10, 10, 390, 50), html)
    png = bytes(page.get_pixmap(dpi=300).tobytes("png"))
    doc.close()
    return png


@pytest.mark.skipif(not HAS_PADDLE, reason="paddleocr non installé (pip install -r requirements-ocr.txt)")
def test_paddle_reads_fictive_scanned_payslip(tmp_path: Path) -> None:
    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text((72, 60), "Bulletin fictif", fontsize=12)
    fr = "<p style='font-size:20px;font-family:sans-serif'>Salaire de base 424.100</p>"
    ar = "<p style='font-size:22px'>الأجر الأساسي</p>"
    page.insert_image(pymupdf.Rect(72, 100, 472, 160), stream=_rendered_line_png(fr))
    page.insert_image(pymupdf.Rect(72, 200, 472, 260), stream=_rendered_line_png(ar))
    path = tmp_path / "scan.pdf"
    doc.save(path)
    doc.close()

    out = ocr_pending_zones(read_pdf(path), path)
    ocr = [line for line in out.pages[0].lines if line.source == "ocr"]
    assert len(ocr) == 2, out.warnings
    assert _cer("Salaire de base 424.100", ocr[0].text) <= 0.1
    assert ocr[0].language == "fr" and "424.100" in ocr[0].text
    assert _cer("الأجر الأساسي", ocr[1].text.replace("  ", " ")) <= 0.2
    assert ocr[1].language == "ar"
    assert all(0.0 < line.confidence <= 1.0 for line in ocr)
    assert 72 <= ocr[0].bbox[0] < ocr[0].bbox[2] <= 472 and 100 <= ocr[0].bbox[1] < ocr[0].bbox[3] <= 160
    assert out.pages[0].pending_zones == []
    assert [line.line_id for line in out.pages[0].lines] == ["p1_l1", "p1_l2", "p1_l3"]


_AR_WORDS = ["الأجر الأساسي", "منحة النقل", "منحة الحضور", "الضمان الاجتماعي", "الضريبة على الدخل",
             "الصنف", "الدرجة", "الأقدمية", "الساعات الإضافية", "صافي الأجر"]

_A4_SCRIPT = """
import sys
from pathlib import Path
from src.document_intelligence.reading.ocr import ocr_pending_zones
from src.document_intelligence.reading.pdf_natif import read_pdf
path = Path(sys.argv[1])
out = ocr_pending_zones(read_pdf(path), path)
page = out.pages[0]
print(sum(1 for line in page.lines if line.source == "ocr"), len(page.pending_zones))
"""


def _dense_arabic_a4_scan(path: Path) -> None:
    """Scan FICTIF : une page A4 entière (image 300 DPI) d'arabe dense, de montants, de dates et un tableau."""
    rng = np.random.default_rng(7)
    paras = [
        f"<p>{i + 1}. {' '.join(_AR_WORDS[(i + k) % 10] for k in range(6))} : "
        f"{rng.integers(100, 9999)}.{rng.integers(0, 999):03d} د بتاريخ "
        f"{rng.integers(1, 28):02d}/{rng.integers(1, 12):02d}/20{rng.integers(10, 25)}</p>"
        for i in range(14)
    ]
    rows = "".join(
        f"<tr><td>{w}</td><td>{rng.integers(1, 30)}</td><td>{rng.integers(100, 5000)}.{rng.integers(0, 999):03d}</td></tr>"
        for w in _AR_WORDS
    )
    html = ('<div dir="rtl" style="font-family: sans-serif; font-size: 11pt;"><h2>كشف الأجر الشهري</h2>'
            + "".join(paras[:7]) + '<table border="1" style="width: 100%;">' + rows + "</table>"
            + "".join(paras[7:]) + "</div>")
    src = pymupdf.open()
    src.new_page(width=595, height=842).insert_htmlbox(pymupdf.Rect(36, 36, 559, 806), html)
    png = src[0].get_pixmap(dpi=300).tobytes("png")
    src.close()
    doc = pymupdf.open()
    doc.new_page(width=595, height=842).insert_image(pymupdf.Rect(0, 0, 595, 842), stream=png)
    doc.save(path)
    doc.close()


@pytest.mark.skipif(not HAS_PADDLE, reason="paddleocr non installé (pip install -r requirements-ocr.txt)")
def test_paddle_full_a4_page_at_300_dpi_does_not_crash(tmp_path: Path) -> None:
    """Cas des vraies pages : PP-OCRv5_server_det plantait (access violation) sur une page A4 entière à 300 DPI.

    Lancé dans un sous-processus : un plantage natif tuerait sinon toute la session pytest.
    """
    path = tmp_path / "a4.pdf"
    _dense_arabic_a4_scan(path)
    repo = Path(__file__).resolve().parents[3]
    proc = subprocess.run([sys.executable, "-X", "faulthandler", "-c", _A4_SCRIPT, str(path)],
                          cwd=repo, capture_output=True, text=True, encoding="utf-8", errors="replace",
                          timeout=600, check=False)
    assert proc.returncode == 0, proc.stderr[-2000:]
    n_lines, n_pending = (int(v) for v in proc.stdout.strip().splitlines()[-1].split())
    assert n_lines >= 20 and n_pending == 0


def test_default_detector_is_mobile() -> None:
    assert PaddleEngine().det_model == DET_MODEL == "PP-OCRv5_mobile_det"
