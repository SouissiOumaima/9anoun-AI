"""Adapter between the DS1 tool envelope and DS2 legal_retrieval.v0."""

from __future__ import annotations

from typing import Any, Callable, Mapping

from .tool_contracts import ToolContractError

LegalRetrievalHandler = Callable[[Mapping[str, Any]], Mapping[str, Any]]


class LegalRetrievalAdapter:
    """Call DS2's real handler and normalize its common-v0 response for DS1."""

    def __init__(self, handler: LegalRetrievalHandler | None = None) -> None:
        self._handler = handler

    def __call__(self, payload: Mapping[str, Any]) -> Mapping[str, Any]:
        if payload.get("agent") != "legal_retrieval" or payload.get("operation") not in {"search", "get_article"}:
            raise ToolContractError("Legal retrieval adapter only accepts legal_retrieval.search or get_article")
        request = payload.get("params", {}).get("legal_retrieval_request")
        if not isinstance(request, Mapping):
            raise ToolContractError("Legal retrieval call requires a legal_retrieval_request object")
        if request.get("contract_version") != "legal_retrieval.v0":
            raise ToolContractError("Legal retrieval request must use legal_retrieval.v0")
        if request.get("request_id") != payload.get("request_id"):
            raise ToolContractError("Legal retrieval request_id must match the orchestrator request")

        response = dict(self._resolve_handler(str(payload["operation"]))(request))
        status = response.get("status")
        if status == "ok":
            if not response.get("results") or not response.get("citations"):
                raise ToolContractError("Legal retrieval ok response requires results and citations")
            return {
                "status": "success",
                "data": {
                    "results": response["results"], "computed_by": response.get("computed_by"),
                    "mode": response.get("mode"),
                },
                "citations": response["citations"], "error": None,
            }
        if status == "refus":
            return {"status": "refused", "data": None, "citations": [], "error": response.get("refus")}
        if status == "erreur":
            return {"status": "error", "data": None, "citations": [], "error": response.get("erreur")}
        raise ToolContractError("Legal retrieval response has an invalid status")

    def _resolve_handler(self, operation: str) -> LegalRetrievalHandler:
        if self._handler is not None:
            return self._handler
        try:
            if operation == "get_article":
                from src.legal_retrieval.contract.get_article import get_article
                return get_article
            from src.legal_retrieval.contract.handler import handle
        except ImportError as error:
            raise ToolContractError("DS2 legal retrieval dependencies are not installed") from error
        return handle
