"""Chaîne complète DS3 pour une fiche de paie en PDF : lecture -> Gemini -> vérification -> réponse ds3.v2.

    1. lecture du PDF (texte natif) ............ reading/pdf_natif.py
    2. Gemini : où se trouve chaque valeur ...... extraction/gemini.py
    3. vérification contre le document .......... extraction/verify.py
    4. normalisation au format du contrat ....... extraction/normalize.py
    5. réponse ds3.v2 avec citations ............ extraction/assemble.py

Ne lève jamais d'exception : un problème devient une réponse « refus » ou « erreur ».
L'OCR (partie A) n'est pas encore branché : une page sans texte natif donne un refus SOURCE_MANQUANTE.
"""

from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Any

from src.document_intelligence.contract.v2.models import DS3Request, DS3Response, Erreur, Refus, ResponseMeta
from src.document_intelligence.extraction.assemble import (
    COMPUTED_BY,
    PIPELINE_VERSION,
    build_payslip_response,
)
from src.document_intelligence.extraction.gemini import GeminiError, ask_gemini
from src.document_intelligence.reading.pdf_natif import read_pdf

log = logging.getLogger(__name__)


def _envelope(req: DS3Request, started: float) -> dict[str, Any]:
    return {
        "request_id": req.request_id, "case_id": req.case_id, "computed_by": COMPUTED_BY, "mode": "live",
        "operation": req.operation, "card_id": req.context.card_id, "document_id": req.document.document_id,
        "citations": [], "result": None,
        "meta": ResponseMeta(pipeline_version=PIPELINE_VERSION, processing_ms=_ms(started)),
    }


def _ms(started: float) -> int:
    return int((time.perf_counter() - started) * 1000)


def analyze_payslip_pdf(pdf_path: Path, req: DS3Request, client: Any | None = None,
                        model: str | None = None) -> dict[str, Any]:
    """Analyse une fiche de paie en PDF et renvoie la réponse ds3.v2 (dict JSON)."""
    started = time.perf_counter()
    try:
        doc = read_pdf(pdf_path, document_id=req.document.document_id)
    except Exception:
        log.exception("Lecture impossible : %s", pdf_path.name)
        return DS3Response(
            **_envelope(req, started), status="refus", ds3_code="FILE_EMPTY_OR_CORRUPTED",
            refus=Refus(code="PARAM_INVALIDE", message_fr="Le fichier est vide ou endommagé et ne peut pas être lu.",
                        message_ar="الملف فارغ أو تالف ولا يمكن قراءته."),
        ).to_json()

    if not any(page.lines for page in doc.pages):
        return DS3Response(
            **_envelope(req, started), status="refus", ds3_code="UNREADABLE_DOCUMENT",
            refus=Refus(code="SOURCE_MANQUANTE",
                        message_fr="Aucun texte lisible dans ce document : rien n'est extrait.",
                        message_ar="لا يوجد أي نص مقروء في هذه الوثيقة."),
            warnings=[*doc.warnings, "Aucun texte natif : le document doit passer par l'OCR (partie A)."],
        ).to_json()

    read_ms = _ms(started)
    extraction_started = time.perf_counter()
    try:
        answer = ask_gemini(doc, client=client, model=model, cache_scope=(
            req.context.organization_id, req.context.user_id, req.context.role,
            req.context.card_id, req.document.document_id, req.document.storage_ref,
        ))
    except GeminiError as exc:
        log.warning("%s : %s", pdf_path.name, exc)  # détail technique dans le journal, pas dans la réponse
        return DS3Response(
            **_envelope(req, started), status="erreur", refus=None, ds3_code="INTERNAL_ERROR", retryable=True,
            erreur=Erreur(type="INTERNAL_ERROR",
                          message_fr="Le service d'analyse est momentanément indisponible. Réessayez.",
                          message_ar="خدمة التحليل غير متاحة مؤقتا. أعد المحاولة."),
        ).to_json()

    response = build_payslip_response(req, doc, answer, processing_ms=_ms(started))
    response["warnings"] = doc.warnings + response["warnings"]
    log.info("DS3 timings read_ms=%d extraction_ms=%d total_ms=%d", read_ms,
             _ms(extraction_started), _ms(started))
    return response
