import pytest

from src.orchestrator.context import ContextResolutionError, resolve_context
from src.orchestrator.models import ActiveContext, CardType, UserIdentity


def actor() -> UserIdentity:
    return UserIdentity(
        organization_id="org-a",
        user_id="user-1",
        role="comptable",
        authorized_card_ids=frozenset({"company-a"}),
    )


def test_authorized_card_context_is_returned() -> None:
    context = ActiveContext("org-a", "company-a", CardType.COMPANY)
    assert resolve_context(actor=actor(), context=context) is context


def test_general_question_without_card_is_allowed() -> None:
    context = ActiveContext("org-a")
    assert resolve_context(actor=actor(), context=context) is context


def test_cross_organization_context_is_rejected() -> None:
    with pytest.raises(ContextResolutionError, match="organization mismatch"):
        resolve_context(actor=actor(), context=ActiveContext("org-b"))


def test_unauthorized_card_context_is_rejected() -> None:
    context = ActiveContext("org-a", "company-b", CardType.COMPANY)
    with pytest.raises(ContextResolutionError, match="not authorized"):
        resolve_context(actor=actor(), context=context)


def test_partial_card_definition_is_rejected() -> None:
    with pytest.raises(ValueError, match="supplied together"):
        ActiveContext("org-a", card_id="company-a")
