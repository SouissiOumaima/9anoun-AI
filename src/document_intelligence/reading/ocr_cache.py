"""Lecture OCR en arrière-plan, dans un processus séparé, avec un cache par carte et par document (D42).

Pourquoi (voir `docs/PROPOSITION_INTEGRATION_OCR.md`, section 7) :
- l'OCR prend environ 27 s par page sur CPU, au-delà des 20 s (P95) visées pour une réponse : il tourne en
  arrière-plan, et la question suivante lit le résultat gardé en cache ;
- un plantage natif de Paddle (access violation) tue le processus qui l'a appelé : l'OCR tourne donc dans un
  **processus séparé** (`python -m src.document_intelligence.reading.ocr fichier --json sortie`), jamais dans le
  processus du service. Ce module n'importe ni Paddle ni `ocr.py`.

État exposé au pipeline par `OcrCache.lookup_or_start(path, card_id=..., document_id=...)` :
- `pret` : le document lu (natif + OCR) est dans le cache ; `state.document` le contient ;
- `en_cours` : la lecture vient d'être lancée, ou tourne déjà (verrou) : le service répond TIMEOUT réessayable ;
- `echec` : la lecture a planté, dépassé le délai ou rendu un JSON invalide ; on ne relance pas en boucle
  (nouvel essai seulement si le fichier change, donc si son empreinte change).

Cache : `<DS3_CACHE_DIR>/cards/<carte>/documents/<document>/<sha256[:24]>_<code version>.json`, écrit de façon
atomique. Noms volontairement courts : sous Windows sans chemins longs, un chemin complet ne doit pas dépasser
260 caractères (fichiers temporaires compris).
Contrôles d'accès (comme le stockage, D40) : `card_id` et `document_id` sont de simples noms, et le chemin résolu
reste dans `DS3_CACHE_DIR`. Le cache contient le texte du document : il n'est jamais journalisé. Le JSON temporaire
écrit par le processus OCR (`.part`) est supprimé dans tous les cas.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import logging
import os
import subprocess
import sys
import threading
import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Final, Literal, Protocol

from src.document_intelligence.intermediate import IntermediateDocument

log = logging.getLogger(__name__)

CACHE_DIR_ENV: Final = "DS3_CACHE_DIR"
CACHE_VERSION: Final = "pdf_natif-0.3+ocr_paddle-0.1"
"""Version des lecteurs : un nouveau lecteur donne un nouveau nom de fichier de cache (pas de résultat périmé).
À mettre à jour avec `pdf_natif.READER_NAME` et `ocr.READER_SUFFIX` (vérifié par un test). Elle entre dans le nom
du fichier sous forme d'un code court (`version_code`), pour garder des chemins courts."""

FILE_HASH_CHARS: Final = 24
"""Caractères de l'empreinte SHA-256 du fichier gardés dans le nom (96 bits : collision accidentelle impossible en
pratique pour quelques milliers de documents par document_id)."""
VERSION_CODE_CHARS: Final = 8
TEMP_SUFFIX_CHARS: Final = 8

DEFAULT_TIMEOUT_S: Final = 900.0
"""Délai maximal d'une lecture OCR (environ 27 s par page mesurées : marge pour une trentaine de pages)."""

REPO_ROOT: Final = Path(__file__).resolve().parents[3]

OcrStatus = Literal["pret", "en_cours", "echec"]


@dataclass(frozen=True)
class OcrState:
    """État de la lecture OCR d'un document. `document` n'est rempli que si `status == "pret"`."""

    status: OcrStatus
    document: IntermediateDocument | None = None


class OcrBackend(Protocol):
    """Ce que le pipeline utilise (et que les tests remplacent par un faux)."""

    def lookup_or_start(self, path: Path, *, card_id: str, document_id: str) -> OcrState: ...


class CacheAccessError(ValueError):
    """Identifiant ou chemin refusé (sortie du dossier de cache, nom qui n'est pas un simple nom)."""


RunProcess = Callable[[list[str], float], int]
"""Lance une commande avec un délai maximal et renvoie son code de sortie (remplaçable dans les tests)."""

Launcher = Callable[[Callable[[], None]], None]
"""Démarre un travail en arrière-plan (remplaçable dans les tests par un appel direct)."""


def run_cli(cmd: list[str], timeout_s: float) -> int:
    """Lance le processus OCR. Sa sortie contient le texte du document : elle est jetée, jamais journalisée."""
    proc = subprocess.run(cmd, cwd=REPO_ROOT, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                          stderr=subprocess.DEVNULL, timeout=timeout_s, check=False)
    return proc.returncode


def start_thread(job: Callable[[], None]) -> None:
    """Le fil d'arrière-plan ne fait qu'attendre le processus OCR : Paddle ne tourne pas dans ce processus."""
    threading.Thread(target=job, name="ds3-ocr", daemon=True).start()


def ocr_command(source: Path, output: Path) -> list[str]:
    return [sys.executable, "-m", "src.document_intelligence.reading.ocr", str(source), "--json", str(output)]


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def version_code(version: str | None = None) -> str:
    """Code court (8 caractères) de la version des lecteurs : change dès que `CACHE_VERSION` change."""
    return hashlib.sha256((version or CACHE_VERSION).encode("utf-8")).hexdigest()[:VERSION_CODE_CHARS]


def cache_key(file_hash: str) -> str:
    """Nom de base des fichiers d'un document : 24 caractères d'empreinte du fichier + code de version (33 car.)."""
    return f"{file_hash[:FILE_HASH_CHARS]}_{version_code()}"


def temp_path(target: Path) -> Path:
    """Fichier voisin temporaire court (sans PID) : `<nom>.<8 caractères>.tmp`."""
    return target.with_name(f"{target.name}.{uuid.uuid4().hex[:TEMP_SUFFIX_CHARS]}.tmp")


def write_atomically(target: Path, text: str) -> None:
    """Écrit dans un fichier voisin puis le renomme : un lecteur ne voit jamais un fichier à moitié écrit."""
    tmp = temp_path(target)
    try:
        tmp.write_text(text, encoding="utf-8")
        os.replace(tmp, target)
    finally:
        tmp.unlink(missing_ok=True)


def remove_file(path: Path, attempts: int = 20, pause_s: float = 0.05) -> bool:
    """Supprime un fichier ; sous Windows, réessaie s'il est ouvert un instant par un autre fil (WinError 32).

    Renvoie False si le fichier n'a pas pu être supprimé (un verrou restant est sans danger : le cache et le
    marqueur d'échec sont lus avant lui, et un verrou trop vieux est considéré comme abandonné).
    """
    for attempt in range(attempts):
        try:
            path.unlink(missing_ok=True)
            return True
        except PermissionError:
            if attempt + 1 < attempts:
                time.sleep(pause_s)
    log.warning("Fichier temporaire impossible à supprimer pour l'instant : %s", path.name)
    return False


def _check_name(value: str, what: str) -> str:
    """Un identifiant de carte ou de document doit être un simple nom (comme `file_name` dans le stockage)."""
    if (not value or value in {".", ".."} or value != PurePosixPath(value).name
            or any(c in value for c in ("\\", ":", "\0"))):
        raise CacheAccessError(f"{what} refusé : un simple nom est attendu.")
    return value


def run_ocr_job(source: Path, document_id: str, final: Path, *, timeout_s: float,
                run_process: RunProcess = run_cli) -> bool:
    """Lance l'OCR dans un processus séparé et range le résultat dans `final`. Renvoie False en cas d'échec.

    Le JSON temporaire (`.part`) contient le texte du document : il est supprimé dans tous les cas (succès,
    plantage du processus, délai dépassé, JSON invalide). Rien n'est deviné : un échec ne produit aucune ligne.
    """
    part = final.with_name(f"{final.stem}.part")
    try:
        code = run_process(ocr_command(source, part), timeout_s)
        if code != 0:
            log.warning("OCR %s : le processus s'est arrêté avec le code %s.", document_id, code)
            return False
        if not part.exists():
            log.warning("OCR %s : aucun résultat écrit par le processus.", document_id)
            return False
        doc = IntermediateDocument.model_validate_json(part.read_text(encoding="utf-8"))
        write_atomically(final, doc.model_copy(update={"document_id": document_id}).model_dump_json())
        return True
    except subprocess.TimeoutExpired:
        log.warning("OCR %s : délai de %.0f s dépassé.", document_id, timeout_s)
        return False
    except (ValueError, OSError) as exc:  # JSON invalide (ValidationError est un ValueError) ou fichier illisible
        log.warning("OCR %s : résultat inutilisable (%s).", document_id, type(exc).__name__)
        return False
    finally:
        remove_file(part)


class OcrCache:
    """Cache des lectures OCR et lancement en arrière-plan (un seul OCR par fichier, grâce à un verrou)."""

    def __init__(self, cache_dir: Path, *, timeout_s: float = DEFAULT_TIMEOUT_S, lock_max_age_s: float | None = None,
                 run_process: RunProcess = run_cli, launcher: Launcher = start_thread,
                 clock: Callable[[], float] = time.time) -> None:
        self.cache_dir = cache_dir.resolve()
        self.timeout_s = timeout_s
        self.lock_max_age_s = lock_max_age_s if lock_max_age_s is not None else timeout_s + 60.0
        self.run_process = run_process
        self.launcher = launcher
        self.clock = clock

    def folder(self, card_id: str, document_id: str) -> Path:
        """Dossier du document dans le cache, après les contrôles d'accès."""
        card, document = _check_name(card_id, "card_id"), _check_name(document_id, "document_id")
        folder = (self.cache_dir / "cards" / card / "documents" / document).resolve()
        if not folder.is_relative_to(self.cache_dir):
            raise CacheAccessError("chemin hors du dossier de cache.")
        return folder

    def paths(self, path: Path, *, card_id: str, document_id: str) -> tuple[Path, Path, Path]:
        """Fichiers du document dans le cache : résultat (`.json`), marqueur d'échec (`.echec`), verrou (`.lock`)."""
        folder = self.folder(card_id, document_id)
        key = cache_key(file_sha256(path))
        return folder / f"{key}.json", folder / f"{key}.echec", folder / f"{key}.lock"

    def lookup_or_start(self, path: Path, *, card_id: str, document_id: str) -> OcrState:
        final, failed, lock = self.paths(path, card_id=card_id, document_id=document_id)
        folder = final.parent

        if final.exists():
            try:
                return OcrState("pret", IntermediateDocument.model_validate_json(final.read_text(encoding="utf-8")))
            except ValueError:
                log.warning("OCR %s : cache illisible, supprimé ; nouvelle lecture.", document_id)
                remove_file(final)
        if failed.exists():
            return OcrState("echec")

        folder.mkdir(parents=True, exist_ok=True)
        try:
            fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)  # création atomique : un seul gagnant
        except FileExistsError:
            return self._existing_lock(lock, failed, document_id)
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump({"started_at": self.clock(), "pid": os.getpid()}, handle)

        def job() -> None:
            try:
                if not run_ocr_job(path, document_id, final, timeout_s=self.timeout_s, run_process=self.run_process):
                    self._mark_failed(failed, "ocr")
            except Exception:  # un fil d'arrière-plan ne doit jamais mourir en silence
                log.exception("OCR %s : erreur inattendue.", document_id)
                self._mark_failed(failed, "erreur_interne")
            finally:
                remove_file(lock)

        self.launcher(job)
        if final.exists():  # lanceur synchrone (tests) : le résultat est déjà là
            return self.lookup_or_start(path, card_id=card_id, document_id=document_id)
        return OcrState("echec") if failed.exists() else OcrState("en_cours")

    def _existing_lock(self, lock: Path, failed: Path, document_id: str) -> OcrState:
        """Lecture déjà lancée. Un verrou trop vieux veut dire que son processus est mort sans nettoyer : échec."""
        try:
            started = float(json.loads(lock.read_text(encoding="utf-8"))["started_at"])
        except (OSError, ValueError, KeyError, TypeError):
            started = lock.stat().st_mtime if lock.exists() else self.clock()
        if self.clock() - started <= self.lock_max_age_s:
            return OcrState("en_cours")
        log.warning("OCR %s : verrou abandonné (plus de %.0f s), lecture considérée en échec.",
                    document_id, self.lock_max_age_s)
        self._mark_failed(failed, "verrou_abandonne")
        remove_file(lock)
        return OcrState("echec")

    def _mark_failed(self, failed: Path, reason: str) -> None:
        """Marqueur d'échec sans aucun texte du document."""
        write_atomically(failed, json.dumps({"reason": reason, "at": self.clock()}))


def default_backend() -> OcrCache | None:
    """Le cache configuré par `DS3_CACHE_DIR`, ou None si l'OCR ne peut pas tourner sur ce serveur.

    None quand `DS3_CACHE_DIR` n'est pas défini ou que PaddleOCR n'est pas installé : le pipeline répond alors
    comme sans OCR (zones en attente, avertissement), sans lancer de processus voué à l'échec.
    """
    value = os.getenv(CACHE_DIR_ENV)
    if not value or importlib.util.find_spec("paddleocr") is None:
        return None
    return OcrCache(Path(value))
