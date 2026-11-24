"""Chaîne complète DS3 pour une fiche de paie (PDF, PNG ou JPG) : lecture -> Gemini -> vérification -> ds3.v2.

    1. lecture : texte natif du PDF ............ reading/pdf_natif.py
       puis OCR des zones en attente / image .. reading/ocr.py (partie A, D41)
    2. Gemini : où se trouve chaque valeur ...... extraction/gemini.py
    3. vérification contre le document .......... extraction/verify.py
    4. normalisation au format du contrat ....... extraction/normalize.py
    5. réponse ds3.v2 avec citations ............ extraction/assemble.py

Ne lève jamais d'exception : un problème devient une réponse « refus » ou « erreur ».

OCR : appelé seulement s'il reste des zones en attente (un PDF entièrement natif ne paie aucun temps d'OCR),
ou pour une image, et seulement s'il est disponible. Par ordre de priorité :
1. un backend passé en paramètre (`ocr_backend`, pour les tests) ;
2. un moteur passé en paramètre (`ocr_engine`, pour les tests), utilisé dans le processus ;
3. **fonctionnement normal (D42)** : le backend en arrière-plan de `reading/ocr_cache.py` (processus séparé,
   cache, verrou), actif quand PaddleOCR est installé et que DS3_CACHE_DIR est défini. À la première question,
   l'OCR est lancé en arrière-plan et la réponse est `erreur` TIMEOUT réessayable ; chaque nouvel essai reçoit la
   même réponse tant que la lecture n'est pas terminée ; ensuite, le document lu est servi depuis le cache ;
4. démonstrations seulement (option B, D41) : PaddleOCR dans le processus du service si DS3_OCR_INPROCESS=1 et
   DS3_CACHE_DIR absent. À éviter : un plantage natif de Paddle arrêterait le service, et une page prend ~27 s.
Sans OCR disponible : un PDF est lu comme avant (zones non lues, avertissement) ; une image est refusée (D41).
OCR en échec : un PDF garde sa lecture native (avertissement) ; une image valide reçoit SOURCE_MANQUANTE.
Si rien n'est lisible, même après l'OCR : refus SOURCE_MANQUANTE (« citation ou silence »).
"""

from __future__ import annotations

import importlib.util
import logging
import os
import time
from pathlib import Path
from typing import Any, Final

from src.document_intelligence.contract.v2.mock import _REFUS
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
from src.document_intelligence.reading import ocr_cache
from src.document_intelligence.reading.ocr_cache import CacheAccessError, OcrBackend
from src.document_intelligence.reading.pdf_natif import read_pdf

log = logging.getLogger(__name__)

IMAGE_EXTENSIONS: Final = frozenset({".png", ".jpg", ".jpeg"})
INPROCESS_ENV: Final = "DS3_OCR_INPROCESS"
OCR_UNAVAILABLE_WARNING: Final = (
    "OCR non disponible (non installé, ou ni DS3_CACHE_DIR ni DS3_OCR_INPROCESS définis) : "
    "les zones en attente ne sont pas lues."
)
OCR_FAILED_WARNING: Final = "OCR interrompu : les zones en attente ne sont pas lues (rien n'est deviné)."
OCR_IMAGE_FAILED_WARNING: Final = "OCR interrompu : l'image n'a pas pu être lue (rien n'est deviné)."
OCR_PENDING_FR: Final = "Lecture du document en cours : réessayez dans quelques instants."
OCR_PENDING_AR: Final = "قراءة الوثيقة جارية: أعد المحاولة بعد لحظات."
IMAGE_SIGNATURES: Final = {".png": (b"\x89PNG\r\n\x1a\n",), ".jpg": (b"\xff\xd8\xff",), ".jpeg": (b"\xff\xd8\xff",)}
OCR_IMAGE_FR: Final = ("La lecture des images n'est pas possible : l'OCR n'est pas installé ou pas activé sur ce "
                       "serveur. Envoyez un PDF avec du texte.")
OCR_IMAGE_AR: Final = "قراءة الصور غير ممكنة: نظام OCR غير مثبت أو غير مفعّل على هذا الخادم. أرسل ملف PDF يحتوي على نص."


class OcrUnavailable(Exception):
    """L'OCR n'est pas disponible pour lire une image. Levée seulement par `read_document`."""


class OcrPending(Exception):
    """La lecture OCR du document tourne en arrière-plan (lancée par cette question ou une précédente, D42)."""


class OcrFailed(Exception):
    """L'OCR d'une image valide a échoué (plantage, délai dépassé, verrou abandonné) : rien n'a été lu."""


class OcrAccessDenied(Exception):
    """Carte ou document refusé par les contrôles d'accès du cache OCR (pas un simple nom)."""


def paddle_installed() -> bool:
    """PaddleOCR est-il installé ? Vérifié sans le charger (le chargement prend plusieurs secondes)."""
    return importlib.util.find_spec("paddleocr") is not None


def ocr_inprocess_enabled() -> bool:
    """L'OCR dans le processus du service est-il autorisé ? (DS3_OCR_INPROCESS=1, démonstrations seulement)."""
    return os.getenv(INPROCESS_ENV) == "1"


def default_backend() -> OcrBackend | None:
    """Backend en arrière-plan du serveur (D42) : PaddleOCR installé et DS3_CACHE_DIR défini, sinon None."""
    if not paddle_installed():
        return None
    return ocr_cache.default_backend()


def ocr_available(ocr_engine: Any | None = None, ocr_backend: OcrBackend | None = None) -> bool:
    """Un OCR peut-il être utilisé ? Le service et le pipeline appellent cette même fonction (D41, D42).

    Oui si un backend ou un moteur est fourni, si le backend en arrière-plan est configuré (PaddleOCR installé et
    DS3_CACHE_DIR défini), ou si PaddleOCR est installé et autorisé dans le processus (DS3_OCR_INPROCESS=1).
    Ce n'est qu'une disponibilité : `read_document` prend toujours le backend du serveur avant l'OCR dans le
    processus ; celui-ci ne sert que sans DS3_CACHE_DIR (ou avec un moteur passé en paramètre, pour les tests).
    """
    return (ocr_backend is not None or ocr_engine is not None or default_backend() is not None
            or (paddle_installed() and ocr_inprocess_enabled()))


def _check_image(path: Path) -> None:
    """Refuse une image corrompue AVANT l'OCR (elle doit donner FILE_EMPTY_OR_CORRUPTED, pas SOURCE_MANQUANTE).

    Signature du format d'abord (sans dépendance), puis décodage complet par Pillow quand il est installé :
    `verify()` seul ne lit pas les pixels (un JPEG tronqué le passe), `load()` décode toute l'image.
    """
    with path.open("rb") as handle:
        head = handle.read(8)
    if not head.startswith(IMAGE_SIGNATURES[path.suffix.lower()]):
        raise ValueError("signature d'image invalide")
    try:
        from PIL import Image
    except ImportError:  # sans Pillow, le processus OCR échouera de lui-même (état echec)
        return
    with Image.open(path) as image:
        image.verify()  # structure du fichier (sommes de contrôle PNG)
    with Image.open(path) as image:  # verify() rend l'objet inutilisable : on rouvre
        image.load()  # pixels : un fichier tronqué lève OSError


def _read_with_backend(path: Path, document_id: str, card_id: str, backend: OcrBackend,
                       native: IntermediateDocument | None) -> IntermediateDocument:
    """Lecture OCR en arrière-plan (D42). `native` : lecture native d'un PDF, None pour une image."""
    if native is None:
        _check_image(path)
    try:
        state = backend.lookup_or_start(path, card_id=card_id, document_id=document_id)
    except CacheAccessError as exc:
        raise OcrAccessDenied(str(exc)) from exc
    if state.status == "pret" and state.document is not None:
        return state.document
    if state.status == "en_cours":
        raise OcrPending()
    if native is None:  # image valide dont l'OCR a échoué : rien d'autre à lire
        raise OcrFailed()
    native.warnings.append(OCR_FAILED_WARNING)  # PDF : lecture native seule
    return native


def read_document(path: Path, document_id: str, ocr_engine: Any | None = None, *,
                  ocr_backend: OcrBackend | None = None, card_id: str | None = None) -> IntermediateDocument:
    """Lit le document : texte natif du PDF puis OCR des zones en attente ; image : OCR de toute l'image.

    - backend en arrière-plan (fourni, ou configuré sur le serveur, D42) : lève `OcrPending` tant que la lecture
      n'est pas terminée, `OcrFailed` si l'OCR d'une image a échoué ; un PDF dont l'OCR a échoué garde sa lecture
      native (avertissement). `card_id` est alors obligatoire (dossier du cache) ;
    - moteur dans le processus (`ocr_engine`, ou DS3_OCR_INPROCESS=1) : zones en attente ou image lues tout de suite ;
    - OCR non disponible : un PDF est lu comme avant (avertissement) ; une image lève `OcrUnavailable`
      (le service l'a normalement déjà refusée avant, D41).
    L'ordre de lecture des lignes OCR est celui que donne `reading/ocr.py`. Les autres erreurs (fichier
    corrompu) remontent à l'appelant.
    """
    is_image = path.suffix.lower() in IMAGE_EXTENSIONS
    native = None if is_image else read_pdf(path, document_id=document_id)
    if native is not None and not any(page.pending_zones for page in native.pages):
        return native  # PDF entièrement natif : ni OCR ni cache

    backend = ocr_backend
    if backend is None and ocr_engine is None:
        backend = default_backend()
    if backend is not None:
        if card_id is None:
            raise ValueError("card_id est obligatoire pour la lecture OCR en arrière-plan.")
        return _read_with_backend(path, document_id, card_id, backend, native)

    use_ocr = ocr_available(ocr_engine)
    if is_image:
        if not use_ocr:
            raise OcrUnavailable(OCR_UNAVAILABLE_WARNING)
        try:
            from src.document_intelligence.reading.ocr import read_image
        except ImportError as exc:  # numpy / Pillow absents
            raise OcrUnavailable(OCR_UNAVAILABLE_WARNING) from exc
        return read_image(path, engine=ocr_engine, document_id=document_id)

    doc = native
    assert doc is not None
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
                        model: str | None = None, ocr_engine: Any | None = None,
                        ocr_backend: OcrBackend | None = None) -> dict[str, Any]:
    """Analyse une fiche de paie (PDF, PNG ou JPG) et renvoie la réponse ds3.v2 (dict JSON).

    `ocr_backend` et `ocr_engine` permettent aux tests de remplacer le cache OCR ou PaddleOCR (même rôle que
    `client` pour Gemini). Le nom est gardé pour ne rien casser chez les appelants, même si les images sont acceptées.
    """
    started = time.perf_counter()
    try:
        doc = read_document(pdf_path, req.document.document_id, ocr_engine,
                            ocr_backend=ocr_backend, card_id=req.context.card_id)
    except OcrPending:  # D42 : l'OCR tourne en arrière-plan ; DS1 repose la question (bouton Réessayer)
        return DS3Response(
            **_envelope(req, started), status="erreur", refus=None, ds3_code="TIMEOUT", retryable=True,
            erreur=Erreur(type="TIMEOUT", message_fr=OCR_PENDING_FR, message_ar=OCR_PENDING_AR),
        ).to_json()
    except OcrFailed:  # image valide, OCR en échec : jamais FILE_EMPTY_OR_CORRUPTED, Gemini pas appelé
        return DS3Response(
            **_envelope(req, started), status="refus", ds3_code="UNREADABLE_DOCUMENT",
            refus=Refus(code="SOURCE_MANQUANTE",
                        message_fr="Aucun texte lisible dans ce document : rien n'est extrait.",
                        message_ar="لا يوجد أي نص مقروء في هذه الوثيقة."),
            warnings=[OCR_IMAGE_FAILED_WARNING],
        ).to_json()
    except OcrAccessDenied:  # même réponse neutre que le stockage (D40) : document_id non renvoyé
        refus_code, fr, ar = _REFUS["ACCESS_DENIED"]
        return DS3Response(
            **{**_envelope(req, started), "document_id": None}, status="refus", ds3_code="ACCESS_DENIED",
            refus=Refus(code=refus_code, message_fr=fr, message_ar=ar),
        ).to_json()
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
