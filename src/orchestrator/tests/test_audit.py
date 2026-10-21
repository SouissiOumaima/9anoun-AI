from src.orchestrator.audit import AuditTrail
from src.orchestrator.models import ActiveContext, RequestEnvelope, UserIdentity
from src.orchestrator.state_machine import StateMachine


def test_flow_audit_masks_message_and_tool_params() -> None:
    audit = AuditTrail()
    envelope = RequestEnvelope(
        request_id="request-audit", message="Secret salary is 9000 TND", language="fr",
        actor=UserIdentity("org-1", "user-1", "comptable", frozenset()), context=ActiveContext("org-1"),
    )
    machine = StateMachine(
        lambda _: {"status": "success", "data": {}, "citations": [], "error": None}, audit_hook=audit.record_flow,
    )
    machine.run(envelope)
    event = audit.export()[0]
    serialized = str(event)
    assert event["event_type"] == "flow_completed"
    assert event["details"]["message_sha256"]
    assert "Secret salary" not in serialized
    assert "9000" not in serialized
