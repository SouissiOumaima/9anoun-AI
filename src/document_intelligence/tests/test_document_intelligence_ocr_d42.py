"""D42 : lecture OCR en arrière-plan branchée dans la chaîne DS3 et dans le service live.

Scénarios vérifiés (section 5 de docs/PROPOSITION_INTEGRATION_OCR.md) : attente, nouvel essai, succès, échec,
indisponibilité, images, formats, transmission du backend, contrôles d'accès, et le vrai `OcrCache` de bout en bout
avec un faux processus OCR. Aucun modèle, aucun processus, aucun réseau : ce fichier n'importe pas `reading/ocr.py`,
il tourne avec ou sans requirements-ocr.txt.
"""

from __future__ import annotations

import copy
import sys
import types
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pymupdf
import pytest

from src.document_intelligence.contract.v2.generate_examples import REQUESTS
from src.document_intelligence.contract.v2.models import DS3Response
from src.document_intelligence.evaluation.fictive_documents import DOCS_DIR
from src.document_intelligence.evaluation.run_gemini_eval import request_for, score_case
from src.document_intelligence.extraction import pipeline
from src.document_intelligence.extraction.assemble import PAYSLIP_FIELDS, GeminiPayslipAnswer
from src.document_intelligence.extraction.pipeline import analyze_payslip_pdf
from src.document_intelligence.extraction.verify import RawField
from src.document_intelligence.intermediate import IntermediateDocument, TextLine
from src.document_intelligence.reading import ocr_cache
from src.document_intelligence.reading.ocr_cache import CacheAccessError, OcrCache, OcrState
from src.document_intelligence.reading.pdf_natif import ROW_SEPARATOR, read_pdf
from src.document_intelligence.service import handle_request
from src.document_intelligence.tests.test_document_intelligence_gemini import FakeClient, _output_json
from src.document_intelligence.tests.test_document_intelligence_golden import CASES, _perfect_gemini

SCAN = CASES["DS3-03"]  # fiche arabe scannée : une seule zone image, aucune ligne native
NATIVE = CASES["DS3-01"]
SCAN_PATH = DOCS_DIR / SCAN["requete"]["file_name"]

# Ce que l'OCR lirait sur la fiche scannée DS3-03 (mêmes lignes que test_document_intelligence_ocr_pipeline.py).
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
OCR_CONFIDENCE = 0.87  # sous le seuil 0,90 de DS1 : champs visibles mais non sélectionnables (D39)


def ocr_read(path: Path, document_id: str, lines: list[str] | None = None) -> IntermediateDocument:
    """Ce que le processus OCR mettrait en cache : lecture native, puis les zones en attente remplacées par des
    lignes OCR (une par texte), comme `reading/ocr.py`."""
    doc = read_pdf(path, document_id=document_id).model_copy(deep=True)
    page = doc.pages[0]
    for i, text in enumerate(SCAN_LINES if lines is None else lines):
        page.lines.append(TextLine(line_id=f"p1_o{i + 1}", page=1, text=text, bbox=(20.0, 40.0 + 20 * i, 500.0,
                                   55.0 + 20 * i), confidence=OCR_CONFIDENCE, source="ocr", language="ar"))
    for p in doc.pages:
        p.pending_zones = []
    doc.reader = f"{doc.reader}+ocr_paddle-0.1"
    return doc


class FakeBackend:
    """Faux backend OCR : renvoie les états donnés dans l'ordre (le dernier se répète), et garde les appels."""

    def __init__(self, *states: OcrState, error: Exception | None = None) -> None:
        self.states = list(states)
        self.error = error
        self.calls: list[tuple[str, str, str]] = []

    def lookup_or_start(self, path: Path, *, card_id: str, document_id: str) -> OcrState:
        self.calls.append((path.name, card_id, document_id))
        if self.error:
            raise self.error
        return self.states.pop(0) if len(self.states) > 1 else self.states[0]


def pret(doc: IntermediateDocument) -> OcrState:
    return OcrState("pret", doc)


EN_COURS = OcrState("en_cours")
ECHEC = OcrState("echec")


def scan_client() -> FakeClient:
    """Faux Gemini « parfait » pour DS3-03, construit sur les lignes OCR."""
    return FakeClient(_output_json(_perfect_gemini(SCAN, ocr_read(SCAN_PATH, SCAN["doc_id"]))))


def assert_timeout(resp: dict[str, Any]) -> None:
    DS3Response.model_validate(resp)
    assert resp["status"] == "erreur" and resp["ds3_code"] == "TIMEOUT" and resp["retryable"] is True
    assert resp["erreur"]["type"] == "TIMEOUT"
    assert resp["erreur"]["message_fr"] == pipeline.OCR_PENDING_FR and resp["erreur"]["message_ar"]
    assert resp["result"] is None and resp["citations"] == []  # jamais de résultat partiel


def png_bytes() -> bytes:
    pix = pymupdf.Pixmap(pymupdf.csRGB, pymupdf.IRect(0, 0, 900, 700), False)
    pix.clear_with(240)
    return bytes(pix.tobytes("png"))


def mixed_pdf(path: Path) -> Path:
    """Une ligne native lisible et une zone image en attente d'OCR."""
    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text((72, 100), "Salaire de base 424,100", fontsize=11)
    pix = pymupdf.Pixmap(pymupdf.csRGB, pymupdf.IRect(0, 0, 600, 220), False)
    pix.clear_with(230)
    page.insert_image(pymupdf.Rect(72, 300, 372, 410), stream=pix.tobytes("png"))
    doc.save(path)
    doc.close()
    return path


# ------------------------------------------------------------ chaîne (pipeline)


def test_scan_is_read_from_the_ocr_cache_and_cited() -> None:
    """Succès : le document lu est servi par le backend ; citations et confiances viennent des lignes OCR."""
    backend = FakeBackend(pret(ocr_read(SCAN_PATH, SCAN["doc_id"])))
    resp = analyze_payslip_pdf(SCAN_PATH, request_for(SCAN), client=scan_client(), ocr_backend=backend)
    DS3Response.model_validate(resp)
    assert resp["status"] == "ok"
    assert score_case(SCAN, resp).count() == {"correct": len(PAYSLIP_FIELDS)}
    assert resp["result"]["fields"]["base_salary"]["confidence"] == OCR_CONFIDENCE  # sans seuil (D39)
    assert any("398,250" in c["excerpt"] for c in resp["citations"])
    assert backend.calls == [(SCAN_PATH.name, "company_eval", SCAN["doc_id"])]


def test_native_pdf_never_calls_the_backend() -> None:
    backend = FakeBackend(EN_COURS)
    client = FakeClient(_output_json(_perfect_gemini(NATIVE, read_pdf(DOCS_DIR / NATIVE["requete"]["file_name"],
                                                                      document_id=NATIVE["doc_id"]))))
    resp = analyze_payslip_pdf(DOCS_DIR / NATIVE["requete"]["file_name"], request_for(NATIVE), client=client,
                               ocr_backend=backend)
    assert resp["status"] == "ok"
    assert backend.calls == []  # ni OCR ni cache pour un PDF entièrement natif


def test_reading_in_progress_answers_timeout_on_every_retry_then_serves_the_cache() -> None:
    """Attente puis nouvel essai (D42) : TIMEOUT réessayable tant que la lecture tourne, jamais de résultat
    partiel, Gemini pas appelé ; une fois la lecture terminée, la réponse vient du cache."""
    backend = FakeBackend(EN_COURS, EN_COURS, pret(ocr_read(SCAN_PATH, SCAN["doc_id"])))
    waiting = FakeClient("{}")
    for _ in range(2):
        assert_timeout(analyze_payslip_pdf(SCAN_PATH, request_for(SCAN), client=waiting, ocr_backend=backend))
    assert waiting.calls == []

    resp = analyze_payslip_pdf(SCAN_PATH, request_for(SCAN), client=scan_client(), ocr_backend=backend)
    assert resp["status"] == "ok"
    assert len(backend.calls) == 3


def test_failed_ocr_on_a_scan_keeps_silence() -> None:
    """Échec : lecture native seule, avertissement, SOURCE_MANQUANTE si rien n'est lisible, aucune exception."""
    client = FakeClient("{}")
    resp = analyze_payslip_pdf(SCAN_PATH, request_for(SCAN), client=client, ocr_backend=FakeBackend(ECHEC))
    DS3Response.model_validate(resp)
    assert resp["status"] == "refus" and resp["refus"]["code"] == "SOURCE_MANQUANTE"
    assert pipeline.OCR_FAILED_WARNING in resp["warnings"]
    assert client.calls == []


def test_failed_ocr_on_a_mixed_pdf_still_uses_its_native_lines(tmp_path: Path) -> None:
    pdf = mixed_pdf(tmp_path / "mixte.pdf")
    native = read_pdf(pdf, document_id="doc_mixte")
    line = next(line for p in native.pages for line in p.lines)
    answer = GeminiPayslipAnswer(document_type="fiche_de_paie",
                                 fields={"base_salary": RawField(raw="424,100", line_id=line.line_id)})
    resp = analyze_payslip_pdf(pdf, request_for(NATIVE), client=FakeClient(_output_json(answer)),
                               ocr_backend=FakeBackend(ECHEC))
    DS3Response.model_validate(resp)
    assert resp["status"] == "ok"
    assert resp["result"]["fields"]["base_salary"]["value"] == "424.100"
    assert pipeline.OCR_FAILED_WARNING in resp["warnings"]


def test_valid_image_whose_ocr_fails_is_source_manquante_never_corrupted(tmp_path: Path) -> None:
    png = tmp_path / "paie.png"
    png.write_bytes(png_bytes())
    client = FakeClient("{}")
    resp = analyze_payslip_pdf(png, request_for(SCAN), client=client, ocr_backend=FakeBackend(ECHEC))
    DS3Response.model_validate(resp)
    assert resp["status"] == "refus" and resp["refus"]["code"] == "SOURCE_MANQUANTE"
    assert resp["ds3_code"] == "UNREADABLE_DOCUMENT"
    assert pipeline.OCR_IMAGE_FAILED_WARNING in resp["warnings"]
    assert client.calls == []


def test_broken_image_is_corrupted_and_never_reaches_the_backend(tmp_path: Path) -> None:
    fake = tmp_path / "casse.png"
    fake.write_bytes(b"ceci n'est pas une image")
    backend = FakeBackend(EN_COURS)
    resp = analyze_payslip_pdf(fake, request_for(SCAN), client=FakeClient("{}"), ocr_backend=backend)
    assert resp["status"] == "refus" and resp["ds3_code"] == "FILE_EMPTY_OR_CORRUPTED"
    assert backend.calls == []


def test_truncated_jpeg_is_corrupted_and_never_reaches_the_backend(tmp_path: Path) -> None:
    """Un JPEG coupé passe `Image.verify()` : seul le décodage complet le détecte (relecture Graphify, #58)."""
    image_module = pytest.importorskip("PIL.Image")
    full = tmp_path / "complet.jpg"
    image_module.frombytes("RGB", (600, 400), bytes(range(256)) * 2812 + bytes(128)).save(full, "JPEG")
    cut = tmp_path / "coupe.jpg"
    cut.write_bytes(full.read_bytes()[: int(full.stat().st_size * 0.6)])
    backend = FakeBackend(EN_COURS)
    resp = analyze_payslip_pdf(cut, request_for(SCAN), client=FakeClient("{}"), ocr_backend=backend)
    assert resp["status"] == "refus" and resp["ds3_code"] == "FILE_EMPTY_OR_CORRUPTED"
    assert backend.calls == []
    assert_timeout(analyze_payslip_pdf(full, request_for(SCAN), client=FakeClient("{}"), ocr_backend=backend))


def test_server_backend_wins_over_in_process_ocr(monkeypatch: pytest.MonkeyPatch) -> None:
    """DS3_CACHE_DIR configuré ET DS3_OCR_INPROCESS=1 : c'est le backend en arrière-plan qui lit, jamais l'OCR
    dans le processus (relecture Graphify, #58)."""
    monkeypatch.setattr(pipeline, "paddle_installed", lambda: True)
    monkeypatch.setenv(pipeline.INPROCESS_ENV, "1")
    backend = FakeBackend(EN_COURS)
    monkeypatch.setattr(ocr_cache, "default_backend", lambda: backend)

    def in_process_ocr(*args: Any, **kwargs: Any) -> None:
        raise AssertionError("OCR lancé dans le processus du service")

    # faux module reading.ocr (sans numpy ni Paddle) : l'appeler ferait échouer le test
    fake_ocr = types.SimpleNamespace(ocr_pending_zones=in_process_ocr, read_image=in_process_ocr)
    monkeypatch.setitem(sys.modules, "src.document_intelligence.reading.ocr", fake_ocr)
    assert_timeout(analyze_payslip_pdf(SCAN_PATH, request_for(SCAN), client=FakeClient("{}")))
    assert backend.calls


def test_without_ocr_a_scan_behaves_as_before() -> None:
    resp = analyze_payslip_pdf(SCAN_PATH, request_for(SCAN), client=FakeClient("{}"))
    assert resp["status"] == "refus" and resp["refus"]["code"] == "SOURCE_MANQUANTE"
    assert pipeline.OCR_UNAVAILABLE_WARNING in resp["warnings"]


def test_cache_access_refusal_is_a_neutral_access_denied() -> None:
    backend = FakeBackend(error=CacheAccessError("document_id refusé"))
    resp = analyze_payslip_pdf(SCAN_PATH, request_for(SCAN), client=FakeClient("{}"), ocr_backend=backend)
    DS3Response.model_validate(resp)
    assert resp["status"] == "refus" and resp["ds3_code"] == "ACCESS_DENIED"
    assert resp["document_id"] is None  # comme le stockage (D40) : rien n'est confirmé


def test_given_backend_takes_priority_over_an_engine() -> None:
    class Engine:
        calls = 0

        def recognize(self, *args: Any) -> list[Any]:
            Engine.calls += 1
            return []

    resp = analyze_payslip_pdf(SCAN_PATH, request_for(SCAN), client=FakeClient("{}"),
                               ocr_engine=Engine(), ocr_backend=FakeBackend(EN_COURS))
    assert_timeout(resp)
    assert Engine.calls == 0


# ------------------------------------------------------------ serveur configuré ou non (D41, D42)


def test_server_backend_is_used_when_paddle_and_cache_dir_are_set(monkeypatch: pytest.MonkeyPatch) -> None:
    """PaddleOCR installé et DS3_CACHE_DIR défini : le backend du serveur est pris par défaut."""
    monkeypatch.setattr(pipeline, "paddle_installed", lambda: True)
    backend = FakeBackend(EN_COURS)
    monkeypatch.setattr(ocr_cache, "default_backend", lambda: backend)
    assert pipeline.ocr_available()
    assert_timeout(analyze_payslip_pdf(SCAN_PATH, request_for(SCAN), client=FakeClient("{}")))
    assert backend.calls


def test_default_backend_needs_both_paddle_and_cache_dir(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(ocr_cache, "default_backend", lambda: FakeBackend(EN_COURS))
    assert pipeline.default_backend() is None  # PaddleOCR non installé (conftest)
    monkeypatch.setattr(pipeline, "paddle_installed", lambda: True)
    assert pipeline.default_backend() is not None


def test_paddle_installed_without_cache_dir_refuses_images_cleanly(monkeypatch: pytest.MonkeyPatch,
                                                                      tmp_path: Path) -> None:
    """Test 5 bis (demandé par Achref) : PaddleOCR installé, DS3_CACHE_DIR absent, image PNG valide ->
    refus D41 HORS_SCOPE au service comme au pipeline ; jamais FILE_EMPTY_OR_CORRUPTED, aucun OCR lancé."""
    monkeypatch.setattr(pipeline, "paddle_installed", lambda: True)
    monkeypatch.delenv(ocr_cache.CACHE_DIR_ENV, raising=False)
    assert ocr_cache.default_backend() is None and not pipeline.ocr_available()

    (tmp_path / "demo").mkdir()
    (tmp_path / "demo" / "paie.png").write_bytes(png_bytes())
    resp = handle_request(image_request("paie.png"), storage_root_dir=tmp_path, client=FakeClient("{}"))
    DS3Response.model_validate(resp)
    assert resp["ds3_code"] == "UNSUPPORTED_FORMAT" and resp["refus"]["message_fr"] == pipeline.OCR_IMAGE_FR

    direct = analyze_payslip_pdf(tmp_path / "demo" / "paie.png", request_for(SCAN), client=FakeClient("{}"))
    assert direct["ds3_code"] == "UNSUPPORTED_FORMAT" and direct["refus"]["code"] == "HORS_SCOPE"


# ------------------------------------------------------------ service live


def image_request(file_name: str) -> dict[str, Any]:
    req = copy.deepcopy(REQUESTS["01_ok_fiche_paie"])
    req["lang"] = "ar"
    req["document"].update({"file_name": file_name, "mime_type": "image/png",
                            "storage_ref": f"local://demo/{file_name}"})
    return req


@pytest.fixture
def storage(tmp_path: Path) -> Path:
    (tmp_path / "demo").mkdir()
    (tmp_path / "demo" / "paie.png").write_bytes(png_bytes())
    (tmp_path / "demo" / "casse.png").write_bytes(b"ceci n'est pas une image")
    (tmp_path / "demo" / "paie.tiff").write_bytes(b"II*\x00")
    return tmp_path


def test_service_reads_an_image_through_the_backend(storage: Path) -> None:
    req = image_request("paie.png")
    backend = FakeBackend(EN_COURS, pret(ocr_read(SCAN_PATH, req["document"]["document_id"])))
    assert_timeout(handle_request(req, storage_root_dir=storage, client=FakeClient("{}"), ocr_backend=backend))

    resp = handle_request(req, storage_root_dir=storage, client=scan_client(), ocr_backend=backend)
    DS3Response.model_validate(resp)
    assert resp["status"] == "ok" and resp["mode"] == "live"
    assert resp["result"]["fields"]["base_salary"]["value"] == "398.250"
    # le backend reçoit le fichier du stockage, la carte active et le document de la requête
    assert backend.calls[0] == ("paie.png", req["context"]["card_id"], req["document"]["document_id"])


@pytest.mark.parametrize(("file_name", "ds3_code"), [("paie.tiff", "UNSUPPORTED_FORMAT"),
                                                     ("casse.png", "FILE_EMPTY_OR_CORRUPTED")])
def test_service_other_formats_and_broken_images(storage: Path, file_name: str, ds3_code: str) -> None:
    backend = FakeBackend(EN_COURS)
    resp = handle_request(image_request(file_name), storage_root_dir=storage, client=FakeClient("{}"),
                          ocr_backend=backend)
    DS3Response.model_validate(resp)
    assert resp["status"] == "refus" and resp["ds3_code"] == ds3_code
    assert backend.calls == []


def test_service_refuses_images_when_no_ocr_is_available(storage: Path) -> None:
    resp = handle_request(image_request("paie.png"), storage_root_dir=storage, client=FakeClient("{}"))
    assert resp["status"] == "refus" and resp["ds3_code"] == "UNSUPPORTED_FORMAT"
    assert resp["refus"]["message_fr"] == pipeline.OCR_IMAGE_FR


# ------------------------------------------------------------ vrai OcrCache, faux processus OCR


class DeferredLauncher:
    """Garde le travail d'arrière-plan au lieu de le lancer : le test décide quand la lecture « se termine »."""

    def __init__(self) -> None:
        self.jobs: list[Callable[[], None]] = []

    def __call__(self, job: Callable[[], None]) -> None:
        self.jobs.append(job)

    def finish(self) -> None:
        while self.jobs:
            self.jobs.pop(0)()


def fake_ocr_process(result: IntermediateDocument | None, runs: list[list[str]]) -> Callable[[list[str], float], int]:
    """Faux `python -m ...reading.ocr fichier --json sortie` : écrit le document lu, ou plante (code 1)."""

    def run(cmd: list[str], timeout_s: float) -> int:
        runs.append(cmd)
        if result is None:
            return 1
        Path(cmd[cmd.index("--json") + 1]).write_text(result.model_dump_json(), encoding="utf-8")
        return 0

    return run


def test_real_cache_end_to_end_timeout_then_ok(tmp_path: Path) -> None:
    """D42 de bout en bout avec le vrai cache : 1re question -> TIMEOUT (lecture lancée) ; question pendant la
    lecture -> TIMEOUT sans relancer ; lecture terminée -> réponse ok tirée du cache ; question suivante -> cache."""
    runs: list[list[str]] = []
    launcher = DeferredLauncher()
    cache = OcrCache(tmp_path / "cache", run_process=fake_ocr_process(ocr_read(SCAN_PATH, SCAN["doc_id"]), runs),
                     launcher=launcher)

    assert_timeout(analyze_payslip_pdf(SCAN_PATH, request_for(SCAN), client=FakeClient("{}"), ocr_backend=cache))
    assert_timeout(analyze_payslip_pdf(SCAN_PATH, request_for(SCAN), client=FakeClient("{}"), ocr_backend=cache))
    assert len(launcher.jobs) == 1  # un seul OCR lancé (verrou)

    launcher.finish()
    for _ in range(2):
        resp = analyze_payslip_pdf(SCAN_PATH, request_for(SCAN), client=scan_client(), ocr_backend=cache)
        assert resp["status"] == "ok"
    assert len(runs) == 1
    cached = list((tmp_path / "cache" / "cards" / "company_eval" / "documents" / SCAN["doc_id"]).iterdir())
    assert [p.suffix for p in cached] == [".json"]  # ni verrou ni .part restants


def test_real_cache_failure_is_not_relaunched(tmp_path: Path) -> None:
    runs: list[list[str]] = []
    launcher = DeferredLauncher()
    cache = OcrCache(tmp_path / "cache", run_process=fake_ocr_process(None, runs), launcher=launcher)
    assert_timeout(analyze_payslip_pdf(SCAN_PATH, request_for(SCAN), client=FakeClient("{}"), ocr_backend=cache))
    launcher.finish()
    for _ in range(2):
        resp = analyze_payslip_pdf(SCAN_PATH, request_for(SCAN), client=FakeClient("{}"), ocr_backend=cache)
        assert resp["status"] == "refus" and resp["refus"]["code"] == "SOURCE_MANQUANTE"
        assert pipeline.OCR_FAILED_WARNING in resp["warnings"]
    assert len(runs) == 1 and launcher.jobs == []  # pas de relance en boucle
