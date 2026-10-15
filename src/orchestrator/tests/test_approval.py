import pytest

from src.orchestrator.approval import ApprovalError, ApprovalStatus, ApprovalWorkflow
from src.orchestrator.audit import AuditTrail
from src.orchestrator.models import ActiveContext, CardType, UserIdentity


def actor(user_id: str = "user-1", organization_id: str = "org-1") -> UserIdentity:
    return UserIdentity(organization_id, user_id, "lawyer", frozenset({"case-1"}))


def proposed(workflow: ApprovalWorkflow):
    return workflow.propose(
        request_id="request-1", actor=actor(), context=ActiveContext("org-1", "case-1", CardType.CASE),
        action_type="generate_letter", summary="Generate a legal letter", idempotency_key="request-1:letter-v1",
    )


def test_action_needs_approval_before_execution() -> None:
    workflow = ApprovalWorkflow(AuditTrail())
    action = proposed(workflow)
    with pytest.raises(ApprovalError, match="only an approved"):
        workflow.execute(action.approval_id, actor(), lambda _: {"document_id": "doc-1"})


def test_requesting_user_can_approve_and_execute_once() -> None:
    workflow = ApprovalWorkflow(AuditTrail())
    action = workflow.approve(proposed(workflow).approval_id, actor())
    assert action.status is ApprovalStatus.APPROVED
    calls = []
    result = workflow.execute(action.approval_id, actor(), lambda item: calls.append(item) or {"document_id": "doc-1"})
    repeated = workflow.execute(action.approval_id, actor(), lambda _: {"document_id": "doc-2"})
    assert result == repeated == {"document_id": "doc-1"}
    assert len(calls) == 1
    assert workflow.get(action.approval_id).status is ApprovalStatus.EXECUTED


def test_other_user_or_organization_cannot_approve() -> None:
    workflow = ApprovalWorkflow(AuditTrail())
    action = proposed(workflow)
    with pytest.raises(ApprovalError, match="only the requesting user"):
        workflow.approve(action.approval_id, actor("user-2"))
    with pytest.raises(ApprovalError, match="only the requesting user"):
        workflow.approve(action.approval_id, actor("user-1", "org-2"))


def test_rejected_action_cannot_execute() -> None:
    workflow = ApprovalWorkflow(AuditTrail())
    action = workflow.reject(proposed(workflow).approval_id, actor())
    assert action.status is ApprovalStatus.REJECTED
    with pytest.raises(ApprovalError, match="only an approved"):
        workflow.execute(action.approval_id, actor(), lambda _: {})


def test_idempotency_key_cannot_create_a_second_action() -> None:
    workflow = ApprovalWorkflow(AuditTrail())
    proposed(workflow)
    with pytest.raises(ApprovalError, match="already been proposed"):
        proposed(workflow)
