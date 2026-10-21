"""Adapter compatible with DS3 v1 and the proposed DS3 v2 contract."""

from __future__ import annotations

from typing import Any, Mapping

from .document_intelligence_response import normalize_ds3_response
from .tool_contracts import ToolContractError

DS3Handler = Any


class DocumentIntelligenceAdapter:
    """Invoke DS3 only with a request bound to DS1's already-scoped context."""

    def __init__(self, handler: DS3Handler | None = None) -> None:
        self._handler = handler

    def __call__(self, payload: Mapping[str, Any]) -> Mapping[str, Any]:
        if payload.get("agent") != "document_intelligence":
            raise ToolContractError("DS3 adapter received an unexpected agent")
        request = payload.get("params", {}).get("ds3_request")
        if not isinstance(request, dict):
            raise ToolContractError("DS3 requires a ds3_request")
        if request.get("request_id") != payload.get("request_id"):
            raise ToolContractError("DS3 request_id must match the DS1 request")
        if request.get("operation") != payload.get("operation"):
            raise ToolContractError("DS3 operation must match the allow-listed tool call")
        if request.get("contract_version") not in {"ds3.v1", "ds3.v2"}:
            raise ToolContractError("DS3 request must use ds3.v1 or ds3.v2")
        if request.get("contract_version") == "ds3.v2" and request.get("lang") not in {"fr", "ar"}:
            raise ToolContractError("DS3 v2 requires lang")
        request_context = request.get("context")
        payload_context = payload.get("context")
        if not isinstance(request_context, dict) or not isinstance(payload_context, dict):
            raise ToolContractError("DS3 requires a scoped context")
        for key in ("organization_id", "card_id", "card_type"):
            if request_context.get(key) != payload_context.get(key):
                raise ToolContractError("DS3 context must match the DS1 active context")
        response = self._resolve_handler(str(request["contract_version"]))(request)
        if not isinstance(response, Mapping):
            raise ToolContractError("DS3 handler must return an object")
        return normalize_ds3_response(response)

    def _resolve_handler(self, version: str) -> DS3Handler:
        if self._handler is not None:
            return self._handler
        try:
            if version == "ds3.v2":
                from src.document_intelligence.contract.v2.mock import handle_request
                return handle_request
            from src.document_intelligence.contract.mock import handle_request
        except ImportError as error:
            raise ToolContractError("DS3 document-intelligence dependencies are not installed") from error
        return handle_request
