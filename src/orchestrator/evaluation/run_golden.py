"""Run the DS1 FR/AR golden set against the current parser and planner."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

from src.orchestrator.mock_specialists import MockSpecialistDispatcher
from src.orchestrator.models import ActiveContext, CardType, RequestEnvelope, UserIdentity
from src.orchestrator.state_machine import Planner, StateMachine


GOLDEN_SET_PATH = Path(__file__).with_name("golden_set.v0.json")
_CARD_IDS = {CardType.COMPANY: "golden-company", CardType.CLIENT: "golden-client", CardType.CASE: "golden-case"}


def _envelope(case: Mapping[str, Any]) -> RequestEnvelope:
    card_type = CardType(case["card_type"]) if case["card_type"] else None
    card_id = _CARD_IDS.get(card_type)
    return RequestEnvelope(
        request_id=f"golden-{case['id']}",
        message=case["message"],
        language=case["language"],
        actor=UserIdentity("golden-org", "golden-user", "evaluator", frozenset(_CARD_IDS.values())),
        context=ActiveContext("golden-org", card_id, card_type),
    )


def _golden_case_card(envelope: RequestEnvelope) -> dict[str, Any]:
    """Small cited Case Card used only for routing evaluation, never as legal data."""

    case_id = envelope.context.card_id
    return {
        "card_id": case_id, "organization_id": envelope.context.organization_id, "card_type": "case",
        "data": {
            "title": "Golden case", "jurisdiction": "TN",
            "documents": [{"document_id": "golden-doc", "label": "Pièce", "file_name": "piece.pdf",
                           "mime_type": "application/pdf", "storage_ref": "golden://doc"}],
            "parties": [{"party_id": "golden-party", "name": "Partie test", "role": "employee",
                         "party_type": "physical_person"}],
            "events": [{"event_id": "golden-event", "date": "2024-01-01", "date_precision": "exact",
                        "description": "Événement de test.", "evidence_ids": ["golden-evidence"], "confidence": 1.0}],
            "claims": [],
            "evidence": [{"evidence_id": "golden-evidence", "document_id": "golden-doc", "type": "document",
                          "description": "Preuve de test.", "citation": {"citation_id": "golden-citation", "page": 1,
                          "excerpt": "Texte de test."}, "confidence": 1.0,
                          "supports": [{"fact_type": "event", "fact_id": "golden-event"}]}],
        },
    }


def run_golden_set(path: Path = GOLDEN_SET_PATH) -> dict[str, Any]:
    """Return metrics and failed case details; no external agent is contacted."""

    cases = json.loads(path.read_text(encoding="utf-8"))
    machine = StateMachine(
        MockSpecialistDispatcher.from_file(), planner=Planner(case_card_provider=_golden_case_card),
    )
    failures: list[dict[str, Any]] = []
    intent_ok = language_ok = flow_ok = 0

    for case in cases:
        result = machine.run(_envelope(case))
        actual_intent = result.parsed.intent.value if result.parsed else None
        actual_language = result.parsed.language if result.parsed else None
        actual_agent = result.tool_call.agent if result.tool_call else None
        checks = {
            "intent": actual_intent == case["intent"],
            "language": actual_language == case["language"],
            "flow": result.state.value == case["state"] and actual_agent == case["agent"],
        }
        intent_ok += checks["intent"]
        language_ok += checks["language"]
        flow_ok += checks["flow"]
        if not all(checks.values()):
            failures.append({
                "id": case["id"], "checks": checks,
                "actual": {"intent": actual_intent, "language": actual_language,
                           "state": result.state.value, "agent": actual_agent, "reason": result.reason},
            })

    total = len(cases)
    return {
        "golden_set_version": "ds1.v0",
        "cases": total,
        "intent_accuracy": intent_ok / total if total else 0.0,
        "language_accuracy": language_ok / total if total else 0.0,
        "flow_accuracy": flow_ok / total if total else 0.0,
        "failures": failures,
        "passed": not failures,
    }


if __name__ == "__main__":
    report = run_golden_set()
    print(json.dumps(report, ensure_ascii=False, indent=2))
    raise SystemExit(0 if report["passed"] else 1)
