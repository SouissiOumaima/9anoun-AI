"""Chaîne complète DS3 pour une fiche de paie (PDF, PNG ou JPG) : lecture -> Gemini -> vérification -> ds3.v2.

    1. lecture : texte natif du PDF ............ reading/pdf_natif.py
       puis OCR des zones en attente / image .. reading/ocr.py (partie A, D41)
    2. Gemini : où se trouve chaque valeur ...... extraction/gemini.py
    3. vérification contre le document .......... extraction/verify.py
    4. normalisation au format du contrat ....... extraction/normalize.py
    5. réponse ds3.v2 avec citations ............ extraction/assemble.py

Ne lève jamais d'exception : un problème devient une réponse « refus » ou « erreur ».

OCR (D41) : appelé seulement s'il reste des zones en attente (un PDF entièrement natif ne paie aucun temps
d'OCR), et seulement s'il est disponible :
- un moteur passé en paramètre (`ocr_engine`, pour les tests) est toujours utilisé ;
- sinon, PaddleOCR n'est lancé **dans le processus du service** que si la variable d'environnement
  DS3_OCR_INPROCESS vaut 1 (démonstrations). Par défaut il ne l'est pas : un plantage natif de Paddle
  arrêterait tout le service, et une page prend environ 27 s. Le fonctionnement normal passera par le backend
  OCR en arrière-plan (processus séparé et cache, D42).
Sans OCR disponible : un PDF est lu comme avant (zones non lues, avertissement) ; une image est refusée.
Si rien n'est lisible, même après l'OCR : refus SOURCE_MANQUANTE (« citation ou silence »).
"""

from __future__ import annotations

import importlib.util
import logging
import os
import time
from pathlib import Path
from typing import Any, Final

from src.document_intelligence.contract.v2.models import (
    DS3Request,
    DS3Response,
    Erreur,
    Refus,
    ResponseMeta,
)
from src.document_intelligence.extraction.assemble import (
    COMPUTED_BY,
    PIPELINE_VERSION,
    build_payslip_response,
)
from src.document_intelligence.extraction.gemini import GeminiError, ask_gemini
from src.document_intelligence.intermediate import IntermediateDocument
from src.document_intelligence.reading.pdf_natif import read_pdf

log = logging.getLogger(__name__)

IMAGE_EXTENSIONS: Final = frozenset({".png", ".jpg", ".jpeg"})
INPROCESS_ENV: Final = "DS3_OCR_INPROCESS"
OCR_UNAVAILABLE_WARNING: Final = (
    "OCR non disponible (non installé, ou DS3_OCR_INPROCESS non activé) : les zones en attente ne sont pas lues."
)
OCR_IMAGE_FR: Final = ("La lecture des images n'est pas possible : l'OCR n'est pas installé ou pas activé sur ce "
                       "serveur. Envoyez un PDF avec du texte.")
OCR_IMAGE_AR: Final = "قراءة الصور غير ممكنة: نظام OCR غير مثبت أو غير مفعّل على هذا الخادم. أرسل ملف PDF يحتوي على نص."


class OcrUnavailable(Exception):
    """L'OCR n'est pas disponible pour lire une image. Levée seulement par `read_document`."""


def paddle_installed() -> bool:
    """PaddleOCR est-il installé ? Vérifié sans le charger (le chargement prend plusieurs secondes)."""
    return importlib.util.find_spec("paddleocr") is not None


def ocr_inprocess_enabled() -> bool:
    """L'OCR dans le processus du service est-il autorisé ? (DS3_OCR_INPROCESS=1, démonstrations seulement)."""
    return os.getenv(INPROCESS_ENV) == "1"


def ocr_available(ocr_engine: Any | None = None) -> bool:
    """Un OCR peut-il être utilisé ? Moteur fourni, ou PaddleOCR installé ET autorisé dans le processus."""
    return ocr_engine is not None or (paddle_installed() and ocr_inprocess_enabled())


def read_document(path: Path, document_id: str, ocr_engine: Any | None = None) -> IntermediateDocument:
    """Lit le document : texte natif du PDF puis OCR des zones en attente ; image : OCR de toute l'image.

    - OCR disponible (voir `ocr_available`) : zones en attente ou image lues par l'OCR ;
    - OCR non disponible : un PDF est lu comme avant (avertissement) ; une image lève `OcrUnavailable`
      (le service l'a normalement déjà refusée avant, D41).
    L'ordre de lecture des lignes OCR est celui que donne `reading/ocr.py`. Les autres erreurs (fichier
    corrompu) remontent à l'appelant.
    """
    is_image = path.suffix.lower() in IMAGE_EXTENSIONS
    use_ocr = ocr_available(ocr_engine)
    if is_image:
        if not use_ocr:
            raise OcrUnavailable(OCR_UNAVAILABLE_WARNING)
        try:
            from src.document_intelligence.reading.ocr import read_image
        except ImportError as exc:  # numpy / Pillow absents
            raise OcrUnavailable(OCR_UNAVAILABLE_WARNING) from exc
        return read_image(path, engine=ocr_engine, document_id=document_id)

    doc = read_pdf(path, document_id=document_id)
    if not any(page.pending_zones for page in doc.pages):
        return doc
    if not use_ocr:
        doc.warnings.append(OCR_UNAVAILABLE_WARNING)
        return doc
    try:
        from src.document_intelligence.reading.ocr import ocr_pending_zones
    except ImportError:  # numpy / Pillow absents : même comportement que sans OCR
        doc.warnings.append(OCR_UNAVAILABLE_WARNING)
        return doc
    return ocr_pending_zones(doc, path, engine=ocr_engine)


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
                        model: str | None = None, ocr_engine: Any | None = None) -> dict[str, Any]:
    """Analyse une fiche de paie (PDF, PNG ou JPG) et renvoie la réponse ds3.v2 (dict JSON).

    `ocr_engine` permet aux tests de remplacer PaddleOCR (même rôle que `client` pour Gemini).
    Le nom est gardé pour ne rien casser chez les appelants, même si les images sont acceptées.
    """
    started = time.perf_counter()
    try:
        doc = read_document(pdf_path, req.document.document_id, ocr_engine)
    except OcrUnavailable:  # image sans OCR disponible (le service la refuse normalement avant, D41)
        return DS3Response(
            **_envelope(req, started), status="refus", ds3_code="UNSUPPORTED_FORMAT",
            refus=Refus(code="HORS_SCOPE", message_fr=OCR_IMAGE_FR, message_ar=OCR_IMAGE_AR),
        ).to_json()
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
            warnings=[*doc.warnings, "Aucun texte lu, ni dans la couche texte du document ni par l'OCR."],
        ).to_json()

    try:
        answer = ask_gemini(doc, client=client, model=model)
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
    return response
