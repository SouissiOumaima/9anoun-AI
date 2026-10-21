"""Adapter between the DS1 tool envelope and the Track B v0 contract."""

from __future__ import annotations

from typing import Any, Callable, Mapping

from .tool_contracts import ToolContractError

TrackBHandler = Callable[[Mapping[str, Any]], Mapping[str, Any]]


class TrackBAdapter:
    """Execute one validated ``track_b.v0`` request and normalize its response.

    The Track B handler is injected so DS1 tests do not depend on optional
    Track B packages. Production can instantiate this class without an argument
    once the Track B dependencies are installed.
    """

    def __init__(self, handler: TrackBHandler | None = None) -> None:
        self._handler = handler

    def __call__(self, payload: Mapping[str, Any]) -> Mapping[str, Any]:
        if payload.get("agent") != "track_b_accounting" or payload.get("operation") != "compute":
            raise ToolContractError("Track B adapter only accepts track_b_accounting.compute")
        request = payload.get("params", {}).get("track_b_request")
        if not isinstance(request, Mapping):
            raise ToolContractError("Track B call requires a track_b_request object")
        if request.get("contract_version") != "track_b.v0":
            raise ToolContractError("Track B request must use track_b.v0")
        if request.get("request_id") != payload.get("request_id"):
            raise ToolContractError("Track B request_id must match the orchestrator request")

        response = dict(self._resolve_handler()(request))
        status = response.get("status")
        if status == "ok":
            if not response.get("citations") or response.get("result") is None:
                raise ToolContractError("Track B ok response requires result and citations")
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
        raise ToolContractError("Track B response has an invalid status")

    def _resolve_handler(self) -> TrackBHandler:
        if self._handler is not None:
            return self._handler
        try:
            from src.track_b_accounting.contract.handler import handle
        except ImportError as error:
            raise ToolContractError("Track B dependencies are not installed") from error
        return handle
