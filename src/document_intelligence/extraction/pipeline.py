"""Chaîne complète DS3 pour une fiche de paie (PDF, PNG ou JPG) : lecture -> Gemini -> vérification -> ds3.v2.

    1. lecture : texte natif du PDF ............ reading/pdf_natif.py
       puis OCR des zones en attente / image .. reading/ocr.py (partie A, D41)
    2. Gemini : où se trouve chaque valeur ...... extraction/gemini.py
    3. vérification contre le document .......... extraction/verify.py
    4. normalisation au format du contrat ....... extraction/normalize.py
    5. réponse ds3.v2 avec citations ............ extraction/assemble.py

Ne lève jamais d'exception : un problème devient une réponse « refus » ou « erreur ».

OCR (D41) : appelé seulement s'il reste des zones en attente (un PDF entièrement natif ne paie aucun temps
d'OCR). Il est importé dans la fonction, pas en tête du module : sans les dépendances de requirements-ocr.txt,
le service fonctionne comme avant (zones non lues, avertissement). Si rien n'est lisible, même après l'OCR :
refus SOURCE_MANQUANTE (« citation ou silence »).
"""

from __future__ import annotations

import importlib.util
import logging
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
OCR_NOT_INSTALLED: Final = "OCR non installé (requirements-ocr.txt) : les zones en attente ne sont pas lues."
OCR_IMAGE_FR: Final = ("La lecture des images (OCR) n'est pas installée sur ce serveur : "
                       "envoyez un PDF avec du texte.")
OCR_IMAGE_AR: Final = "قراءة الصور (OCR) غير مثبتة على هذا الخادم: أرسل ملف PDF يحتوي على نص."


def paddle_installed() -> bool:
    """PaddleOCR est-il installé ? Vérifié sans le charger (le chargement prend plusieurs secondes)."""
    return importlib.util.find_spec("paddleocr") is not None


def _reading_order(doc: IntermediateDocument) -> None:
    """Trie les lignes de chaque page de haut en bas (tri stable).

    L'OCR ajoute ses lignes après les lignes natives : sans ce tri, Gemini lirait une page mixte dans le
    désordre. Les identifiants ne changent pas, donc les citations restent justes.
    """
    for page in doc.pages:
        page.lines.sort(key=lambda line: line.bbox[1])


def read_document(path: Path, document_id: str, ocr_engine: Any | None = None) -> IntermediateDocument:
    """Lit le document : texte natif du PDF puis OCR des zones en attente ; image : OCR de toute l'image.

    - `ocr_engine` donné (tests) : il est toujours utilisé ;
    - sinon, PaddleOCR est utilisé s'il est installé ; s'il ne l'est pas, un PDF est lu comme avant et une
      image lève ImportError (le service l'a normalement déjà refusée avant, voir D41).
    Les autres erreurs (fichier corrompu) remontent à l'appelant.
    """
    is_image = path.suffix.lower() in IMAGE_EXTENSIONS
    use_ocr = ocr_engine is not None or paddle_installed()
    if is_image:
        if not use_ocr:
            raise ImportError(OCR_NOT_INSTALLED)
        from src.document_intelligence.reading.ocr import read_image

        doc = read_image(path, engine=ocr_engine, document_id=document_id)
        _reading_order(doc)
        return doc

    doc = read_pdf(path, document_id=document_id)
    if not any(page.pending_zones for page in doc.pages):
        return doc
    if not use_ocr:
        doc.warnings.append(OCR_NOT_INSTALLED)
        return doc
    try:
        from src.document_intelligence.reading.ocr import ocr_pending_zones
    except ImportError:  # numpy / Pillow absents : même comportement que sans PaddleOCR
        doc.warnings.append(OCR_NOT_INSTALLED)
        return doc
    doc = ocr_pending_zones(doc, path, engine=ocr_engine)
    _reading_order(doc)
    return doc


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
    except ImportError:  # image alors que l'OCR n'est pas installé (le service la refuse normalement avant)
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
