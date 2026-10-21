"""Mock DS3 v2 : même interface que le futur service réel, mais réponses préparées à la main.

Utilisation côté DS1 :

    from src.document_intelligence.contract.v2.mock import handle_request, list_operations
    response = handle_request(request_dict)

Le mock ne lit aucun fichier. Il choisit sa réponse selon la requête :
- requête non conforme                             -> refus PARAM_INVALIDE   (ds3_code INVALID_REQUEST)
- opération inconnue                               -> refus PARAM_INVALIDE   (ds3_code UNSUPPORTED_OPERATION)
- document.card_id différent de context.card_id   -> refus ACCES_REFUSE     (ds3_code ACCESS_DENIED)
- extension non supportée                          -> refus HORS_SCOPE       (ds3_code UNSUPPORTED_FORMAT)
- nom de fichier contenant "corrompu"              -> refus PARAM_INVALIDE   (ds3_code FILE_EMPTY_OR_CORRUPTED)
- nom de fichier contenant "blanc"                 -> refus SOURCE_MANQUANTE (ds3_code UNREADABLE_DOCUMENT)
- nom de fichier contenant "timeout"               -> erreur TIMEOUT, retryable = true
- opération extract_wage_grid                      -> extrait de la grille des salaires n° 2
- nom de fichier contenant "illisible"             -> ok, complete = false (retenue CNSS illisible)
- nom de fichier contenant "arabe"                 -> fiche de paie en arabe (catégorie « 1 ب » -> "1B")
- sinon                                            -> fiche de paie en français lue entièrement

Toutes les données de fiche de paie sont fictives. Le mock ne lève jamais d'exception.
"""

from __future__ import annotations

from pathlib import PurePosixPath
from typing import Any, Final

from pydantic import ValidationError

from src.document_intelligence.contract.v2.models import (
    DocumentAnalysis,
    DocumentCitation,
    DS3Code,
    DS3Request,
    DS3Response,
    Erreur,
    ExtractedField,
    GradeInfo,
    PayLine,
    Refus,
    RefusCode,
    ResponseMeta,
    UnreadableReason,
    ValueType,
    WageGrid,
    WageValue,
)

PIPELINE_VERSION: Final = "ds3-mock-0.2.0"
COMPUTED_BY: Final = "document_intelligence.mock"
SUPPORTED_EXTENSIONS: Final = {".pdf", ".png", ".jpg", ".jpeg", ".docx", ".xlsx", ".csv"}
OPERATIONS: Final = ("analyze_document", "extract_wage_grid")

# Code DS3 -> (code de refus common, message FR, message AR).
_REFUS: Final[dict[DS3Code, tuple[RefusCode, str, str]]] = {
    "INVALID_REQUEST": ("PARAM_INVALIDE", "Requête invalide.", "طلب غير صالح."),
    "UNSUPPORTED_OPERATION": ("PARAM_INVALIDE", "Opération non prise en charge par DS3.", "عملية غير مدعومة."),
    "UNSUPPORTED_FORMAT": (
        "HORS_SCOPE",
        "Format de fichier non supporté (PDF, image, DOCX, XLSX ou CSV attendu).",
        "صيغة الملف غير مدعومة.",
    ),
    "FILE_EMPTY_OR_CORRUPTED": (
        "PARAM_INVALIDE",
        "Le fichier est vide ou endommagé et ne peut pas être lu.",
        "الملف فارغ أو تالف ولا يمكن قراءته.",
    ),
    "FILE_TOO_LARGE": ("PARAM_INVALIDE", "Le fichier dépasse la taille autorisée.", "حجم الملف يتجاوز الحد المسموح به."),
    # Message neutre : ne confirme pas l'existence du document dans une autre carte.
    "ACCESS_DENIED": (
        "ACCES_REFUSE",
        "Ce document n'est pas accessible dans le contexte actuel.",
        "هذه الوثيقة غير متاحة في السياق الحالي.",
    ),
    "UNREADABLE_DOCUMENT": (
        "SOURCE_MANQUANTE",
        "Aucune valeur lisible dans ce document : rien n'est extrait.",
        "لا توجد أي قيمة مقروءة في هذه الوثيقة.",
    ),
    "NO_TABLE_FOUND": (
        "SOURCE_MANQUANTE",
        "Aucune grille de salaires trouvée dans ce document.",
        "لم يتم العثور على جدول أجور في هذه الوثيقة.",
    ),
}

# Code DS3 -> (message FR, message AR, retryable).
_ERREURS: Final[dict[DS3Code, tuple[str, str, bool]]] = {
    "TIMEOUT": ("L'analyse a pris trop de temps. Réessayez.", "استغرق التحليل وقتا طويلا. أعد المحاولة.", True),
    "INTERNAL_ERROR": ("Incident technique pendant l'analyse.", "حدث خلل تقني أثناء التحليل.", False),
}


def list_operations() -> list[dict[str, Any]]:
    """Opérations exposées par DS3, avec champs obligatoires et optionnels."""
    common_required = [
        "contract_version",
        "request_id",
        "lang",
        "operation",
        "context.organization_id",
        "context.user_id",
        "context.role",
        "context.card_id",
        "context.card_type",
        "document.document_id",
        "document.card_id",
        "document.file_name",
        "document.mime_type",
        "document.storage_ref",
    ]
    optional = [
        "case_id",
        "options.language_hint",
        "options.expected_type",
        "options.pages",
        "options.min_confidence",
    ]
    return [
        {
            "operation": "analyze_document",
            "description": "Lit un document de carte (fiche de paie, facture, contrat, pièce) "
            "et renvoie type, résumé, champs extraits, lignes de paie, tableaux et citations.",
            "required": common_required,
            "optional": optional,
            "result_type": "DocumentAnalysis",
        },
        {
            "operation": "extract_wage_grid",
            "description": "Extrait une grille de salaires (catégorie x échelon) d'une convention "
            "collective, avec date d'effet et confiance par case.",
            "required": common_required,
            "optional": optional,
            "result_type": "WageGrid",
        },
    ]


def _meta() -> ResponseMeta:
    return ResponseMeta(pipeline_version=PIPELINE_VERSION, processing_ms=120)


def _envelope(request_id: str | None, operation: str, case_id: str | None, card_id: str | None,
              document_id: str | None) -> dict[str, Any]:
    return {
        "request_id": request_id,
        "case_id": case_id,
        "computed_by": COMPUTED_BY,
        "mode": "mock",
        "operation": operation,
        "card_id": card_id,
        "document_id": document_id,
        "meta": _meta(),
    }


def _refus(env: dict[str, Any], code: DS3Code, detail: str | None = None) -> dict[str, Any]:
    refus_code, fr, ar = _REFUS[code]
    if detail:
        fr = f"{fr} {detail}"
    return DS3Response(
        **env, status="refus", refus=Refus(code=refus_code, message_fr=fr, message_ar=ar),
        citations=[], result=None, ds3_code=code,
    ).to_json()


def _erreur(env: dict[str, Any], code: DS3Code) -> dict[str, Any]:
    fr, ar, retryable = _ERREURS[code]
    return DS3Response(
        **env, status="erreur", refus=None, erreur=Erreur(type=code, message_fr=fr, message_ar=ar),
        citations=[], result=None, ds3_code=code, retryable=retryable,
    ).to_json()


def _field(value: str | None, value_type: ValueType, confidence: float, citation_id: str | None,
           reason: UnreadableReason | None = None, currency: bool = False) -> ExtractedField:
    return ExtractedField(value=value, value_type=value_type, confidence=confidence, citation_id=citation_id,
                          unreadable_reason=reason, currency="TND" if currency else None)


def _absent(value_type: ValueType) -> ExtractedField:
    return _field(None, value_type, 0.0, None, "absent_du_document")


def _payslip(req: DS3Request, env: dict[str, Any], unreadable: bool, arabic: bool) -> dict[str, Any]:
    doc = req.document.document_id

    def cite(cid: str, bbox: list[float], excerpt: str) -> DocumentCitation:
        return DocumentCitation(citation_id=cid, document_id=doc, page=1, bbox=bbox, excerpt=excerpt)

    if arabic:
        excerpts = {
            "c1": "الاسم واللقب : أحمد بن صالح", "c2": "الفترة : من 01/03/2026 إلى 31/03/2026",
            "c3": "تاريخ الانتداب : 01/09/2019", "c4": "الصنف : 1 ب - الدرجة : 2",
            "c5": "الخطة : عون إداري - قار", "c6": "التأجير : شهري - 173,33 س",
            "c7": "الأجر الأساسي 424,100", "c8": "منحة النقل 56,000", "c9": "منحة الحضور 36,000",
            "c10": "الأجر الخام 516,100", "c11": "" if unreadable else "الضمان الاجتماعي 47,378",
        }
        category, qualification, hours = "1B", "عون إداري", "40"
    else:
        excerpts = {
            "c1": "Nom : Ahmed Ben Salah", "c2": "Période : du 01/03/2026 au 31/03/2026",
            "c3": "Date d'entrée : 01/09/2019 - Ancienneté : 6 ans 6 mois", "c4": "Catégorie 3 - Échelon 2",
            "c5": "Emploi : Agent administratif - Permanent", "c6": "Paiement : mensuel - Horaire : 208 h",
            "c7": "Salaire de base 424.100", "c8": "Prime de transport 56.000", "c9": "Prime de présence 36.000",
            "c10": "Salaire brut 516.100", "c11": "" if unreadable else "Retenue CNSS 47.378",
        }
        category, qualification, hours = "3", "Agent administratif", "48"
    boxes: dict[str, list[float]] = {
        "c1": [72, 110, 260, 128], "c2": [72, 140, 300, 158], "c3": [72, 170, 360, 188],
        "c4": [72, 200, 300, 218], "c5": [72, 230, 360, 248], "c6": [72, 260, 360, 278],
        "c7": [400, 300, 470, 318], "c8": [400, 320, 470, 338], "c9": [400, 340, 470, 358],
        "c10": [400, 380, 470, 398], "c11": [400, 420, 470, 438],
    }
    citations = [cite(cid, boxes[cid], text) for cid, text in excerpts.items()]

    fields = {
        "employee_name": _field("أحمد بن صالح" if arabic else "Ahmed Ben Salah", "texte", 0.97, "c1"),
        "period_start": _field("2026-03-01", "date", 0.98, "c2"),
        "period_end": _field("2026-03-31", "date", 0.98, "c2"),
        "hire_date": _field("2019-09-01", "date", 0.93, "c3"),
        "seniority_years_printed": _absent("texte") if arabic else _field("6 ans 6 mois", "texte", 0.92, "c3"),
        "category": _field(category, "texte", 0.95, "c4"),
        "sub_category": _absent("texte"),
        "grade": _field("2", "entier", 0.95, "c4"),
        "job_qualification": _field(qualification, "texte", 0.94, "c5"),
        "employment_status": _field("permanent", "enum", 0.93, "c5"),
        "pay_mode": _field("mensuel", "enum", 0.96, "c6"),
        "work_hours_regime": _field(hours, "entier", 0.95, "c6"),
        "base_salary": _field("424.100", "montant", 0.96, "c7", currency=True),
        "gross_salary": _field("516.100", "montant", 0.95, "c10", currency=True),
        "cnss_employee": (
            _field(None, "montant", 0.31, "c11", "zone_illisible", currency=True)
            if unreadable
            else _field("47.378", "montant", 0.94, "c11", currency=True)
        ),
    }
    pay_lines = [
        PayLine(label="منحة النقل" if arabic else "Prime de transport", amount="56.000", confidence=0.95,
                citation_id="c8"),
        PayLine(label="منحة الحضور" if arabic else "Prime de présence", amount="36.000", confidence=0.95,
                citation_id="c9"),
    ]
    analysis = DocumentAnalysis(
        document_type="fiche_de_paie",
        document_type_confidence=0.97,
        languages=["ar"] if arabic else ["fr"],
        page_count=1,
        complete=not unreadable,
        # Le résumé suit la langue demandée (lang), pas celle du document.
        summary=(f"Fiche de paie de mars 2026, catégorie {category}, échelon 2." if req.lang == "fr"
                 else f"كشف أجر شهر مارس 2026، الصنف {category}، الدرجة 2."),
        fields=fields,
        pay_lines=pay_lines,
    )
    warnings = ["Données fictives (mock)."]
    if arabic:
        warnings.append("Catégorie imprimée « 1 ب », normalisée en « 1B ».")
    if unreadable:
        warnings.append("Page 1 : retenue CNSS illisible, valeur non renvoyée (complete = false).")
    return DS3Response(
        **env, status="ok", refus=None, citations=citations, result=analysis, warnings=warnings,
    ).to_json()


# Grille des salaires n° 2 (page 21), valeurs relevées à la main sur l'image.
# Échelons 1 -> 14 (de droite à gauche dans le document).
_GRID_ROWS: Final[dict[int, list[str]]] = {
    1: ["344.500", "346.700", "348.900", "351.100", "353.300", "355.500", "357.700",
        "359.900", "362.100", "364.300", "366.500", "371.200", "373.400", "375.600"],
    15: ["1275.000", "1291.000", "1307.000", "1323.000", "1339.000", "1355.000", "1371.000",
         "1387.000", "1403.000", "1423.000", "1443.000", "1463.000", "1483.000", "1503.000"],
}
_GRADES: Final = [(1, 1, "0-1"), (2, 1, "1-2"), (3, 2, "2-4"), (4, 2, "4-6"), (5, 2, "6-8"),
                  (6, 2, "8-10"), (7, 2, "10-12"), (8, 2, "12-14"), (9, 2, "14-16"), (10, 2, "16-18"),
                  (11, 2, "18-20"), (12, 2, "20-22"), (13, 2, "22-24"), (14, 2, "24")]


def _wage_grid(req: DS3Request, env: dict[str, Any]) -> dict[str, Any]:
    doc = req.document.document_id
    grid = WageGrid(
        title="جدول الأجور عدد 2",
        sector_ar="أعوان مؤسسات الحراسة والسلامة ونقل العملة",
        sector_code="gardiennage_securite_transport_fonds",  # table des secteurs (D30), libellé arabe identique
        effective_date="2010-05-01",
        unit="TND/mois",
        legal_basis="الفصل 43",
        citation_id="c1",
        complete=False,
        grades=[GradeInfo(grade=g, duration_years=d, seniority=s) for g, d, s in _GRADES],
        values=[
            WageValue(category=cat, grade=i + 1, amount=amount, confidence=0.97)
            for cat, amounts in _GRID_ROWS.items()
            for i, amount in enumerate(amounts)
        ],
        note="Les salaires incluent la prime complémentaire provisoire (أمر عدد 437 لسنة 1981، "
        "المرفع فيها بالأمر عدد 501 لسنة 1982).",
    )
    return DS3Response(
        **env,
        status="ok",
        refus=None,
        citations=[DocumentCitation(citation_id="c1", document_id=doc, page=21, bbox=None,
                                    excerpt="جدول الأجور عدد 2 يقع العمل به بداية من 1 ماي 2010")],
        result=grid,
        warnings=[
            "Mock : seules les catégories 1 et 15 sont fournies (complete = false).",
            "Grille en vigueur à partir de 2010 : vérifier auprès de DS2 si elle a été remplacée.",
        ],
    ).to_json()


def handle_request(request: dict[str, Any]) -> dict[str, Any]:
    """Point d'entrée unique DS3. Reçoit et renvoie du JSON (dict), jamais d'exception."""
    try:
        return _handle(request)
    except Exception:  # noqa: BLE001 - le contrat interdit de propager une exception à DS1
        raw_id = request.get("request_id") if isinstance(request, dict) else None
        env = _envelope(raw_id if isinstance(raw_id, str) else None, "unknown", None, None, None)
        return _erreur(env, "INTERNAL_ERROR")


def _handle(request: dict[str, Any]) -> dict[str, Any]:
    raw_id = request.get("request_id")
    operation = str(request.get("operation", "unknown"))
    env = _envelope(raw_id if isinstance(raw_id, str) and raw_id else None, operation, None, None, None)
    if operation not in OPERATIONS:
        return _refus(env, "UNSUPPORTED_OPERATION", f"Opérations acceptées : {', '.join(OPERATIONS)}.")
    try:
        req = DS3Request.model_validate(request)
    except ValidationError as exc:
        first = exc.errors()[0]
        where = ".".join(str(p) for p in first["loc"])
        return _refus(env, "INVALID_REQUEST", f"{where} : {first['msg']}")

    doc = req.document
    env = _envelope(req.request_id, req.operation, req.case_id, req.context.card_id, None)
    if doc.card_id != req.context.card_id:
        # document_id non renvoyé : on ne confirme rien sur un document d'une autre carte.
        return _refus(env, "ACCESS_DENIED")
    env["document_id"] = doc.document_id
    if PurePosixPath(doc.file_name).suffix.lower() not in SUPPORTED_EXTENSIONS:
        return _refus(env, "UNSUPPORTED_FORMAT")
    name = doc.file_name.lower()
    if "corrompu" in name:
        return _refus(env, "FILE_EMPTY_OR_CORRUPTED")
    if "blanc" in name:
        return _refus(env, "UNREADABLE_DOCUMENT")
    if "timeout" in name:
        return _erreur(env, "TIMEOUT")
    if req.operation == "extract_wage_grid":
        return _wage_grid(req, env)
    return _payslip(req, env, unreadable="illisible" in name, arabic="arabe" in name)
