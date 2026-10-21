"""Human approval gate for future consequential actions.

DS1 v0 tools are read-only. This module prepares the mandatory approval and
idempotency boundary before write-capable adapters are introduced.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from threading import RLock
from typing import Any, Callable, Mapping
from uuid import uuid4

from .audit import AuditEvent, AuditTrail, _utc_now, fingerprint
from .models import ActiveContext, UserIdentity


class ApprovalStatus(str, Enum):
    PENDING = "pending_approval"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXECUTED = "executed"


class ApprovalError(ValueError):
    """A proposed action has an invalid or unsafe approval transition."""


@dataclass(frozen=True, slots=True)
class PendingAction:
    approval_id: str
    request_id: str
    organization_id: str
    requested_by: str
    card_id: str | None
    action_type: str
    summary: str
    idempotency_key: str
    status: ApprovalStatus = ApprovalStatus.PENDING


ActionExecutor = Callable[[PendingAction], Mapping[str, Any]]


class ApprovalWorkflow:
    """In-memory approval store with same-user and same-organization checks."""

    def __init__(self, audit_trail: AuditTrail) -> None:
        self._audit = audit_trail
        self._actions: dict[str, PendingAction] = {}
        self._executed_by_key: dict[str, Mapping[str, Any]] = {}
        self._lock = RLock()

    def propose(
        self,
        *,
        request_id: str,
        actor: UserIdentity,
        context: ActiveContext,
        action_type: str,
        summary: str,
        idempotency_key: str,
    ) -> PendingAction:
        with self._lock:
            if not all((request_id, action_type, summary.strip(), idempotency_key)):
                raise ApprovalError("request_id, action_type, summary and idempotency_key are required")
            if actor.organization_id != context.organization_id:
                raise ApprovalError("organization mismatch")
            if any(existing.idempotency_key == idempotency_key for existing in self._actions.values()):
                raise ApprovalError("idempotency_key has already been proposed")
            action = PendingAction(str(uuid4()), request_id, actor.organization_id, actor.user_id,
                                   context.card_id, action_type, summary, idempotency_key)
            self._actions[action.approval_id] = action
            self._record(action, "approval_proposed")
            return action

    def approve(self, approval_id: str, actor: UserIdentity) -> PendingAction:
        with self._lock:
            return self._transition(approval_id, actor, ApprovalStatus.APPROVED)

    def reject(self, approval_id: str, actor: UserIdentity) -> PendingAction:
        with self._lock:
            return self._transition(approval_id, actor, ApprovalStatus.REJECTED)

    def execute(self, approval_id: str, actor: UserIdentity, executor: ActionExecutor) -> Mapping[str, Any]:
        with self._lock:
            action = self._get_for_actor(approval_id, actor)
            if action.status is ApprovalStatus.EXECUTED:
                return self._executed_by_key[action.idempotency_key]
            if action.status is not ApprovalStatus.APPROVED:
                raise ApprovalError("only an approved action may be executed")
            if action.idempotency_key in self._executed_by_key:
                return self._executed_by_key[action.idempotency_key]

            result = dict(executor(action))
            self._executed_by_key[action.idempotency_key] = result
            executed = self._replace_status(action, ApprovalStatus.EXECUTED)
            self._record(executed, "action_executed")
            return result

    def get(self, approval_id: str) -> PendingAction:
        with self._lock:
            try:
                return self._actions[approval_id]
            except KeyError as error:
                raise ApprovalError("approval was not found") from error

    def list_for_actor(self, actor: UserIdentity) -> tuple[PendingAction, ...]:
        """List only the requesting user's actions in the same organization."""

        with self._lock:
            return tuple(
                action for action in self._actions.values()
                if action.organization_id == actor.organization_id and action.requested_by == actor.user_id
            )

    def _transition(self, approval_id: str, actor: UserIdentity, target: ApprovalStatus) -> PendingAction:
        action = self._get_for_actor(approval_id, actor)
        if action.status is not ApprovalStatus.PENDING:
            raise ApprovalError("only a pending action may be approved or rejected")
        updated = self._replace_status(action, target)
        self._record(updated, f"approval_{target.value}")
        return updated

    def _get_for_actor(self, approval_id: str, actor: UserIdentity) -> PendingAction:
        action = self.get(approval_id)
        if actor.organization_id != action.organization_id or actor.user_id != action.requested_by:
            raise ApprovalError("only the requesting user in the same organization may approve this action")
        return action

    def _replace_status(self, action: PendingAction, status: ApprovalStatus) -> PendingAction:
        updated = PendingAction(
            action.approval_id, action.request_id, action.organization_id, action.requested_by,
            action.card_id, action.action_type, action.summary, action.idempotency_key, status,
        )
        self._actions[action.approval_id] = updated
        return updated

    def _record(self, action: PendingAction, event_type: str) -> None:
        self._audit.record(AuditEvent(
            event_type=event_type,
            occurred_at=_utc_now(),
            request_id=action.request_id,
            organization_id=action.organization_id,
            user_id=action.requested_by,
            card_id=action.card_id,
            details={
                "approval_id": action.approval_id,
                "action_type": action.action_type,
                "status": action.status.value,
                "summary_sha256": fingerprint(action.summary),
                "idempotency_key_sha256": fingerprint(action.idempotency_key),
            },
        ))
