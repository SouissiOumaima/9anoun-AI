"""Tests du contrat DS3 v2 et de son mock.

Lancer depuis la racine du dépôt :
    python -m pytest -q src/document_intelligence/tests/test_document_intelligence_mock_v2.py
"""

from __future__ import annotations

import copy
import json
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest

from src.document_intelligence.contract.v2.generate_examples import DEMO_FILE, REQUESTS, build_demo
from src.document_intelligence.contract.v2.mock import handle_request, list_operations
from src.document_intelligence.contract.v2.models import DS3Response, ExtractedField

REPO = Path(__file__).resolve().parents[3]
COMMON_V0 = REPO / "src" / "shared" / "schemas" / "common.v0.schema.json"


def _resp(name: str) -> dict[str, Any]:
    return handle_request(copy.deepcopy(REQUESTS[name]))


# ------------------------------------------------------------ enveloppe


@pytest.mark.parametrize("name", list(REQUESTS))
def test_every_response_is_a_valid_v2_response(name: str) -> None:
    data = _resp(name)
    DS3Response.model_validate(data)
    assert data["contract_version"] == "ds3.v2"
    assert data["mode"] == "mock"
    assert data["computed_by"] == "document_intelligence.mock"
    assert "result" in data and "refus" in data


@pytest.mark.parametrize(
    ("name", "status", "refus_code", "ds3_code"),
    [
        ("06_refus_acces_autre_carte", "refus", "ACCES_REFUSE", "ACCESS_DENIED"),
        ("07_refus_format", "refus", "HORS_SCOPE", "UNSUPPORTED_FORMAT"),
        ("08_refus_fichier_corrompu", "refus", "PARAM_INVALIDE", "FILE_EMPTY_OR_CORRUPTED"),
        ("09_refus_document_blanc", "refus", "SOURCE_MANQUANTE", "UNREADABLE_DOCUMENT"),
        ("10_refus_requete_invalide", "refus", "PARAM_INVALIDE", "INVALID_REQUEST"),
    ],
)
def test_refusals_follow_the_v1_to_v2_code_mapping(name: str, status: str, refus_code: str, ds3_code: str) -> None:
    data = _resp(name)
    assert data["status"] == status
    assert data["refus"]["code"] == refus_code
    assert data["ds3_code"] == ds3_code
    assert data["refus"]["message_fr"] and data["refus"]["message_ar"]
    assert data["result"] is None and data["citations"] == []
    assert "erreur" not in data and "retryable" not in data


def test_access_denied_message_is_neutral_and_hides_the_document() -> None:
    data = _resp("06_refus_acces_autre_carte")
    assert data["refus"]["message_fr"] == "Ce document n'est pas accessible dans le contexte actuel."
    assert data["refus"]["message_ar"] == "هذه الوثيقة غير متاحة في السياق الحالي."
    assert data["document_id"] is None
    assert "company_077" not in json.dumps(data)


def test_timeout_is_a_retryable_technical_error() -> None:
    data = _resp("11_erreur_timeout")
    assert data["status"] == "erreur"
    assert data["erreur"]["type"] == "TIMEOUT"
    assert data["retryable"] is True
    assert data["refus"] is None and data["result"] is None and data["citations"] == []


def test_unknown_operation_is_refused() -> None:
    req = copy.deepcopy(REQUESTS["01_ok_fiche_paie"])
    req["operation"] = "translate_document"
    data = handle_request(req)
    assert data["status"] == "refus" and data["ds3_code"] == "UNSUPPORTED_OPERATION"
    assert data["request_id"] == "req-101"


@pytest.mark.parametrize("bad", [{}, {"request_id": 42}, {"operation": None}, {"request_id": ""}])
def test_garbage_never_raises_and_request_id_may_be_null(bad: dict[str, Any]) -> None:
    data = handle_request(bad)
    DS3Response.model_validate(data)
    assert data["status"] == "refus"
    assert data["request_id"] is None


def test_case_id_is_echoed_only_when_given() -> None:
    assert _resp("04_ok_fiche_paie_dossier")["case_id"] == "case_015"
    assert "case_id" not in _resp("01_ok_fiche_paie")


# ------------------------------------------------------------ fiche de paie

DS5_FIELDS = {
    "employee_name", "period_start", "period_end", "hire_date", "seniority_years_printed", "category",
    "sub_category", "grade", "job_qualification", "employment_status", "pay_mode", "work_hours_regime",
    "base_salary", "gross_salary", "cnss_employee",
}


def test_payslip_has_all_v2_fields_with_value_types() -> None:
    result = _resp("01_ok_fiche_paie")["result"]
    assert set(result["fields"]) == DS5_FIELDS
    f = result["fields"]
    assert (f["period_start"]["value"], f["period_end"]["value"]) == ("2026-03-01", "2026-03-31")
    assert f["hire_date"] == {**f["hire_date"], "value": "2019-09-01", "value_type": "date"}
    assert f["pay_mode"]["value"] == "mensuel" and f["pay_mode"]["value_type"] == "enum"
    assert f["employment_status"]["value"] in {"permanent", "temporaire", "occasionnel"}
    assert f["work_hours_regime"]["value"] == "48"  # « Horaire : 208 h » -> 48
    assert result["complete"] is True


def test_absent_field_is_null_with_reason_and_keeps_result_complete() -> None:
    result = _resp("01_ok_fiche_paie")["result"]
    sub = result["fields"]["sub_category"]
    assert sub["value"] is None and sub["unreadable_reason"] == "absent_du_document"
    assert sub["citation_id"] is None
    assert result["complete"] is True


def test_unreadable_amount_is_null_never_guessed() -> None:
    data = _resp("02_ok_partiel_fiche_paie_illisible")
    assert data["status"] == "ok"
    assert data["result"]["complete"] is False
    cnss = data["result"]["fields"]["cnss_employee"]
    assert cnss["value"] is None and cnss["unreadable_reason"] == "zone_illisible"
    assert any("illisible" in w for w in data["warnings"])


def test_arabic_category_is_normalized_and_summary_follows_lang() -> None:
    data = _resp("03_ok_fiche_paie_arabe")
    f = data["result"]["fields"]
    assert f["category"]["value"] == "1B"
    assert f["work_hours_regime"]["value"] == "40"  # « 173,33 س » -> 40
    excerpts = {c["citation_id"]: c["excerpt"] for c in data["citations"]}
    assert "1 ب" in excerpts[f["category"]["citation_id"]]
    assert data["result"]["summary"].startswith("كشف أجر")


def test_amounts_are_3_decimal_strings_and_gross_matches_pay_lines() -> None:
    result = _resp("01_ok_fiche_paie")["result"]
    f = result["fields"]
    for name in ("base_salary", "gross_salary", "cnss_employee"):
        assert f[name]["value_type"] == "montant" and f[name]["currency"] == "TND"
    total = Decimal(f["base_salary"]["value"]) + sum(Decimal(line["amount"]) for line in result["pay_lines"])
    assert total == Decimal(f["gross_salary"]["value"])


def test_every_citation_id_points_to_a_citation_of_the_same_document() -> None:
    for name in REQUESTS:
        data = _resp(name)
        if data["status"] != "ok":
            continue
        ids = {c["citation_id"] for c in data["citations"]}
        assert all(c["document_id"] == data["document_id"] for c in data["citations"])
        result = data["result"]
        used = [result.get("citation_id")]
        used += [f["citation_id"] for f in result.get("fields", {}).values()]
        used += [line["citation_id"] for line in result.get("pay_lines", [])]
        assert {u for u in used if u is not None} <= ids


@pytest.mark.parametrize(
    ("value", "value_type"), [("424,100", "montant"), ("01/09/2019", "date"), ("48h", "entier")]
)
def test_field_value_must_match_its_type(value: str, value_type: str) -> None:
    with pytest.raises(ValueError):
        ExtractedField.model_validate(
            {"value": value, "value_type": value_type, "confidence": 0.9, "citation_id": "c1"}
        )


def test_null_value_requires_a_reason() -> None:
    with pytest.raises(ValueError):
        ExtractedField.model_validate({"value": None, "value_type": "montant", "confidence": 0.3, "citation_id": None})


# ------------------------------------------------------------ grille de salaires


SECTORS_TABLE = REPO / "src" / "shared" / "sectors" / "sectors.v0.json"


def test_wage_grid_is_cited_on_its_page() -> None:
    data = _resp("05_ok_grille_salaires")
    grid = data["result"]
    assert data["status"] == "ok" and grid["complete"] is False
    assert data["citations"][0]["page"] == 21 and data["citations"][0]["bbox"] is None


@pytest.mark.skipif(not SECTORS_TABLE.exists(), reason="table des secteurs (D30) absente")
def test_wage_grid_sector_code_comes_from_the_shared_table() -> None:
    """sector_code = code DS2 de la table D30, choisi parce que le libellé arabe est identique."""
    grid = _resp("05_ok_grille_salaires")["result"]
    table = json.loads(SECTORS_TABLE.read_text(encoding="utf-8"))
    by_code = {sector["ds2_code"]: sector for sector in table["sectors"]}
    assert grid["sector_code"] in by_code
    assert by_code[grid["sector_code"]]["label_ar"] == grid["sector_ar"]


# ------------------------------------------------------------ fichiers livrés


def test_operations_list_requires_lang() -> None:
    for op in list_operations():
        assert "lang" in op["required"] and "case_id" in op["optional"]


def test_demo_file_is_up_to_date() -> None:
    on_disk = json.loads(DEMO_FILE.read_text(encoding="utf-8"))
    assert on_disk == json.loads(json.dumps(build_demo(), ensure_ascii=False)), (
        "Relancer : python -m src.document_intelligence.contract.v2.generate_examples"
    )


# ------------------------------------------------------------ conformité au schéma commun


def _common_v1_draft() -> dict[str, Any]:
    """common.v0 + les deux ajouts acceptés pour common.v1 : document_citation et ACCES_REFUSE."""
    schema: dict[str, Any] = json.loads(COMMON_V0.read_text(encoding="utf-8"))
    defs = schema["$defs"]
    defs["corpus_citation"] = defs.pop("citation")
    defs["document_citation"] = {
        "type": "object",
        "required": ["citation_id", "document_id", "page", "bbox", "excerpt"],
        "additionalProperties": False,
        "properties": {
            "citation_id": {"type": "string", "minLength": 1},
            "document_id": {"type": "string", "minLength": 1},
            "page": {"type": "integer", "minimum": 1},
            "bbox": {"type": ["array", "null"], "items": {"type": "number"}, "minItems": 4, "maxItems": 4},
            "excerpt": {"type": "string"},
        },
    }
    defs["citation"] = {"oneOf": [{"$ref": "#/$defs/corpus_citation"}, {"$ref": "#/$defs/document_citation"}]}
    defs["refus_code"]["enum"].append("ACCES_REFUSE")
    return schema


@pytest.mark.skipif(not COMMON_V0.exists(), reason="common.v0 absent")
@pytest.mark.parametrize("name", list(REQUESTS))
def test_response_matches_common_v1_draft(name: str) -> None:
    jsonschema = pytest.importorskip("jsonschema")
    jsonschema.validate(_resp(name), _common_v1_draft())


@pytest.mark.skipif(not COMMON_V0.exists(), reason="common.v0 absent")
@pytest.mark.parametrize(
    "name",
    ["07_refus_format", "08_refus_fichier_corrompu", "09_refus_document_blanc", "11_erreur_timeout"],
)
def test_refusals_without_citations_already_match_common_v0(name: str) -> None:
    jsonschema = pytest.importorskip("jsonschema")
    jsonschema.validate(_resp(name), json.loads(COMMON_V0.read_text(encoding="utf-8")))
