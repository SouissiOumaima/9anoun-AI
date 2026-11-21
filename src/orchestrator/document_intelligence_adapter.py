"""Adapter compatible with DS3 v1 and the proposed DS3 v2 contract."""

from __future__ import annotations

import os
from typing import Any, Mapping

from .document_intelligence_response import normalize_ds3_response
from .tool_contracts import ToolContractError

DS3Handler = Any
DS3_HANDLER_MODE_ENV = "DS3_HANDLER_MODE"
_HANDLER_MODES = frozenset({"mock", "live"})


class DocumentIntelligenceAdapter:
    """Invoke DS3 only with a request bound to DS1's already-scoped context.

    DS3 v2 stays on the deterministic mock unless the backend explicitly sets
    ``DS3_HANDLER_MODE=live`` (or passes ``handler_mode="live"``).  The live
    service itself resolves the trusted ``storage_ref`` through
    ``DS3_STORAGE_ROOT``; DS1 never supplies a filesystem path.
    """

    def __init__(self, handler: DS3Handler | None = None, *, handler_mode: str | None = None) -> None:
        self._handler = handler
        # An empty value is common in local .env files.  It must retain the
        # safe default rather than making every dispatcher construction fail.
        self._handler_mode = handler_mode or os.getenv(DS3_HANDLER_MODE_ENV) or "mock"
        if self._handler_mode not in _HANDLER_MODES:
            raise ValueError(f"{DS3_HANDLER_MODE_ENV} must be one of: {', '.join(sorted(_HANDLER_MODES))}")

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
        if request.get("contract_version") == "ds3.v2" and self._handler_mode == "live":
            self._validate_live_storage_ref(request)
        response = self._resolve_handler(str(request["contract_version"]))(request)
        if not isinstance(response, Mapping):
            raise ToolContractError("DS3 handler must return an object")
        return normalize_ds3_response(response)

    @staticmethod
    def _validate_live_storage_ref(request: Mapping[str, Any]) -> None:
        """Allow live DS3 only for the exact backend-authorized card document."""

        context = request["context"]
        document = request.get("document")
        if not isinstance(document, Mapping):
            raise ToolContractError("DS3 live requires a document reference")
        card_id = context.get("card_id")
        document_id = document.get("document_id")
        expected = f"tradrly://cards/{card_id}/documents/{document_id}"
        if document.get("storage_ref") != expected:
            raise ToolContractError("DS3 live requires the active card's authorized storage_ref")

    def _resolve_handler(self, version: str) -> DS3Handler:
        if self._handler is not None:
            return self._handler
        try:
            if version == "ds3.v2":
                if self._handler_mode == "live":
                    from src.document_intelligence.service import handle_request
                    return handle_request
                from src.document_intelligence.contract.v2.mock import handle_request
                return handle_request
            from src.document_intelligence.contract.mock import handle_request
        except ImportError as error:
            raise ToolContractError("DS3 document-intelligence dependencies are not installed") from error
        return handle_request
