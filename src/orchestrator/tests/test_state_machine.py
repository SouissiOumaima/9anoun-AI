import time

from src.orchestrator.models import ActiveContext, CardType, RequestEnvelope, UserIdentity
from src.orchestrator.state_machine import ExecutionLimits, FlowState, StateMachine


def envelope(message: str, *, card_type: CardType | None = None) -> RequestEnvelope:
    card_id = "company-1" if card_type else None
    return RequestEnvelope(
        request_id="request-1",
        message=message,
        language="ar" if any("\u0600" <= char <= "\u06ff" for char in message) else "fr",
        actor=UserIdentity("org-demo", "user-1", "comptable", frozenset({"company-1", "case-1"})),
        context=ActiveContext("org-demo", card_id, card_type),
    )


def success_executor(payload):
    return {"status": "success", "data": {"agent": payload["agent"]}, "citations": [], "error": None}


def test_general_legal_question_completes_end_to_end() -> None:
    result = StateMachine(success_executor).run(envelope("Quel article du code du travail s'applique ?"))
    assert result.state is FlowState.COMPLETED
    assert result.tool_call.agent == "legal_retrieval"
    assert result.states == (
        FlowState.RECEIVED, FlowState.CONTEXT_VALIDATED, FlowState.UNDERSTOOD,
        FlowState.PLANNED, FlowState.EXECUTING, FlowState.COMPLETED,
    )


def test_legal_prompt_builds_the_ds2_contract_request() -> None:
    result = StateMachine(success_executor).run(envelope(
        "Quel article du code du travail BTP s'applique à un ouvrier au 2024-01-01?"
    ))
    request = result.tool_call.params["legal_retrieval_request"]
    assert result.state is FlowState.COMPLETED
    assert request == {
        "contract_version": "legal_retrieval.v0", "request_id": "request-1",
        "query": "Quel article du code du travail BTP s'applique à un ouvrier au 2024-01-01?",
        "lang": "fr", "top_k": 5, "reference_date": "2024-01-01",
        "sector": "btp",
    }


def test_explicit_btp_article_routes_to_ds2_get_article() -> None:
    result = StateMachine(success_executor).run(envelope("Quel est l'article 39 du BTP au 2024-01-01 ?"))
    assert result.state is FlowState.COMPLETED
    assert result.tool_call.operation == "get_article"
    assert result.tool_call.params["legal_retrieval_request"] == {
        "contract_version": "legal_retrieval.v0", "request_id": "request-1", "lang": "fr",
        "reference_date": "2024-01-01", "source_id": "CCS-BTP", "article": "39",
    }


def test_ambiguous_construction_requests_clarification() -> None:
    result = StateMachine(success_executor).run(envelope("Quel article concerne la construction ?"))
    assert result.state is FlowState.CLARIFICATION_REQUIRED
    assert "ambigu" in result.reason


def test_payroll_request_routes_to_track_b_with_company_context() -> None:
    result = StateMachine(success_executor).run(
        envelope("Calcule le SMIG mensuel 48h au 2024-01-01", card_type=CardType.COMPANY)
    )
    assert result.state is FlowState.COMPLETED
    assert result.tool_call.agent == "track_b_accounting"
    assert result.tool_call.params["track_b_request"]["operation"] == "smig"


def test_track_b_missing_required_fields_requests_clarification() -> None:
    result = StateMachine(success_executor).run(envelope("Calcule le SMIG", card_type=CardType.COMPANY))
    assert result.state is FlowState.CLARIFICATION_REQUIRED
    assert "SMIG requires" in result.reason


def test_salary_base_prompt_extracts_explicit_parameters_for_track_b() -> None:
    result = StateMachine(success_executor).run(envelope(
        "Calcule le salaire de base secteur construction métallique, population admin-tech, "
        "catégorie 4, 15 ans d'ancienneté au 2022-06-01.",
        card_type=CardType.COMPANY,
    ))
    request = result.tool_call.params["track_b_request"]
    assert result.state is FlowState.COMPLETED
    assert request["operation"] == "salaire_base"
    assert request["params"] == {
        "secteur": "METALLURGIE_BATIMENT", "population": "admin_tech", "categorie": "4",
        "anciennete_annees": 15, "date": "2022-06-01",
    }


def test_salary_base_prompt_lists_only_missing_fields() -> None:
    result = StateMachine(success_executor).run(envelope(
        "Calcule le salaire de base secteur construction métallique, catégorie 4 au 2022-06-01.",
        card_type=CardType.COMPANY,
    ))
    assert result.state is FlowState.CLARIFICATION_REQUIRED
    assert "population, anciennete_annees" in result.reason


def test_btp_occasionnel_prompt_omits_forbidden_seniority_and_calls_ds5() -> None:
    result = StateMachine(success_executor).run(envelope(
        "Calcule le salaire de base BTP pour population ouvriers_occasionnels, catégorie 7, "
        "sous-catégorie 2 au 2023-06-01.", card_type=CardType.COMPANY,
    ))
    request = result.tool_call.params["track_b_request"]
    assert result.state is FlowState.COMPLETED
    assert request["params"] == {
        "secteur": "BATIMENT_TRAVAUX_PUBLICS", "population": "ouvriers_occasionnels",
        "categorie": "7", "sous_categorie": "2", "date": "2023-06-01",
    }


def test_ambiguous_message_stops_for_clarification_without_tool_call() -> None:
    result = StateMachine(success_executor).run(envelope("Bonjour"))
    assert result.state is FlowState.CLARIFICATION_REQUIRED
    assert result.tool_call is None


def test_case_analysis_with_company_context_fails_before_execution() -> None:
    result = StateMachine(success_executor).run(envelope("Analyse les preuves de ce dossier", card_type=CardType.COMPANY))
    assert result.state is FlowState.FAILED
    assert "requires one of: case" in result.reason


def test_failed_tool_is_retried_within_budget() -> None:
    calls = []

    def flaky_executor(payload):
        calls.append(payload)
        return {"status": "error", "data": None, "citations": [], "error": {"type": "temporary"}}

    result = StateMachine(flaky_executor, limits=ExecutionLimits(max_retries=1)).run(
        envelope("Quel article du code du travail s'applique ?")
    )
    assert result.state is FlowState.FAILED
    assert result.attempts == 2
    assert len(calls) == 2


def test_temporary_error_can_succeed_on_retry() -> None:
    calls = []

    def recovering_executor(payload):
        calls.append(payload)
        status = "error" if len(calls) == 1 else "success"
        return {"status": status, "data": {} if status == "success" else None, "citations": [], "error": None}

    result = StateMachine(recovering_executor, limits=ExecutionLimits(max_retries=1)).run(
        envelope("Quel article du code du travail s'applique ?")
    )
    assert result.state is FlowState.COMPLETED
    assert result.attempts == 2


def test_non_retryable_specialist_error_is_preserved_without_retry() -> None:
    calls = []

    def denied_executor(payload):
        calls.append(payload)
        return {
            "status": "error", "data": None, "citations": [],
            "error": {"code": "ACCESS_DENIED", "retryable": False},
        }

    result = StateMachine(denied_executor, limits=ExecutionLimits(max_retries=1)).run(
        envelope("Quel article du code du travail s'applique ?")
    )
    assert result.state is FlowState.FAILED
    assert result.attempts == 1
    assert len(calls) == 1
    assert result.tool_response["error"]["code"] == "ACCESS_DENIED"


def test_tool_timeout_fails_after_configured_budget() -> None:
    def slow_executor(payload):
        time.sleep(0.05)
        return {"status": "success", "data": {}, "citations": [], "error": None}

    result = StateMachine(slow_executor, limits=ExecutionLimits(tool_timeout_seconds=0.001, max_retries=0)).run(
        envelope("Quel article du code du travail s'applique ?")
    )
    assert result.state is FlowState.FAILED
    assert result.attempts == 1


def test_max_steps_fails_closed() -> None:
    result = StateMachine(success_executor, limits=ExecutionLimits(max_steps=3)).run(
        envelope("Quel article du code du travail s'applique ?")
    )
    assert result.state is FlowState.FAILED
    assert "maximum state-machine steps" in result.reason
