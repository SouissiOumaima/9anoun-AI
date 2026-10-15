"""Versioned DS1 contracts for calling specialized agents.

The registry is deliberately allow-listed. A planner can select from these
operations but cannot invent an agent, operation, context, or write action.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Mapping

from .context import resolve_context
from .models import ActiveContext, CardType, UserIdentity


class ToolContractError(ValueError):
    """The planned call violates the DS1 tool contract."""


@dataclass(frozen=True, slots=True)
class ToolDefinition:
    agent: str
    operation: str
    allowed_card_types: frozenset[CardType] | None
    read_only: bool = True


TOOL_REGISTRY: dict[tuple[str, str], ToolDefinition] = {
    ("legal_retrieval", "search"): ToolDefinition("legal_retrieval", "search", None),
    ("legal_retrieval", "get_article"): ToolDefinition("legal_retrieval", "get_article", None),
    ("document_intelligence", "analyze_document"): ToolDefinition(
        "document_intelligence", "analyze_document", frozenset(CardType)
    ),
    ("document_intelligence", "extract_wage_grid"): ToolDefinition(
        "document_intelligence", "extract_wage_grid", frozenset(CardType)
    ),
    ("track_a_legal", "analyze_case"): ToolDefinition(
        "track_a_legal", "analyze_case", frozenset({CardType.CASE})
    ),
    ("track_b_accounting", "compute"): ToolDefinition(
        "track_b_accounting", "compute", frozenset({CardType.COMPANY, CardType.CLIENT})
    ),
}


@dataclass(frozen=True, slots=True)
class ToolCall:
    """A scoped request ready for an approved specialized-agent adapter."""

    tool_call_id: str
    request_id: str
    agent: str
    operation: str
    context: ActiveContext
    params: Mapping[str, Any]
    read_only: bool = True
    contract_version: str = "orchestrator.tool.v0"

    def to_payload(self) -> dict[str, Any]:
        """Produce the JSON-safe transport payload; permissions stay backend-side."""

        context: dict[str, Any] = {"organization_id": self.context.organization_id}
        if self.context.card_id is not None:
            context.update({"card_id": self.context.card_id, "card_type": self.context.card_type.value})
        if self.context.entity_ids:
            context["entity_ids"] = dict(self.context.entity_ids)
        return {
            "contract_version": self.contract_version,
            "tool_call_id": self.tool_call_id,
            "request_id": self.request_id,
            "agent": self.agent,
            "operation": self.operation,
            "read_only": self.read_only,
            "context": context,
            "params": dict(self.params),
        }


def build_tool_call(
    *,
    tool_call_id: str,
    request_id: str,
    actor: UserIdentity,
    context: ActiveContext,
    agent: str,
    operation: str,
    params: Mapping[str, Any],
) -> ToolCall:
    """Validate and build one allow-listed, read-only specialized-agent call."""

    if not tool_call_id or not request_id:
        raise ToolContractError("tool_call_id and request_id are required")
    try:
        definition = TOOL_REGISTRY[(agent, operation)]
    except KeyError as error:
        raise ToolContractError("agent operation is not allow-listed") from error

    resolve_context(actor=actor, context=context)
    if definition.allowed_card_types is not None and context.card_type not in definition.allowed_card_types:
        allowed = ", ".join(sorted(card_type.value for card_type in definition.allowed_card_types))
        raise ToolContractError(f"{agent}.{operation} requires one of: {allowed}")

    try:
        json.dumps(params, ensure_ascii=False)
    except (TypeError, ValueError) as error:
        raise ToolContractError("params must be JSON serializable") from error

    return ToolCall(tool_call_id, request_id, agent, operation, context, dict(params), definition.read_only)
