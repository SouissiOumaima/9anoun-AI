import pytest

from src.orchestrator.hybrid_dispatcher import HybridSpecialistDispatcher
from src.orchestrator.models import ActiveContext, CardType, RequestEnvelope, UserIdentity
from src.orchestrator.state_machine import FlowState, StateMachine, StructuredTrackBPlanner
from src.orchestrator.tool_contracts import ToolContractError
from src.orchestrator.track_b_requests import build_track_b_request


def envelope(message: str, request_id: str = "structured-1") -> RequestEnvelope:
    return RequestEnvelope(
        request_id=request_id, message=message, language="fr",
        actor=UserIdentity("org-demo", "user-1", "comptable", frozenset({"company-1"})),
        context=ActiveContext("org-demo", "company-1", CardType.COMPANY),
    )


def test_structured_salary_base_uses_real_track_b_and_citation() -> None:
    planner = StructuredTrackBPlanner(operation="salaire_base", params={
        "secteur": "METALLURGIE_BATIMENT", "population": "admin_tech", "categorie": "4",
        "anciennete_annees": 15, "date": "2022-06-01",
    })
    result = StateMachine(HybridSpecialistDispatcher(), planner=planner).run(envelope("Calcule le salaire de base."))
    assert result.state is FlowState.COMPLETED
    assert result.tool_response["data"]["result"]["montant"] == "593.873"
    assert result.tool_response["citations"][0]["page"] == 30


def test_structured_prime_uses_real_track_b_and_citation() -> None:
    planner = StructuredTrackBPlanner(operation="prime", params={
        "secteur": "METALLURGIE_BATIMENT", "code": "prime_transport", "date": "2024-06-01", "groupe": "cadres",
    })
    result = StateMachine(HybridSpecialistDispatcher(), planner=planner).run(envelope("Calcule la prime de transport."))
    assert result.state is FlowState.COMPLETED
    assert result.tool_response["data"]["result"]["montant"] == "100.533"
    assert result.tool_response["citations"][0]["page"] == 16


def test_builder_delegates_a_missing_population_to_ds5() -> None:
    request = build_track_b_request(
        request_id="bad", language="fr", operation="salaire_base",
        params={"secteur": "METALLURGIE_BATIMENT", "categorie": "4", "date": "2024-01-01"},
    )
    assert "population" not in request["params"]


def test_builder_still_rejects_other_incomplete_salary_parameters() -> None:
    with pytest.raises(ToolContractError, match="Track B request is invalid"):
        build_track_b_request(
            request_id="bad", language="fr", operation="salaire_base", params={"secteur": "METALLURGIE_BATIMENT"},
        )


def test_structured_planner_requires_a_payroll_intent() -> None:
    planner = StructuredTrackBPlanner(operation="smig", params={"mode": "mensuel", "regime_heures": 48, "date": "2024-01-01"})
    result = StateMachine(HybridSpecialistDispatcher(), planner=planner).run(envelope("Analyse ce document."))
    assert result.state is FlowState.CLARIFICATION_REQUIRED
