from src.orchestrator.hybrid_dispatcher import HybridSpecialistDispatcher
from src.orchestrator.models import ActiveContext, CardType, RequestEnvelope, UserIdentity
from src.orchestrator.state_machine import FlowState, StateMachine


def _track_b_payload(operation: str, params: dict) -> dict:
    return {
        "request_id": f"hybrid-{operation}", "agent": "track_b_accounting", "operation": "compute",
        "params": {"track_b_request": {
            "contract_version": "track_b.v0", "request_id": f"hybrid-{operation}",
            "operation": operation, "params": params, "lang": "fr",
        }},
    }


def test_hybrid_flow_uses_real_track_b_smig_with_citation() -> None:
    envelope = RequestEnvelope(
        request_id="hybrid-smig", message="Calcule le SMIG mensuel 48h au 2024-01-01", language="fr",
        actor=UserIdentity("org-demo", "user-1", "comptable", frozenset({"company-1"})),
        context=ActiveContext("org-demo", "company-1", CardType.COMPANY),
    )
    result = StateMachine(HybridSpecialistDispatcher()).run(envelope)
    assert result.state is FlowState.COMPLETED
    assert result.tool_response["data"]["result"]["montant"] == "459.264"
    assert result.tool_response["citations"][0]["page"] == 2
    assert result.tool_response["data"]["computed_by"] == "track_b_accounting.calc.smig"


def test_hybrid_preserves_track_b_out_of_scope_refusal() -> None:
    response = HybridSpecialistDispatcher()(_track_b_payload("cotisation_cnss", {"salaire_brut": "1000.000", "date": "2024-01-01"}))
    assert response["status"] == "refused"
    assert response["error"]["code"] == "HORS_SCOPE"


def test_hybrid_preserves_track_b_source_missing_refusal() -> None:
    response = HybridSpecialistDispatcher()(_track_b_payload("salaire_base", {
        "secteur": "METALLURGIE_BATIMENT", "population": "admin_tech", "categorie": "4",
        "anciennete_annees": 15, "date": "2021-11-30",
    }))
    assert response["status"] == "refused"
    assert response["error"]["code"] == "SOURCE_MANQUANTE"


def test_hybrid_preserves_track_b_invalid_parameter_refusal() -> None:
    response = HybridSpecialistDispatcher()(_track_b_payload("salaire_base", {
        "secteur": "METALLURGIE_BATIMENT", "population": "admin_tech", "categorie": "19",
        "anciennete_annees": 5, "date": "2024-01-01",
    }))
    assert response["status"] == "refused"
    assert response["error"]["code"] == "PARAM_INVALIDE"


def test_hybrid_uses_real_ds2_adapter_with_citations() -> None:
    response = HybridSpecialistDispatcher()({
        "request_id": "hybrid-ds2", "agent": "legal_retrieval", "operation": "search",
        "params": {"legal_retrieval_request": {
            "contract_version": "legal_retrieval.v0", "request_id": "hybrid-ds2",
            "query": "Quel article du BTP s'applique ?", "sector": "btp", "lang": "fr", "top_k": 5,
        }},
    })
    assert response["status"] == "success"
    assert response["data"]["results"]
    assert response["citations"]


def test_hybrid_uses_real_ds4_handler_and_preserves_source_missing_refusal() -> None:
    response = HybridSpecialistDispatcher()({
        "request_id": "hybrid-ds4", "agent": "track_a_legal", "operation": "analyze_case",
        "context": {"organization_id": "org-demo", "card_id": "case-1", "card_type": "case"},
        "params": {"track_a_request": {
            "contract_version": "track_a.v0", "request_id": "hybrid-ds4", "case_id": "case-1", "lang": "fr",
            "parties": [], "events": [], "claims": [], "evidence": [],
        }},
    })
    assert response["status"] == "refused"
    assert response["error"]["code"] == "SOURCE_MANQUANTE"
