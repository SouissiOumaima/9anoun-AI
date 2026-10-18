"""DS2 contract tests: JSON Schema validation, common envelope, handler and HTTP."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from jsonschema import Draft202012Validator

from src.legal_retrieval.contract.api import app
from src.legal_retrieval.contract.handler import _demo, handle, validation_errors

# tests -> legal_retrieval -> src ; the team schema lives in src/shared/schemas
_COMMON = Path(__file__).resolve().parents[2] / "shared" / "schemas" / "common.v0.schema.json"


@pytest.fixture(autouse=True)
def _mock_mode(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """These tests check the MOCK contract: point the store to an empty folder.

    Without this, a machine where the corpus is ingested would answer in live
    mode (real BM25, test_legal_search.py) and the demo assertions would not hold.
    """
    monkeypatch.setenv("DS2_CORPUS_DIR", str(tmp_path))


def _request(**overrides: Any) -> dict[str, Any]:
    """Demo request with some fields overridden."""
    return {**_demo()["request"], **overrides}


# --- schemas ------------------------------------------------------------
def test_demo_pair_matches_the_schemas() -> None:
    assert validation_errors(_demo()["request"], "search_request") == []
    assert validation_errors(_demo()["response"], "search_response") == []


@pytest.mark.skipif(not _COMMON.exists(), reason="common.v0.schema.json not merged yet")
@pytest.mark.parametrize("request_", [
    _request(),                          # ok
    _request(sector="banques"),          # refus SOURCE_MANQUANTE
    _request(query=""),                  # refus PARAM_INVALIDE (contract)
])
def test_every_response_conforms_to_the_team_common_envelope(request_: dict[str, Any]) -> None:
    """The REAL team file is used, not DS2's copy of its definitions."""
    common = json.loads(_COMMON.read_text(encoding="utf-8"))
    errors = list(Draft202012Validator(common).iter_errors(handle(request_)))
    assert errors == []


# --- status ok : all versions -----------------------------------------
def test_top_k_counts_articles_and_keeps_all_their_versions() -> None:
    response = handle(_request(top_k=1))
    versions = [r["article_id"] for r in response["results"]]
    # 1 article requested -> its 2 versions (new AND old) are both returned
    assert versions == ["MOCK-CCS-BTP-ART-50-v2", "MOCK-CCS-BTP-ART-50-v1"]
    assert response["status"] == "ok" and response["request_id"] == "demo-001"


def test_one_citation_per_article_in_the_same_order() -> None:
    response = handle(_request())
    assert response["citations"] == [r["citation"] for r in response["results"]]
    assert all(c["data_file"].startswith("data/processed/") for c in response["citations"])


def test_at_most_one_applicable_version_per_article() -> None:
    results = handle(_request())["results"]
    for group in {r["version_group"] for r in results}:
        applicable = [r for r in results
                      if r["version_group"] == group and r["applicable_at_reference_date"]]
        assert len(applicable) <= 1


def test_repealed_and_unavailable_previous_versions_are_announced() -> None:
    results = {r["article_id"]: r for r in handle(_request())["results"]}
    repealed = results["MOCK-CCS-BTP-ART-39-v1"]
    assert repealed["status"] == "abroge" and repealed["amended_by"]  # cited, not hidden
    # modified article whose old text is not in the corpus: caller must say so
    assert results["MOCK-CCS-BTP-ART-51-v2"]["previous_version_available"] is False


# --- status refus : Citation ou Silence ---------------------------------
def test_no_relevant_article_gives_bilingual_source_manquante() -> None:
    response = handle(_request(sector="banques"))  # mock only has BTP articles
    assert response["status"] == "refus" and response["results"] == []
    assert response["citations"] == []
    assert response["refus"]["code"] == "SOURCE_MANQUANTE"
    assert response["refus"]["message_fr"] and response["refus"]["message_ar"]


@pytest.mark.parametrize("bad", [
    {"query": ""},                                   # empty question
    {"reference_date": "15/01/2024"},                # wrong date format
    {"reference_date": "2024-13-45"},                # matches the pattern, not a real date
    {"contract_version": "legal_retrieval.v9"},      # wrong contract
    {"unknown": 1},                                  # no extra fields
])
def test_non_conforming_requests_give_param_invalide(bad: dict[str, Any]) -> None:
    response = handle(_request(**bad))
    assert response["status"] == "refus" and response["refus"]["code"] == "PARAM_INVALIDE"
    assert response["computed_by"] == "legal_retrieval.contract"


def test_non_dict_request_is_refused_not_crashing() -> None:
    response = handle(["not", "a", "dict"])
    assert response["status"] == "refus" and response["request_id"] is None


# --- status erreur -------------------------------------------------------
def test_internal_bug_gives_erreur_without_internal_detail() -> None:
    with patch("src.legal_retrieval.contract.handler._search", side_effect=KeyError("secret")):
        response = handle(_request())
    assert response["status"] == "erreur" and response["citations"] == []
    assert "secret" not in json.dumps(response, ensure_ascii=False)


# --- HTTP ---------------------------------------------------------------
def test_http_codes() -> None:
    client = TestClient(app)
    assert client.get("/health").json()["status"] == "ok"
    assert client.post("/legal/search", json=_request()).status_code == 200
    # "no source" is a valid answer -> 200 ; a malformed request -> 422
    assert client.post("/legal/search", json=_request(sector="banques")).status_code == 200
    assert client.post("/legal/search", json=_request(query="")).status_code == 422


def test_http_code_follows_the_layer_not_the_refusal_code() -> None:
    """A BUSINESS refusal using PARAM_INVALIDE stays 200 (review of PR #6)."""
    business = {**handle(_request(sector="banques")), "computed_by": "legal_retrieval.search.mock"}
    business["refus"] = {**business["refus"], "code": "PARAM_INVALIDE"}
    with patch("src.legal_retrieval.contract.api.handle", return_value=business):
        assert TestClient(app).post("/legal/search", json=_request()).status_code == 200


# --- integration examples for DS1 ---------------------------------------
_EXAMPLES = Path(__file__).resolve().parents[3] / "data" / "mock_cards" / "legal_retrieval_requests_demo.json"


def test_integration_examples_file_is_up_to_date() -> None:
    """The file sent to DS1 must equal what the handler produces today."""
    from src.legal_retrieval.tools.build_demo_examples import build

    on_disk = json.loads(_EXAMPLES.read_text(encoding="utf-8"))
    assert on_disk == json.loads(json.dumps(build(), ensure_ascii=False)), (
        "re-run: python -m src.legal_retrieval.tools.build_demo_examples")


def test_erreur_example_is_valid() -> None:
    from src.legal_retrieval.tools.build_demo_examples import ERREUR_EXAMPLE

    assert validation_errors(ERREUR_EXAMPLE, "search_response") == []
    if _COMMON.exists():
        common = json.loads(_COMMON.read_text(encoding="utf-8"))
        assert list(Draft202012Validator(common).iter_errors(ERREUR_EXAMPLE)) == []
