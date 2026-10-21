"""Tests du service réel DS3 (handle_request en live), avec un faux client Gemini et un stockage temporaire."""

from __future__ import annotations

import copy
import json
import shutil
from pathlib import Path
from typing import Any

import pytest

from src.document_intelligence.contract.v2.generate_examples import REQUESTS
from src.document_intelligence.contract.v2.mock import handle_request as mock_handle_request
from src.document_intelligence.contract.v2.models import DS3Response
from src.document_intelligence.evaluation.fictive_documents import DOCS_DIR
from src.document_intelligence.evaluation.run_gemini_eval import score_case
from src.document_intelligence.extraction.assemble import PAYSLIP_FIELDS
from src.document_intelligence.reading.pdf_natif import read_pdf
from src.document_intelligence.service import STORAGE_ROOT_ENV, handle_request
from src.document_intelligence.tests.test_document_intelligence_gemini import FakeClient, _output_json
from src.document_intelligence.tests.test_document_intelligence_golden import CASES, _perfect_gemini

CARD = "company_042"
CASE = CASES["DS3-01"]
PDF_NAME = CASE["requete"]["file_name"]


@pytest.fixture
def storage(tmp_path: Path) -> Path:
    """Stockage temporaire : <racine>/cards/company_042/documents/doc_7f3a/paie_fictive_01_fr.pdf."""
    folder = tmp_path / "cards" / CARD / "documents" / "doc_7f3a"
    folder.mkdir(parents=True)
    shutil.copy(DOCS_DIR / PDF_NAME, folder / PDF_NAME)
    (tmp_path / "demo").mkdir()
    shutil.copy(DOCS_DIR / PDF_NAME, tmp_path / "demo" / PDF_NAME)
    return tmp_path


def _client() -> FakeClient:
    doc = read_pdf(DOCS_DIR / PDF_NAME, document_id=CASE["doc_id"])
    return FakeClient(_output_json(_perfect_gemini(CASE, doc)))


def _request(**document: Any) -> dict[str, Any]:
    req = copy.deepcopy(REQUESTS["01_ok_fiche_paie"])
    req["document"].update({"file_name": PDF_NAME, "mime_type": "application/pdf",
                            "storage_ref": f"tradrly://cards/{CARD}/documents/doc_7f3a"})
    req["document"].update(document)
    return req


def _call(req: dict[str, Any], storage: Path | None, client: FakeClient | None = None) -> dict[str, Any]:
    resp = handle_request(req, storage_root_dir=storage, client=client or _client())
    DS3Response.model_validate(resp)
    return resp


# ------------------------------------------------------------ cas nominal


def test_live_payslip_is_read_and_scored_like_the_golden_set(storage: Path) -> None:
    resp = _call(_request(), storage)
    assert resp["status"] == "ok"
    assert resp["mode"] == "live" and resp["computed_by"] == "document_intelligence.service"
    assert resp["request_id"] == "req-101" and resp["card_id"] == CARD
    assert score_case(CASE, resp).count() == {"correct": len(PAYSLIP_FIELDS)}


def test_local_storage_ref_works(storage: Path) -> None:
    assert _call(_request(storage_ref=f"local://demo/{PDF_NAME}"), storage)["status"] == "ok"


def test_document_file_directly_in_the_documents_folder(storage: Path) -> None:
    flat = storage / "cards" / CARD / "documents"
    shutil.copy(DOCS_DIR / PDF_NAME, flat / PDF_NAME)
    resp = _call(_request(storage_ref=f"tradrly://cards/{CARD}/documents/doc_absent"), storage)
    assert resp["status"] == "ok"


def test_storage_root_can_come_from_the_environment(storage: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(STORAGE_ROOT_ENV, str(storage))
    assert _call(_request(), None)["status"] == "ok"


def test_same_interface_as_the_mock(storage: Path) -> None:
    """DS1 ne change qu'une ligne : mêmes clés de réponse et mêmes champs que le mock."""
    live = _call(_request(), storage)
    mock = mock_handle_request(_request())
    assert set(live) == set(mock)
    assert set(live["result"]["fields"]) == set(mock["result"]["fields"])
    assert (live["mode"], mock["mode"]) == ("live", "mock")


# ------------------------------------------------------------ sécurité : rien n'est lu


@pytest.mark.parametrize(
    "document",
    [
        {"card_id": "company_077"},  # document d'une autre carte
        {"storage_ref": "tradrly://cards/company_077/documents/doc_7f3a"},  # stockage d'une autre carte
        {"storage_ref": "local://../secret.pdf"},  # chemin qui sort du stockage
    ],
)
def test_access_is_refused_without_calling_gemini(storage: Path, document: dict[str, str]) -> None:
    (storage.parent / "secret.pdf").write_bytes((DOCS_DIR / PDF_NAME).read_bytes())
    client = _client()
    resp = _call(_request(**document), storage, client)
    assert resp["status"] == "refus" and resp["refus"]["code"] == "ACCES_REFUSE"
    assert resp["document_id"] is None
    assert client.calls == []


# ------------------------------------------------------------ refus et erreurs


@pytest.mark.parametrize(
    ("document", "ds3_code", "refus_code"),
    [
        ({"storage_ref": f"tradrly://cards/{CARD}/documents/inconnu", "file_name": "absent.pdf"},
         "FILE_EMPTY_OR_CORRUPTED", "PARAM_INVALIDE"),
        ({"storage_ref": "s3://bucket/x.pdf"}, "INVALID_REQUEST", "PARAM_INVALIDE"),
        ({"storage_ref": "tradrly://cards/x"}, "INVALID_REQUEST", "PARAM_INVALIDE"),
        ({"file_name": "paie.docx"}, "UNSUPPORTED_FORMAT", "HORS_SCOPE"),
        ({"file_name": "../../../../secret.pdf"}, "INVALID_REQUEST", "PARAM_INVALIDE"),  # nom avec dossiers
        ({"file_name": "..\\secret.pdf"}, "INVALID_REQUEST", "PARAM_INVALIDE"),
    ],
)
def test_storage_and_format_problems_are_refused(storage: Path, document: dict[str, str], ds3_code: str,
                                                 refus_code: str) -> None:
    client = _client()
    resp = _call(_request(**document), storage, client)
    assert resp["status"] == "refus"
    assert (resp["ds3_code"], resp["refus"]["code"]) == (ds3_code, refus_code)
    assert client.calls == []


def test_empty_and_too_large_files_are_refused(storage: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    (storage / "demo" / "vide.pdf").write_bytes(b"")
    resp = _call(_request(file_name="vide.pdf", storage_ref="local://demo/vide.pdf"), storage)
    assert resp["ds3_code"] == "FILE_EMPTY_OR_CORRUPTED"
    monkeypatch.setattr("src.document_intelligence.service.MAX_FILE_BYTES", 10)
    assert _call(_request(), storage)["ds3_code"] == "FILE_TOO_LARGE"


def test_wage_grid_is_not_yet_available_live(storage: Path) -> None:
    req = copy.deepcopy(REQUESTS["05_ok_grille_salaires"])
    resp = _call(req, storage)
    assert resp["status"] == "refus" and resp["ds3_code"] == "UNSUPPORTED_OPERATION"
    assert "mock" in resp["refus"]["message_fr"] and resp["refus"]["message_ar"]


def test_only_payslips_are_read_live(storage: Path) -> None:
    req = _request()
    req["options"]["expected_type"] = "facture"
    resp = _call(req, storage)
    assert resp["refus"]["code"] == "HORS_SCOPE" and "fiches de paie" in resp["refus"]["message_fr"]


def test_missing_storage_configuration_is_a_technical_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(STORAGE_ROOT_ENV, raising=False)
    resp = _call(_request(), None)
    assert resp["status"] == "erreur" and resp["erreur"]["type"] == "INTERNAL_ERROR"


def test_invalid_request_is_refused(storage: Path) -> None:
    req = _request()
    del req["lang"]
    assert _call(req, storage)["ds3_code"] == "INVALID_REQUEST"


def test_gemini_failure_is_a_retryable_error(storage: Path) -> None:
    resp = _call(_request(), storage, FakeClient(error=RuntimeError("quota")))
    assert resp["status"] == "erreur" and resp["retryable"] is True


@pytest.mark.parametrize("bad", [{}, {"request_id": 42}, {"operation": None}, "pas un dict"])
def test_garbage_never_raises(storage: Path, bad: Any) -> None:
    resp = handle_request(bad, storage_root_dir=storage, client=_client())
    DS3Response.model_validate(resp)
    assert resp["status"] in {"refus", "erreur"}
    assert json.dumps(resp)
