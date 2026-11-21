import src.orchestrator.web_app as web_app
from src.document_intelligence import service as ds3_service
from src.orchestrator.document_intelligence_adapter import DocumentIntelligenceAdapter
from src.orchestrator.hybrid_dispatcher import HybridSpecialistDispatcher
from src.orchestrator.models import ActiveContext, CardType
from src.orchestrator.document_to_track_b import build_payroll_prefill

from src.orchestrator.web_app import (
    approval_history, audit_history, available_cards, calculate, chat, decide_approval,
    calculate_from_document_review, confirm_document_review, prepare_from_card, propose_approval,
)


def test_api_calculates_real_smig_with_citation() -> None:
    response = calculate({"operation": "smig", "card_type": "company", "language": "fr", "params": {"mode": "mensuel", "regime_heures": 48, "date": "2024-01-01"}})
    assert response["user_response"]["status"] == "success"
    assert response["result"]["montant"] == "459.264"
    assert response["citations"][0]["page"] == 2


def test_api_calculates_real_salary_base() -> None:
    response = calculate({"operation": "salaire_base", "card_type": "company", "language": "fr", "params": {"secteur": "METALLURGIE_BATIMENT", "population": "admin_tech", "categorie": "4", "anciennete_annees": 15, "date": "2022-06-01"}})
    assert response["user_response"]["status"] == "success"
    assert response["result"]["montant"] == "593.873"


def test_api_returns_safe_invalid_parameter_response() -> None:
    response = calculate({"operation": "salaire_base", "card_type": "company", "language": "fr", "params": {"secteur": "METALLURGIE_BATIMENT"}})
    assert response["user_response"]["code"] == "INVALID_PARAMETERS"
    assert response["result"] is None


def test_card_selector_only_exposes_authorized_minimal_data() -> None:
    cards = available_cards()
    assert [card["card_id"] for card in cards] == ["company-demo-001", "client-demo-001", "case-demo-001"]
    assert cards[2]["label"] == "Affaire Démo"
    assert cards[0]["employees"] == [{"employee_id": "employee-demo-01", "label": "Ahmed"}]
    assert "track_b_profile" not in cards[0]
    assert cards[0]["documents"] == [
        {"document_id": "doc-company-payslip-01", "label": "Fiche de paie fictive — mars 2026"},
        {"document_id": "doc-company-payslip-02", "label": "Fiche de paie fictive avec pièges — février 2024"},
        {"document_id": "doc-company-payslip-scan-01", "label": "Fiche de paie scannée — mars 2026"},
        {"document_id": "doc-company-wage-grid-01", "label": "Convention collective — grille des salaires"},
    ]


def test_chat_routes_selected_card_document_to_ds3() -> None:
    response = chat({
        "message": "Analyse ce document PDF", "language": "fr", "card_id": "company-demo-001",
        "document_id": "doc-company-payslip-scan-01",
    })
    assert response["user_response"]["status"] == "success"
    assert response["route"] == {"agent": "document_intelligence", "operation": "analyze_document"}
    assert response["answer"]["kind"] == "document"
    assert response["answer"]["fields"]["cnss_employee"]["value"] is None
    assert response["citations"][0]["document_id"] == "doc-company-payslip-scan-01"


def test_document_review_requires_user_selection_and_never_starts_calculation() -> None:
    response = chat({
        "message": "Analyse ce document PDF", "language": "fr", "card_id": "company-demo-001",
        "document_id": "doc-company-payslip-scan-01",
    })
    review = response["document_review"]
    assert review["threshold"] == 0.9
    assert review["mode"] == "mock"
    states = {field["name"]: field["state"] for field in review["fields"]}
    assert states["base_salary"] == "verified"
    assert states["cnss_employee"] == "unavailable"
    assert states["sub_category"] == "unavailable"
    confirmed = confirm_document_review({
        "review_id": review["review_id"], "confirmed_fields": ["base_salary"],
    })
    assert confirmed["status"] == "confirmed"
    assert confirmed["next_action"] == "review_ds5_prefill_then_submit_explicit_calculation"
    assert confirmed["ds5_prefill"]["candidates"][0]["operation"] == "salaire_base"


def test_document_review_rejects_an_unusable_field() -> None:
    response = chat({
        "message": "Analyse ce document PDF", "language": "fr", "card_id": "company-demo-001",
        "document_id": "doc-company-payslip-scan-01",
    })
    rejected = confirm_document_review({
        "review_id": response["document_review"]["review_id"], "confirmed_fields": ["cnss_employee"],
    })
    assert rejected["error"] == "unconfirmed_or_unusable_field"


def test_low_confidence_document_field_is_visible_but_cannot_be_confirmed() -> None:
    review = web_app._create_document_review(
        data={"mode": "live", "result": {"fields": {
            "weak_field": {
                "value": "valeur lue", "value_type": "texte", "confidence": 0.89,
                "citation_id": "citation-weak",
            },
        }}},
        citations=[{
            "citation_id": "citation-weak", "document_id": "doc-company-payslip-01",
            "page": 1, "excerpt": "valeur lue",
        }],
        context=ActiveContext(
            "org-demo", "company-demo-001", CardType.COMPANY,
            {"document_id": "doc-company-payslip-01"},
        ),
    )
    assert review is not None
    assert review["fields"][0]["state"] == "review_required"
    rejected = confirm_document_review({
        "review_id": review["review_id"], "confirmed_fields": ["weak_field"],
    })
    assert rejected["error"] == "unconfirmed_or_unusable_field"


def test_mock_document_review_cannot_launch_a_real_ds5_calculation() -> None:
    response = chat({
        "message": "Analyse ce document PDF", "language": "fr", "card_id": "company-demo-001",
        "document_id": "doc-company-payslip-01",
    })
    review = response["document_review"]
    confirmed = confirm_document_review({
        "review_id": review["review_id"],
        "confirmed_fields": ["period_start", "pay_mode", "work_hours_regime", "hire_date", "category", "base_salary"],
    })
    assert {candidate["operation"] for candidate in confirmed["ds5_prefill"]["candidates"]} == {
        "smig", "salaire_base", "prime",
    }
    calculation = calculate_from_document_review({
        "review_id": review["review_id"], "operation": "salaire_base", "language": "fr",
        "user_inputs": {"population": "admin_tech", "anciennete_annees": "6.495890", "secteur": "INTERDIT"},
    })
    assert calculation["user_response"]["status"] == "refused"
    assert calculation["user_response"]["specialist_code"] == "NON_LIVE_DOCUMENT"
    assert calculation["user_response"]["message_ar"]


def test_document_calculation_rejects_every_mode_other_than_live() -> None:
    for mode in (None, "mock", "MOCK", "demo"):
        response = chat({
            "message": "Analyse ce document PDF", "language": "fr", "card_id": "company-demo-001",
            "document_id": "doc-company-payslip-01",
        })
        review = response["document_review"]
        confirmed = confirm_document_review({
            "review_id": review["review_id"],
            "confirmed_fields": ["period_start", "pay_mode", "work_hours_regime"],
        })
        assert confirmed["status"] == "confirmed"
        web_app._DOCUMENT_REVIEWS[review["review_id"]]["mode"] = mode
        calculation = calculate_from_document_review({
            "review_id": review["review_id"], "operation": "smig", "language": "fr", "user_inputs": {},
        })
        assert calculation["user_response"]["status"] == "refused"
        assert calculation["user_response"]["specialist_code"] == "NON_LIVE_DOCUMENT"
        assert calculation["user_response"]["message_fr"]
        assert calculation["user_response"]["message_ar"]


def test_live_ds3_service_can_launch_explicit_ds5_calculation_with_separate_citations(monkeypatch) -> None:
    cards = web_app._demo_cards()
    document = cards[0]["data"]["documents"][0]
    document.update({
        "label": "Fiche de paie fictive — PDF",
        "file_name": "paie_fictive_01_fr.pdf",
        "mime_type": "application/pdf",
    })
    monkeypatch.setattr(web_app, "_demo_cards", lambda: cards)
    fields = {
        "period_start": {"value": "2024-01-01", "value_type": "date", "confidence": 0.95, "citation_id": "c-period"},
        "pay_mode": {"value": "mensuel", "value_type": "texte", "confidence": 0.95, "citation_id": "c-mode"},
        "work_hours_regime": {"value": "48", "value_type": "entier", "confidence": 0.95, "citation_id": "c-hours"},
        "hire_date": {"value": "2017-07-01", "value_type": "date", "confidence": 0.95, "citation_id": "c-hire"},
        "category": {"value": "4", "value_type": "texte", "confidence": 0.95, "citation_id": "c-category"},
        "base_salary": {"value": "500.000", "value_type": "montant", "confidence": 0.95, "citation_id": "c-salary"},
    }
    citations = [
        {"citation_id": citation_id, "document_id": "doc-company-payslip-01", "page": 1, "excerpt": citation_id}
        for citation_id in ("c-period", "c-mode", "c-hours", "c-hire", "c-category", "c-salary")
    ]

    def live_handler(request):
        assert request["document"]["file_name"] == "paie_fictive_01_fr.pdf"
        assert request["document"]["mime_type"] == "application/pdf"
        assert request["document"]["storage_ref"] == (
            "tradrly://cards/company-demo-001/documents/doc-company-payslip-01"
        )
        return {
            "contract_version": "ds3.v2", "request_id": request["request_id"],
            "operation": request["operation"], "status": "ok", "refus": None,
            "computed_by": "document_intelligence.service", "mode": "live",
            "result": {"complete": True, "document_type": "fiche_de_paie", "fields": fields},
            "citations": citations, "warnings": [], "ds3_code": None,
        }

    monkeypatch.setattr(ds3_service, "handle_request", live_handler)
    response = chat(
        {
            "message": "Analyse ce document PDF", "language": "fr", "card_id": "company-demo-001",
            "document_id": "doc-company-payslip-01",
        },
        dispatcher=HybridSpecialistDispatcher(
            document_intelligence_adapter=DocumentIntelligenceAdapter(handler_mode="live"),
        ),
    )
    review = response["document_review"]
    assert review["mode"] == "live"
    assert response["citations"] == citations
    confirmed = confirm_document_review({
        "review_id": review["review_id"],
        "confirmed_fields": ["period_start", "pay_mode", "work_hours_regime", "hire_date", "category", "base_salary"],
    })
    assert confirmed["status"] == "confirmed"
    calculation = calculate_from_document_review({
        "review_id": review["review_id"], "operation": "salaire_base", "language": "fr",
        "user_inputs": {"population": "admin_tech", "anciennete_annees": "6.495890", "secteur": "INTERDIT"},
    })
    assert calculation["user_response"]["status"] == "success"
    assert calculation["prepared_params"]["secteur"] == "METALLURGIE_BATIMENT"
    assert calculation["document_citations"]
    assert calculation["payroll_citations"]
    assert calculation["salary_comparison_warning"] is not None


def test_document_seniority_is_only_a_proposal_until_the_user_confirms_it() -> None:
    response = chat({
        "message": "Analyse ce document PDF", "language": "fr", "card_id": "company-demo-001",
        "document_id": "doc-company-payslip-01",
    })
    review = response["document_review"]
    confirmed = confirm_document_review({
        "review_id": review["review_id"], "confirmed_fields": ["period_start", "hire_date", "category"],
    })
    salary = next(item for item in confirmed["ds5_prefill"]["candidates"] if item["operation"] == "salaire_base")
    assert "anciennete_annees" not in salary["params"]
    assert salary["proposed_values"]["anciennete_annees"]


def test_document_review_cannot_call_ds5_before_confirmation() -> None:
    blocked = calculate_from_document_review({
        "review_id": "unknown", "operation": "smig", "language": "fr", "user_inputs": {},
    })
    assert blocked["error"] == "document_confirmation_required"


def test_document_prefill_rejects_a_sector_without_an_active_d30_grid() -> None:
    prefill = build_payroll_prefill(
        fields={
            "period_start": {"value": "2024-01-01"},
            "category": {"value": "4"},
        },
        confirmed_fields={"period_start", "category"},
        company_sector="UNKNOWN_SECTOR",
    )
    salary = next(item for item in prefill["candidates"] if item["operation"] == "salaire_base")
    assert "secteur" in salary["missing"]
    assert "secteur" not in salary["params"]


def test_chat_rejects_document_not_owned_by_active_card() -> None:
    response = chat({
        "message": "Analyse ce document PDF", "language": "fr", "card_id": "client-demo-001",
        "document_id": "doc-company-payslip-01",
    })
    assert response["user_response"]["status"] == "error"


def test_chat_handles_a_cited_arabic_ds2_success_or_reasoned_refusal() -> None:
    response = chat({
        "message": "ما هو الفصل القانوني المتعلق بمنحة النقل في قطاع BTP؟", "language": "ar",
    })
    assert response["route"] == {"agent": "legal_retrieval", "operation": "search"}
    assert response["user_response"]["status"] in {"success", "refused"}
    if response["user_response"]["status"] == "success":
        assert response["answer"]["kind"] == "legal_research"
        assert response["answer"]["mode"] in {"mock", "live"}
        assert response["citations"]
    else:
        assert response["answer"] is None
        assert response["user_response"]["code"] in {"SOURCE_MISSING", "OUT_OF_SCOPE"}
        assert response["user_response"]["message_fr"]
        assert response["user_response"]["message_ar"]


def test_chat_names_the_actual_sector_choices_in_both_languages() -> None:
    response = chat({
        "message": "Calcule le salaire de base BTP et associations, catégorie 4 au 2024-01-01.",
        "language": "fr", "card_id": "company-demo-001",
    })
    user = response["user_response"]
    assert user["status"] == "clarification_required"
    assert "BTP" in user["message_fr"]
    assert "Associations" in user["message_fr"]
    assert "البناء والأشغال العامة" in user["message_ar"]
    assert "جمعيات رعاية الأشخاص المعوقين" in user["message_ar"]


def test_chat_explains_a_single_ambiguous_building_term_without_claiming_multiple_sectors() -> None:
    response = chat({
        "message": "Calcule le salaire de base bâtiment, catégorie 4 au 2024-01-01.",
        "language": "fr", "card_id": "company-demo-001",
    })
    user = response["user_response"]
    assert user["status"] == "clarification_required"
    assert "Ce terme peut correspondre" in user["message_fr"]
    assert "BTP" in user["message_fr"]
    assert "Construction métallique" in user["message_fr"]
    assert "قد يشير هذا المصطلح" in user["message_ar"]


def test_chat_limits_a_metallurgy_clarification_to_the_d30_choice() -> None:
    response = chat({
        "message": "Calcule le salaire de base métallurgie, catégorie 4 au 2024-01-01.",
        "language": "fr", "card_id": "company-demo-001",
    })
    user = response["user_response"]
    assert user["status"] == "clarification_required"
    assert "métallurgie" in user["message_fr"]
    assert "Construction métallique" in user["message_fr"]
    assert "BTP" not in user["message_fr"]
    assert "البناء المعدني" in user["message_ar"]


def test_chat_routes_case_prompt_to_real_ds4_handler() -> None:
    response = chat({
        "message": "Analyse les preuves de ce dossier", "language": "fr", "card_id": "case-demo-001",
    })
    assert response["user_response"]["status"] == "refused"
    assert response["user_response"]["code"] == "SOURCE_MISSING"
    assert response["route"] == {"agent": "track_a_legal", "operation": "analyze_case"}
    assert response["answer"] is None


def test_chat_asks_for_clarification_without_guessing_payroll_fields() -> None:
    response = chat({"message": "Calcule le salaire de base", "language": "fr", "card_id": "company-demo-001"})
    assert response["user_response"]["code"] == "CLARIFICATION_REQUIRED"
    assert response["route"] == {"agent": None, "operation": None}


def test_chat_calculates_btp_occasional_salary_from_prompt() -> None:
    response = chat({
        "message": "Calcule le salaire de base BTP pour population ouvriers_occasionnels, catégorie 7, "
        "sous-catégorie 2 au 2023-06-01.",
        "language": "fr", "card_id": "company-demo-001",
    })
    assert response["user_response"]["status"] == "success"
    assert response["answer"]["amount"] == "4.276"
    assert response["answer"]["unit"] == "TND/heure"


def test_chat_displays_ds5_article_13_hypotheses_with_salary() -> None:
    response = chat({
        "message": "Calcule le salaire de base secteur construction métallique, population admin-tech, "
        "catégorie 4, 25 ans d'ancienneté au 2024-06-01.",
        "language": "fr", "card_id": "company-demo-001",
    })
    assert response["user_response"]["status"] == "success"
    assert response["answer"]["hypotheses"]
    assert response["answer"]["hypotheses_label"] == "Hypothèses"


def test_chat_runs_human_approval_lifecycle_from_prompt_only() -> None:
    proposed = chat({
        "message": "Génère un rapport de paie", "language": "fr", "card_id": "company-demo-001",
    })
    assert proposed["answer"]["status"] == "pending_approval"
    assert proposed["route"] == {"agent": "orchestrator", "operation": "human_approval"}

    approved = chat({"message": "Approuve la dernière demande", "language": "fr"})
    assert approved["answer"]["status"] == "approved"

    executed = chat({"message": "Exécute la dernière demande", "language": "fr"})
    assert executed["answer"]["status"] == "executed"


def test_chat_refuses_payroll_report_proposal_without_company_card() -> None:
    response = chat({"message": "Génère un rapport de paie", "language": "fr", "card_id": "client-demo-001"})
    assert response["user_response"]["status"] == "error"
    assert response["user_response"]["next_action"] == "select_company_card"


def test_card_prepare_prefills_salary_without_inference() -> None:
    response = prepare_from_card({
        "operation": "salaire_base", "card_id": "company-demo-001",
        "employee_id": "employee-demo-01", "date": "2022-06-01",
    })
    assert response["missing"] == []
    assert response["prepared_params"]["categorie"] == "4"
    assert response["prepared_params"]["anciennete_annees"] == 15


def test_card_prepare_keeps_missing_date_explicit() -> None:
    response = prepare_from_card({
        "operation": "salaire_base", "card_id": "company-demo-001",
        "employee_id": "employee-demo-01",
    })
    assert response["missing"] == ["date"]


def test_calculation_creates_unique_safe_audit_history_entry() -> None:
    response = calculate({
        "operation": "smig", "card_id": "company-demo-001", "language": "fr",
        "params": {"mode": "mensuel", "regime_heures": 48, "date": "2024-01-01"},
    })
    event = audit_history()[0]
    serialized = str(event)
    assert response["request_id"].startswith("web-")
    assert event["request_id"] == response["request_id"]
    assert event["operation"] == "smig"
    assert event["card_id"] == "company-demo-001"
    assert "459.264" not in serialized
    assert "regime_heures" not in serialized


def test_human_approval_requires_pending_then_approval_before_mock_execution() -> None:
    proposed = propose_approval({"action_type": "generate_payroll_report", "card_id": "company-demo-001"})
    approval_id = proposed["action"]["approval_id"]
    assert proposed["action"]["status"] == "pending_approval"
    assert decide_approval(approval_id, "execute")["error"] == "invalid_transition"
    assert decide_approval(approval_id, "approve")["action"]["status"] == "approved"
    assert decide_approval(approval_id, "execute")["action"]["status"] == "executed"
    assert approval_history()[0]["approval_id"] == approval_id


def test_human_approval_rejects_incompatible_card() -> None:
    response = propose_approval({"action_type": "generate_payroll_report", "card_id": "client-demo-001"})
    assert response["error"] == "incompatible_card"
