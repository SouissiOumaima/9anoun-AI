"""Mock DS3 : même interface que le futur service réel, mais réponses préparées à la main.

Utilisation côté DS1 :

    from src.document_intelligence.contract.mock import handle_request, list_operations
    response = handle_request(request_dict)

Le mock ne lit aucun fichier. Il choisit sa réponse selon la requête :
- document.card_id différent de context.card_id   -> erreur ACCESS_DENIED
- extension non supportée                          -> erreur UNSUPPORTED_FORMAT
- nom de fichier contenant "corrompu"              -> erreur FILE_EMPTY_OR_CORRUPTED
- nom de fichier contenant "illisible"             -> succès partiel (un montant illisible)
- opération extract_wage_grid                      -> extrait de la grille des salaires n° 2
- sinon                                            -> fiche de paie fictive lue avec succès

Toutes les données de fiche de paie sont fictives.
"""

from __future__ import annotations

from pathlib import PurePosixPath
from typing import Any

from pydantic import ValidationError

from src.document_intelligence.contract.models import (
    Citation,
    DocumentAnalysis,
    DS3Error,
    DS3Request,
    DS3Response,
    ErrorCode,
    ExtractedField,
    GradeInfo,
    Position,
    ResponseMeta,
    WageGrid,
    WageValue,
)

PIPELINE_VERSION = "ds3-mock-0.1.0"
SUPPORTED_EXTENSIONS = {".pdf", ".png", ".jpg", ".jpeg", ".docx", ".xlsx", ".csv"}

_ERRORS: dict[ErrorCode, tuple[str, str, bool]] = {
    "INVALID_REQUEST": ("Requête invalide : voir le détail.", "طلب غير صالح.", False),
    "UNSUPPORTED_FORMAT": (
        "Format de fichier non supporté (PDF, image, DOCX, XLSX ou CSV attendu).",
        "صيغة الملف غير مدعومة.",
        False,
    ),
    "FILE_EMPTY_OR_CORRUPTED": (
        "Le fichier est vide ou endommagé et ne peut pas être lu.",
        "الملف فارغ أو تالف ولا يمكن قراءته.",
        False,
    ),
    "ACCESS_DENIED": (
        "Ce document n'appartient pas à la carte active.",
        "هذه الوثيقة لا تنتمي إلى البطاقة النشطة.",
        False,
    ),
}


def list_operations() -> list[dict[str, Any]]:
    """Opérations exposées par DS3, avec champs obligatoires et optionnels."""
    common_required = [
        "contract_version",
        "request_id",
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
        "options.language_hint",
        "options.expected_type",
        "options.pages",
        "options.min_confidence",
    ]
    return [
        {
            "operation": "analyze_document",
            "description": "Lit un document de carte (fiche de paie, facture, contrat, pièce) "
            "et renvoie type, résumé, champs extraits, tableaux et citations.",
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
    return ResponseMeta(pipeline_version=PIPELINE_VERSION, mode="mock", processing_ms=120)


def _error(request_id: str, operation: str, code: ErrorCode, detail: str | None = None,
           card_id: str | None = None, document_id: str | None = None) -> dict[str, Any]:
    fr, ar, retryable = _ERRORS[code]
    if detail:
        fr = f"{fr} {detail}"
    return DS3Response(
        request_id=request_id,
        operation=operation,
        status="error",
        card_id=card_id,
        document_id=document_id,
        result=None,
        error=DS3Error(code=code, message_fr=fr, message_ar=ar, retryable=retryable),
        meta=_meta(),
    ).model_dump(mode="json")


def _payslip(req: DS3Request, unreadable: bool) -> dict[str, Any]:
    doc = req.document.document_id
    cites = [
        Citation(citation_id="c1", document_id=doc, position=Position(page=1, bbox=[72, 110, 260, 128]),
                 excerpt="Nom : Ahmed Ben Salah"),
        Citation(citation_id="c2", document_id=doc, position=Position(page=1, bbox=[72, 140, 300, 158]),
                 excerpt="Période : Mars 2026"),
        Citation(citation_id="c3", document_id=doc, position=Position(page=1, bbox=[72, 170, 300, 188]),
                 excerpt="Catégorie 3 - Échelon 2"),
        Citation(citation_id="c4", document_id=doc, position=Position(page=1, bbox=[400, 300, 470, 318]),
                 excerpt="Salaire de base 424.100"),
        Citation(citation_id="c5", document_id=doc, position=Position(page=1, bbox=[400, 360, 470, 378]),
                 excerpt="Salaire brut 516.100"),
        Citation(citation_id="c6", document_id=doc, position=Position(page=1, bbox=[400, 330, 470, 348]),
                 excerpt="" if unreadable else "Retenue CNSS 48.931"),
    ]
    fields = {
        "employee_name": ExtractedField(value="Ahmed Ben Salah", confidence=0.97, citation_id="c1"),
        "period": ExtractedField(value="2026-03", confidence=0.98, citation_id="c2"),
        "category": ExtractedField(value="3", confidence=0.95, citation_id="c3"),
        "grade": ExtractedField(value="2", confidence=0.95, citation_id="c3"),
        "base_salary": ExtractedField(value="424.100", confidence=0.96, citation_id="c4", currency="TND"),
        "gross_salary": ExtractedField(value="516.100", confidence=0.95, citation_id="c5", currency="TND"),
        "cnss_employee": (
            ExtractedField(value=None, confidence=0.31, citation_id="c6",
                           unreadable_reason="zone_illisible", currency="TND")
            if unreadable
            else ExtractedField(value="48.931", confidence=0.94, citation_id="c6", currency="TND")
        ),
    }
    analysis = DocumentAnalysis(
        document_type="fiche_de_paie",
        document_type_confidence=0.97,
        languages=["fr"],
        page_count=1,
        summary="Fiche de paie de mars 2026 pour un employé de catégorie 3, échelon 2.",
        fields=fields,
    )
    warnings = ["Données fictives (mock)."]
    if unreadable:
        warnings.append("Page 1 : retenue CNSS illisible, valeur non renvoyée.")
    return DS3Response(
        request_id=req.request_id,
        operation=req.operation,
        status="partial" if unreadable else "success",
        card_id=req.context.card_id,
        document_id=doc,
        result=analysis,
        citations=cites,
        warnings=warnings,
        meta=_meta(),
    ).model_dump(mode="json")


# Grille des salaires n° 2 (page 21), valeurs relevées à la main sur l'image.
# Échelons 1 -> 14 (de droite à gauche dans le document).
_GRID_ROWS: dict[int, list[str]] = {
    1: ["344.500", "346.700", "348.900", "351.100", "353.300", "355.500", "357.700",
        "359.900", "362.100", "364.300", "366.500", "371.200", "373.400", "375.600"],
    15: ["1275.000", "1291.000", "1307.000", "1323.000", "1339.000", "1355.000", "1371.000",
         "1387.000", "1403.000", "1423.000", "1443.000", "1463.000", "1483.000", "1503.000"],
}
_GRADES = [(1, 1, "0-1"), (2, 1, "1-2"), (3, 2, "2-4"), (4, 2, "4-6"), (5, 2, "6-8"),
           (6, 2, "8-10"), (7, 2, "10-12"), (8, 2, "12-14"), (9, 2, "14-16"), (10, 2, "16-18"),
           (11, 2, "18-20"), (12, 2, "20-22"), (13, 2, "22-24"), (14, 2, "24")]


def _wage_grid(req: DS3Request) -> dict[str, Any]:
    doc = req.document.document_id
    grid = WageGrid(
        title="جدول الأجور عدد 2",
        sector_ar="أعوان مؤسسات الحراسة والسلامة ونقل العملة",
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
        request_id=req.request_id,
        operation=req.operation,
        status="success",
        card_id=req.context.card_id,
        document_id=doc,
        result=grid,
        citations=[Citation(citation_id="c1", document_id=doc, position=Position(page=21),
                            excerpt="جدول الأجور عدد 2 يقع العمل به بداية من 1 ماي 2010")],
        warnings=[
            "Mock : seules les catégories 1 et 15 sont fournies (complete=false).",
            "Grille en vigueur à partir de 2010 : vérifier auprès de DS2 si elle a été remplacée.",
        ],
        meta=_meta(),
    ).model_dump(mode="json")


def handle_request(request: dict[str, Any]) -> dict[str, Any]:
    """Point d'entrée unique DS3. Reçoit et renvoie du JSON (dict), jamais d'exception."""
    request_id = str(request.get("request_id", "unknown"))
    operation = str(request.get("operation", "unknown"))
    try:
        req = DS3Request.model_validate(request)
    except ValidationError as exc:
        first = exc.errors()[0]
        where = ".".join(str(p) for p in first["loc"])
        return _error(request_id, operation, "INVALID_REQUEST", f"{where} : {first['msg']}")

    doc = req.document
    if doc.card_id != req.context.card_id:
        return _error(req.request_id, req.operation, "ACCESS_DENIED", card_id=req.context.card_id)
    if PurePosixPath(doc.file_name).suffix.lower() not in SUPPORTED_EXTENSIONS:
        return _error(req.request_id, req.operation, "UNSUPPORTED_FORMAT",
                      card_id=req.context.card_id, document_id=doc.document_id)
    name = doc.file_name.lower()
    if "corrompu" in name:
        return _error(req.request_id, req.operation, "FILE_EMPTY_OR_CORRUPTED",
                      card_id=req.context.card_id, document_id=doc.document_id)
    if req.operation == "extract_wage_grid":
        return _wage_grid(req)
    return _payslip(req, unreadable="illisible" in name)
