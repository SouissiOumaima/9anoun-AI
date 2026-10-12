"""Tests du mock DS3 (document_intelligence) : chaque réponse doit respecter le contrat ds3.v1."""

from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest

from src.document_intelligence.contract.generate_examples import DEMO_FILE, build_demo
from src.document_intelligence.contract.mock import handle_request, list_operations
from src.document_intelligence.contract.models import DS3Response

DEMO: list[dict[str, Any]] = json.loads(Path(DEMO_FILE).read_text("utf-8"))


def _load(name: str) -> dict[str, Any]:
    for case in DEMO:
        if case["name"] == name:
            request: dict[str, Any] = case["request"]
            return request
    raise KeyError(name)


@pytest.mark.parametrize("case", DEMO, ids=lambda c: c["name"])
def test_every_response_matches_contract(case: dict[str, Any]) -> None:
    DS3Response.model_validate(handle_request(case["request"]))


def test_demo_file_is_up_to_date() -> None:
    """Le fichier d'exemples doit correspondre au mock actuel (sinon : relancer generate_examples)."""
    assert DEMO == json.loads(json.dumps(build_demo()))


def test_success_payslip_fields_have_citations() -> None:
    r = handle_request(_load("01_analyze_fiche_paie"))
    assert r["status"] == "success"
    cited = {c["citation_id"] for c in r["citations"]}
    for field in r["result"]["fields"].values():
        assert field["citation_id"] in cited


def test_unreadable_value_is_null_not_guessed() -> None:
    r = handle_request(_load("02_analyze_fiche_paie_illisible"))
    cnss = r["result"]["fields"]["cnss_employee"]
    assert r["status"] == "partial"
    assert cnss["value"] is None
    assert cnss["unreadable_reason"] == "zone_illisible"
    assert cnss["confidence"] < 0.5


def test_amounts_are_three_decimal_strings() -> None:
    r = handle_request(_load("03_extract_wage_grid"))
    for v in r["result"]["values"]:
        assert Decimal(v["amount"]).as_tuple().exponent == -3


def test_wage_grid_increases_with_grade() -> None:
    r = handle_request(_load("03_extract_wage_grid"))
    by_cat: dict[int, list[Decimal]] = {}
    for v in sorted(r["result"]["values"], key=lambda v: (v["category"], v["grade"])):
        by_cat.setdefault(v["category"], []).append(Decimal(v["amount"]))
    for amounts in by_cat.values():
        assert amounts == sorted(amounts)


def test_document_from_other_card_is_refused() -> None:
    r = handle_request(_load("05_erreur_acces_autre_carte"))
    assert r["status"] == "error"
    assert r["error"]["code"] == "ACCESS_DENIED"
    assert r["result"] is None


def test_invalid_request_returns_error_not_exception() -> None:
    r = handle_request({"request_id": "x", "operation": "analyze_document"})
    assert r["status"] == "error"
    assert r["error"]["code"] == "INVALID_REQUEST"


def test_unknown_operation_is_rejected() -> None:
    req = _load("01_analyze_fiche_paie") | {"operation": "translate_document"}
    assert handle_request(req)["error"]["code"] == "INVALID_REQUEST"


def test_operations_are_listed() -> None:
    assert {op["operation"] for op in list_operations()} == {"analyze_document", "extract_wage_grid"}
