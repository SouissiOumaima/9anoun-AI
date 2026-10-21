"""Demonstrate an authorized Company Card → real DS5 salary-base flow."""

from __future__ import annotations

import json
from pathlib import Path
import sys

from .card_repository import MockCardRepository
from .card_to_track_b import CardToTrackBMapper
from .hybrid_dispatcher import HybridSpecialistDispatcher
from .models import ActiveContext, CardType, RequestEnvelope, UserIdentity
from .response_formatter import format_flow_result
from .state_machine import StateMachine, StructuredTrackBPlanner


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    cards = json.loads(Path("data/mock_cards/orchestrator_cards_demo.json").read_text(encoding="utf-8"))
    repository = MockCardRepository.from_payload(cards)
    actor = UserIdentity("org-demo", "demo-user", "comptable", frozenset({"company-demo-001"}))
    context = ActiveContext("org-demo", "company-demo-001", CardType.COMPANY)
    prepared = CardToTrackBMapper(repository).prepare_salary_base(
        actor=actor, context=context, employee_id="employee-demo-01", date="2022-06-01"
    )
    if not prepared.ready:
        print(json.dumps({"status": "clarification_required", "missing": prepared.missing}, ensure_ascii=False))
        return
    envelope = RequestEnvelope("card-track-b-demo", "Calcule le salaire de base de cet employé.", "fr", actor, context)
    result = StateMachine(
        HybridSpecialistDispatcher(),
        planner=StructuredTrackBPlanner(operation=prepared.operation, params=prepared.params),
    ).run(envelope)
    print(json.dumps({
        "prepared_params": prepared.params,
        "response": result.tool_response,
        "user_response": format_flow_result(result).to_payload(),
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
