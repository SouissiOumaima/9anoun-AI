import pytest

from src.orchestrator.legal_retrieval_adapter import LegalRetrievalAdapter
from src.orchestrator.tool_contracts import ToolContractError


PAYLOAD = {
    "request_id": "legal-1", "agent": "legal_retrieval", "operation": "search",
    "params": {"legal_retrieval_request": {
        "contract_version": "legal_retrieval.v0", "request_id": "legal-1",
        "query": "Quel est le préavis dans le BTP ?", "sector": "btp", "lang": "fr", "top_k": 5,
    }},
}


def test_adapter_normalizes_cited_legal_retrieval_success() -> None:
    response = LegalRetrievalAdapter(lambda request: {
        "status": "ok", "results": [{"article_id": "BTP-1"}],
        "citations": [{"source_file": "source.pdf", "page": 2}], "refus": None,
        "computed_by": "legal_retrieval.search.mock", "mode": "mock",
    })(PAYLOAD)
    assert response["status"] == "success"
    assert response["data"]["results"][0]["article_id"] == "BTP-1"


def test_adapter_preserves_legal_retrieval_refusal() -> None:
    response = LegalRetrievalAdapter(lambda _: {
        "status": "refus", "results": [], "citations": [],
        "refus": {"code": "SOURCE_MANQUANTE"},
    })(PAYLOAD)
    assert response == {
        "status": "refused", "data": None, "citations": [],
        "error": {"code": "SOURCE_MANQUANTE"},
    }


def test_adapter_rejects_wrong_request_id() -> None:
    invalid = {**PAYLOAD, "params": {"legal_retrieval_request": {**PAYLOAD["params"]["legal_retrieval_request"], "request_id": "other"}}}
    with pytest.raises(ToolContractError, match="request_id"):
        LegalRetrievalAdapter(lambda _: {})(invalid)


def test_adapter_accepts_get_article_operation() -> None:
    payload = {
        "request_id": "article-1", "agent": "legal_retrieval", "operation": "get_article",
        "params": {"legal_retrieval_request": {
            "contract_version": "legal_retrieval.v0", "request_id": "article-1",
            "source_id": "CCS-BTP", "article": "39", "lang": "fr",
        }},
    }
    response = LegalRetrievalAdapter(lambda _: {
        "status": "ok", "results": [{"article_id": "CCS-BTP-ART-39-v1"}],
        "citations": [{"source_file": "source.pdf", "page": None}], "refus": None,
    })(payload)
    assert response["status"] == "success"
