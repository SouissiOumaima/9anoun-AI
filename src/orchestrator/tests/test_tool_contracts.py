import pytest

from src.orchestrator.models import ActiveContext, CardType, UserIdentity
from src.orchestrator.tool_contracts import ToolContractError, build_tool_call


def actor(*cards: str) -> UserIdentity:
    return UserIdentity("org-demo", "user-demo", "comptable", frozenset(cards))


def test_legal_search_allows_general_question_without_card() -> None:
    call = build_tool_call(
        tool_call_id="call-1", request_id="request-1", actor=actor(), context=ActiveContext("org-demo"),
        agent="legal_retrieval", operation="search", params={"query": "préavis"},
    )
    assert call.read_only is True
    assert call.to_payload()["context"] == {"organization_id": "org-demo"}


def test_track_b_call_requires_authorized_company_or_client_card() -> None:
    context = ActiveContext("org-demo", "company-1", CardType.COMPANY)
    call = build_tool_call(
        tool_call_id="call-2", request_id="request-2", actor=actor("company-1"), context=context,
        agent="track_b_accounting", operation="compute", params={"operation": "smig"},
    )
    assert call.agent == "track_b_accounting"


def test_track_a_call_rejects_company_card() -> None:
    context = ActiveContext("org-demo", "company-1", CardType.COMPANY)
    with pytest.raises(ToolContractError, match="requires one of: case"):
        build_tool_call(
            tool_call_id="call-3", request_id="request-3", actor=actor("company-1"), context=context,
            agent="track_a_legal", operation="analyze_case", params={},
        )


def test_unknown_agent_operation_is_rejected() -> None:
    with pytest.raises(ToolContractError, match="not allow-listed"):
        build_tool_call(
            tool_call_id="call-4", request_id="request-4", actor=actor(), context=ActiveContext("org-demo"),
            agent="untrusted_agent", operation="write", params={},
        )


def test_unauthorized_card_is_rejected_before_tool_call() -> None:
    context = ActiveContext("org-demo", "company-1", CardType.COMPANY)
    with pytest.raises(PermissionError, match="not authorized"):
        build_tool_call(
            tool_call_id="call-5", request_id="request-5", actor=actor(), context=context,
            agent="track_b_accounting", operation="compute", params={},
        )


def test_params_must_be_json_serializable() -> None:
    with pytest.raises(ToolContractError, match="JSON serializable"):
        build_tool_call(
            tool_call_id="call-6", request_id="request-6", actor=actor(), context=ActiveContext("org-demo"),
            agent="legal_retrieval", operation="search", params={"query": {1, 2}},
        )
