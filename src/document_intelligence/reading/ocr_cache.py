"""Lecture OCR en arrière-plan, dans un processus séparé, avec un cache par carte et par document (D42).

Pourquoi (voir D41 dans `docs/DECISIONS.md`) :
- l'OCR prend environ 27 s par page sur CPU, au-delà des 20 s (P95) visées pour une réponse : il tourne en
  arrière-plan, et la question suivante lit le résultat gardé en cache ;
- un plantage natif de Paddle (access violation) tue le processus qui l'a appelé : l'OCR tourne donc dans un
  **processus séparé** (`python -m src.document_intelligence.reading.ocr fichier --json sortie`), jamais dans le
  processus du service. Ce module n'importe ni Paddle ni `ocr.py`.

État exposé au pipeline par `OcrCache.lookup_or_start(path, card_id=..., document_id=...)` :
- `pret` : le document lu (natif + OCR) est dans le cache ; `state.document` le contient ;
- `en_cours` : la lecture est en file d'attente ou tourne déjà (verrou) : le service répond TIMEOUT réessayable ;
- `echec` : la lecture a planté, dépassé le délai ou rendu un JSON invalide. L'échec n'est pas définitif : un
  nouvel essai est permis après `retry_delay_s` (10 min par défaut), au plus `max_attempts` essais en tout
  (3 par défaut). Le compteur et l'heure du dernier échec sont dans le marqueur `.echec` (aucun texte du
  document) : ils valent aussi après un redémarrage du service. Un fichier modifié (autre empreinte) repart de zéro.

Un seul OCR à la fois pour tout le cache (un OCR prend tout le CPU) : chaque demande crée le verrou de son document
(`.lock`, état `attente`), qui sert aussi de ticket dans la file ; le verrou global `<DS3_CACHE_DIR>/ocr_actif.lock`,
créé de façon atomique, désigne la seule lecture active. Quand elle se termine, ou à la question suivante, la plus
ancienne demande en attente démarre. La file est sur disque : elle survit à un redémarrage et vaut entre plusieurs
processus du service. Aucun fil ne tourne en permanence : un fil `daemon` n'existe que le temps d'une lecture, il ne
bloque jamais l'arrêt du service.

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
import math
import os
import subprocess
import sys
import threading
import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any, Final, Literal, Protocol

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

RETRY_DELAY_ENV: Final = "DS3_OCR_RETRY_DELAY_S"
MAX_ATTEMPTS_ENV: Final = "DS3_OCR_MAX_ATTEMPTS"
DEFAULT_RETRY_DELAY_S: Final = 600.0
"""Délai avant un nouvel essai après un échec (10 min) : laisse passer une panne passagère sans relancer en boucle."""
DEFAULT_MAX_ATTEMPTS: Final = 3
"""Nombre maximal d'essais d'un même fichier, premier essai compris. Au-delà, l'échec est définitif."""

SLOT_NAME: Final = "ocr_actif.lock"
"""Verrou global, à la racine du cache : il existe tant qu'une lecture OCR tourne (une seule pour tout le cache)."""

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


def part_path(sibling: Path) -> Path:
    """JSON temporaire écrit par le processus OCR (`<nom de base>.part`), voisin du résultat, du marqueur et du verrou."""
    return sibling.with_name(f"{sibling.stem}.part")


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


def read_json(path: Path) -> dict[str, Any] | None:
    """Petit fichier JSON d'état (verrou, marqueur) ; None s'il est absent, vide, illisible ou n'est pas un objet."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return data if isinstance(data, dict) else None


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
    part = part_path(final)
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


LockStage = Literal["attente", "lecture"]


@dataclass(frozen=True)
class LockInfo:
    """Contenu du verrou d'un document : `attente` (dans la file) ou `lecture` (l'OCR tourne), depuis `since`.

    `attempt` est le numéro de l'essai (1, 2, ...) ; `source` le chemin du fichier à lire (jamais son texte).
    """

    stage: LockStage
    since: float
    attempt: int = 1
    source: str | None = None


@dataclass(frozen=True)
class Failure:
    """Contenu du marqueur d'échec : nombre d'essais déjà faits et heure du dernier échec (aucun texte)."""

    attempts: int
    at: float


class OcrCache:
    """Cache des lectures OCR, file d'attente et lancement en arrière-plan.

    Un seul OCR par fichier (verrou du document) et un seul OCR à la fois pour tout le cache (verrou global).
    """

    def __init__(self, cache_dir: Path, *, timeout_s: float = DEFAULT_TIMEOUT_S, lock_max_age_s: float | None = None,
                 retry_delay_s: float = DEFAULT_RETRY_DELAY_S, max_attempts: int = DEFAULT_MAX_ATTEMPTS,
                 run_process: RunProcess = run_cli, launcher: Launcher = start_thread,
                 clock: Callable[[], float] = time.time) -> None:
        if retry_delay_s < 0 or max_attempts < 1:
            raise ValueError("retry_delay_s doit être positif ou nul et max_attempts au moins 1.")
        self.cache_dir = cache_dir.resolve()
        self.timeout_s = timeout_s
        # Âge maximal d'une lecture ACTIVE (verrou `lecture` ou verrou global) : au-delà, son processus est considéré
        # comme mort sans nettoyer. Une demande en `attente` n'expire pas : elle démarrera à son tour.
        self.lock_max_age_s = lock_max_age_s if lock_max_age_s is not None else timeout_s + 60.0
        self.retry_delay_s = retry_delay_s
        self.max_attempts = max_attempts
        self.run_process = run_process
        self.launcher = launcher
        self.clock = clock

    @property
    def slot(self) -> Path:
        return self.cache_dir / SLOT_NAME

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

        ready = self._ready(final, document_id)
        if ready is not None:
            return ready
        attempt = 1
        if failed.exists():
            failure = self.failure(failed)
            if not self.can_retry(failure):
                return OcrState("echec")
            attempt = failure.attempts + 1

        final.parent.mkdir(parents=True, exist_ok=True)
        if not self._enqueue(lock, path, attempt):
            state = self._existing_lock(lock)
            self.pump()
            return state
        self.pump()
        ready = self._ready(final, document_id)  # lanceur synchrone (tests) : le résultat est peut-être déjà là
        if ready is not None:
            return ready
        if not lock.exists() and failed.exists():  # lecture déjà terminée en échec (lanceur synchrone)
            return OcrState("echec")
        return OcrState("en_cours")

    # ------------------------------------------------------------ échec non définitif

    def failure(self, failed: Path) -> Failure:
        """Lit le marqueur d'échec. Un marqueur sans compteur (PR #46) compte pour un essai ; un marqueur illisible
        rend l'échec définitif (aucune relance en boucle sur un état qu'on ne sait pas lire)."""
        data = read_json(failed)
        try:
            if data is None:
                raise ValueError
            return Failure(max(1, int(data.get("attempts", 1))), float(data["at"]))
        except (KeyError, TypeError, ValueError):
            return Failure(self.max_attempts, self.clock())

    def can_retry(self, failure: Failure) -> bool:
        """Nouvel essai permis s'il reste des essais et que le délai est passé.

        Une heure d'échec dans le futur (horloge du serveur reculée) permet aussi l'essai : sinon le document
        resterait bloqué jusqu'à cette heure. Le nombre d'essais reste borné par `max_attempts`.
        """
        if failure.attempts >= self.max_attempts:
            return False
        elapsed = self.clock() - failure.at
        return elapsed >= self.retry_delay_s or elapsed < 0

    def _mark_failed(self, failed: Path, reason: str, attempts: int) -> None:
        """Marqueur d'échec sans aucun texte du document : raison, heure, nombre d'essais faits."""
        write_atomically(failed, json.dumps({"reason": reason, "at": self.clock(), "attempts": attempts}))

    # ------------------------------------------------------------ verrou du document (ticket de la file)

    def _ready(self, final: Path, document_id: str) -> OcrState | None:
        if not final.exists():
            return None
        try:
            return OcrState("pret", IntermediateDocument.model_validate_json(final.read_text(encoding="utf-8")))
        except ValueError:
            log.warning("OCR %s : cache illisible, supprimé ; nouvelle lecture.", document_id)
            remove_file(final)
            return None

    def _enqueue(self, lock: Path, source: Path, attempt: int) -> bool:
        """Crée le verrou du document en état `attente` (création atomique : un seul gagnant)."""
        try:
            fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError:
            return False
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump({"stage": "attente", "since": self.clock(), "attempt": attempt,
                       "source": str(source.resolve()), "pid": os.getpid()}, handle)
        return True

    def lock_info(self, lock: Path) -> LockInfo:
        """Lit un verrou. Un verrou de la PR #46 (`started_at`) est une lecture active ; un verrou illisible (par
        exemple en cours d'écriture) aussi, datée du fichier : il n'est jamais pris dans la file par erreur."""
        data = read_json(lock)
        try:
            if data is None:
                raise ValueError
            stage = data.get("stage", "lecture")
            if stage not in ("attente", "lecture"):
                raise ValueError
            source = data.get("source")
            since = data["since"] if "since" in data else data["started_at"]  # `started_at` : verrou de la PR #46
            return LockInfo("attente" if stage == "attente" else "lecture", float(since),
                            max(1, int(data.get("attempt", 1))), source if isinstance(source, str) else None)
        except (KeyError, TypeError, ValueError):
            try:
                since = lock.stat().st_mtime
            except OSError:
                since = self.clock()
            return LockInfo("lecture", since)

    def _existing_lock(self, lock: Path) -> OcrState:
        """Lecture déjà demandée. En attente : elle démarrera à son tour. Active depuis trop longtemps : son processus
        est mort sans nettoyer, c'est un échec (compté comme un essai)."""
        info = self.lock_info(lock)
        if info.stage == "attente" or self.clock() - info.since <= self.lock_max_age_s:
            return OcrState("en_cours")
        log.warning("OCR %s : verrou abandonné (plus de %.0f s), lecture considérée en échec.",
                    lock.parent.name, self.lock_max_age_s)
        self._abandon(lock, info)
        return OcrState("echec")

    def _abandon(self, lock: Path, info: LockInfo) -> None:
        """Lecture abandonnée : marqueur d'échec, puis suppression du `.part` éventuel laissé par le processus
        orphelin (il contient le texte du document, et plus personne ne viendra le nettoyer) et du verrou."""
        self._mark_failed(lock.with_suffix(".echec"), "verrou_abandonne", info.attempt)
        remove_file(part_path(lock))
        remove_file(lock)

    # ------------------------------------------------------------ file : un seul OCR à la fois

    def pump(self) -> None:
        """Démarre la plus ancienne demande en attente si aucun OCR ne tourne dans tout le cache."""
        token = uuid.uuid4().hex
        if not self._take_slot(token):
            return
        try:
            waiting = self._oldest_waiting()
            if waiting is None:
                self._release_slot(token)
                return
            lock, info = waiting
            now = self.clock()
            write_atomically(lock, json.dumps({"stage": "lecture", "since": now, "attempt": info.attempt,
                                               "source": info.source, "pid": os.getpid()}))
            write_atomically(self.slot, json.dumps({"since": now, "token": token, "pid": os.getpid(),
                                                    "lock": lock.relative_to(self.cache_dir).as_posix()}))
        except OSError:
            log.warning("OCR : impossible de démarrer la lecture suivante pour l'instant.")
            self._release_slot(token)
            return
        try:
            self.launcher(lambda: self._run(lock, info, token))
        except Exception:  # fil impossible à créer : le verrou du document expirera, compté comme un échec
            log.exception("OCR %s : lancement impossible.", lock.parent.name)
            self._release_slot(token)

    def _take_slot(self, token: str) -> bool:
        """Prend le verrou global (création atomique). Un verrou global trop vieux est abandonné puis repris."""
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        for _ in range(2):
            try:
                fd = os.open(self.slot, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            except FileExistsError:
                if not self._slot_abandoned():
                    return False
                continue
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump({"since": self.clock(), "token": token, "pid": os.getpid()}, handle)
            return True
        return False

    def _slot_abandoned(self) -> bool:
        """Verrou global plus vieux que `lock_max_age_s` : la lecture active est morte (redémarrage, plantage).

        Plusieurs processus peuvent voir le même verrou expiré en même temps. Le premier qui le récupère crée aussitôt
        son propre verrou : un autre processus ne doit pas supprimer ce nouveau verrou. La récupération est donc
        atomique : le verrou est d'abord renommé vers un nom unique (`os.replace`), puis on vérifie que c'est bien le
        verrou expiré lu (même contenu, donc même token). Seul ce processus marque alors la lecture morte en échec et
        supprime le verrou expiré. Sinon, c'est le nouveau verrou d'un autre processus : il est remis en place, et on
        ne touche à rien.
        """
        try:
            raw = self.slot.read_bytes()
        except FileNotFoundError:
            return True  # supprimé entre-temps : on peut réessayer de le prendre
        except OSError:
            return False  # occupé un instant (Windows) : on réessaiera à la question suivante
        try:
            data = json.loads(raw.decode("utf-8"))
            since = float(data["since"]) if isinstance(data, dict) else float("nan")
        except (KeyError, TypeError, ValueError):
            data = {}
            try:
                since = self.slot.stat().st_mtime
            except OSError:
                return True
        if not isinstance(data, dict) or not math.isfinite(since):
            data, since = {}, self.clock()  # contenu inattendu : traité comme récent, jamais supprimé à tort
        if self.clock() - since <= self.lock_max_age_s:
            return False

        claimed = self.slot.with_name(f"{SLOT_NAME}.{uuid.uuid4().hex[:TEMP_SUFFIX_CHARS]}.abandon")
        try:
            os.replace(self.slot, claimed)  # atomique : un seul processus récupère ce fichier
        except FileNotFoundError:
            return True  # un autre processus l'a déjà récupéré : on peut réessayer de prendre le verrou
        except OSError:
            return False
        try:
            same = claimed.read_bytes() == raw
        except OSError:
            same = False
        if not same:  # ce n'est plus le verrou expiré lu : c'est le nouveau verrou d'un autre processus
            self._put_slot_back(claimed)
            return False

        log.warning("OCR : verrou global abandonné (plus de %.0f s).", self.lock_max_age_s)
        name = data.get("lock")
        if isinstance(name, str):
            lock = (self.cache_dir / name).resolve()
            if lock.is_relative_to(self.cache_dir) and lock.suffix == ".lock" and lock.exists():
                info = self.lock_info(lock)
                if info.stage == "lecture":
                    self._abandon(lock, info)
        remove_file(claimed)
        return True

    def _put_slot_back(self, claimed: Path) -> None:
        """Remet en place le verrou d'un autre processus récupéré par erreur, sans jamais écraser un verrou plus récent
        (`os.link` échoue si le nom existe déjà)."""
        try:
            os.link(claimed, self.slot)
        except FileExistsError:
            log.warning("OCR : verrou global recréé entre-temps ; le verrou récupéré par erreur est retiré.")
        except OSError:
            try:
                os.rename(claimed, self.slot)  # sous Windows, échoue aussi si le nom existe déjà
                return
            except OSError:
                log.warning("OCR : verrou global impossible à remettre en place pour l'instant.")
        remove_file(claimed)

    def _release_slot(self, token: str) -> None:
        """Rend le verrou global, seulement s'il est toujours à nous (il a pu être déclaré abandonné et repris)."""
        if (read_json(self.slot) or {}).get("token") == token:
            remove_file(self.slot)

    def _oldest_waiting(self) -> tuple[Path, LockInfo] | None:
        waiting = [(info.since, str(lock), lock, info)
                   for lock in self.cache_dir.glob("cards/*/documents/*/*.lock")
                   for info in [self.lock_info(lock)] if info.stage == "attente"]
        if not waiting:
            return None
        _, _, lock, info = min(waiting, key=lambda item: (item[0], item[1]))
        return lock, info

    def _run(self, lock: Path, info: LockInfo, token: str) -> None:
        """Travail d'arrière-plan : une lecture, puis la demande suivante de la file."""
        final, failed, document_id = lock.with_suffix(".json"), lock.with_suffix(".echec"), lock.parent.name
        try:
            source = Path(info.source) if info.source else None
            if final.exists():
                pass  # déjà lu (verrou resté en place) : rien à refaire
            elif (source is None or not source.is_file()
                  or not lock.name.startswith(file_sha256(source)[:FILE_HASH_CHARS])):
                # fichier supprimé ou modifié depuis la demande : la lecture ne correspond plus à ce verrou
                log.warning("OCR %s : fichier absent ou modifié depuis la demande, lecture abandonnée.", document_id)
            elif run_ocr_job(source, document_id, final, timeout_s=self.timeout_s, run_process=self.run_process):
                remove_file(failed)
            else:
                self._mark_failed(failed, "ocr", info.attempt)
        except Exception:  # un fil d'arrière-plan ne doit jamais mourir en silence
            log.exception("OCR %s : erreur inattendue.", document_id)
            self._mark_failed(failed, "erreur_interne", info.attempt)
        finally:
            remove_file(lock)
            self._release_slot(token)
            try:
                self.pump()
            except Exception:
                log.exception("OCR : démarrage de la lecture suivante impossible.")


def _env_number(name: str, default: float, minimum: float) -> float:
    """Réglage numérique lu dans l'environnement. Valeur illisible, non finie (`nan`, `inf`) ou trop petite : la
    valeur par défaut documentée est utilisée, avec un avertissement (jamais de plantage au démarrage)."""
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        value = float(raw)
    except ValueError:
        value = minimum - 1
    if not math.isfinite(value) or value < minimum:
        log.warning("%s invalide (%r) : valeur par défaut %s utilisée.", name, raw, default)
        return default
    return value


def default_backend() -> OcrCache | None:
    """Le cache configuré par `DS3_CACHE_DIR`, ou None si l'OCR ne peut pas tourner sur ce serveur.

    None quand `DS3_CACHE_DIR` n'est pas défini ou que PaddleOCR n'est pas installé : le pipeline répond alors
    comme sans OCR (zones en attente, avertissement), sans lancer de processus voué à l'échec.
    Réglages facultatifs : `DS3_OCR_RETRY_DELAY_S` (délai avant un nouvel essai, en secondes) et
    `DS3_OCR_MAX_ATTEMPTS` (nombre maximal d'essais).
    """
    value = os.getenv(CACHE_DIR_ENV)
    if not value or importlib.util.find_spec("paddleocr") is None:
        return None
    return OcrCache(Path(value), retry_delay_s=_env_number(RETRY_DELAY_ENV, DEFAULT_RETRY_DELAY_S, 0.0),
                    max_attempts=int(_env_number(MAX_ATTEMPTS_ENV, DEFAULT_MAX_ATTEMPTS, 1.0)))
