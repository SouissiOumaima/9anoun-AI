"""Local-only web form and JSON API for the DS1 → DS5 structured flow.

Run: ``python -m src.orchestrator.web_app`` then open http://127.0.0.1:8765.
This demo uses fictitious local identity/context and must not be exposed as a
production authentication service.
"""

from __future__ import annotations

import json
from decimal import Decimal, InvalidOperation
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Lock
from typing import Any, Mapping
from uuid import uuid4

from .audit import AuditTrail
from .approval import ApprovalError, ApprovalStatus, ApprovalWorkflow, PendingAction
from .card_repository import CardNotFoundError, MockCardRepository
from .card_to_track_b import CardToTrackBMapper
from .document_intelligence_response import assess_document_fields
from .document_to_track_b import build_payroll_prefill
from .hybrid_dispatcher import HybridSpecialistDispatcher
from .models import ActiveContext, CardType, RequestEnvelope, UserIdentity
from .response_formatter import UserResponse, UserResponseCode, format_flow_result
from .state_machine import Planner, StateMachine, StructuredTrackBPlanner
from .tool_contracts import ToolContractError
from .case_integration import CaseIntegrationWorkflow, CaseWorkflowError

HOST, PORT = "127.0.0.1", 8765
_HTML_PATH = Path(__file__).with_name("web_ui") / "index.html"
_CARD_IDS = {
    "company": "company-demo-001", "client": "client-demo-001", "case": "case-demo-001",
}
_CARDS_PATH = Path("data/mock_cards/orchestrator_cards_demo.json")
_WEB_AUDIT = AuditTrail()
_WEB_APPROVALS = ApprovalWorkflow(_WEB_AUDIT)
_DOCUMENT_REVIEWS: dict[str, dict[str, Any]] = {}
_DOCUMENT_REVIEWS_LOCK = Lock()
_CASE_WORKFLOW = CaseIntegrationWorkflow(audit=_WEB_AUDIT)
_E2E_SCENARIO = Path(__file__).resolve().parents[2] / 'data/mock_cards/orchestrator_case_e2e_demo.json'
_REVIEW_MIN_CONFIDENCE = 0.90  # Local UI review threshold for payroll-bound facts.
_APPROVAL_ACTIONS = {
    "generate_payroll_report": {
        "card_type": CardType.COMPANY,
        "summary": "Générer un rapport de paie pour la Company Card sélectionnée.",
    },
}


def _demo_cards() -> list[Mapping[str, Any]]:
    return json.loads(_CARDS_PATH.read_text(encoding="utf-8"))


def case_integration_action(payload: Mapping[str, Any], *, complete: bool = False) -> dict[str, Any]:
    """Local fictitious-session entry point; callers cannot supply facts or service responses."""
    scenario = json.loads(_E2E_SCENARIO.read_text(encoding='utf-8'))
    card = scenario['card']
    actor = UserIdentity('org-demo', 'local-web-user', 'lawyer', frozenset({card['card_id']}))
    document = card['data']['documents'][0]
    context = ActiveContext('org-demo', card['card_id'], CardType.CASE, {
        'document_id': document['document_id'], 'document_file_name': document['file_name'],
        'document_mime_type': document['mime_type'], 'document_storage_ref': document['storage_ref'],
    })
    repository = MockCardRepository.from_payload([card])
    language = payload.get('language', 'fr')
    if language not in {'fr', 'ar'}:
        return {'status': 'blocked', 'code': 'INVALID_LANGUAGE'}
    try:
        if complete:
            return _CASE_WORKFLOW.complete(
                actor=actor, context=context, repository=repository,
                review_id=payload.get('review_id'), confirmed_fact_ids=payload.get('confirmed_fact_ids'),
                confirm_document_link=payload.get('confirm_document_link'),
            )
        return _CASE_WORKFLOW.prepare(
            actor=actor, context=context, repository=repository, language=language,
            subject_id=scenario['subject_id'], evidence_id=scenario['evidence_id'],
            legal_request=scenario['legal_request'],
        )
    except CaseWorkflowError as error:
        return {'status': 'blocked', 'code': error.code,
                'message_fr': 'Le scénario ne peut pas continuer. Aucun fait ni source ne sera inventé.',
                'message_ar': 'لا يمكن متابعة السيناريو. لن يتم اختلاق أي واقعة أو مصدر.'}
    except Exception:
        return {'status': 'blocked', 'code': 'INTEGRATION_ERROR',
                'message_fr': 'Incident technique. Aucun résultat juridique n’est validé.',
                'message_ar': 'حدث خطأ تقني. لا توجد نتيجة قانونية معتمدة.'}


def _demo_actor() -> UserIdentity:
    return UserIdentity("org-demo", "local-web-user", "comptable", frozenset(_CARD_IDS.values()))


def _context_for_card(card_id: str, document_id: str | None = None) -> ActiveContext:
    card = next((item for item in _demo_cards() if item["card_id"] == card_id), None)
    if card is None or card["organization_id"] != "org-demo":
        raise CardNotFoundError("card was not found or is not available")
    entity_ids: dict[str, str] = {}
    if document_id is not None:
        document = next(
            (item for item in card["data"].get("documents", []) if item.get("document_id") == document_id), None,
        )
        if not isinstance(document, Mapping):
            raise CardNotFoundError("document was not found on the active card")
        for source, target in (
            ("document_id", "document_id"), ("file_name", "document_file_name"),
            ("mime_type", "document_mime_type"), ("storage_ref", "document_storage_ref"),
        ):
            value = document.get(source)
            if not isinstance(value, str) or not value:
                raise CardNotFoundError("document metadata is incomplete")
            entity_ids[target] = value
    return ActiveContext("org-demo", card_id, CardType(card["card_type"]), entity_ids)


def available_cards() -> list[dict[str, Any]]:
    """Return the minimal, authorized Card selector data for the local demo."""

    actor = _demo_actor()
    visible: list[dict[str, Any]] = []
    for item in _demo_cards():
        if item["card_id"] not in actor.authorized_card_ids or item["organization_id"] != actor.organization_id:
            continue
        data = item["data"]
        visible.append({
            "card_id": item["card_id"], "card_type": item["card_type"],
            "label": data.get("name") or data.get("title") or item["card_id"],
            "employees": [
                {"employee_id": employee["employee_id"], "label": employee.get("name", employee["employee_id"])}
                for employee in data.get("employees", [])
            ],
            "documents": [
                {"document_id": document["document_id"], "label": document.get("label", document["file_name"])}
                for document in data.get("documents", [])
                if isinstance(document, Mapping) and isinstance(document.get("document_id"), str)
            ],
        })
    return visible


def prepare_from_card(payload: Mapping[str, Any]) -> dict[str, Any]:
    """Prepare form values from one authorized active Card without inference."""

    operation = payload.get("operation")
    card_id = payload.get("card_id")
    document_id = payload.get("document_id")
    if operation not in {"smig", "salaire_base", "prime"} or not isinstance(card_id, str):
        return {"prepared_params": {}, "missing": ["card_id"], "error": "invalid_request"}
    if operation == "smig":
        return {"prepared_params": {}, "missing": []}
    if operation == "salaire_base" and not payload.get("employee_id"):
        return {"prepared_params": {}, "missing": ["employee_id"]}
    try:
        mapper = CardToTrackBMapper(MockCardRepository.from_payload(_demo_cards()))
        actor, context = _demo_actor(), _context_for_card(card_id)
        if operation == "salaire_base":
            prepared = mapper.prepare_salary_base(
                actor=actor, context=context, employee_id=str(payload.get("employee_id") or ""),
                date=payload.get("date") if isinstance(payload.get("date"), str) else None,
            )
        else:
            prepared = mapper.prepare_prime(
                actor=actor, context=context, code=payload.get("code") if isinstance(payload.get("code"), str) else None,
                date=payload.get("date") if isinstance(payload.get("date"), str) else None,
            )
    except (CardNotFoundError, ToolContractError):
        missing = ["employee_id"] if operation == "salaire_base" else ["card_id"]
        return {"prepared_params": {}, "missing": missing, "error": "card_unavailable"}
    return {"prepared_params": dict(prepared.params), "missing": list(prepared.missing)}


def audit_history() -> list[dict[str, Any]]:
    """Return a minimal history view: never expose messages, params or amounts."""

    history: list[dict[str, Any]] = []
    for event in reversed(_WEB_AUDIT.export()):
        details = event["details"]
        if not details.get("agent"):
            continue
        history.append({
            "occurred_at": event["occurred_at"],
            "request_id": event["request_id"],
            "card_id": event["card_id"],
            "operation": details.get("domain_operation") or details.get("operation"),
            "agent": details.get("agent"),
            "state": details.get("final_state"),
            "attempts": details.get("attempts"),
        })
    return history


def chat(
    payload: Mapping[str, Any], *, dispatcher: HybridSpecialistDispatcher | None = None,
) -> dict[str, Any]:
    """Run one free-text question through the DS1 parser and allow-listed planner."""

    message = payload.get("message")
    language = payload.get("language", "fr")
    card_id = payload.get("card_id")
    document_id = payload.get("document_id")
    if not isinstance(message, str) or not message.strip() or language not in {"fr", "ar"}:
        return _input_error("Veuillez écrire une question valide.", "يرجى كتابة سؤال صحيح.")
    try:
        context = _context_for_card(card_id, document_id if isinstance(document_id, str) and document_id else None) if isinstance(card_id, str) and card_id else ActiveContext("org-demo")
    except CardNotFoundError:
        return _input_error("Carte active non autorisée.", "البطاقة النشطة غير مصرح بها.")
    request_id = f"chat-{uuid4()}"
    approval_response = _approval_from_prompt(message, context, request_id)
    if approval_response is not None:
        return approval_response
    envelope = RequestEnvelope(request_id, message, language, _demo_actor(), context)
    repository = MockCardRepository.from_payload(_demo_cards())
    planner = Planner(case_card_provider=lambda request: repository.read_active_case_card(
        actor=request.actor, context=request.context,
    ))
    result = StateMachine(
        dispatcher or HybridSpecialistDispatcher(), planner=planner, audit_hook=_WEB_AUDIT.record_flow,
    ).run(envelope)
    tool_response = result.tool_response or {}
    data = tool_response.get("data", tool_response)
    return {
        "request_id": request_id,
        "user_response": format_flow_result(result).to_payload(),
        "route": {
            "agent": result.tool_call.agent if result.tool_call else None,
            "operation": result.tool_call.operation if result.tool_call else None,
        },
        "answer": _chat_answer(data, language) if tool_response else None,
        "citations": tool_response.get("citations", []),
        "document_review": _create_document_review(
            data=data, citations=tool_response.get("citations", []), context=context,
        ) if result.tool_call and result.tool_call.agent == "document_intelligence" and isinstance(data, Mapping) else None,
    }


def _create_document_review(
    *, data: Mapping[str, Any], citations: Any, context: ActiveContext,
) -> dict[str, Any] | None:
    """Prepare a user-review screen from cited DS3 fields; never calculate or infer."""

    result = data.get("result")
    if not isinstance(result, Mapping) or not isinstance(result.get("fields"), Mapping):
        return None
    citation_list = [item for item in citations if isinstance(item, Mapping)] if isinstance(citations, list) else []
    assessments = {
        item.name: item for item in assess_document_fields(
            result=result, citations=citation_list, minimum_confidence=_REVIEW_MIN_CONFIDENCE,
        )
    }
    citation_by_id = {item.get("citation_id"): item for item in citation_list if isinstance(item.get("citation_id"), str)}
    fields: list[dict[str, Any]] = []
    selectable: set[str] = set()
    for name, field in result["fields"].items():
        if not isinstance(name, str) or not isinstance(field, Mapping):
            continue
        assessment = assessments.get(name)
        citation = citation_by_id.get(field.get("citation_id"))
        has_value_and_citation = field.get("value") is not None and citation is not None and bool(citation.get("excerpt"))
        state = "verified" if assessment and assessment.usable else "review_required" if has_value_and_citation else "unavailable"
        # Only documentary facts at or above the agreed DS5 threshold may be
        # confirmed for a calculation.  Lower-confidence values remain visible
        # to the user, but cannot cross the DS3 -> DS5 boundary.
        if state == "verified":
            selectable.add(name)
        fields.append({
            "name": name, "value": field.get("value"), "value_type": field.get("value_type"),
            "confidence": field.get("confidence"), "citation_id": field.get("citation_id"),
            "page": citation.get("page", citation.get("position", {}).get("page")) if isinstance(citation, Mapping) else None,
            "excerpt": citation.get("excerpt") if isinstance(citation, Mapping) else None,
            "state": state, "reason": assessment.reason if assessment and not assessment.usable else None,
        })
    review_id = f"review-{uuid4()}"
    with _DOCUMENT_REVIEWS_LOCK:
        _DOCUMENT_REVIEWS[review_id] = {
            "organization_id": context.organization_id, "card_id": context.card_id,
            "document_id": context.entity_ids.get("document_id"), "selectable": selectable,
            "mode": data.get("mode"),
            "fields": {name: dict(field) for name, field in result["fields"].items()
                       if isinstance(name, str) and isinstance(field, Mapping)},
            "citations": citation_list,
        }
    return {
        "review_id": review_id, "complete": data.get("complete", result.get("complete", True)),
        "threshold": _REVIEW_MIN_CONFIDENCE, "mode": data.get("mode"), "fields": fields,
    }


def confirm_document_review(payload: Mapping[str, Any]) -> dict[str, Any]:
    """Record selections and produce a non-executable, DS5-safe prefill."""

    review_id = payload.get("review_id")
    confirmed = payload.get("confirmed_fields")
    if not isinstance(review_id, str) or not isinstance(confirmed, list) or not all(isinstance(item, str) for item in confirmed):
        return {"error": "invalid_review"}
    with _DOCUMENT_REVIEWS_LOCK:
        review = _DOCUMENT_REVIEWS.get(review_id)
    if review is None:
        return {"error": "review_not_found"}
    if len(confirmed) != len(set(confirmed)) or not set(confirmed).issubset(review["selectable"]):
        return {"error": "unconfirmed_or_unusable_field"}
    company_sector: str | None = None
    if isinstance(review.get("card_id"), str):
        card = next((item for item in _demo_cards() if item.get("card_id") == review["card_id"]), None)
        if isinstance(card, Mapping):
            defaults = card.get("data", {}).get("track_b_defaults", {}) if isinstance(card.get("data"), Mapping) else {}
            company_sector = defaults.get("secteur") if isinstance(defaults.get("secteur"), str) else None
    prefill = build_payroll_prefill(
        fields=review["fields"], confirmed_fields=set(confirmed), company_sector=company_sector,
    )
    with _DOCUMENT_REVIEWS_LOCK:
        review["confirmed_fields"] = set(confirmed)
        review["ds5_prefill"] = prefill
    return {
        "review_id": review_id, "status": "confirmed", "confirmed_fields": confirmed,
        "next_action": "review_ds5_prefill_then_submit_explicit_calculation",
        "ds5_prefill": prefill,
    }


def calculate_from_document_review(payload: Mapping[str, Any]) -> dict[str, Any]:
    """Run DS5 only after DS3 evidence and all interpretation inputs are explicit."""

    review_id, operation = payload.get("review_id"), payload.get("operation")
    user_inputs, language = payload.get("user_inputs", {}), payload.get("language", "fr")
    if not isinstance(review_id, str) or operation not in {"smig", "salaire_base", "prime"}:
        return {"error": "invalid_review_calculation"}
    if not isinstance(user_inputs, Mapping) or language not in {"fr", "ar"}:
        return {"error": "invalid_review_calculation"}
    with _DOCUMENT_REVIEWS_LOCK:
        review = _DOCUMENT_REVIEWS.get(review_id)
    if review is None or not isinstance(review.get("confirmed_fields"), set):
        return {"error": "document_confirmation_required"}
    if review.get("mode") != "live":
        refusal = UserResponse(
            status="refused",
            code=UserResponseCode.OUT_OF_SCOPE,
            message_fr="Le calcul exige une lecture DS3 réelle (mode live) et ne peut pas être exécuté.",
            message_ar="يتطلب الحساب قراءة حقيقية من DS3 في وضع live ولا يمكن تنفيذه.",
            next_action="use_a_live_document",
            request_id=review_id,
            specialist_code="NON_LIVE_DOCUMENT",
        ).to_payload()
        return {
            "user_response": refusal, "result": None, "citations": [],
            "document_citations": list(review["citations"]), "payroll_citations": [],
            "salary_comparison_warning": None,
        }
    prefill = review.get("ds5_prefill")
    if not isinstance(prefill, Mapping):
        return {"error": "document_confirmation_required"}
    candidate = next((item for item in prefill.get("candidates", [])
                      if isinstance(item, Mapping) and item.get("operation") == operation), None)
    if not isinstance(candidate, Mapping) or not isinstance(candidate.get("params"), Mapping):
        return {"error": "operation_not_available"}
    params = dict(candidate["params"])
    permitted = {
        "salaire_base": {"population", "sous_categorie", "anciennete_annees"},
        "prime": {"code", "groupe", "transport_assure", "variante", "condition_remplie"},
        "smig": set(),
    }[operation]
    for key in permitted:
        value = user_inputs.get(key)
        if key == "anciennete_annees" and isinstance(value, str) and value:
            try:
                # The value is user-confirmed; float is only the JSON transport
                # representation. DS5 converts it with Decimal(str(value)).
                params[key] = float(Decimal(value.replace(",", ".")))
            except InvalidOperation:
                return {"error": "invalid_seniority_confirmation"}
        elif isinstance(value, (str, bool)) and value != "":
            params[key] = value
    result = calculate({"operation": operation, "language": language, "card_id": review["card_id"], "params": params})
    result["document_citations"] = list(review["citations"])
    result["payroll_citations"] = list(result.get("citations", []))
    result["salary_comparison_warning"] = _printed_salary_warning(
        operation=operation, fields=review["fields"], confirmed=review["confirmed_fields"],
        payroll_result=result.get("result"), language=language,
    )
    return result


def _printed_salary_warning(*, operation: str, fields: Mapping[str, Any], confirmed: set[str],
                            payroll_result: Any, language: str) -> dict[str, Any] | None:
    """Compare only two monthly base-salary amounts; it never blocks DS5."""

    if operation != "salaire_base" or "base_salary" not in confirmed or not isinstance(payroll_result, Mapping):
        return None
    printed = fields.get("base_salary")
    calculated = payroll_result.get("montant")
    if not isinstance(printed, Mapping) or not isinstance(printed.get("value"), str) or not isinstance(calculated, str):
        return None
    try:
        difference = abs(Decimal(printed["value"]) - Decimal(calculated))
    except (InvalidOperation, TypeError):
        return None
    if difference <= Decimal("0.010"):
        return None
    fr = f"Le salaire de base imprimé ({printed['value']}) diffère du montant de la grille à cette date ({calculated}). À vérifier."
    ar = f"الأجر الأساسي المطبوع ({printed['value']}) يختلف عن مبلغ الجدول في هذا التاريخ ({calculated}). يُرجى التحقق."
    return {"message": ar if language == "ar" else fr, "message_fr": fr, "message_ar": ar, "tolerance_tnd": "0.010"}


def _approval_from_prompt(
    message: str, context: ActiveContext, request_id: str,
) -> dict[str, Any] | None:
    """Handle the small allow-listed approval vocabulary from the chat prompt.

    This is deliberately separate from the specialist planner: it never turns
    arbitrary text into a write action.  It only controls the single simulated
    payroll-report action already protected by ``ApprovalWorkflow``.
    """

    lowered = message.casefold()
    proposal_words = ("génère", "générer", "genere", "generer", "crée", "créer", "cree", "creer", "produis")
    if "rapport de paie" in lowered and any(word in lowered for word in proposal_words):
        if context.card_type is not CardType.COMPANY:
            return _approval_chat_response(
                request_id, None, "Choisissez une Company Card pour proposer ce rapport.",
                "اختر بطاقة شركة لاقتراح هذا التقرير.", "select_company_card",
            )
        definition = _APPROVAL_ACTIONS["generate_payroll_report"]
        action = _WEB_APPROVALS.propose(
            request_id=request_id, actor=_demo_actor(), context=context,
            action_type="generate_payroll_report", summary=str(definition["summary"]),
            idempotency_key=f"approval-{uuid4()}",
        )
        return _approval_chat_response(
            request_id, action,
            "Action proposée. Écrivez « Approuve la dernière demande » ou « Refuse la dernière demande ».",
            "تم اقتراح الإجراء. اكتب «وافق على آخر طلب» أو «ارفض آخر طلب».",
            "human_approval",
        )

    decision: str | None = None
    desired_status: ApprovalStatus | None = None
    if any(word in lowered for word in ("approuve", "approuver", "valide", "valider")):
        decision, desired_status = "approve", ApprovalStatus.PENDING
    elif any(word in lowered for word in ("refuse", "refuser", "rejette", "rejeter")):
        decision, desired_status = "reject", ApprovalStatus.PENDING
    elif any(word in lowered for word in ("exécute", "exécuter", "execute", "executer")):
        decision, desired_status = "execute", ApprovalStatus.APPROVED
    if decision is None:
        return None

    actions = tuple(reversed(_WEB_APPROVALS.list_for_actor(_demo_actor())))
    action = next((item for item in actions if item.status is desired_status), None)
    if action is None:
        expected = "en attente" if desired_status is ApprovalStatus.PENDING else "approuvée"
        return _approval_chat_response(
            request_id, None, f"Aucune action {expected} à traiter.",
            "لا يوجد إجراء مناسب لمعالجته.", "human_approval",
        )
    outcome = decide_approval(action.approval_id, decision)
    updated = outcome.get("action")
    if not isinstance(updated, Mapping):
        return _approval_chat_response(
            request_id, None, "La transition de validation a été refusée.",
            "تم رفض انتقال الموافقة.", "human_approval",
        )
    final_action = _WEB_APPROVALS.get(str(updated["approval_id"]))
    messages = {
        "approve": ("Action approuvée. Écrivez « Exécute la dernière demande » pour lancer la démo.", "تمت الموافقة على الإجراء. اكتب «نفذ آخر طلب» لتشغيل العرض."),
        "reject": ("Action refusée.", "تم رفض الإجراء."),
        "execute": ("Action exécutée dans la démo.", "تم تنفيذ الإجراء في العرض."),
    }
    message_fr, message_ar = messages[decision]
    return _approval_chat_response(request_id, final_action, message_fr, message_ar, "human_approval")


def _approval_chat_response(
    request_id: str, action: PendingAction | None, message_fr: str, message_ar: str, next_action: str,
) -> dict[str, Any]:
    """Return an approval outcome in the same display contract as chat tools."""

    status = "success" if action is not None else "error"
    code = UserResponseCode.SUCCESS if action is not None else UserResponseCode.INVALID_PARAMETERS
    payload = UserResponse(status, code, message_fr, message_ar, next_action, request_id).to_payload()
    approval = _approval_payload(action) if action is not None else None
    return {
        "request_id": request_id,
        "user_response": payload,
        "route": {"agent": "orchestrator", "operation": "human_approval"},
        "answer": {
            "kind": "approval", "text": message_fr,
            "approval_id": approval["approval_id"] if approval else "—",
            "status": approval["status"] if approval else "not_found",
        },
        "citations": [],
    }


def _chat_answer(data: Any, language: str = "fr") -> dict[str, Any] | None:
    """Turn known specialist response shapes into small display-safe summaries."""

    if not isinstance(data, Mapping):
        return None
    result = data.get("result")
    if isinstance(result, Mapping) and "montant" in result:
        detail = result.get("detail")
        hypotheses: list[Any] = []
        if isinstance(detail, Mapping):
            candidate = detail.get("hypotheses_ar" if language == "ar" else "hypotheses")
            if isinstance(candidate, list):
                hypotheses = candidate
        return {
            "kind": "calculation", "amount": result.get("montant"), "unit": result.get("unite"),
            "hypotheses": hypotheses,
            "hypotheses_label": "الفرضيات" if language == "ar" else "Hypothèses",
        }
    findings = data.get("findings")
    if isinstance(findings, list) and findings:
        first = findings[0]
        return {"kind": "legal_research", "text": first.get("summary")} if isinstance(first, Mapping) else None
    results = data.get("results")
    if isinstance(results, list) and results:
        first = results[0]
        if isinstance(first, Mapping):
            notices: list[str] = []
            for item in results:
                if not isinstance(item, Mapping):
                    continue
                if item.get("status") == "abroge" and item.get("amended_by"):
                    notices.append(f"Cet article est abrogé par {item['amended_by']}.")
                if item.get("previous_version_available") is False:
                    notices.append("L'ancienne version de cet article n'est pas disponible dans le corpus.")
            return {
                "kind": "legal_research",
                "text": first.get("text"),
                "article": first.get("article_number"),
                "status": first.get("status"),
                "notices": notices,
                "mode": data.get("mode"),
            }
    if isinstance(data.get("text"), str):
        return {"kind": "document", "text": data["text"]}
    if isinstance(data.get("result"), Mapping):
        result = data["result"]
        if "analysis_status" in result and "legal_conclusion" in result:
            return {
                "kind": "case_preparatory", "case_id": result.get("case_id"),
                "analysis_status": result.get("analysis_status"),
                "case_summary": result.get("case_summary", {}),
                "timeline": result.get("timeline", []),
                "uncertain_information": result.get("uncertain_information", []),
                "legal_conclusion": None,
                "message_fr": "Analyse préparatoire uniquement. Aucune conclusion juridique validée. La revue humaine reste nécessaire.",
                "message_ar": "تحليل تحضيري فقط. لا توجد خلاصة قانونية معتمدة. تبقى المراجعة البشرية ضرورية.",
            }
        fields = result.get("fields")
        if isinstance(fields, Mapping):
            return {
                "kind": "document", "text": result.get("summary"),
                "document_type": result.get("document_type"), "fields": fields,
                "warnings": data.get("warnings", []),
            }
        if isinstance(result.get("values"), list):
            return {
                "kind": "wage_grid", "text": result.get("title"),
                "effective_date": result.get("effective_date"), "complete": result.get("complete"),
                "warnings": data.get("warnings", []),
            }
    facts, risks = data.get("facts"), data.get("risks")
    if isinstance(facts, list) or isinstance(risks, list):
        return {"kind": "case", "facts": facts or [], "risks": risks or []}
    return None


def _approval_payload(action: PendingAction) -> dict[str, Any]:
    return {
        "approval_id": action.approval_id,
        "request_id": action.request_id,
        "card_id": action.card_id,
        "action_type": action.action_type,
        "summary": action.summary,
        "status": action.status.value,
    }


def approval_history() -> list[dict[str, Any]]:
    """Return the local user's approval actions, not the audit event internals."""

    return [_approval_payload(action) for action in reversed(_WEB_APPROVALS.list_for_actor(_demo_actor()))]


def propose_approval(payload: Mapping[str, Any]) -> dict[str, Any]:
    """Create a pending mock write action; no specialist action is run here."""

    action_type, card_id = payload.get("action_type"), payload.get("card_id")
    definition = _APPROVAL_ACTIONS.get(action_type)
    if definition is None or not isinstance(card_id, str):
        return {"error": "invalid_action"}
    try:
        actor, context = _demo_actor(), _context_for_card(card_id)
        if context.card_type is not definition["card_type"]:
            return {"error": "incompatible_card"}
        action = _WEB_APPROVALS.propose(
            request_id=f"approval-{uuid4()}", actor=actor, context=context,
            action_type=str(action_type), summary=str(definition["summary"]),
            idempotency_key=f"approval-{uuid4()}",
        )
    except (ApprovalError, CardNotFoundError):
        return {"error": "proposal_failed"}
    return {"action": _approval_payload(action)}


def decide_approval(approval_id: str, decision: str) -> dict[str, Any]:
    """Approve, reject, or execute an existing action with a mock executor."""

    try:
        actor = _demo_actor()
        if decision == "approve":
            action = _WEB_APPROVALS.approve(approval_id, actor)
        elif decision == "reject":
            action = _WEB_APPROVALS.reject(approval_id, actor)
        elif decision == "execute":
            _WEB_APPROVALS.execute(approval_id, actor, lambda _: {"execution": "mock_completed"})
            action = _WEB_APPROVALS.get(approval_id)
        else:
            return {"error": "invalid_decision"}
    except ApprovalError:
        return {"error": "invalid_transition"}
    return {"action": _approval_payload(action)}


def calculate(payload: Mapping[str, Any]) -> dict[str, Any]:
    """Execute one explicit Track B request through the same DS1 flow as the demos."""

    operation = payload.get("operation")
    language = payload.get("language", "fr")
    card_choice = payload.get("card_type", "company")  # Legacy v1 input.
    params = payload.get("params", {})
    if operation not in {"smig", "salaire_base", "prime"} or language not in {"fr", "ar"}:
        return _input_error("Opération ou langue invalide.", "العملية أو اللغة غير صالحة.")
    card_id = payload.get("card_id", _CARD_IDS.get(card_choice))
    if not isinstance(card_id, str) or not isinstance(params, Mapping):
        return _input_error("Carte ou paramètres invalides.", "البطاقة أو المعطيات غير صالحة.")

    messages = {
        "smig": "Calcule le SMIG.",
        "salaire_base": "Calcule le salaire de base.",
        "prime": "Calcule la prime.",
    }
    try:
        actor, context = _demo_actor(), _context_for_card(card_id)
    except CardNotFoundError:
        return _input_error("Carte active non autorisée.", "البطاقة النشطة غير مصرح بها.")
    request_id = f"web-{uuid4()}"
    envelope = RequestEnvelope(
        request_id=request_id,
        message=messages[operation], language=language, actor=actor, context=context,
    )
    try:
        result = StateMachine(
            HybridSpecialistDispatcher(),
            planner=StructuredTrackBPlanner(operation=operation, params=params),
            audit_hook=_WEB_AUDIT.record_flow,
        ).run(envelope)
    except ToolContractError as error:
        return _input_error("Les paramètres de calcul sont incomplets ou invalides.", "معطيات الحساب ناقصة أو غير صالحة.", str(error))

    tool_data = result.tool_response.get("data") if result.tool_response else None
    return {
        "request_id": request_id,
        "user_response": format_flow_result(result).to_payload(),
        "result": tool_data.get("result") if isinstance(tool_data, Mapping) else None,
        "citations": result.tool_response.get("citations", []) if result.tool_response else [],
        "prepared_params": dict(params),
    }


def _input_error(message_fr: str, message_ar: str, _internal: str | None = None) -> dict[str, Any]:
    response = UserResponse(
        "error", UserResponseCode.INVALID_PARAMETERS, message_fr, message_ar,
        "correct_parameters", "local-web-request",
    )
    return {"user_response": response.to_payload(), "result": None, "citations": [], "prepared_params": {}}


class AppHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:  # noqa: N802 - stdlib handler contract
        if self.path == "/api/cards":
            self._send_json(HTTPStatus.OK, {"cards": available_cards()})
            return
        if self.path == "/api/audit":
            self._send_json(HTTPStatus.OK, {"events": audit_history()})
            return
        if self.path == "/api/approvals":
            self._send_json(HTTPStatus.OK, {"actions": approval_history()})
            return
        if self.path != "/":
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        self._send(HTTPStatus.OK, _HTML_PATH.read_bytes(), "text/html; charset=utf-8")

    def do_POST(self) -> None:  # noqa: N802 - stdlib handler contract
        is_approval_decision = self.path.startswith("/api/approvals/") and self.path.count("/") == 3
        if self.path not in {"/api/chat", "/api/calculate", "/api/prepare", "/api/approvals", "/api/document-reviews/confirm", "/api/document-reviews/calculate", "/api/case-integration/prepare", "/api/case-integration/complete"} and not is_approval_decision:
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        try:
            content_length = int(self.headers.get("Content-Length", "0"))
            payload = json.loads(self.rfile.read(content_length).decode("utf-8"))
            if not isinstance(payload, dict):
                raise ValueError("payload must be an object")
            if self.path == "/api/chat":
                response = chat(payload)
            elif self.path.startswith('/api/case-integration/'):
                response = case_integration_action(payload, complete=self.path.endswith('/complete'))
            elif self.path == "/api/prepare":
                response = prepare_from_card(payload)
            elif self.path == "/api/calculate":
                response = calculate(payload)
            elif self.path == "/api/approvals":
                response = propose_approval(payload)
            elif self.path == "/api/document-reviews/confirm":
                response = confirm_document_review(payload)
            elif self.path == "/api/document-reviews/calculate":
                response = calculate_from_document_review(payload)
            else:
                response = decide_approval(self.path.rsplit("/", 1)[-1], str(payload.get("decision", "")))
            self._send_json(HTTPStatus.OK, response)
        except (ValueError, json.JSONDecodeError):
            self._send_json(HTTPStatus.BAD_REQUEST, _input_error("Requête JSON invalide.", "طلب JSON غير صالح."))

    def _send_json(self, status: HTTPStatus, payload: Mapping[str, Any]) -> None:
        self._send(status, json.dumps(payload, ensure_ascii=False).encode("utf-8"), "application/json; charset=utf-8")

    def _send(self, status: HTTPStatus, content: bytes, content_type: str) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        self.wfile.write(content)

    def log_message(self, _format: str, *_args: Any) -> None:
        return


def main() -> None:
    server = ThreadingHTTPServer((HOST, PORT), AppHandler)
    print(f"9anoun local interface: http://{HOST}:{PORT}")
    print("Press Ctrl+C to stop.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
