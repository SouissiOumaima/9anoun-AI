"""DS2 contract tests: JSON Schema validation, CLI-style handler and HTTP."""

from __future__ import annotations

from typing import Any

from fastapi.testclient import TestClient

from src.legal_retrieval.contract.api import app
from src.legal_retrieval.contract.handler import _demo, handle, validation_errors


def _request(**overrides: Any) -> dict[str, Any]:
    """Demo request with some fields overridden."""
    return {**_demo()["request"], **overrides}


def test_demo_pair_matches_the_schemas() -> None:
    assert validation_errors(_demo()["request"], "search_request") == []
    assert validation_errors(_demo()["response"], "search_response") == []


def test_top_k_counts_articles_and_keeps_all_their_versions() -> None:
    response = handle(_request(top_k=1))
    versions = [r["article_id"] for r in response["results"]]
    # 1 article requested -> its 2 versions (new AND old) are both returned
    assert versions == ["MOCK-CCS-BTP-ART-50-v2", "MOCK-CCS-BTP-ART-50-v1"]
    assert response["status"] == "success" and response["request_id"] == "demo-001"


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


def test_invalid_requests_return_explicit_error() -> None:
    assert handle(_request(query=""))["status"] == "error"  # empty query
    assert handle(_request(reference_date="15/01/2024"))["status"] == "error"  # bad date
    assert handle(_request(contract_version="legal_retrieval.v9"))["status"] == "error"
    assert "unknown" in handle(_request(unknown=1))["error"]  # no extra fields


def test_http_endpoints() -> None:
    client = TestClient(app)
    assert client.get("/health").json()["status"] == "ok"
    ok = client.post("/legal/search", json=_request())
    assert ok.status_code == 200 and ok.json()["mode"] == "mock"
    assert client.post("/legal/search", json=_request(query="")).status_code == 422
