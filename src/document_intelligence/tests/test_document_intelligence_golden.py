"""Jeu de référence DS3 sur les documents fictifs : cohérence et test de bout en bout sans Gemini.

Le test de bout en bout enchaîne le vrai lecteur (PDF -> format intermédiaire), la vérification,
la normalisation et l'assemblage. Gemini est remplacé par un « Gemini parfait » : il recopie le texte
imprimé (texte_imprime du jeu de référence) et cite la ligne qui le contient. Si ce test passe, toute
erreur future sur ces documents viendra de Gemini, pas du code autour.
"""

from __future__ import annotations

import csv
import json
from typing import Any

import pytest

from src.document_intelligence.contract.v2.models import DS3Request, DS3Response
from src.document_intelligence.evaluation import check_golden
from src.document_intelligence.evaluation.fictive_documents import (
    DOCS_DIR,
    GOLDEN_FILE,
    SOURCES_FILE,
    build_golden,
)
from src.document_intelligence.extraction.assemble import (
    GeminiPayslipAnswer,
    RawPayLine,
    build_payslip_response,
)
from src.document_intelligence.extraction.verify import RawField, contains_value
from src.document_intelligence.intermediate import IntermediateDocument
from src.document_intelligence.reading.pdf_natif import ROW_SEPARATOR, read_pdf

GOLDEN: dict[str, Any] = json.loads(GOLDEN_FILE.read_text(encoding="utf-8"))
CASES = {case["id"]: case for case in GOLDEN["cases"]}
NEEDS_OCR = {"DS3-03"}  # page scannée : attend l'OCR de la partie A


def test_golden_set_is_consistent() -> None:
    assert check_golden.main([]) == 0


def test_golden_file_is_up_to_date() -> None:
    assert GOLDEN == json.loads(json.dumps(build_golden(), ensure_ascii=False)), (
        "Relancer : python -m src.document_intelligence.evaluation.fictive_documents"
    )


def test_every_registered_document_exists() -> None:
    with SOURCES_FILE.open(encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            assert (DOCS_DIR / row["fichier"]).is_file(), row["fichier"]


def test_scanned_document_has_no_text_layer() -> None:
    doc = read_pdf(DOCS_DIR / CASES["DS3-03"]["requete"]["file_name"])
    assert doc.pages[0].lines == []
    assert doc.pages[0].pending_zones and doc.pages[0].pending_zones[0].reason == "image"


# ------------------------------------------------------------ bout en bout avec un « Gemini parfait »


def _line_with(doc: IntermediateDocument, printed: str) -> str:
    for page in doc.pages:
        for line in page.lines:
            if contains_value(line.text, printed):
                return line.line_id
    raise AssertionError(f"« {printed} » introuvable dans le document")


def _perfect_gemini(case: dict[str, Any], doc: IntermediateDocument) -> GeminiPayslipAnswer:
    fields: dict[str, RawField] = {}
    image_zones = [z.zone_id for p in doc.pages for z in p.pending_zones if z.reason == "image"]
    for name, printed in case["texte_imprime"].items():
        if printed is None:  # valeur cachée (tampon) : Gemini signale la zone, sans valeur
            fields[name] = RawField(raw=None, line_id=image_zones[0])
        else:
            fields[name] = RawField(raw=printed, line_id=_line_with(doc, printed))
    attendu = case["attendu"]
    pay_lines = []
    for line in attendu.get("pay_lines", []):
        line_id = _line_with(doc, line["label"])
        found = doc.find_line(line_id)
        assert found is not None
        printed_amount = found.text.split(ROW_SEPARATOR)[-1]  # « Prime de transport  56,000 » -> « 56,000 »
        pay_lines.append(RawPayLine(label=line["label"], amount=printed_amount, line_id=line_id))
    return GeminiPayslipAnswer(document_type=attendu.get("document_type", "facture"), fields=fields,
                               pay_lines=pay_lines)


def _request(case: dict[str, Any]) -> DS3Request:
    return DS3Request.model_validate({
        "contract_version": "ds3.v2", "request_id": f"req-{case['id']}", "lang": case["requete"]["lang"],
        "operation": "analyze_document",
        "context": {"organization_id": "org_demo", "user_id": "u1", "role": "accountant",
                    "card_id": "company_042", "card_type": "company"},
        "document": {"document_id": case["doc_id"], "card_id": "company_042",
                     "file_name": case["requete"]["file_name"], "mime_type": "application/pdf",
                     "storage_ref": "tradrly://fictif"},
        "options": {"expected_type": case["requete"]["expected_type"]},
    })


@pytest.mark.parametrize("case_id", sorted(set(CASES) - NEEDS_OCR))
def test_pipeline_gives_the_expected_answer(case_id: str) -> None:
    case = CASES[case_id]
    doc = read_pdf(DOCS_DIR / case["requete"]["file_name"], document_id=case["doc_id"])
    resp = build_payslip_response(_request(case), doc, _perfect_gemini(case, doc))
    DS3Response.model_validate(resp)
    attendu = case["attendu"]

    if attendu["issue"] == "refus":
        assert resp["status"] == "refus" and resp["refus"]["code"] == attendu["code_v2"]
        return

    assert resp["status"] == "ok"
    assert resp["result"]["complete"] is (attendu["issue"] == "ok")
    got = resp["result"]["fields"]
    for name, expected in attendu["fields"].items():
        assert got[name]["value"] == expected, name
        if expected is None:
            assert got[name]["unreadable_reason"] == attendu["unreadable"][name], name
    for name in set(got) - set(attendu["fields"]):
        assert got[name]["unreadable_reason"] == "absent_du_document", name
    assert [(p["label"], p["amount"]) for p in resp["result"]["pay_lines"]] == [
        (p["label"], p["amount"]) for p in attendu["pay_lines"]
    ]
    # Chaque valeur renvoyée est citée par sa ligne, avec la page et la position.
    cited = {c["citation_id"]: c for c in resp["citations"]}
    for name, f in got.items():
        if f["value"] is not None:
            assert cited[f["citation_id"]]["page"] == 1 and cited[f["citation_id"]]["bbox"], name
