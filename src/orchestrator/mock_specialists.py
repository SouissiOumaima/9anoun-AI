"""Temporary specialist-agent doubles for DS1 integration tests and demos."""

from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
from typing import Any, Mapping

from .tool_contracts import ToolContractError

DEFAULT_RESPONSES_PATH = Path("data/mock_cards/orchestrator_agent_responses_demo.json")


class MockSpecialistDispatcher:
    """Route allow-listed DS1 tool calls to stable, JSON-defined mock replies."""

    def __init__(self, responses: Mapping[str, Mapping[str, Any]]) -> None:
        self._responses = {key: deepcopy(value) for key, value in responses.items()}

    @classmethod
    def from_file(cls, path: Path = DEFAULT_RESPONSES_PATH) -> "MockSpecialistDispatcher":
        return cls(json.loads(path.read_text(encoding="utf-8")))

    def __call__(self, payload: Mapping[str, Any]) -> Mapping[str, Any]:
        key = f"{payload.get('agent')}.{payload.get('operation')}"
        if key not in self._responses:
            raise ToolContractError("no mock response exists for this agent operation")
        if payload.get("agent") == "track_b_accounting" and not payload.get("params", {}).get("track_b_request"):
            raise ToolContractError("Track B mock requires a track_b_request")
        return deepcopy(self._responses[key])
