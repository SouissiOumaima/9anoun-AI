"""DS4 realistic mock: requests valid; committed responses conform to both schemas."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from src.legal_retrieval.contract.handler import validation_errors
from src.legal_retrieval.tools.build_ds4_mock import CASES, OUTPUT, V0

_ROOT = Path(__file__).resolve().parents[3]
_COMMON = _ROOT / "src" / "shared" / "schemas" / "common.v0.schema.json"
_MOCK = _ROOT / OUTPUT


@pytest.mark.parametrize("case", CASES, ids=[c[0] for c in CASES])
def test_every_case_request_is_a_valid_get_article_request(case: tuple) -> None:
    assert validation_errors({"contract_version": V0, **case[2]}, "get_article_request") == []


@pytest.mark.skipif(not _MOCK.exists(), reason="mock DS4 not generated yet")
def test_committed_mock_is_live_and_conforms() -> None:
    data = json.loads(_MOCK.read_text(encoding="utf-8"))
    common = json.loads(_COMMON.read_text(encoding="utf-8"))
    assert [c["id"] for c in data["cases"]] == [c[0] for c in CASES]
    for case in data["cases"]:
        response = case["expected_response"]
        assert response["mode"] == "live"  # real articles only
        assert validation_errors(response, "search_response") == []
        assert list(Draft202012Validator(common).iter_errors(response)) == []
