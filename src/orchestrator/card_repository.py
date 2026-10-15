"""Read-only mock card access behind DS1 authorization checks.

This is the Database Agent v1 seam: production adapters can replace this
repository, but must retain its actor/context authorization boundary.
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from typing import Any, Iterable, Mapping

from .context import ContextResolutionError, resolve_context
from .case_card import CaseCardValidationError, validate_case_card_references
from .models import ActiveContext, CardType, UserIdentity


class CardNotFoundError(LookupError):
    """The requested card does not exist in the configured data source."""


@dataclass(frozen=True, slots=True)
class CardRecord:
    card_id: str
    organization_id: str
    card_type: CardType
    data: Mapping[str, Any]


class MockCardRepository:
    """In-memory, read-only card repository used before the approved DB API exists."""

    def __init__(self, cards: Iterable[CardRecord]) -> None:
        self._cards = {card.card_id: card for card in cards}

    @classmethod
    def from_payload(cls, payload: Iterable[Mapping[str, Any]]) -> "MockCardRepository":
        """Build the mock repository from JSON-compatible test data."""

        cards = (
            CardRecord(
                card_id=str(item["card_id"]),
                organization_id=str(item["organization_id"]),
                card_type=CardType(str(item["card_type"])),
                data=deepcopy(item["data"]),
            )
            for item in payload
        )
        return cls(cards)

    def read_active_card(self, *, actor: UserIdentity, context: ActiveContext) -> CardRecord:
        """Read exactly the active card; no listing, search, or cross-card join."""

        resolve_context(actor=actor, context=context)
        if context.card_id is None:
            raise ContextResolutionError("an active card is required for card data access")

        try:
            card = self._cards[context.card_id]
        except KeyError as error:
            raise CardNotFoundError("active card was not found") from error

        if card.organization_id != context.organization_id or card.card_type is not context.card_type:
            raise ContextResolutionError("active context does not match stored card")

        # Return a detached value so callers cannot mutate the repository's state.
        return CardRecord(card.card_id, card.organization_id, card.card_type, deepcopy(card.data))

    def read_active_case_card(self, *, actor: UserIdentity, context: ActiveContext) -> Mapping[str, Any]:
        """Return one validated structured Case Card from the active context only."""

        record = self.read_active_card(actor=actor, context=context)
        if record.card_type is not CardType.CASE:
            raise ContextResolutionError("an active Case Card is required")
        card = {
            "card_id": record.card_id,
            "organization_id": record.organization_id,
            "card_type": record.card_type.value,
            "data": deepcopy(record.data),
        }
        try:
            validate_case_card_references(card)
        except CaseCardValidationError as error:
            raise ContextResolutionError("the active Case Card is incomplete or inconsistent") from error
        return card
