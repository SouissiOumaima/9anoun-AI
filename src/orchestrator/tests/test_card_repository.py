import json
from pathlib import Path

import pytest

from src.orchestrator.card_repository import CardNotFoundError, MockCardRepository
from src.orchestrator.context import ContextResolutionError
from src.orchestrator.models import ActiveContext, CardType, UserIdentity


CARDS_PATH = Path("data/mock_cards/orchestrator_cards_demo.json")


@pytest.fixture()
def repository() -> MockCardRepository:
    return MockCardRepository.from_payload(json.loads(CARDS_PATH.read_text(encoding="utf-8")))


def actor(*card_ids: str) -> UserIdentity:
    return UserIdentity("org-demo", "user-demo", "comptable", frozenset(card_ids))


def context(card_id: str = "company-demo-001") -> ActiveContext:
    return ActiveContext("org-demo", card_id, CardType.COMPANY)


def test_authorized_actor_can_read_exact_active_card(repository: MockCardRepository) -> None:
    card = repository.read_active_card(actor=actor("company-demo-001"), context=context())
    assert card.card_id == "company-demo-001"
    assert card.data["employees"][0]["employee_id"] == "employee-demo-01"


def test_actor_cannot_read_a_card_not_in_permissions(repository: MockCardRepository) -> None:
    with pytest.raises(ContextResolutionError, match="not authorized"):
        repository.read_active_card(actor=actor(), context=context())


def test_no_card_means_no_card_data_access(repository: MockCardRepository) -> None:
    with pytest.raises(ContextResolutionError, match="active card is required"):
        repository.read_active_card(actor=actor(), context=ActiveContext("org-demo"))


def test_unknown_card_is_not_exposed(repository: MockCardRepository) -> None:
    unknown = ActiveContext("org-demo", "company-unknown", CardType.COMPANY)
    with pytest.raises(CardNotFoundError):
        repository.read_active_card(actor=actor("company-unknown"), context=unknown)


def test_returned_data_cannot_mutate_repository(repository: MockCardRepository) -> None:
    allowed = actor("company-demo-001")
    first = repository.read_active_card(actor=allowed, context=context())
    first.data["employees"][0]["name"] = "Modified"
    second = repository.read_active_card(actor=allowed, context=context())
    assert second.data["employees"][0]["name"] == "Ahmed"
