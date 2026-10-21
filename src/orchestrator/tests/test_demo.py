import pytest

from src.orchestrator.demo import build_demo_envelope
from src.orchestrator.mock_specialists import MockSpecialistDispatcher
from src.orchestrator.models import CardType


def test_demo_envelope_uses_requested_mock_card() -> None:
    envelope = build_demo_envelope("Calcule le salaire", "company")
    assert envelope.context.card_type is CardType.COMPANY
    assert envelope.context.card_id == "company-demo-001"


def test_demo_rejects_unknown_card() -> None:
    with pytest.raises(ValueError, match="company"):
        build_demo_envelope("Question", "unknown")


def test_demo_dispatcher_returns_contract_like_response() -> None:
    result = MockSpecialistDispatcher.from_file()({"agent": "legal_retrieval", "operation": "search", "params": {}})
    assert result["status"] == "success"
    assert result["data"]["findings"]
