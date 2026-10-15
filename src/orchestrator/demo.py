"""Interactive local demo for the current DS1 flow.

Run from the repository root with ``python -m src.orchestrator.demo``.
All specialized-agent responses are deliberately mocked; no external service or
real card data is used.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from .card_repository import MockCardRepository
from .hybrid_dispatcher import HybridSpecialistDispatcher
from .models import ActiveContext, CardType, RequestEnvelope, UserIdentity
from .response_formatter import format_flow_result
from .state_machine import Planner, StateMachine

_DEMO_CARDS = {
    "company": "company-demo-001",
    "client": "client-demo-001",
    "case": "case-demo-001",
}


def build_demo_envelope(message: str, card_choice: str = "") -> RequestEnvelope:
    """Build a fully authorized fictitious request for local exploration."""

    normalized = card_choice.strip().lower()
    if normalized and normalized not in _DEMO_CARDS:
        raise ValueError("card must be empty, company, client, or case")
    card_type = CardType(normalized) if normalized else None
    card_id = _DEMO_CARDS.get(normalized)
    return RequestEnvelope(
        request_id="local-demo-request",
        message=message,
        language="ar" if any("\u0600" <= char <= "\u06ff" for char in message) else "fr",
        actor=UserIdentity(
            organization_id="org-demo",
            user_id="local-demo-user",
            role="demo",
            authorized_card_ids=frozenset(_DEMO_CARDS.values()),
        ),
        context=ActiveContext("org-demo", card_id, card_type),
    )


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    print("9anoun DS1 - local mock demo")
    print("Card: leave empty for a general legal question; otherwise company / client / case.")
    message = input("Your question: ").strip()
    card_choice = input("Active card: ").strip()
    try:
        cards = json.loads(Path("data/mock_cards/orchestrator_cards_demo.json").read_text(encoding="utf-8"))
        repository = MockCardRepository.from_payload(cards)
        planner = Planner(case_card_provider=lambda envelope: repository.read_active_case_card(
            actor=envelope.actor, context=envelope.context,
        ))
        result = StateMachine(HybridSpecialistDispatcher(), planner=planner).run(
            build_demo_envelope(message, card_choice)
        )
    except ValueError as error:
        print(f"Invalid input: {error}")
        return

    output = {
        "final_state": result.state.value,
        "states": [state.value for state in result.states],
        "intent": result.parsed.intent.value if result.parsed else None,
        "entities": result.parsed.entities if result.parsed else {},
        "tool": f"{result.tool_call.agent}.{result.tool_call.operation}" if result.tool_call else None,
        "response": result.tool_response,
        "user_response": format_flow_result(result).to_payload(),
    }
    print(json.dumps(output, ensure_ascii=False, indent=2, default=list))


if __name__ == "__main__":
    main()
