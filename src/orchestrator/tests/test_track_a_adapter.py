import pytest

from src.orchestrator.track_a_adapter import TrackAAdapter
from src.orchestrator.track_a_requests import build_track_a_request
from src.orchestrator.tool_contracts import ToolContractError


PAYLOAD = {
    "request_id": "track-a-1",
    "agent": "track_a_legal",
    "operation": "analyze_case",
    "context": {"card_id": "case-1", "card_type": "case", "organization_id": "org-demo"},
    "params": {"track_a_request": build_track_a_request(
        request_id="track-a-1", case_id="case-1", language="fr",
    )},
}


def test_adapter_normalizes_cited_track_a_success() -> None:
    response = TrackAAdapter(lambda _: {
        "status": "ok", "result": {"case_id": "case-1"},
        "citations": [{"source_file": "source.pdf", "page": 2}], "refus": None,
        "computed_by": "track_a_legal.handler",
    })(PAYLOAD)
    assert response["status"] == "success"
    assert response["data"]["result"]["case_id"] == "case-1"


def test_adapter_preserves_track_a_source_missing_refusal() -> None:
    response = TrackAAdapter(lambda _: {
        "status": "refus", "result": None, "citations": [],
        "refus": {"code": "SOURCE_MANQUANTE"},
    })(PAYLOAD)
    assert response == {
        "status": "refused", "data": None, "citations": [],
        "error": {"code": "SOURCE_MANQUANTE"},
    }


def test_adapter_rejects_case_not_matching_active_card() -> None:
    invalid = {**PAYLOAD, "params": {"track_a_request": build_track_a_request(
        request_id="track-a-1", case_id="other-case", language="fr",
    )}}
    with pytest.raises(ToolContractError, match="case_id"):
        TrackAAdapter(lambda _: {})(invalid)
