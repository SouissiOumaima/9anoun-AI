"""OCR branché dans la chaîne DS3 et dans le service live (D41), avec un faux moteur d'OCR et un faux Gemini.

Aucun modèle chargé, aucun appel réseau : les tests passent avec ou sans requirements-ocr.txt.
"""

from __future__ import annotations

import copy
import sys
from pathlib import Path
from typing import Any

import pymupdf
import pytest

from src.document_intelligence.contract.v2.generate_examples import (
    REQUESTS,
)
from src.document_intelligence.contract.v2.models import DS3Response
from src.document_intelligence.evaluation.fictive_documents import (
    DOCS_DIR,
)
from src.document_intelligence.evaluation.run_gemini_eval import (
    request_for,
    score_case,
)
from src.document_intelligence.extraction import pipeline
from src.document_intelligence.extraction.assemble import (
    PAYSLIP_FIELDS,
    GeminiPayslipAnswer,
)
from src.document_intelligence.extraction.pipeline import (
    analyze_payslip_pdf,
    read_document,
)
from src.document_intelligence.extraction.verify import RawField
from src.document_intelligence.reading.ocr import Image3, OcrBox, OcrLang
from src.document_intelligence.reading.pdf_natif import ROW_SEPARATOR
from src.document_intelligence.service import handle_request
from src.document_intelligence.tests.test_document_intelligence_gemini import (
    FakeClient,
    _output_json,
)
from src.document_intelligence.tests.test_document_intelligence_golden import (
    CASES,
    _perfect_gemini,
)

SCAN = CASES["DS3-03"]  # fiche arabe scannée : une seule zone image, aucune ligne native
NATIVE = CASES["DS3-01"]

# Ce qu'un OCR lirait sur la fiche scannée DS3-03 (une boîte par ligne).
SCAN_LINES = [
    f"الاسم : سامي بن عمر{ROW_SEPARATOR}الفترة : ماي 2026",
    "تاريخ الانتداب : 01/03/2021",
    "الصنف : 1 ب - الدرجة : 3",
    "الخطة : عون تنفيذ - قار",
    "التأجير : شهري - 173,33 س",
    f"الأجر الأساسي{ROW_SEPARATOR}398,250",
    f"منحة النقل{ROW_SEPARATOR}56,000",
    f"الأجر الخام{ROW_SEPARATOR}454,250",
    f"الضمان الاجتماعي{ROW_SEPARATOR}41,700",
]
OCR_CONFIDENCE = 0.87  # sous le seuil 0,90 de DS1 : ces champs passeront « à confirmer » (D39)


class FakeEngine:
    """Faux moteur d'OCR : renvoie les mêmes boîtes à chaque appel et garde la trace des appels."""

    name = "fake"

    def __init__(self, lines: list[str] | None = None, error: Exception | None = None) -> None:
        self.lines = lines or []
        self.error = error
        self.calls: list[OcrLang] = []

    def recognize(self, image: Image3, lang: OcrLang) -> list[OcrBox]:
        self.calls.append(lang)
        if self.error:
            raise self.error
        return [OcrBox(text, OCR_CONFIDENCE, (20.0, 40.0 + 60 * i, 900.0, 80.0 + 60 * i))
                for i, text in enumerate(self.lines)]


def _scan_client(path: Path) -> FakeClient:
    """Faux Gemini « parfait » pour DS3-03, construit sur les lignes que l'OCR a produites."""
    doc = read_document(path, SCAN["doc_id"], FakeEngine(SCAN_LINES))
    return FakeClient(_output_json(_perfect_gemini(SCAN, doc)))


# ------------------------------------------------------------ chaîne (pipeline)


def test_scanned_payslip_is_read_by_ocr_and_cited() -> None:
    path = DOCS_DIR / SCAN["requete"]["file_name"]
    engine = FakeEngine(SCAN_LINES)
    resp = analyze_payslip_pdf(path, request_for(SCAN), client=_scan_client(path), ocr_engine=engine)
    DS3Response.model_validate(resp)

    assert engine.calls == ["ar"]  # une seule zone, lue une fois (texte arabe : pas de seconde passe)
    assert resp["status"] == "ok"
    assert score_case(SCAN, resp).count() == {"correct": len(PAYSLIP_FIELDS)}
    base = resp["result"]["fields"]["base_salary"]
    assert base["confidence"] == OCR_CONFIDENCE  # la vraie confiance de l'OCR, sans seuil (D39)
    excerpts = {c["excerpt"] for c in resp["citations"]}
    assert any("398,250" in e for e in excerpts)


def test_native_pdf_never_calls_the_ocr() -> None:
    engine = FakeEngine(SCAN_LINES)
    doc = read_document(DOCS_DIR / NATIVE["requete"]["file_name"], NATIVE["doc_id"], engine)
    assert engine.calls == []  # aucun temps d'OCR sur un PDF entièrement natif
    assert all(line.source == "natif" for page in doc.pages for line in page.lines)


def test_ocr_failure_keeps_silence_and_never_raises() -> None:
    path = DOCS_DIR / SCAN["requete"]["file_name"]
    client = FakeClient("{}")
    resp = analyze_payslip_pdf(path, request_for(SCAN), client=client,
                               ocr_engine=FakeEngine(error=RuntimeError("plantage")))
    assert resp["status"] == "refus" and resp["refus"]["code"] == "SOURCE_MANQUANTE"
    assert client.calls == []  # rien de lisible : Gemini n'est pas appelé
    assert any("échec" in w for w in resp["warnings"])


def test_without_ocr_a_pdf_behaves_as_before() -> None:
    path = DOCS_DIR / SCAN["requete"]["file_name"]
    resp = analyze_payslip_pdf(path, request_for(SCAN), client=FakeClient("{}"))
    assert resp["status"] == "refus" and resp["refus"]["code"] == "SOURCE_MANQUANTE"
    assert pipeline.OCR_UNAVAILABLE_WARNING in resp["warnings"]


def test_installed_paddle_is_not_run_in_process_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    """PaddleOCR installé mais DS3_OCR_INPROCESS absent : pas d'OCR dans le processus du service."""
    monkeypatch.setattr(pipeline, "paddle_installed", lambda: True)
    used = FakeEngine(SCAN_LINES)
    monkeypatch.setattr("src.document_intelligence.reading.ocr.default_engine", lambda: used)
    doc = read_document(DOCS_DIR / SCAN["requete"]["file_name"], SCAN["doc_id"])
    assert used.calls == []
    assert pipeline.OCR_UNAVAILABLE_WARNING in doc.warnings


def test_in_process_ocr_is_used_only_when_enabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(pipeline, "paddle_installed", lambda: True)
    monkeypatch.setenv(pipeline.INPROCESS_ENV, "1")
    used = FakeEngine(SCAN_LINES)
    monkeypatch.setattr("src.document_intelligence.reading.ocr.default_engine", lambda: used)
    doc = read_document(DOCS_DIR / SCAN["requete"]["file_name"], SCAN["doc_id"])
    assert used.calls == ["ar"]
    assert any(line.source == "ocr" for page in doc.pages for line in page.lines)


def test_missing_numpy_or_pillow_keeps_the_pdf_readable(monkeypatch: pytest.MonkeyPatch) -> None:
    """Le module OCR ne s'importe pas (numpy / Pillow absents) : le PDF est lu comme sans OCR."""
    monkeypatch.setitem(sys.modules, "src.document_intelligence.reading.ocr", None)  # import -> ImportError
    doc = read_document(DOCS_DIR / SCAN["requete"]["file_name"], SCAN["doc_id"], FakeEngine(SCAN_LINES))
    assert pipeline.OCR_UNAVAILABLE_WARNING in doc.warnings
    assert all(page.pending_zones for page in doc.pages)


def test_image_where_ocr_reads_nothing_gives_source_manquante(tmp_path: Path) -> None:
    png = tmp_path / "paie.png"
    png.write_bytes(_png_bytes())
    client = FakeClient("{}")
    resp = analyze_payslip_pdf(png, request_for(SCAN), client=client, ocr_engine=FakeEngine([]))
    assert resp["status"] == "refus" and resp["refus"]["code"] == "SOURCE_MANQUANTE"
    assert client.calls == []


def test_mixed_pdf_cites_native_and_ocr_lines(tmp_path: Path) -> None:
    """Une ligne native et une zone image lue par l'OCR : les deux sont citées, chacune avec sa confiance."""
    pdf = tmp_path / "mixte.pdf"
    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text((72, 100), "Salaire de base 424,100", fontsize=11)
    pix = pymupdf.Pixmap(pymupdf.csRGB, pymupdf.IRect(0, 0, 600, 220), False)
    pix.clear_with(230)
    page.insert_image(pymupdf.Rect(72, 300, 372, 410), stream=pix.tobytes("png"))
    doc.save(pdf)
    doc.close()

    read = read_document(pdf, "doc_mixte", FakeEngine(["Catégorie : 3"]))
    native = next(line for p in read.pages for line in p.lines if line.source == "natif")
    ocr_line = next(line for p in read.pages for line in p.lines if line.source == "ocr")
    answer = GeminiPayslipAnswer(document_type="fiche_de_paie", fields={
        "base_salary": RawField(raw="424,100", line_id=native.line_id),
        "category": RawField(raw="3", line_id=ocr_line.line_id),
    })
    resp = analyze_payslip_pdf(pdf, request_for(NATIVE), client=FakeClient(_output_json(answer)),
                               ocr_engine=FakeEngine(["Catégorie : 3"]))
    DS3Response.model_validate(resp)
    fields = resp["result"]["fields"]
    assert (fields["base_salary"]["value"], fields["base_salary"]["confidence"]) == ("424.100", 1.0)
    assert (fields["category"]["value"], fields["category"]["confidence"]) == ("3", OCR_CONFIDENCE)
    excerpts = " | ".join(c["excerpt"] for c in resp["citations"])
    assert "424,100" in excerpts and "Catégorie" in excerpts


def test_image_without_ocr_is_refused_by_the_pipeline(tmp_path: Path) -> None:
    png = tmp_path / "paie.png"
    png.write_bytes(_png_bytes())
    resp = analyze_payslip_pdf(png, request_for(SCAN), client=FakeClient("{}"))
    assert resp["status"] == "refus" and resp["ds3_code"] == "UNSUPPORTED_FORMAT"
    assert resp["refus"]["message_fr"] == pipeline.OCR_IMAGE_FR


# ------------------------------------------------------------ service live


def _png_bytes() -> bytes:
    pix = pymupdf.Pixmap(pymupdf.csRGB, pymupdf.IRect(0, 0, 900, 700), False)
    pix.clear_with(240)
    return bytes(pix.tobytes("png"))


def _image_request(file_name: str) -> dict[str, Any]:
    req = copy.deepcopy(REQUESTS["01_ok_fiche_paie"])
    req["lang"] = "ar"
    req["document"].update({"file_name": file_name, "mime_type": "image/png",
                            "storage_ref": f"local://demo/{file_name}"})
    return req


@pytest.fixture
def storage(tmp_path: Path) -> Path:
    (tmp_path / "demo").mkdir()
    (tmp_path / "demo" / "paie.png").write_bytes(_png_bytes())
    (tmp_path / "demo" / "casse.png").write_bytes(b"ceci n'est pas une image")
    return tmp_path


def test_service_reads_an_image_with_the_given_engine(storage: Path) -> None:
    engine = FakeEngine(SCAN_LINES)
    resp = handle_request(_image_request("paie.png"), storage_root_dir=storage,
                          client=_scan_client(storage / "demo" / "paie.png"), ocr_engine=engine)
    DS3Response.model_validate(resp)
    assert resp["status"] == "ok" and resp["mode"] == "live"
    assert engine.calls  # le moteur passé au service a bien été transmis au pipeline
    assert resp["result"]["fields"]["base_salary"]["value"] == "398.250"


def test_service_refuses_an_image_when_ocr_is_not_installed(storage: Path) -> None:
    client = FakeClient("{}")
    resp = handle_request(_image_request("absente.png"), storage_root_dir=storage, client=client)
    DS3Response.model_validate(resp)
    assert resp["status"] == "refus" and resp["ds3_code"] == "UNSUPPORTED_FORMAT"
    assert resp["refus"]["code"] == "HORS_SCOPE" and "OCR" in resp["refus"]["message_fr"]
    assert resp["refus"]["message_ar"]
    assert client.calls == []  # décidé avant toute lecture : le fichier n'existe même pas


@pytest.mark.parametrize(("file_name", "ds3_code"), [("paie.tiff", "UNSUPPORTED_FORMAT"),
                                                     ("casse.png", "FILE_EMPTY_OR_CORRUPTED")])
def test_service_other_formats_and_broken_images(storage: Path, file_name: str, ds3_code: str) -> None:
    (storage / "demo" / "paie.tiff").write_bytes(b"II*\x00")
    resp = handle_request(_image_request(file_name), storage_root_dir=storage, client=FakeClient("{}"),
                          ocr_engine=FakeEngine(SCAN_LINES))
    DS3Response.model_validate(resp)
    assert resp["status"] == "refus" and resp["ds3_code"] == ds3_code
