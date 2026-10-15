"""Run explicit salary-base and prime requests through the real DS5 handler."""

from __future__ import annotations

import json
from pathlib import Path
import sys

from .hybrid_dispatcher import HybridSpecialistDispatcher
from .models import ActiveContext, CardType, RequestEnvelope, UserIdentity
from .response_formatter import format_flow_result
from .state_machine import StateMachine, StructuredTrackBPlanner

_DEMO_PATH = Path("data/mock_cards/orchestrator_track_b_structured_demo.json")


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    cases = json.loads(_DEMO_PATH.read_text(encoding="utf-8"))
    for case in cases:
        card_type = CardType(case["card_type"])
        envelope = RequestEnvelope(
            request_id=case["request_id"], message=case["message"], language="fr",
            actor=UserIdentity("org-demo", "demo-user", "comptable", frozenset({"company-demo-001"})),
            context=ActiveContext("org-demo", "company-demo-001", card_type),
        )
        machine = StateMachine(
            HybridSpecialistDispatcher(),
            planner=StructuredTrackBPlanner(operation=case["operation"], params=case["params"]),
        )
        result = machine.run(envelope)
        print(json.dumps({
            "request_id": result.request_id,
            "state": result.state.value,
            "response": result.tool_response,
            "user_response": format_flow_result(result).to_payload(),
        }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
