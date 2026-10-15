"""Adapter between the DS1 tool envelope and the DS4 Track A v0 contract."""

from __future__ import annotations

from typing import Any, Callable, Mapping

from .tool_contracts import ToolContractError

TrackAHandler = Callable[[Mapping[str, Any]], Mapping[str, Any]]


class TrackAAdapter:
    """Execute DS4's case-analysis handler and normalize its response for DS1."""

    def __init__(self, handler: TrackAHandler | None = None) -> None:
        self._handler = handler

    def __call__(self, payload: Mapping[str, Any]) -> Mapping[str, Any]:
        if payload.get("agent") != "track_a_legal" or payload.get("operation") != "analyze_case":
            raise ToolContractError("Track A adapter only accepts track_a_legal.analyze_case")
        request = payload.get("params", {}).get("track_a_request")
        if not isinstance(request, Mapping):
            raise ToolContractError("Track A call requires a track_a_request object")
        if request.get("contract_version") != "track_a.v0":
            raise ToolContractError("Track A request must use track_a.v0")
        if request.get("request_id") != payload.get("request_id"):
            raise ToolContractError("Track A request_id must match the orchestrator request")
        if request.get("case_id") != payload.get("context", {}).get("card_id"):
            raise ToolContractError("Track A case_id must match the active Case Card")

        response = dict(self._resolve_handler()(request))
        status = response.get("status")
        if status == "ok":
            if response.get("result") is None or not response.get("citations"):
                raise ToolContractError("Track A ok response requires result and citations")
            return {
                "status": "success",
                "data": {"result": response["result"], "computed_by": response.get("computed_by")},
                "citations": response["citations"],
                "error": None,
            }
        if status == "refus":
            return {"status": "refused", "data": None, "citations": [], "error": response.get("refus")}
        if status == "erreur":
            return {"status": "error", "data": None, "citations": [], "error": response.get("erreur")}
        raise ToolContractError("Track A response has an invalid status")

    def _resolve_handler(self) -> TrackAHandler:
        if self._handler is not None:
            return self._handler
        try:
            from src.track_a_legal.handler import handle
        except ImportError as error:
            raise ToolContractError("DS4 Track A dependencies are not installed") from error
        return handle
