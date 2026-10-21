import json
from pathlib import Path

import pytest

from src.orchestrator.card_repository import MockCardRepository
from src.orchestrator.card_to_track_b import CardToTrackBMapper
from src.orchestrator.context import ContextResolutionError
from src.orchestrator.hybrid_dispatcher import HybridSpecialistDispatcher
from src.orchestrator.models import ActiveContext, CardType, RequestEnvelope, UserIdentity
from src.orchestrator.state_machine import FlowState, StateMachine, StructuredTrackBPlanner


@pytest.fixture()
def setup():
    cards = json.loads(Path("data/mock_cards/orchestrator_cards_demo.json").read_text(encoding="utf-8"))
    actor = UserIdentity("org-demo", "user-1", "comptable", frozenset({"company-demo-001"}))
    context = ActiveContext("org-demo", "company-demo-001", CardType.COMPANY)
    return CardToTrackBMapper(MockCardRepository.from_payload(cards)), actor, context


def test_authorized_card_prepares_salary_base_without_inference(setup) -> None:
    mapper, actor, context = setup
    prepared = mapper.prepare_salary_base(actor=actor, context=context, employee_id="employee-demo-01", date="2022-06-01")
    assert prepared.ready
    assert prepared.params == {
        "secteur": "METALLURGIE_BATIMENT", "population": "admin_tech", "categorie": "4",
        "anciennete_annees": 15, "date": "2022-06-01",
    }


def test_missing_date_requires_clarification_instead_of_defaulting(setup) -> None:
    mapper, actor, context = setup
    prepared = mapper.prepare_salary_base(actor=actor, context=context, employee_id="employee-demo-01", date=None)
    assert not prepared.ready
    assert prepared.missing == ("date",)


def test_prime_group_from_card_requires_user_confirmation(setup) -> None:
    mapper, actor, context = setup
    prepared = mapper.prepare_prime(actor=actor, context=context, code="prime_transport", date="2024-06-01")
    assert not prepared.ready
    assert prepared.missing == ("groupe",)


def test_card_mapper_keeps_authorization_boundary(setup) -> None:
    mapper, _, context = setup
    unauthorized = UserIdentity("org-demo", "user-2", "comptable", frozenset())
    with pytest.raises(ContextResolutionError):
        mapper.prepare_salary_base(actor=unauthorized, context=context, employee_id="employee-demo-01", date="2022-06-01")


def test_prepared_card_values_run_real_ds5_salary_flow(setup) -> None:
    mapper, actor, context = setup
    prepared = mapper.prepare_salary_base(actor=actor, context=context, employee_id="employee-demo-01", date="2022-06-01")
    envelope = RequestEnvelope("card-flow-1", "Calcule le salaire de base de cet employé.", "fr", actor, context)
    result = StateMachine(HybridSpecialistDispatcher(), planner=StructuredTrackBPlanner(operation=prepared.operation, params=prepared.params)).run(envelope)
    assert result.state is FlowState.COMPLETED
    assert result.tool_response["data"]["result"]["montant"] == "593.873"
