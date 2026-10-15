import pytest

from src.orchestrator.document_intelligence_adapter import DocumentIntelligenceAdapter
from src.orchestrator.document_intelligence_requests import build_document_intelligence_request
from src.orchestrator.document_intelligence_response import assess_document_fields
from src.orchestrator.hybrid_dispatcher import HybridSpecialistDispatcher
from src.orchestrator.models import ActiveContext, CardType, UserIdentity
from src.orchestrator.models import RequestEnvelope
from src.orchestrator.seniority import SeniorityError, calculate_seniority_years
from src.orchestrator.state_machine import FlowState, StateMachine
from src.orchestrator.tool_contracts import build_tool_call


def _request() -> tuple[dict, dict]:
    actor = UserIdentity("org-demo", "user-1", "comptable", frozenset({"company-1"}))
    context = ActiveContext("org-demo", "company-1", CardType.COMPANY, {
        "document_id": "doc-1", "document_file_name": "paie_illisible.pdf",
        "document_mime_type": "application/pdf", "document_storage_ref": "tradrly://company-1/doc-1",
    })
    request = build_document_intelligence_request(
        request_id="ds3-1", actor=actor, context=context, language="fr",
    )
    payload = build_tool_call(
        tool_call_id="tool-1", request_id="ds3-1", actor=actor, context=context,
        agent="document_intelligence", operation="analyze_document", params={"ds3_request": request},
    ).to_payload()
    return request, payload


def test_ds3_partial_response_is_preserved() -> None:
    _, payload = _request()
    response = DocumentIntelligenceAdapter()(payload)
    assert response["status"] == "partial"
    assert response["data"]["result"]["fields"]["cnss_employee"]["value"] is None
    assert response["data"]["mode"] == "mock"


def test_ds3_adapter_rejects_context_substitution() -> None:
    _, payload = _request()
    payload["params"]["ds3_request"]["context"]["card_id"] = "company-other"
    try:
        DocumentIntelligenceAdapter()(payload)
    except Exception as error:
        assert "active context" in str(error)
    else:
        raise AssertionError("context substitution was accepted")


def test_ds1_completes_a_partial_ds3_mock_response() -> None:
    actor = UserIdentity("org-demo", "user-1", "comptable", frozenset({"company-1"}))
    context = ActiveContext("org-demo", "company-1", CardType.COMPANY, {
        "document_id": "doc-1", "document_file_name": "paie_illisible.pdf",
        "document_mime_type": "application/pdf", "document_storage_ref": "tradrly://company-1/doc-1",
    })
    result = StateMachine(HybridSpecialistDispatcher()).run(RequestEnvelope(
        request_id="ds3-flow", message="Analyse ce document PDF", language="fr", actor=actor, context=context,
    ))
    assert result.state is FlowState.COMPLETED
    assert result.tool_call.operation == "analyze_document"
    assert result.tool_response["status"] == "partial"


def test_ds3_v2_complete_false_normalizes_to_partial() -> None:
    request, payload = _request()
    request.update({"contract_version": "ds3.v2", "lang": "fr"})
    payload["params"]["ds3_request"] = request
    response = DocumentIntelligenceAdapter(lambda _: {
        "contract_version": "ds3.v2", "request_id": "ds3-1", "operation": "analyze_document",
        "status": "ok", "refus": None, "computed_by": "document_intelligence.mock", "mode": "mock",
        "result": {"complete": False, "fields": {}}, "citations": [], "warnings": ["Champ illisible"],
        "ds3_code": None,
    })(payload)
    assert response["status"] == "partial"
    assert response["data"]["complete"] is False


def test_ds1_assessment_rejects_null_low_confidence_or_uncited_fields() -> None:
    result = {"fields": {
        "valid": {"value": "424.100", "confidence": 0.96, "citation_id": "c1"},
        "missing": {"value": None, "confidence": 0.96, "citation_id": "c1"},
        "weak": {"value": "x", "confidence": 0.5, "citation_id": "c1"},
        "uncited": {"value": "x", "confidence": 0.96, "citation_id": "unknown"},
    }}
    assessments = assess_document_fields(
        result=result, citations=[{"citation_id": "c1", "excerpt": "Salaire de base"}], minimum_confidence=0.8,
    )
    assert [(item.name, item.usable, item.reason) for item in assessments] == [
        ("valid", True, None), ("missing", False, "value_missing"),
        ("weak", False, "confidence_below_threshold"), ("uncited", False, "citation_missing"),
    ]


def test_seniority_is_calculated_from_explicit_documented_dates() -> None:
    assert calculate_seniority_years(hire_date="2020-01-01", reference_date="2024-01-01") == 4
    assert calculate_seniority_years(hire_date="2020-01-01", reference_date="2024-07-02") > 4


def test_seniority_refuses_missing_or_reversed_dates() -> None:
    with pytest.raises(SeniorityError):
        calculate_seniority_years(hire_date="", reference_date="2024-01-01")
    with pytest.raises(SeniorityError):
        calculate_seniority_years(hire_date="2025-01-01", reference_date="2024-01-01")
