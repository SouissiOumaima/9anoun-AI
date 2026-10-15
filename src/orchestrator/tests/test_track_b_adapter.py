import pytest

from src.orchestrator.tool_contracts import ToolContractError
from src.orchestrator.track_b_adapter import TrackBAdapter
from src.orchestrator.models import ActiveContext, CardType, RequestEnvelope, UserIdentity
from src.orchestrator.state_machine import FlowState, StateMachine


PAYLOAD = {
    "request_id": "request-1",
    "agent": "track_b_accounting",
    "operation": "compute",
    "params": {"track_b_request": {
        "contract_version": "track_b.v0", "request_id": "request-1", "operation": "smig",
        "params": {"mode": "mensuel", "regime_heures": 48, "date": "2024-01-01"}, "lang": "fr",
    }},
}


def test_adapter_normalizes_cited_track_b_success() -> None:
    def handler(request):
        assert request == PAYLOAD["params"]["track_b_request"]
        return {
            "status": "ok", "result": {"montant": "459.264", "unite": "TND/mois", "detail": {}},
            "citations": [{"source_file": "source.pdf", "page": 2}], "refus": None,
            "computed_by": "track_b_accounting.calc.smig",
        }

    response = TrackBAdapter(handler)(PAYLOAD)
    assert response["status"] == "success"
    assert response["data"]["result"]["montant"] == "459.264"
    assert response["citations"][0]["page"] == 2


def test_adapter_preserves_a_track_b_business_refusal() -> None:
    response = TrackBAdapter(lambda _: {"status": "refus", "result": None, "citations": [],
                                         "refus": {"code": "HORS_SCOPE"}})(PAYLOAD)
    assert response == {"status": "refused", "data": None, "citations": [], "error": {"code": "HORS_SCOPE"}}


def test_adapter_rejects_wrong_inner_contract_or_request_id() -> None:
    invalid = {**PAYLOAD, "params": {"track_b_request": {**PAYLOAD["params"]["track_b_request"], "request_id": "other"}}}
    with pytest.raises(ToolContractError, match="request_id"):
        TrackBAdapter(lambda _: {})(invalid)


def test_adapter_rejects_uncited_ok_response() -> None:
    with pytest.raises(ToolContractError, match="citations"):
        TrackBAdapter(lambda _: {"status": "ok", "result": {}, "citations": []})(PAYLOAD)


def test_state_machine_runs_a_smig_request_through_track_b_contract() -> None:
    received = []

    def handler(request):
        received.append(request)
        return {
            "status": "ok", "result": {"montant": "459.264", "unite": "TND/mois", "detail": {}},
            "citations": [{"source_file": "source.pdf", "page": 2}], "refus": None,
            "computed_by": "track_b_accounting.calc.smig",
        }

    envelope = RequestEnvelope(
        request_id="track-b-e2e-1", message="Calcule le SMIG mensuel 48h au 2024-01-01", language="fr",
        actor=UserIdentity("org-demo", "user-1", "comptable", frozenset({"company-1"})),
        context=ActiveContext("org-demo", "company-1", CardType.COMPANY),
    )
    result = StateMachine(TrackBAdapter(handler)).run(envelope)
    assert result.state is FlowState.COMPLETED
    assert received[0] == {
        "contract_version": "track_b.v0", "request_id": "track-b-e2e-1", "operation": "smig",
        "params": {"mode": "mensuel", "regime_heures": 48, "date": "2024-01-01"}, "lang": "fr",
    }
    assert result.tool_response["data"]["result"]["montant"] == "459.264"
