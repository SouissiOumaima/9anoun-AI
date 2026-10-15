from src.orchestrator.mock_specialists import MockSpecialistDispatcher
from src.orchestrator.models import ActiveContext, CardType, RequestEnvelope, UserIdentity
from src.orchestrator.state_machine import FlowState, Planner, StateMachine


def envelope(message: str, card_type: CardType | None = None) -> RequestEnvelope:
    card_id = {CardType.COMPANY: "company-1", CardType.CLIENT: "client-1", CardType.CASE: "case-1"}.get(card_type)
    return RequestEnvelope(
        request_id=f"mock-{card_type or 'general'}", message=message, language="fr",
        actor=UserIdentity("org-demo", "user-1", "demo", frozenset({"company-1", "client-1", "case-1"})),
        context=ActiveContext("org-demo", card_id, card_type),
    )


def case_card(request: RequestEnvelope) -> dict:
    return {
        "card_id": request.context.card_id, "organization_id": request.context.organization_id, "card_type": "case",
        "data": {
            "title": "Mock case", "jurisdiction": "TN",
            "documents": [{"document_id": "doc-1", "label": "Pièce", "file_name": "piece.pdf",
                           "mime_type": "application/pdf", "storage_ref": "mock://doc-1"}],
            "parties": [{"party_id": "party-1", "name": "Partie", "role": "employee", "party_type": "physical_person"}],
            "events": [{"event_id": "event-1", "date": "2024-01-01", "date_precision": "exact",
                        "description": "Fait.", "evidence_ids": ["evidence-1"], "confidence": 1.0}],
            "claims": [],
            "evidence": [{"evidence_id": "evidence-1", "document_id": "doc-1", "type": "document",
                          "description": "Preuve.", "citation": {"citation_id": "citation-1", "page": 1,
                          "excerpt": "Extrait."}, "confidence": 1.0,
                          "supports": [{"fact_type": "event", "fact_id": "event-1"}]}],
        },
    }


def test_mock_routes_and_document_metadata_requirement() -> None:
    machine = StateMachine(MockSpecialistDispatcher.from_file(), planner=Planner(case_card_provider=case_card))
    cases = [
        ("Quel article du code du travail s'applique ?", None, "legal_retrieval"),
        ("Analyse cette facture", CardType.COMPANY, None),
        ("Analyse les preuves de ce dossier", CardType.CASE, "track_a_legal"),
        ("Calcule le SMIG mensuel 48h au 2024-01-01", CardType.COMPANY, "track_b_accounting"),
    ]
    for message, card_type, expected_agent in cases:
        result = machine.run(envelope(message, card_type))
        if expected_agent is None:
            assert result.state is FlowState.CLARIFICATION_REQUIRED
            assert result.tool_call is None
        else:
            assert result.state is FlowState.COMPLETED
            assert result.tool_call.agent == expected_agent
            assert result.tool_response["status"] == "success"


def test_dispatcher_returns_detached_mock_data() -> None:
    dispatcher = MockSpecialistDispatcher.from_file()
    payload = {"agent": "legal_retrieval", "operation": "search", "params": {}}
    first = dispatcher(payload)
    first["data"]["findings"][0]["summary"] = "changed"
    assert dispatcher(payload)["data"]["findings"][0]["summary"] != "changed"
