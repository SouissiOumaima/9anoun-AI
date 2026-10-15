import json
from pathlib import Path

import pytest

from src.orchestrator.card_repository import MockCardRepository
from src.orchestrator.case_card import CaseCardValidationError, validate_case_card_references
from src.orchestrator.models import ActiveContext, CardType, RequestEnvelope, UserIdentity
from src.orchestrator.state_machine import FlowState, Planner, StateMachine
from src.orchestrator.track_a_requests import build_track_a_request_from_case_card


CARDS_PATH = Path("data/mock_cards/orchestrator_cards_demo.json")


def _case_card() -> dict:
    cards = json.loads(CARDS_PATH.read_text(encoding="utf-8"))
    return next(card for card in cards if card["card_id"] == "case-demo-001")


def test_demo_case_card_has_resolvable_fact_and_evidence_links() -> None:
    validate_case_card_references(_case_card())


def test_evidence_cannot_reference_a_document_outside_the_case() -> None:
    card = _case_card()
    card["data"]["evidence"][0]["document_id"] = "foreign-document"
    with pytest.raises(CaseCardValidationError, match="document_id"):
        validate_case_card_references(card)


def test_claim_cannot_reference_an_unknown_event() -> None:
    card = _case_card()
    card["data"]["claims"][0]["event_ids"] = ["missing-event"]
    with pytest.raises(CaseCardValidationError, match="event_ids"):
        validate_case_card_references(card)


def test_evidence_support_must_be_declared_by_the_fact() -> None:
    card = _case_card()
    card["data"]["claims"][0]["evidence_ids"] = []
    with pytest.raises(CaseCardValidationError, match="reciprocally"):
        validate_case_card_references(card)


def test_case_card_maps_to_a_cited_track_a_request() -> None:
    request = build_track_a_request_from_case_card(
        request_id="request-1", case_id="case-demo-001", language="fr", case_card=_case_card(),
    )
    assert request["parties"][0]["party_id"] == "party-employee-001"
    assert request["events"][1]["source_ids"] == ["evidence-termination-letter-001"]
    assert request["evidence"][0]["source"].endswith("citation=case-citation-001&page=1")


def test_planner_sends_case_card_facts_to_ds4() -> None:
    repository = MockCardRepository.from_payload(json.loads(CARDS_PATH.read_text(encoding="utf-8")))
    envelope = RequestEnvelope(
        request_id="case-flow-1", message="Analyse les preuves de ce dossier", language="fr",
        actor=UserIdentity("org-demo", "user-1", "lawyer", frozenset({"case-demo-001"})),
        context=ActiveContext("org-demo", "case-demo-001", CardType.CASE),
    )
    planner = Planner(case_card_provider=lambda request: repository.read_active_case_card(
        actor=request.actor, context=request.context,
    ))
    result = StateMachine(
        lambda payload: {"status": "success", "data": payload["params"], "citations": [], "error": None},
        planner=planner,
    ).run(envelope)
    request = result.tool_call.params["track_a_request"]
    assert result.state is FlowState.COMPLETED
    assert request["parties"]
    assert request["events"]
    assert request["claims"]
    assert request["evidence"]
