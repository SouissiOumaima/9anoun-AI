"""Tests de l'assemblage de la réponse ds3.v2 (étape 5 de l'extracteur DS3).

Aucun appel à Gemini : on lui substitue une réponse écrite à la main (GeminiPayslipAnswer).
"""

from __future__ import annotations

from typing import Any

import pytest

from src.document_intelligence.contract.v2.models import DS3Request, DS3Response
from src.document_intelligence.extraction.assemble import (
    PAYSLIP_FIELDS,
    GeminiPayslipAnswer,
    RawPayLine,
    build_payslip_response,
)
from src.document_intelligence.extraction.verify import RawField
from src.document_intelligence.intermediate import (
    IntermediateDocument,
    PageContent,
    PendingZone,
    Source,
    TextLine,
)
from src.document_intelligence.tests.test_document_intelligence_mock_v2 import _common_v1_draft

LINES = [
    "Nom : Ahmed Ben Salah",
    "Période : Mars 2026",
    "Date d'entrée : 01/09/2019",
    "Catégorie : 3   Échelon : 2",
    "Emploi : Agent administratif   Statut : Permanent",
    "Paiement : Mensuel   Horaire : 208 h",
    "Salaire de base 424,100",
    "Prime de transport 56,000",
    "Prime de présence 36,000",
    "Salaire brut 516,100",
    "Retenue CNSS 47,378",
]


def _doc(confidence: float = 1.0, source: Source = "natif", pending: bool = False) -> IntermediateDocument:
    lines = [
        TextLine(line_id=f"p1_l{i}", page=1, text=text, bbox=(72, 100 + 20 * i, 400, 115 + 20 * i),
                 confidence=confidence, source=source, language="fr")
        for i, text in enumerate(LINES, start=1)
    ]
    zones = [PendingZone(zone_id="p1_u1", page=1, bbox=(380, 420, 470, 440))] if pending else []
    page = PageContent(page=1, width=595, height=842, kind="texte", lines=lines, pending_zones=zones)
    return IntermediateDocument(document_id="doc_7f3a", file_name="paie.pdf", page_count=1, reader="test",
                                pages=[page])


def _req(lang: str = "fr", expected: str | None = "fiche_de_paie") -> DS3Request:
    return DS3Request.model_validate({
        "contract_version": "ds3.v2", "request_id": "req-201", "lang": lang, "operation": "analyze_document",
        "context": {"organization_id": "org_demo", "user_id": "u1", "role": "accountant",
                    "card_id": "company_042", "card_type": "company"},
        "document": {"document_id": "doc_7f3a", "card_id": "company_042", "file_name": "paie.pdf",
                     "mime_type": "application/pdf", "storage_ref": "tradrly://x"},
        "options": {"expected_type": expected},
    })


def _answer(**overrides: RawField) -> GeminiPayslipAnswer:
    fields = {
        "employee_name": RawField(raw="Ahmed Ben Salah", line_id="p1_l1"),
        "period_start": RawField(raw="Mars 2026", line_id="p1_l2"),
        "period_end": RawField(raw="Mars 2026", line_id="p1_l2"),
        "hire_date": RawField(raw="01/09/2019", line_id="p1_l3"),
        "category": RawField(raw="3", line_id="p1_l4"),
        "grade": RawField(raw="2", line_id="p1_l4"),
        "job_qualification": RawField(raw="Agent administratif", line_id="p1_l5"),
        "employment_status": RawField(raw="Permanent", line_id="p1_l5"),
        "pay_mode": RawField(raw="Mensuel", line_id="p1_l6"),
        "work_hours_regime": RawField(raw="208 h", line_id="p1_l6"),
        "base_salary": RawField(raw="424,100", line_id="p1_l7"),
        "gross_salary": RawField(raw="516,100", line_id="p1_l10"),
        "cnss_employee": RawField(raw="47,378", line_id="p1_l11"),
        "sub_category": RawField(raw=None, line_id=None),
    }
    fields.update(overrides)
    return GeminiPayslipAnswer(
        document_type="fiche_de_paie",
        fields=fields,
        pay_lines=[RawPayLine(label="Prime de transport", amount="56,000", line_id="p1_l8"),
                   RawPayLine(label="Prime de présence", amount="36,000", line_id="p1_l9")],
    )


def _build(answer: GeminiPayslipAnswer | None = None, **kwargs: Any) -> dict[str, Any]:
    return build_payslip_response(kwargs.pop("req", _req()), kwargs.pop("doc", _doc()), answer or _answer())


def _value(resp: dict[str, Any], name: str) -> Any:
    return resp["result"]["fields"][name]["value"]


# ------------------------------------------------------------ cas nominal


def test_full_payslip_gives_a_valid_complete_response() -> None:
    resp = _build()
    DS3Response.model_validate(resp)
    assert resp["status"] == "ok" and resp["mode"] == "live"
    assert resp["computed_by"] == "document_intelligence.service"
    assert set(resp["result"]["fields"]) == set(PAYSLIP_FIELDS)
    assert resp["result"]["complete"] is True
    assert resp["warnings"] == []


def test_values_are_normalized() -> None:
    resp = _build()
    assert (_value(resp, "period_start"), _value(resp, "period_end")) == ("2026-03-01", "2026-03-31")
    assert _value(resp, "hire_date") == "2019-09-01"
    assert _value(resp, "base_salary") == "424.100"
    assert _value(resp, "work_hours_regime") == "48"
    assert _value(resp, "employment_status") == "permanent"
    assert _value(resp, "pay_mode") == "mensuel"
    assert [(p["label"], p["amount"]) for p in resp["result"]["pay_lines"]] == [
        ("Prime de transport", "56.000"), ("Prime de présence", "36.000")]


def test_citation_is_the_document_line() -> None:
    resp = _build()
    field = resp["result"]["fields"]["base_salary"]
    assert field["citation_id"] == "p1_l7"
    cite = next(c for c in resp["citations"] if c["citation_id"] == "p1_l7")
    assert cite == {"citation_id": "p1_l7", "document_id": "doc_7f3a", "page": 1,
                    "bbox": [72.0, 240.0, 400.0, 255.0], "excerpt": "Salaire de base 424,100"}


def test_each_line_is_cited_once() -> None:
    ids = [c["citation_id"] for c in _build()["citations"]]
    assert len(ids) == len(set(ids))


def test_confidence_comes_from_the_line_not_from_gemini() -> None:
    resp = _build(doc=_doc(confidence=0.72, source="ocr"))
    assert resp["result"]["fields"]["base_salary"]["confidence"] == 0.72


def test_absent_field_is_null_and_keeps_response_complete() -> None:
    resp = _build()
    sub = resp["result"]["fields"]["sub_category"]
    assert sub["value"] is None and sub["unreadable_reason"] == "absent_du_document"
    assert resp["result"]["complete"] is True


# ------------------------------------------------------------ « citation ou silence »


def test_invented_value_is_null_and_response_incomplete() -> None:
    resp = _build(_answer(base_salary=RawField(raw="425,000", line_id="p1_l7")))
    field = resp["result"]["fields"]["base_salary"]
    assert field["value"] is None and field["unreadable_reason"] == "valeur_incoherente"
    assert resp["result"]["complete"] is False
    assert any("425,000" in w for w in resp["warnings"])


def test_printed_but_unconvertible_value_keeps_its_citation() -> None:
    doc = _doc()
    doc.pages[0].lines[5] = doc.pages[0].lines[5].model_copy(update={"text": "Paiement : Mensuel   Horaire : 195 h"})
    resp = _build(_answer(work_hours_regime=RawField(raw="195 h", line_id="p1_l6")), doc=doc)
    field = resp["result"]["fields"]["work_hours_regime"]
    assert field["value"] is None and field["unreadable_reason"] == "valeur_incoherente"
    assert field["citation_id"] == "p1_l6"  # DS1 peut montrer où se trouve la valeur imprimée
    assert resp["result"]["complete"] is False


def test_value_in_unread_zone_is_unreadable() -> None:
    resp = _build(_answer(cnss_employee=RawField(raw=None, line_id="p1_u1")), doc=_doc(pending=True))
    assert resp["result"]["fields"]["cnss_employee"]["unreadable_reason"] == "zone_illisible"
    assert resp["result"]["complete"] is False


def test_invented_pay_line_is_dropped() -> None:
    answer = _answer()
    answer.pay_lines.append(RawPayLine(label="Prime de rendement", amount="50,000", line_id="p1_l8"))
    resp = _build(answer)
    assert [p["label"] for p in resp["result"]["pay_lines"]] == ["Prime de transport", "Prime de présence"]
    assert any("Prime de rendement" in w for w in resp["warnings"])


def test_nothing_verified_gives_source_manquante() -> None:
    empty = GeminiPayslipAnswer(document_type="fiche_de_paie",
                                fields={"base_salary": RawField(raw="999,999", line_id="p1_l7")})
    resp = _build(empty)
    assert resp["status"] == "refus" and resp["refus"]["code"] == "SOURCE_MANQUANTE"
    assert resp["result"] is None and resp["citations"] == []


# ------------------------------------------------------------ divers


def test_summary_follows_lang() -> None:
    assert _build()["result"]["summary"] == "Fiche de paie du 2026-03-01 au 2026-03-31, catégorie 3, échelon 2."
    assert _build(req=_req(lang="ar"))["result"]["summary"].startswith("كشف أجر")


def test_type_mismatch_lowers_confidence_and_warns() -> None:
    answer = _answer()
    answer.document_type = "facture"
    resp = _build(answer)
    assert resp["result"]["document_type_confidence"] == 0.50
    assert "différent du type attendu" in resp["warnings"][0]


@pytest.mark.parametrize("case", ["ok", "refus"])
def test_matches_common_v1_draft(case: str) -> None:
    jsonschema = pytest.importorskip("jsonschema")
    answer = _answer() if case == "ok" else GeminiPayslipAnswer(document_type="fiche_de_paie", fields={})
    jsonschema.validate(_build(answer), _common_v1_draft())
