"""Le stockage de démonstration (demo_live/) reste utilisable par DS1 pour le test d'intégration live.

Faux client Gemini : aucun appel réseau. Si un fichier est déplacé ou une requête cassée, ce test échoue.
"""

from __future__ import annotations

import json
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path
from typing import Any

import pymupdf
import pytest

from src.document_intelligence.contract.v2.models import DS3Response
from src.document_intelligence.evaluation.run_gemini_eval import score_case
from src.document_intelligence.reading.pdf_natif import read_pdf
from src.document_intelligence.service import handle_request
from src.document_intelligence.tests.test_document_intelligence_gemini import FakeClient, _output_json
from src.document_intelligence.tests.test_document_intelligence_golden import CASES, _perfect_gemini

DEMO = Path(__file__).resolve().parents[1] / "evaluation" / "demo_live"
ROOT = DEMO / "ds3_stockage"
CARD = "company-demo-001"  # carte de démonstration de DS1 (data/mock_cards/orchestrator_cards_demo.json)


def _load(name: str) -> dict[str, Any]:
    data: dict[str, Any] = json.loads((DEMO / name).read_text(encoding="utf-8"))
    return data


@pytest.mark.parametrize(("request_file", "case_id"), [("requete_doc-company-payslip-01.json", "DS3-01"),
                                                      ("requete_doc-company-payslip-02.json", "DS3-04")])
def test_demo_requests_are_answered_like_the_golden_set(request_file: str, case_id: str) -> None:
    req = _load(request_file)
    doc_meta = req["document"]
    assert req["context"]["card_id"] == doc_meta["card_id"] == CARD
    assert doc_meta["storage_ref"] == f"tradrly://cards/{CARD}/documents/{doc_meta['document_id']}"
    pdf = ROOT / "cards" / CARD / "documents" / doc_meta["document_id"] / doc_meta["file_name"]
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
    req = _load("requete_doc-company-payslip-01.json")
    req["context"]["card_id"] = "client-demo-001"  # une autre carte de DS1
    client = FakeClient("{}")
    resp = handle_request(req, storage_root_dir=ROOT, client=client)
    assert resp["status"] == "refus" and resp["refus"]["code"] == "ACCES_REFUSE"
    assert client.calls == []


def test_demo_copies_are_the_golden_set_pdfs() -> None:
    """La copie de démo et le PDF du jeu de référence sont les mêmes octets (pas de version qui dérive)."""
    golden_docs = DEMO.parent / "golden_sets" / "documents"
    for request_file in ("requete_doc-company-payslip-01.json", "requete_doc-company-payslip-02.json"):
        doc_meta = _load(request_file)["document"]
        demo_pdf = ROOT / "cards" / CARD / "documents" / doc_meta["document_id"] / doc_meta["file_name"]
        assert demo_pdf.read_bytes() == (golden_docs / doc_meta["file_name"]).read_bytes()


def test_payslip_01_is_aligned_on_the_positive_ds1_ds3_ds5_scenario() -> None:
    """Fiche 01 : grille METALLURGIE_BATIMENT / admin_tech, catégorie 3 (confirmée par DS5).

    Base 641,013 ; régime « 42 h/semaine » imprimé sans équivalent mensuel -> null (ni 40 ni 48) ;
    montants cohérents entre eux ; PDF entièrement natif (aucune image, donc jamais d'OCR).
    """
    req = _load("requete_doc-company-payslip-01.json")
    doc_meta = req["document"]
    pdf = ROOT / "cards" / CARD / "documents" / doc_meta["document_id"] / doc_meta["file_name"]
    with pymupdf.open(pdf) as opened:
        assert all(not page.get_images() for page in opened)

    case = CASES["DS3-01"]
    client = FakeClient(_output_json(_perfect_gemini(case, read_pdf(pdf, document_id=case["doc_id"]))))
    resp = handle_request(req, storage_root_dir=ROOT, client=client)
    fields = resp["result"]["fields"]
    assert fields["base_salary"]["value"] == "641.013"
    assert fields["category"]["value"] == "3"
    assert fields["work_hours_regime"]["value"] is None
    assert fields["work_hours_regime"]["unreadable_reason"] == "valeur_incoherente"
    assert resp["result"]["complete"] is False

    base, gross, cnss = (Decimal(fields[name]["value"]) for name in ("base_salary", "gross_salary", "cnss_employee"))
    primes = sum(Decimal(line["amount"]) for line in case["attendu"]["pay_lines"])
    assert gross == base + primes
    assert cnss == (gross * Decimal("0.0918")).quantize(Decimal("0.001"), rounding=ROUND_HALF_UP)
    assert "Net à payer" in pdf_text(pdf) and f"{gross - cnss}".replace(".", ",") in pdf_text(pdf)


def pdf_text(path: Path) -> str:
    with pymupdf.open(path) as opened:
        return "".join(page.get_text() for page in opened)
