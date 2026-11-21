"""Service réel DS3 (mode live) : même interface que le mock v2.

Utilisation côté DS1 (seule la ligne d'import change par rapport au mock) :

    from src.document_intelligence.service import handle_request
    response = handle_request(request_dict)        # contrat ds3.v2, mode = "live"

Ce que fait le service, dans l'ordre :
1. mêmes contrôles que le mock : opération connue, requête conforme au contrat, document de la carte active ;
2. retrouve le fichier à partir de `document.storage_ref` (voir « Stockage » ci-dessous) ;
3. vérifie ce qui est disponible en live aujourd'hui : fiches de paie en PDF, PNG ou JPG (images lues par
   l'OCR de la partie A, D41), opération `analyze_document` ;
4. appelle la chaîne d'extraction (lecture, Gemini, vérification, normalisation, réponse citée).
Il ne lève jamais d'exception : tout problème devient une réponse `refus` ou `erreur`.

Stockage (provisoire, en attendant l'accès au stockage Tradrly défini avec DS1 / le backend) :
les fichiers sont lus dans un dossier racine, donné par `storage_root=` ou par la variable
d'environnement DS3_STORAGE_ROOT. Deux formes de `storage_ref` sont acceptées :
- `tradrly://cards/<card_id>/documents/<document_id>` -> <racine>/cards/<card_id>/documents/<document_id>/<file_name>
  (ou <racine>/cards/<card_id>/documents/<file_name> si le dossier du document n'existe pas) ;
- `local://<chemin relatif>` -> <racine>/<chemin relatif> (pour les tests et les démonstrations).
Un chemin qui sortirait du dossier racine, ou une carte différente de la carte active dans
`tradrly://cards/<card_id>/...`, est refusé sans lire le fichier.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import time
from pathlib import Path, PurePosixPath
from typing import Any, Final

from pydantic import ValidationError

from src.document_intelligence.contract.v2.mock import _ERREURS, _REFUS, OPERATIONS
from src.document_intelligence.contract.v2.models import (
    DS3Code,
    DS3Request,
    DS3Response,
    Erreur,
    Refus,
    ResponseMeta,
)
from src.document_intelligence.extraction import pipeline
from src.document_intelligence.extraction.assemble import COMPUTED_BY, PIPELINE_VERSION
from src.document_intelligence.extraction.pipeline import (
    IMAGE_EXTENSIONS,
    OCR_IMAGE_AR,
    OCR_IMAGE_FR,
    analyze_payslip_pdf,
)

log = logging.getLogger(__name__)

STORAGE_ROOT_ENV: Final = "DS3_STORAGE_ROOT"
MAX_FILE_BYTES: Final = 20 * 1024 * 1024
LIVE_EXTENSIONS: Final = {".pdf", *IMAGE_EXTENSIONS}
LIVE_DOCUMENT_TYPES: Final = {None, "fiche_de_paie"}


class StorageError(Exception):
    """Le fichier ne peut pas être retrouvé dans le stockage. `code` dit quelle réponse renvoyer."""

    def __init__(self, code: DS3Code, detail: str) -> None:
        super().__init__(detail)
        self.code: DS3Code = code
        self.detail = detail


# ------------------------------------------------------------------ réponses


def _envelope(request_id: str | None, operation: str, case_id: str | None, card_id: str | None,
              document_id: str | None, started: float) -> dict[str, Any]:
    return {
        "request_id": request_id, "case_id": case_id, "computed_by": COMPUTED_BY, "mode": "live",
        "operation": operation, "card_id": card_id, "document_id": document_id,
        "meta": ResponseMeta(pipeline_version=PIPELINE_VERSION,
                             processing_ms=int((time.perf_counter() - started) * 1000)),
    }


def _refus(env: dict[str, Any], code: DS3Code, detail: str | None = None,
           live_fr: str | None = None, live_ar: str | None = None) -> dict[str, Any]:
    """Refus au format commun. `live_fr` / `live_ar` remplacent le message pour une limite propre au live."""
    refus_code, fr, ar = _REFUS[code]
    message_fr = live_fr or (f"{fr} {detail}" if detail else fr)
    return DS3Response(
        **env, status="refus", refus=Refus(code=refus_code, message_fr=message_fr, message_ar=live_ar or ar),
        citations=[], result=None, ds3_code=code,
    ).to_json()


def _erreur(env: dict[str, Any], code: DS3Code) -> dict[str, Any]:
    fr, ar, retryable = _ERREURS[code]
    return DS3Response(
        **env, status="erreur", refus=None, erreur=Erreur(type=code, message_fr=fr, message_ar=ar),
        citations=[], result=None, ds3_code=code, retryable=retryable,
    ).to_json()


# ------------------------------------------------------------------ stockage


def storage_root(explicit: Path | str | None = None) -> Path | None:
    """Dossier racine du stockage : paramètre explicite, sinon DS3_STORAGE_ROOT, sinon None."""
    value = explicit if explicit is not None else os.getenv(STORAGE_ROOT_ENV)
    return Path(value).resolve() if value else None


def resolve_storage_ref(req: DS3Request, root: Path) -> Path:
    """Chemin du fichier sur le disque. Lève StorageError si la référence est refusée ou introuvable."""
    ref = req.document.storage_ref
    name = req.document.file_name
    if name != PurePosixPath(name).name or "\\" in name or name in {"", ".", ".."}:
        raise StorageError("INVALID_REQUEST", "file_name doit être un simple nom de fichier, sans dossier.")
    if ref.startswith("tradrly://"):
        parts = PurePosixPath(ref.removeprefix("tradrly://")).parts
        if len(parts) != 4 or parts[0] != "cards" or parts[2] != "documents":
            raise StorageError("INVALID_REQUEST", "storage_ref attendu : tradrly://cards/<carte>/documents/<document>.")
        if parts[1] != req.context.card_id:
            raise StorageError("ACCESS_DENIED", "storage_ref d'une autre carte.")
        folder = root.joinpath(*parts)
        candidate = folder / req.document.file_name if folder.is_dir() else folder.parent / req.document.file_name
    elif ref.startswith("local://"):
        candidate = root / ref.removeprefix("local://")
    else:
        raise StorageError("INVALID_REQUEST", "storage_ref doit commencer par tradrly:// ou local://.")

    path = candidate.resolve()
    if not path.is_relative_to(root):
        raise StorageError("ACCESS_DENIED", "chemin hors du stockage.")
    if not path.is_file():
        raise StorageError("FILE_EMPTY_OR_CORRUPTED", "document introuvable dans le stockage.")
    size = path.stat().st_size
    if size == 0:
        raise StorageError("FILE_EMPTY_OR_CORRUPTED", "fichier vide.")
    if size > MAX_FILE_BYTES:
        raise StorageError("FILE_TOO_LARGE", f"limite : {MAX_FILE_BYTES // (1024 * 1024)} Mo.")
    return path


# ------------------------------------------------------------------ point d'entrée


def handle_request(request: dict[str, Any], *, storage_root_dir: Path | str | None = None,
                   client: Any | None = None, model: str | None = None,
                   ocr_engine: Any | None = None) -> dict[str, Any]:
    """Point d'entrée unique DS3 en live. Reçoit et renvoie du JSON (dict), jamais d'exception.

    `client` et `model` permettent aux tests de remplacer Gemini (aucun appel réseau) ;
    `ocr_engine` permet de remplacer PaddleOCR (aucun modèle chargé).
    """
    started = time.perf_counter()
    try:
        return _handle(request, storage_root_dir, client, model, ocr_engine, started)
    except Exception:  # le contrat interdit de propager une exception à DS1
        log.exception("Erreur interne DS3")
        raw_id = request.get("request_id") if isinstance(request, dict) else None
        env = _envelope(raw_id if isinstance(raw_id, str) and raw_id else None, "unknown",
                        None, None, None, started)
        return _erreur(env, "INTERNAL_ERROR")


def _handle(request: dict[str, Any], root_dir: Path | str | None, client: Any | None, model: str | None,
            ocr_engine: Any | None, started: float) -> dict[str, Any]:
    raw_id = request.get("request_id")
    operation = str(request.get("operation", "unknown"))
    env = _envelope(raw_id if isinstance(raw_id, str) and raw_id else None, operation, None, None, None, started)
    if operation not in OPERATIONS:
        return _refus(env, "UNSUPPORTED_OPERATION", f"Opérations acceptées : {', '.join(OPERATIONS)}.")
    try:
        req = DS3Request.model_validate(request)
    except ValidationError as exc:
        first = exc.errors()[0]
        return _refus(env, "INVALID_REQUEST", f"{'.'.join(str(p) for p in first['loc'])} : {first['msg']}")

    env = _envelope(req.request_id, req.operation, req.case_id, req.context.card_id, None, started)
    if req.document.card_id != req.context.card_id:
        return _refus(env, "ACCESS_DENIED")  # document_id non renvoyé, rien n'est lu
    env["document_id"] = req.document.document_id

    # Ce qui est disponible en live aujourd'hui.
    if req.operation == "extract_wage_grid":
        return _refus(env, "UNSUPPORTED_OPERATION",
                      live_fr="La lecture des grilles de salaires n'est pas encore disponible en live "
                      "(utiliser le mock v2).",
                      live_ar="قراءة جداول الأجور غير متاحة بعد في الخدمة الفعلية.")
    suffix = PurePosixPath(req.document.file_name).suffix.lower()
    if suffix not in LIVE_EXTENSIONS:
        return _refus(env, "UNSUPPORTED_FORMAT",
                      live_fr="Format pas encore pris en charge en live : seuls les PDF, PNG et JPG le sont.",
                      live_ar="هذه الصيغة غير مدعومة بعد في الخدمة الفعلية: ملفات PDF وPNG وJPG فقط حاليا.")
    if suffix in IMAGE_EXTENSIONS and ocr_engine is None and not pipeline.paddle_installed():
        # D41 : refus clair, décidé avant toute lecture du fichier.
        return _refus(env, "UNSUPPORTED_FORMAT", live_fr=OCR_IMAGE_FR, live_ar=OCR_IMAGE_AR)
    if req.options.expected_type not in LIVE_DOCUMENT_TYPES:
        return _refus(env, "UNSUPPORTED_FORMAT",
                      live_fr="Type de document pas encore pris en charge en live : seules les fiches de paie "
                      "le sont pour l'instant.",
                      live_ar="هذا النوع من الوثائق غير مدعوم بعد في الخدمة الفعلية: كشوف الأجور فقط حاليا.")

    root = storage_root(root_dir)
    if root is None or not root.is_dir():
        log.error("Stockage DS3 non configuré (%s absent ou invalide).", STORAGE_ROOT_ENV)
        return _erreur(env, "INTERNAL_ERROR")
    try:
        path = resolve_storage_ref(req, root)
    except StorageError as exc:
        if exc.code == "ACCESS_DENIED":
            env["document_id"] = None
            return _refus(env, "ACCESS_DENIED")
        return _refus(env, exc.code, exc.detail)

    return analyze_payslip_pdf(path, req, client=client, model=model, ocr_engine=ocr_engine)


# ------------------------------------------------------------------ démonstration en ligne de commande


def main(argv: list[str] | None = None) -> int:
    """Lance le service sur une requête JSON : python -m src.document_intelligence.service requete.json --root DOSSIER"""
    parser = argparse.ArgumentParser(description="Service DS3 live sur une requête ds3.v2 (fichier JSON).")
    parser.add_argument("request", type=Path)
    parser.add_argument("--root", type=Path, help=f"Dossier du stockage (sinon {STORAGE_ROOT_ENV}).")
    parser.add_argument("--model", help="Modèle Gemini (sinon GEMINI_MODEL du .env).")
    args = parser.parse_args(argv)
    try:
        from dotenv import load_dotenv

        load_dotenv()
    except ImportError:
        pass
    request = json.loads(args.request.read_text(encoding="utf-8"))
    response = handle_request(request, storage_root_dir=args.root, model=args.model)
    print(json.dumps(response, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
