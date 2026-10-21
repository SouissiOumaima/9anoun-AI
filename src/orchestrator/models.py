"""Typed, transport-neutral models owned by the DS1 orchestration layer."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import FrozenSet, Mapping


class CardType(str, Enum):
    """The only card categories an orchestrated request may target."""

    COMPANY = "company"
    CLIENT = "client"
    CASE = "case"


class Intent(str, Enum):
    """Supported routing intents for the DS1 baseline parser."""

    LEGAL_RESEARCH = "legal_research"
    PAYROLL_CALCULATION = "payroll_calculation"
    DOCUMENT_ANALYSIS = "document_analysis"
    CASE_ANALYSIS = "case_analysis"
    GENERATE_DELIVERABLE = "generate_deliverable"
    CLARIFICATION_REQUIRED = "clarification_required"


@dataclass(frozen=True, slots=True)
class UserIdentity:
    """Backend-authenticated identity; it is never inferred from an LLM prompt."""

    organization_id: str
    user_id: str
    role: str
    authorized_card_ids: FrozenSet[str]


@dataclass(frozen=True, slots=True)
class ActiveContext:
    """The scoped card and optional entities available to one request."""

    organization_id: str
    card_id: str | None = None
    card_type: CardType | None = None
    entity_ids: Mapping[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        has_card = self.card_id is not None
        if has_card != (self.card_type is not None):
            raise ValueError("card_id and card_type must be supplied together")
        if not self.organization_id:
            raise ValueError("organization_id is required")


@dataclass(frozen=True, slots=True)
class RequestEnvelope:
    """Validated entry point for the future planner/state-machine pipeline."""

    request_id: str
    message: str
    language: str
    actor: UserIdentity
    context: ActiveContext

    def __post_init__(self) -> None:
        if not self.request_id:
            raise ValueError("request_id is required")
        if not self.message.strip():
            raise ValueError("message is required")
        if self.language not in {"fr", "ar"}:
            raise ValueError("language must be 'fr' or 'ar'")


@dataclass(frozen=True, slots=True)
class ParsedRequest:
    """Structured, non-authoritative interpretation of a user message.

    Entities are hints for the planner only. Access control continues to rely
    exclusively on ``UserIdentity`` and ``ActiveContext``.
    """

    intent: Intent
    language: str
    entities: Mapping[str, tuple[str, ...]]
    confidence: float
    needs_clarification: bool

    def __post_init__(self) -> None:
        if self.language not in {"fr", "ar"}:
            raise ValueError("language must be 'fr' or 'ar'")
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError("confidence must be between 0 and 1")
