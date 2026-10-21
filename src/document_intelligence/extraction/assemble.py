"""Assemblage de la réponse ds3.v2 pour une fiche de paie (étape 5 de l'extracteur DS3).

Entrées :
- la requête DS1 (DS3Request v2) ;
- le document au format intermédiaire (lignes avec page, bbox, confiance) ;
- la réponse de Gemini (GeminiPayslipAnswer) : pour chaque champ, la valeur recopiée et sa ligne.

Traitement, entièrement par du code :
1. vérification de chaque valeur contre le document (verify.py) ;
2. normalisation au format du contrat (normalize.py) ;
3. citation = la ligne du document (page, bbox, texte exact) ;
4. confiance = celle de la ligne (1.0 en natif, valeur de l'OCR sinon), jamais celle de Gemini ;
5. résumé écrit par le code à partir des valeurs retenues (aucun texte libre du modèle).
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Final

from pydantic import BaseModel, ConfigDict

from src.document_intelligence.contract.v2.models import (
    DocumentAnalysis,
    DocumentCitation,
    DocumentType,
    DS3Request,
    DS3Response,
    ExtractedField,
    Language,
    PayLine,
    Refus,
    ResponseMeta,
    ValueType,
)
from src.document_intelligence.extraction.normalize import (
    EMPLOYMENT_STATUSES,
    PAY_MODES,
    month_period,
    normalize_amount,
    normalize_category,
    normalize_date,
    normalize_enum,
    normalize_hours,
    to_latin_digits,
)
from src.document_intelligence.extraction.verify import RawField, canon, verify_all, verify_field
from src.document_intelligence.intermediate import IntermediateDocument, TextLine

PIPELINE_VERSION: Final = "ds3-extract-0.1.0"
COMPUTED_BY: Final = "document_intelligence.service"


class RawPayLine(BaseModel):
    """Ligne de prime ou d'indemnité, telle que Gemini l'a recopiée."""

    model_config = ConfigDict(extra="forbid")

    label: str
    amount: str | None
    line_id: str | None


class GeminiPayslipAnswer(BaseModel):
    """Ce qu'on demande à Gemini pour une fiche de paie (c'est aussi le format JSON imposé à l'étape 2)."""

    model_config = ConfigDict(extra="forbid")

    document_type: DocumentType
    fields: dict[str, RawField]
    pay_lines: list[RawPayLine] = []


# ------------------------------------------------------------------ règles par champ


def _text(raw: str) -> str | None:
    return " ".join(raw.split()) or None


def _integer(raw: str) -> str | None:
    text = to_latin_digits(raw).strip()
    return text if text.isdigit() and len(text) <= 3 else None


def _period_start(raw: str) -> str | None:
    """« 01/03/2026 » ou « Mars 2026 » -> premier jour."""
    period = month_period(raw)
    return normalize_date(raw) or (period[0] if period else None)


def _period_end(raw: str) -> str | None:
    """« 31/03/2026 » ou « Mars 2026 » -> dernier jour."""
    period = month_period(raw)
    return normalize_date(raw) or (period[1] if period else None)


@dataclass(frozen=True)
class FieldSpec:
    value_type: ValueType
    normalize: Callable[[str], str | None]
    currency: bool = False


PAYSLIP_FIELDS: Final[dict[str, FieldSpec]] = {
    "employee_name": FieldSpec("texte", _text),
    "period_start": FieldSpec("date", _period_start),
    "period_end": FieldSpec("date", _period_end),
    "hire_date": FieldSpec("date", normalize_date),
    "seniority_years_printed": FieldSpec("texte", _text),
    "category": FieldSpec("texte", normalize_category),
    "sub_category": FieldSpec("texte", _text),
    "grade": FieldSpec("entier", _integer),
    "job_qualification": FieldSpec("texte", _text),
    "employment_status": FieldSpec("enum", lambda raw: normalize_enum(raw, EMPLOYMENT_STATUSES)),
    "pay_mode": FieldSpec("enum", lambda raw: normalize_enum(raw, PAY_MODES)),
    "work_hours_regime": FieldSpec("entier", normalize_hours),
    "base_salary": FieldSpec("montant", normalize_amount, currency=True),
    "gross_salary": FieldSpec("montant", normalize_amount, currency=True),
    "cnss_employee": FieldSpec("montant", normalize_amount, currency=True),
}


# ------------------------------------------------------------------ assemblage


class _Citations:
    """Une citation par ligne utilisée ; citation_id = identifiant de la ligne (ex. "p1_l7")."""

    def __init__(self, document_id: str) -> None:
        self.document_id = document_id
        self.by_id: dict[str, DocumentCitation] = {}

    def cite(self, line: TextLine) -> str:
        if line.line_id not in self.by_id:
            self.by_id[line.line_id] = DocumentCitation(
                citation_id=line.line_id, document_id=self.document_id, page=line.page,
                bbox=list(line.bbox), excerpt=line.text,
            )
        return line.line_id


def _pay_lines(raw_lines: list[RawPayLine], doc: IntermediateDocument,
               citations: _Citations) -> tuple[list[PayLine], list[str]]:
    lines: list[PayLine] = []
    warnings: list[str] = []
    for raw in raw_lines:
        checked = verify_field(f"pay_lines « {raw.label} »", RawField(raw=raw.amount, line_id=raw.line_id), doc)
        warnings.extend(checked.warnings)
        if checked.line is None or checked.raw is None:
            continue  # montant rejeté : la ligne de paie n'est pas renvoyée (voir l'avertissement)
        if canon(raw.label) not in canon(checked.line.text):
            warnings.append(f"pay_lines : libellé « {raw.label} » absent de la ligne {checked.line.line_id}, ignoré.")
            continue
        amount = normalize_amount(checked.raw)
        lines.append(PayLine(
            label=_text(raw.label) or raw.label,
            amount=amount,
            confidence=checked.line.confidence,
            citation_id=citations.cite(checked.line),
            unreadable_reason=None if amount else "valeur_incoherente",
        ))
    return lines, warnings


def _summary(fields: dict[str, ExtractedField], lang: Language) -> str:
    def v(name: str) -> str | None:
        return fields[name].value

    if lang == "ar":
        parts = ["كشف أجر"]
        if v("period_start") and v("period_end"):
            parts.append(f"من {v('period_start')} إلى {v('period_end')}")
        if v("category"):
            parts.append(f"الصنف {v('category')}")
        if v("grade"):
            parts.append(f"الدرجة {v('grade')}")
        return "، ".join(parts) + "."
    parts = ["Fiche de paie"]
    if v("period_start") and v("period_end"):
        parts.append(f"du {v('period_start')} au {v('period_end')}")
    if v("category"):
        parts.append(f"catégorie {v('category')}")
    if v("grade"):
        parts.append(f"échelon {v('grade')}")
    return parts[0] + (" " + ", ".join(parts[1:]) if len(parts) > 1 else "") + "."


def _languages(doc: IntermediateDocument) -> list[Language]:
    found = {line.language for page in doc.pages for line in page.lines}
    langs: list[Language] = []
    if found & {"ar", "mixte"}:
        langs.append("ar")
    if found & {"fr", "mixte"}:
        langs.append("fr")
    return langs or ["fr"]


def _type_confidence(answer: GeminiPayslipAnswer, req: DS3Request) -> tuple[float, list[str]]:
    """Règle provisoire (à valider) : la confiance du type dépend de l'accord avec le type attendu par DS1."""
    expected = req.options.expected_type
    if expected is None:
        return 0.80, []
    if answer.document_type == expected:
        return 0.95, []
    return 0.50, [f"Type lu « {answer.document_type} » différent du type attendu « {expected} »."]


def build_payslip_response(req: DS3Request, doc: IntermediateDocument, answer: GeminiPayslipAnswer,
                           processing_ms: int = 0) -> dict[str, Any]:
    """Construit la réponse ds3.v2 (dict JSON) à partir de la réponse de Gemini."""
    envelope: dict[str, Any] = {
        "request_id": req.request_id, "case_id": req.case_id, "computed_by": COMPUTED_BY, "mode": "live",
        "operation": req.operation, "card_id": req.context.card_id, "document_id": req.document.document_id,
        "meta": ResponseMeta(pipeline_version=PIPELINE_VERSION, processing_ms=processing_ms),
    }
    citations = _Citations(req.document.document_id)
    verified, warnings = verify_all(answer.fields, doc, list(PAYSLIP_FIELDS))

    fields: dict[str, ExtractedField] = {}
    for name, spec in PAYSLIP_FIELDS.items():
        check = verified[name]
        currency = "TND" if spec.currency else None
        if check.line is None or check.raw is None:
            fields[name] = ExtractedField(value=None, value_type=spec.value_type, confidence=0.0,
                                          citation_id=None, unreadable_reason=check.reason, currency=currency)
            continue
        value = spec.normalize(check.raw)
        if value is None:
            warnings.append(f"{name} : « {check.raw} » imprimé mais non convertible, valeur non renvoyée.")
        fields[name] = ExtractedField(
            value=value, value_type=spec.value_type, confidence=check.line.confidence,
            citation_id=citations.cite(check.line),
            unreadable_reason=None if value is not None else "valeur_incoherente", currency=currency,
        )

    pay_lines, pay_warnings = _pay_lines(answer.pay_lines, doc, citations)
    warnings.extend(pay_warnings)

    if not citations.by_id:
        # Aucune valeur vérifiée : on ne renvoie rien plutôt qu'un résultat vide (« citation ou silence »).
        return DS3Response(
            **envelope, status="refus", citations=[], result=None, warnings=warnings,
            ds3_code="UNREADABLE_DOCUMENT",
            refus=Refus(code="SOURCE_MANQUANTE",
                        message_fr="Aucune valeur lisible dans ce document : rien n'est extrait.",
                        message_ar="لا توجد أي قيمة مقروءة في هذه الوثيقة."),
        ).to_json()

    type_confidence, type_warnings = _type_confidence(answer, req)
    incomplete = {"zone_illisible", "valeur_incoherente"}
    complete = all(f.unreadable_reason not in incomplete for f in fields.values()) and all(
        line.unreadable_reason is None for line in pay_lines
    )
    analysis = DocumentAnalysis(
        document_type=answer.document_type,
        document_type_confidence=type_confidence,
        languages=_languages(doc),
        page_count=doc.page_count,
        complete=complete,
        summary=_summary(fields, req.lang),
        fields=fields,
        pay_lines=pay_lines,
    )
    return DS3Response(
        **envelope, status="ok", refus=None, citations=list(citations.by_id.values()), result=analysis,
        warnings=type_warnings + warnings,
    ).to_json()
