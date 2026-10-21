"""Privacy-conscious in-memory audit trail owned by DS1.

It stores operational metadata, hashes of free text, and no card payloads or
tool parameters. A production sink can persist the same event contract.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from hashlib import sha256
from threading import Lock
from typing import Any, Mapping

from .models import RequestEnvelope


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def fingerprint(value: str) -> str:
    """Return a stable SHA-256 fingerprint without retaining the raw value."""

    return sha256(value.encode("utf-8")).hexdigest()


@dataclass(frozen=True, slots=True)
class AuditEvent:
    event_type: str
    occurred_at: str
    request_id: str
    organization_id: str
    user_id: str
    card_id: str | None
    details: Mapping[str, Any]


class AuditTrail:
    """Append-only audit events with a JSON-safe export for tests/adapters."""

    def __init__(self) -> None:
        self._events: list[AuditEvent] = []
        self._lock = Lock()

    def record(self, event: AuditEvent) -> None:
        with self._lock:
            self._events.append(event)

    def record_flow(self, envelope: RequestEnvelope, result: Any) -> None:
        """Record only routing metadata from a completed state-machine run."""

        tool_call = result.tool_call
        track_b_request = tool_call.params.get("track_b_request", {}) if tool_call else {}
        domain_operation = track_b_request.get("operation") if isinstance(track_b_request, Mapping) else None
        self.record(AuditEvent(
            event_type="flow_completed",
            occurred_at=_utc_now(),
            request_id=envelope.request_id,
            organization_id=envelope.actor.organization_id,
            user_id=envelope.actor.user_id,
            card_id=envelope.context.card_id,
            details={
                "message_sha256": fingerprint(envelope.message),
                "message_length": len(envelope.message),
                "final_state": result.state.value,
                "states": [state.value for state in result.states],
                "intent": result.parsed.intent.value if result.parsed else None,
                "agent": tool_call.agent if tool_call else None,
                "operation": tool_call.operation if tool_call else None,
                "domain_operation": domain_operation,
                "attempts": result.attempts,
                "reason": result.reason,
            },
        ))

    def events(self) -> tuple[AuditEvent, ...]:
        with self._lock:
            return tuple(self._events)

    def export(self) -> list[dict[str, Any]]:
        return [asdict(event) for event in self.events()]
