"""Le stockage de démonstration (demo_live/) reste utilisable par DS1 pour le test d'intégration live.

Faux client Gemini : aucun appel réseau. Si un fichier est déplacé ou une requête cassée, ce test échoue.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from src.document_intelligence.contract.v2.models import DS3Response
from src.document_intelligence.evaluation.run_gemini_eval import score_case
from src.document_intelligence.reading.pdf_natif import read_pdf
from src.document_intelligence.service import handle_request
from src.document_intelligence.tests.test_document_intelligence_gemini import FakeClient, _output_json
from src.document_intelligence.tests.test_document_intelligence_golden import CASES, _perfect_gemini

DEMO = Path(__file__).resolve().parents[1] / "evaluation" / "demo_live"
ROOT = DEMO / "ds3_stockage"


def _load(name: str) -> dict[str, Any]:
    data: dict[str, Any] = json.loads((DEMO / name).read_text(encoding="utf-8"))
    return data


@pytest.mark.parametrize(("request_file", "case_id"), [("requete_doc_7f3a.json", "DS3-01"),
                                                      ("requete_doc_8b21.json", "DS3-04")])
def test_demo_requests_are_answered_like_the_golden_set(request_file: str, case_id: str) -> None:
    req = _load(request_file)
    doc_meta = req["document"]
    assert doc_meta["storage_ref"].startswith("tradrly://cards/company_042/documents/")
    pdf = ROOT / "cards" / "company_042" / "documents" / doc_meta["document_id"] / doc_meta["file_name"]
    assert pdf.is_file()

    case = CASES[case_id]
    client = FakeClient(_output_json(_perfect_gemini(case, read_pdf(pdf, document_id=case["doc_id"]))))
    resp = handle_request(req, storage_root_dir=ROOT, client=client)
    DS3Response.model_validate(resp)
    assert (resp["status"], resp["mode"]) == ("ok", "live")
    counts = score_case(case, resp).count()
    assert counts.get("faux", 0) == 0 and counts.get("invention", 0) == 0
    assert counts.get("correct", 0) == sum(counts.values())


def test_demo_storage_refuses_another_card_without_reading() -> None:
    req = _load("requete_doc_7f3a.json")
    req["context"]["card_id"] = "company_077"
    client = FakeClient("{}")
    resp = handle_request(req, storage_root_dir=ROOT, client=client)
    assert resp["status"] == "refus" and resp["refus"]["code"] == "ACCES_REFUSE"
    assert client.calls == []
