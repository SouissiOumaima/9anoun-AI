"""Tests du cache OCR en arrière-plan (`reading/ocr_cache.py`) sur des documents FICTIFS.

Aucun vrai modèle : le processus OCR est remplacé par une fonction qui écrit (ou non) le JSON attendu, et le
lancement en arrière-plan par un appel direct ou différé. Le temps est simulé (horloge remplaçable) :
aucun test n'attend un vrai délai. Seuls deux tests lancent un vrai sous-processus Python,
minuscule (`python -c ...`), pour vérifier `run_cli` : aucun OCR n'y tourne.
"""

from __future__ import annotations

import json
import logging
import subprocess
import sys
import threading
import time
from collections.abc import Callable
from pathlib import Path

import pytest

from src.document_intelligence.intermediate import (
    IntermediateDocument,
    PageContent,
    TextLine,
)
from src.document_intelligence.reading import ocr_cache
from src.document_intelligence.reading.ocr_cache import (
    CACHE_VERSION,
    CacheAccessError,
    OcrCache,
    default_backend,
    ocr_command,
    run_cli,
    run_ocr_job,
    start_thread,
    write_atomically,
)

SECRET = "Salaire SECRET 424.100"
CARD, DOC = "company_042", "doc_7f3a"


def _doc_json(document_id: str = "nom_du_fichier") -> str:
    line = TextLine(line_id="p1_l1", page=1, text=SECRET, bbox=(10, 10, 200, 30), confidence=0.93, source="ocr",
                    language="fr")
    doc = IntermediateDocument(document_id=document_id, file_name="scan.pdf", page_count=1,
                               reader="pdf_natif-0.3+ocr_paddle-0.1",
                               pages=[PageContent(page=1, width=595, height=842, kind="image", lines=[line])])
    return doc.model_dump_json()


class FakeProcess:
    """Remplace le processus OCR : écrit `content` dans le fichier `--json`, puis renvoie `code` (ou lève)."""

    def __init__(self, content: str | None = None, code: int = 0, raises: BaseException | None = None) -> None:
        self.content, self.code, self.raises = content, code, raises
        self.calls: list[list[str]] = []
        self.parts_seen: list[Path] = []

    def __call__(self, cmd: list[str], timeout_s: float) -> int:
        self.calls.append(cmd)
        part = Path(cmd[cmd.index("--json") + 1])
        self.parts_seen.append(part)
        if self.content is not None:
            part.write_text(self.content, encoding="utf-8")
        if self.raises is not None:
            raise self.raises
        return self.code


def _sync(job: Callable[[], None]) -> None:
    job()


class Deferred:
    """Lanceur qui garde les travaux sans les exécuter (lecture « en cours »)."""

    def __init__(self) -> None:
        self.jobs: list[Callable[[], None]] = []

    def __call__(self, job: Callable[[], None]) -> None:
        self.jobs.append(job)

    def run_all(self) -> None:
        while self.jobs:  # une lecture qui se termine lance la suivante de la file (ajoutée ici)
            self.jobs.pop(0)()

    def run_one(self) -> None:
        self.jobs.pop(0)()


@pytest.fixture()
def source(tmp_path: Path) -> Path:
    path = tmp_path / "stockage" / "scan.pdf"
    path.parent.mkdir()
    path.write_bytes(b"%PDF fictif")
    return path


def _cache(tmp_path: Path, process: FakeProcess, launcher: Callable[[Callable[[], None]], None] = _sync,
           **kwargs: float | Callable[[], float]) -> OcrCache:
    return OcrCache(tmp_path / "cache", run_process=process, launcher=launcher, **kwargs)  # type: ignore[arg-type]


def _leftovers(folder: Path, *suffixes: str) -> list[str]:
    return [p.name for p in folder.iterdir() if p.suffix in suffixes] if folder.exists() else []


# ------------------------------------------------------------ cas nominal


def test_success_is_cached_atomically_and_the_temporary_json_is_deleted(tmp_path: Path, source: Path) -> None:
    process = FakeProcess(_doc_json())
    cache = _cache(tmp_path, process)

    state = cache.lookup_or_start(source, card_id=CARD, document_id=DOC)

    assert state.status == "pret" and state.document is not None
    assert state.document.document_id == DOC  # remis sur le document lu (la CLI utilise le nom du fichier)
    assert state.document.pages[0].lines[0].text == SECRET
    folder = cache.folder(CARD, DOC)
    assert folder == (tmp_path / "cache" / "cards" / CARD / "documents" / DOC).resolve()
    assert [p.name for p in folder.iterdir()] == [f"{ocr_cache.cache_key(ocr_cache.file_sha256(source))}.json"]
    assert not process.parts_seen[0].exists()  # remarque 4 : JSON temporaire supprimé

    again = cache.lookup_or_start(source, card_id=CARD, document_id=DOC)
    assert again.status == "pret" and len(process.calls) == 1  # lu dans le cache, pas de nouvel OCR


def test_ocr_command_runs_the_existing_cli_module(tmp_path: Path) -> None:
    cmd = ocr_command(tmp_path / "a.pdf", tmp_path / "a.part")
    assert cmd[0] == sys.executable
    assert cmd[1:4] == ["-m", "src.document_intelligence.reading.ocr", str(tmp_path / "a.pdf")]
    assert cmd[4:] == ["--json", str(tmp_path / "a.part")]


# ------------------------------------------------------------ échecs : le JSON temporaire disparaît toujours


@pytest.mark.parametrize(
    ("process", "reason"),
    [
        (FakeProcess(_doc_json()[:40], code=3221225477), "plantage natif (access violation)"),
        (FakeProcess("{pas du json " + SECRET, code=0), "JSON invalide"),
        (FakeProcess(None, code=0), "aucun résultat écrit"),
        (FakeProcess(_doc_json(), raises=subprocess.TimeoutExpired("ocr", 1.0)), "délai dépassé"),
    ],
)
def test_failures_give_echec_without_text_and_delete_the_temporary_json(
        tmp_path: Path, source: Path, process: FakeProcess, reason: str, caplog: pytest.LogCaptureFixture) -> None:
    cache = _cache(tmp_path, process)
    with caplog.at_level(logging.WARNING):
        state = cache.lookup_or_start(source, card_id=CARD, document_id=DOC)

    assert state.status == "echec" and state.document is None, reason
    folder = cache.folder(CARD, DOC)
    assert not process.parts_seen[0].exists(), reason
    assert _leftovers(folder, ".part", ".lock", ".tmp", ".json") == []
    marker = next(folder.glob("*.echec"))
    assert SECRET not in marker.read_text(encoding="utf-8")  # aucun texte du document dans le marqueur
    assert SECRET not in caplog.text  # ni dans le journal

    assert cache.lookup_or_start(source, card_id=CARD, document_id=DOC).status == "echec"
    assert len(process.calls) == 1  # pas de relance en boucle


def test_unexpected_error_in_the_job_is_an_echec(tmp_path: Path, source: Path) -> None:
    process = FakeProcess(_doc_json(), raises=RuntimeError("panne"))
    cache = _cache(tmp_path, process)
    assert cache.lookup_or_start(source, card_id=CARD, document_id=DOC).status == "echec"
    folder = cache.folder(CARD, DOC)
    assert not process.parts_seen[0].exists()
    assert json.loads(next(folder.glob("*.echec")).read_text(encoding="utf-8"))["reason"] == "erreur_interne"
    assert _leftovers(folder, ".lock") == []


def test_a_changed_file_is_read_again(tmp_path: Path, source: Path) -> None:
    process = FakeProcess(None, code=1)
    cache = _cache(tmp_path, process)
    assert cache.lookup_or_start(source, card_id=CARD, document_id=DOC).status == "echec"
    source.write_bytes(b"%PDF fictif, version 2")
    process.content, process.code = _doc_json(), 0
    assert cache.lookup_or_start(source, card_id=CARD, document_id=DOC).status == "pret"
    assert len(process.calls) == 2


def test_an_unreadable_cache_file_is_replaced(tmp_path: Path, source: Path) -> None:
    process = FakeProcess(_doc_json())
    cache = _cache(tmp_path, process)
    folder = cache.folder(CARD, DOC)
    folder.mkdir(parents=True)
    (folder / f"{ocr_cache.cache_key(ocr_cache.file_sha256(source))}.json").write_text("abîmé", encoding="utf-8")
    assert cache.lookup_or_start(source, card_id=CARD, document_id=DOC).status == "pret"
    assert len(process.calls) == 1


# ------------------------------------------------------------ verrou : jamais deux OCR du même fichier


def test_lock_prevents_a_second_ocr_and_the_next_question_reads_the_cache(tmp_path: Path, source: Path) -> None:
    process, launcher = FakeProcess(_doc_json()), Deferred()
    cache = _cache(tmp_path, process, launcher)

    assert cache.lookup_or_start(source, card_id=CARD, document_id=DOC).status == "en_cours"  # 1re question
    assert cache.lookup_or_start(source, card_id=CARD, document_id=DOC).status == "en_cours"  # verrou
    assert len(launcher.jobs) == 1 and process.calls == []

    launcher.run_all()  # l'OCR d'arrière-plan se termine
    folder = cache.folder(CARD, DOC)
    assert _leftovers(folder, ".lock", ".part") == []
    state = cache.lookup_or_start(source, card_id=CARD, document_id=DOC)  # question suivante
    assert state.status == "pret" and len(process.calls) == 1


def test_an_abandoned_lock_becomes_an_echec(tmp_path: Path, source: Path) -> None:
    now = [1000.0]
    process, launcher = FakeProcess(_doc_json()), Deferred()
    cache = _cache(tmp_path, process, launcher, timeout_s=10.0, lock_max_age_s=60.0, clock=lambda: now[0])

    assert cache.lookup_or_start(source, card_id=CARD, document_id=DOC).status == "en_cours"
    now[0] += 59
    assert cache.lookup_or_start(source, card_id=CARD, document_id=DOC).status == "en_cours"
    now[0] += 2  # le processus est mort sans nettoyer son verrou
    assert cache.lookup_or_start(source, card_id=CARD, document_id=DOC).status == "echec"
    assert _leftovers(cache.folder(CARD, DOC), ".lock") == []


def test_an_abandoned_lock_also_deletes_the_orphan_part_file(tmp_path: Path, source: Path) -> None:
    """Le processus orphelin a laissé son `.part` (texte du document) : supprimé avec le verrou abandonné."""
    now = [1000.0]
    cache = _cache(tmp_path, FakeProcess(_doc_json()), Deferred(), lock_max_age_s=60.0, clock=lambda: now[0])
    assert cache.lookup_or_start(source, card_id=CARD, document_id=DOC).status == "en_cours"
    final, failed, lock = cache.paths(source, card_id=CARD, document_id=DOC)
    part = ocr_cache.part_path(final)
    assert part == ocr_cache.part_path(lock) and part.parent == lock.parent  # même nom de base que le verrou
    part.write_text(SECRET, encoding="utf-8")  # écrit à moitié, puis le processus meurt

    now[0] += 30  # verrou encore récent : la lecture tourne peut-être toujours, on ne touche à rien
    assert cache.lookup_or_start(source, card_id=CARD, document_id=DOC).status == "en_cours"
    assert part.exists()

    now[0] += 31  # verrou abandonné
    assert cache.lookup_or_start(source, card_id=CARD, document_id=DOC).status == "echec"
    assert not part.exists() and not lock.exists() and not final.exists()
    assert SECRET not in failed.read_text(encoding="utf-8")  # le marqueur d'échec ne contient aucun texte
    assert _leftovers(cache.folder(CARD, DOC), ".lock", ".part", ".tmp") == []


def test_an_unreadable_lock_uses_the_file_date(tmp_path: Path, source: Path) -> None:
    cache = _cache(tmp_path, FakeProcess(_doc_json()), Deferred(), lock_max_age_s=3600.0)
    folder = cache.folder(CARD, DOC)
    folder.mkdir(parents=True)
    (folder / f"{ocr_cache.cache_key(ocr_cache.file_sha256(source))}.lock").write_text("?", encoding="utf-8")
    assert cache.lookup_or_start(source, card_id=CARD, document_id=DOC).status == "en_cours"


def test_default_lock_age_is_the_timeout_plus_a_margin(tmp_path: Path) -> None:
    assert OcrCache(tmp_path, timeout_s=100.0).lock_max_age_s == 160.0


# ------------------------------------------------------------ contrôles d'accès


@pytest.mark.parametrize("bad", ["", ".", "..", "../autre", "a/b", "a\\b", "C:doc", "x\0y"])
def test_card_and_document_ids_must_be_simple_names(tmp_path: Path, source: Path, bad: str) -> None:
    cache = _cache(tmp_path, FakeProcess(_doc_json()))
    with pytest.raises(CacheAccessError):
        cache.lookup_or_start(source, card_id=bad, document_id=DOC)
    with pytest.raises(CacheAccessError):
        cache.lookup_or_start(source, card_id=CARD, document_id=bad)
    assert not (tmp_path / "cache").exists() or not any((tmp_path / "cache").rglob("*.json"))


def test_a_folder_that_resolves_outside_the_cache_is_refused(tmp_path: Path, source: Path) -> None:
    cache = _cache(tmp_path, FakeProcess(_doc_json()))
    outside = tmp_path / "ailleurs"
    outside.mkdir()
    link = tmp_path / "cache" / "cards" / CARD / "documents" / DOC
    link.parent.mkdir(parents=True)
    try:
        link.symlink_to(outside, target_is_directory=True)
    except OSError:
        pytest.skip("liens symboliques non autorisés sur ce poste")
    with pytest.raises(CacheAccessError):
        cache.lookup_or_start(source, card_id=CARD, document_id=DOC)


def test_another_card_never_reads_this_cache(tmp_path: Path, source: Path) -> None:
    process = FakeProcess(_doc_json())
    cache = _cache(tmp_path, process)
    assert cache.lookup_or_start(source, card_id=CARD, document_id=DOC).status == "pret"
    assert cache.folder("company_999", DOC) != cache.folder(CARD, DOC)
    assert cache.lookup_or_start(source, card_id="company_999", document_id=DOC).status == "pret"
    assert len(process.calls) == 2  # la seconde carte a sa propre lecture, jamais celle de la première


# ------------------------------------------------------------ morceaux techniques


def test_run_ocr_job_can_be_called_directly(tmp_path: Path, source: Path) -> None:
    final = tmp_path / "k.json"
    assert run_ocr_job(source, DOC, final, timeout_s=5.0, run_process=FakeProcess(_doc_json()))
    assert IntermediateDocument.model_validate_json(final.read_text(encoding="utf-8")).document_id == DOC
    assert not (tmp_path / "k.part").exists()


def test_remove_file_retries_while_the_file_is_busy(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Sous Windows, un fichier ouvert un instant par un autre fil ne peut pas être supprimé (WinError 32)."""
    target = tmp_path / "x.lock"
    target.write_text("{}", encoding="utf-8")
    real_unlink, tries = Path.unlink, [0]

    def busy_twice(self: Path, missing_ok: bool = False) -> None:
        tries[0] += 1
        if tries[0] <= 2:
            raise PermissionError("WinError 32")
        real_unlink(self, missing_ok=missing_ok)

    monkeypatch.setattr(Path, "unlink", busy_twice)
    assert ocr_cache.remove_file(target, pause_s=0.0) and not target.exists() and tries[0] == 3

    tries[0] = -100  # toujours occupé : abandon propre, sans exception
    target.write_text("{}", encoding="utf-8")
    assert ocr_cache.remove_file(target, attempts=3, pause_s=0.0) is False


def test_write_atomically_leaves_no_temporary_file(tmp_path: Path) -> None:
    target = tmp_path / "cache.json"
    write_atomically(target, "{}")
    write_atomically(target, '{"a": 1}')
    assert json.loads(target.read_text(encoding="utf-8")) == {"a": 1}
    assert [p.name for p in tmp_path.iterdir()] == ["cache.json"]


def test_cache_names_are_short_and_change_with_the_reader_version(monkeypatch: pytest.MonkeyPatch,
                                                                   tmp_path: Path) -> None:
    key = ocr_cache.cache_key("a" * 64)
    assert key == "a" * 24 + "_" + ocr_cache.version_code() and len(key) == 33
    assert ocr_cache.cache_key("a" * 64) == key  # stable pour une même version
    monkeypatch.setattr(ocr_cache, "CACHE_VERSION", "pdf_natif-0.4+ocr_paddle-0.1")
    assert ocr_cache.cache_key("a" * 64) != key  # nouveau lecteur : nouveau nom, donc cache invalidé
    tmp = ocr_cache.temp_path(tmp_path / f"{key}.echec")
    assert tmp.name.startswith(f"{key}.echec.") and tmp.name.endswith(".tmp")
    random_part = tmp.name.removeprefix(f"{key}.echec.").removesuffix(".tmp")
    assert len(random_part) == 8 and all(c in "0123456789abcdef" for c in random_part)  # pas de PID


def test_deep_cache_dir_keeps_every_written_path_under_240_characters(tmp_path: Path, source: Path,
                                                                      monkeypatch: pytest.MonkeyPatch) -> None:
    """Sous Windows sans chemins longs, un chemin complet est refusé au-delà de 260 caractères (FileNotFoundError).

    Dossier de cache volontairement profond : son chemin complet fait 120 caractères. Avec des identifiants longs,
    tout fichier écrit (résultat, marqueur d'échec, verrou, JSON temporaire de l'OCR, fichiers .tmp) doit tenir dans
    les 120 caractères restants, soit moins de 240 au total. Le test vérifie la longueur elle-même : il échoue même
    sur un poste où les chemins longs sont activés.
    """
    base = len(str(tmp_path.resolve())) + 1
    root = tmp_path / ("c" * max(1, 120 - base))  # chemin complet de 120 caractères (ou plus si tmp_path est long)
    root_len = len(str(root.resolve()))
    written: list[Path] = []
    real_temp_path = ocr_cache.temp_path

    def recording_temp_path(target: Path) -> Path:
        tmp = real_temp_path(target)
        written.append(tmp)
        return tmp

    monkeypatch.setattr(ocr_cache, "temp_path", recording_temp_path)
    card, doc = "company-demo-001", "doc-company-payslip-01"

    ok = FakeProcess(_doc_json())
    cache = OcrCache(root, run_process=ok, launcher=_sync)
    assert cache.lookup_or_start(source, card_id=card, document_id=doc).status == "pret"
    source.write_bytes(b"%PDF fictif, autre version")  # autre empreinte : nouvelle lecture, qui échoue
    crash = FakeProcess(None, code=1)
    cache_fail = OcrCache(root, run_process=crash, launcher=_sync)
    assert cache_fail.lookup_or_start(source, card_id=card, document_id=doc).status == "echec"

    final, failed, lock = cache_fail.paths(source, card_id=card, document_id=doc)
    written += [final, failed, lock, *ok.parts_seen, *crash.parts_seen]
    assert all(p.resolve().is_relative_to(root.resolve()) for p in written)
    longest = max(len(str(p.resolve())) for p in written)
    assert longest - root_len <= 120, f"partie du chemin ajoutée par le cache : {longest - root_len} caractères"
    if root_len <= 120:
        assert longest < 240, f"chemin le plus long : {longest} caractères"


def test_run_cli_returns_the_exit_code_and_respects_the_timeout() -> None:
    # vrai sous-processus minuscule (aucun OCR) : code de sortie transmis, sortie jetée
    assert run_cli([sys.executable, "-c", "import sys; print('texte'); sys.exit(3)"], 30.0) == 3
    with pytest.raises(subprocess.TimeoutExpired):
        run_cli([sys.executable, "-c", "import time; time.sleep(5)"], 0.5)


def test_start_thread_runs_the_job_in_the_background() -> None:
    done = threading.Event()
    start_thread(done.set)
    assert done.wait(5.0)


def test_cache_version_follows_the_reader_versions() -> None:
    pytest.importorskip("numpy")
    pytest.importorskip("PIL")
    from src.document_intelligence.reading.ocr import READER_SUFFIX
    from src.document_intelligence.reading.pdf_natif import READER_NAME

    assert CACHE_VERSION == f"{READER_NAME}+{READER_SUFFIX}"


def test_default_backend_needs_the_cache_dir_and_paddleocr(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(ocr_cache.CACHE_DIR_ENV, raising=False)
    assert default_backend() is None
    monkeypatch.setenv(ocr_cache.CACHE_DIR_ENV, str(tmp_path))
    monkeypatch.setattr(ocr_cache.importlib.util, "find_spec", lambda name: None)
    assert default_backend() is None
    monkeypatch.setattr(ocr_cache.importlib.util, "find_spec", lambda name: object())
    backend = default_backend()
    assert isinstance(backend, OcrCache) and backend.cache_dir == tmp_path.resolve()


def test_background_thread_end_to_end_with_a_fake_process(tmp_path: Path, source: Path) -> None:
    """Vrai fil d'arrière-plan, faux processus : en_cours, puis prêt quand le fil a fini."""
    gate = threading.Event()

    class SlowProcess(FakeProcess):
        def __call__(self, cmd: list[str], timeout_s: float) -> int:
            gate.wait(5.0)
            return super().__call__(cmd, timeout_s)

    cache = OcrCache(tmp_path / "cache", run_process=SlowProcess(_doc_json()))
    assert cache.lookup_or_start(source, card_id=CARD, document_id=DOC).status == "en_cours"
    gate.set()
    deadline = time.monotonic() + 5.0
    state = cache.lookup_or_start(source, card_id=CARD, document_id=DOC)
    while state.status == "en_cours" and time.monotonic() < deadline:
        time.sleep(0.05)
        state = cache.lookup_or_start(source, card_id=CARD, document_id=DOC)
    assert state.status == "pret"
    deadline = time.monotonic() + 5.0  # le fil retire son verrou juste après avoir écrit le cache
    while _leftovers(cache.folder(CARD, DOC), ".lock") and time.monotonic() < deadline:
        time.sleep(0.05)
    assert _leftovers(cache.folder(CARD, DOC), ".lock", ".part") == []


# ------------------------------------------------------------ D42 : échec non définitif (délai, nombre d'essais)


class Clock:
    """Horloge simulée : le temps n'avance que quand le test le décide (aucun vrai sleep)."""

    def __init__(self, now: float = 1000.0) -> None:
        self.now = now

    def __call__(self) -> float:
        return self.now


def _marker(cache: OcrCache, source: Path) -> dict[str, object]:
    _, failed, _ = cache.paths(source, card_id=CARD, document_id=DOC)
    text = failed.read_text(encoding="utf-8")
    assert SECRET not in text  # jamais de texte du document dans le marqueur
    data = json.loads(text)
    assert set(data) == {"reason", "at", "attempts"}
    return data


def test_a_failure_is_retried_after_the_delay_at_most_max_attempts(tmp_path: Path, source: Path) -> None:
    clock, process = Clock(), FakeProcess("{pas du json " + SECRET, code=0)
    cache = _cache(tmp_path, process, retry_delay_s=600.0, max_attempts=3, clock=clock)

    assert cache.lookup_or_start(source, card_id=CARD, document_id=DOC).status == "echec"
    assert _marker(cache, source)["attempts"] == 1 and len(process.calls) == 1

    clock.now += 599  # délai pas encore passé : echec, rien n'est relancé
    assert cache.lookup_or_start(source, card_id=CARD, document_id=DOC).status == "echec"
    assert len(process.calls) == 1

    clock.now += 1  # délai passé : 2e essai, qui échoue aussi
    assert cache.lookup_or_start(source, card_id=CARD, document_id=DOC).status == "echec"
    assert len(process.calls) == 2 and _marker(cache, source) == {"reason": "ocr", "at": 1600.0, "attempts": 2}

    clock.now += 600  # 3e et dernier essai
    assert cache.lookup_or_start(source, card_id=CARD, document_id=DOC).status == "echec"
    assert len(process.calls) == 3 and _marker(cache, source)["attempts"] == 3

    clock.now += 10 * 86400  # échec définitif, même longtemps après
    assert cache.lookup_or_start(source, card_id=CARD, document_id=DOC).status == "echec"
    assert len(process.calls) == 3
    assert all(not part.exists() for part in process.parts_seen)
    assert _leftovers(cache.folder(CARD, DOC), ".part", ".lock", ".tmp", ".json") == []


def test_a_successful_retry_is_cached_and_removes_the_failure_marker(tmp_path: Path, source: Path) -> None:
    clock, process = Clock(), FakeProcess(None, code=1)
    cache = _cache(tmp_path, process, clock=clock)
    assert cache.lookup_or_start(source, card_id=CARD, document_id=DOC).status == "echec"

    process.content, process.code = _doc_json(), 0  # la panne était passagère
    clock.now += ocr_cache.DEFAULT_RETRY_DELAY_S  # délai par défaut : 10 min
    state = cache.lookup_or_start(source, card_id=CARD, document_id=DOC)
    assert state.status == "pret" and state.document is not None
    assert [p.suffix for p in cache.folder(CARD, DOC).iterdir()] == [".json"]  # marqueur supprimé


def test_the_retry_counter_and_delay_survive_a_restart(tmp_path: Path, source: Path) -> None:
    clock, process = Clock(), FakeProcess(None, code=1)
    first = _cache(tmp_path, process, clock=clock, max_attempts=2)
    assert first.lookup_or_start(source, card_id=CARD, document_id=DOC).status == "echec"

    # redémarrage du service : nouvel objet, rien en mémoire, seul le marqueur sur disque compte
    restarted = _cache(tmp_path, process, clock=clock, max_attempts=2)
    clock.now += 300
    assert restarted.lookup_or_start(source, card_id=CARD, document_id=DOC).status == "echec"
    assert len(process.calls) == 1  # le délai a été lu dans le marqueur
    clock.now += 300
    assert restarted.lookup_or_start(source, card_id=CARD, document_id=DOC).status == "echec"
    assert len(process.calls) == 2 and _marker(restarted, source)["attempts"] == 2

    again = _cache(tmp_path, process, clock=clock, max_attempts=2)
    clock.now += 3600
    assert again.lookup_or_start(source, card_id=CARD, document_id=DOC).status == "echec"
    assert len(process.calls) == 2  # le compteur a été lu dans le marqueur : plus d'essai


def test_a_retry_in_progress_is_en_cours_not_echec(tmp_path: Path, source: Path) -> None:
    clock, process, launcher = Clock(), FakeProcess(None, code=1), Deferred()
    cache = _cache(tmp_path, process, launcher, clock=clock)
    assert cache.lookup_or_start(source, card_id=CARD, document_id=DOC).status == "en_cours"
    launcher.run_all()
    assert cache.lookup_or_start(source, card_id=CARD, document_id=DOC).status == "echec"

    clock.now += 600
    process.content, process.code = _doc_json(), 0
    assert cache.lookup_or_start(source, card_id=CARD, document_id=DOC).status == "en_cours"  # 2e essai lancé
    assert cache.lookup_or_start(source, card_id=CARD, document_id=DOC).status == "en_cours"  # pas de 3e
    assert len(launcher.jobs) == 1
    launcher.run_all()
    assert cache.lookup_or_start(source, card_id=CARD, document_id=DOC).status == "pret"
    assert len(process.calls) == 2


def test_an_abandoned_lock_counts_as_one_attempt_and_can_be_retried(tmp_path: Path, source: Path) -> None:
    clock, process, launcher = Clock(), FakeProcess(_doc_json()), Deferred()
    cache = _cache(tmp_path, process, launcher, lock_max_age_s=60.0, clock=clock)
    assert cache.lookup_or_start(source, card_id=CARD, document_id=DOC).status == "en_cours"
    launcher.jobs.clear()  # le processus meurt sans jamais terminer
    clock.now += 61
    assert cache.lookup_or_start(source, card_id=CARD, document_id=DOC).status == "echec"
    marker = _marker(cache, source)
    assert marker["reason"] == "verrou_abandonne" and marker["attempts"] == 1
    clock.now += 600
    assert cache.lookup_or_start(source, card_id=CARD, document_id=DOC).status == "en_cours"
    launcher.run_all()
    assert cache.lookup_or_start(source, card_id=CARD, document_id=DOC).status == "pret"


def test_an_old_marker_without_counter_is_one_attempt(tmp_path: Path, source: Path) -> None:
    clock, process = Clock(), FakeProcess(_doc_json())
    cache = _cache(tmp_path, process, clock=clock)
    _, failed, _ = cache.paths(source, card_id=CARD, document_id=DOC)
    failed.parent.mkdir(parents=True)
    failed.write_text(json.dumps({"reason": "ocr", "at": 1000.0}), encoding="utf-8")  # format de la PR #46
    assert cache.failure(failed) == ocr_cache.Failure(1, 1000.0)
    assert cache.lookup_or_start(source, card_id=CARD, document_id=DOC).status == "echec"
    clock.now += 600
    assert cache.lookup_or_start(source, card_id=CARD, document_id=DOC).status == "pret"


@pytest.mark.parametrize("content", ["", "abîmé", "[]", '{"attempts": 1}', '{"at": "hier"}'])
def test_an_unreadable_marker_is_a_final_failure(tmp_path: Path, source: Path, content: str) -> None:
    clock, process = Clock(), FakeProcess(_doc_json())
    cache = _cache(tmp_path, process, clock=clock)
    _, failed, _ = cache.paths(source, card_id=CARD, document_id=DOC)
    failed.parent.mkdir(parents=True)
    failed.write_text(content, encoding="utf-8")
    clock.now += 10 * 86400
    assert cache.lookup_or_start(source, card_id=CARD, document_id=DOC).status == "echec"
    assert process.calls == []  # jamais de relance sur un état qu'on ne sait pas lire


def test_a_failure_time_in_the_future_does_not_block_the_retry(tmp_path: Path) -> None:
    clock = Clock()
    cache = OcrCache(tmp_path, clock=clock)
    assert cache.can_retry(ocr_cache.Failure(1, clock.now + 86400))  # horloge du serveur reculée
    assert not cache.can_retry(ocr_cache.Failure(3, clock.now + 86400))  # toujours borné par max_attempts


@pytest.mark.parametrize(("delay", "attempts"), [(-1.0, 3), (600.0, 0)])
def test_invalid_retry_settings_are_refused(tmp_path: Path, delay: float, attempts: int) -> None:
    with pytest.raises(ValueError):
        OcrCache(tmp_path, retry_delay_s=delay, max_attempts=attempts)


def test_default_backend_reads_the_retry_settings(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(ocr_cache.CACHE_DIR_ENV, str(tmp_path))
    monkeypatch.delenv(ocr_cache.RETRY_DELAY_ENV, raising=False)
    monkeypatch.delenv(ocr_cache.MAX_ATTEMPTS_ENV, raising=False)
    monkeypatch.setattr(ocr_cache.importlib.util, "find_spec", lambda name: object())
    backend = default_backend()
    assert backend is not None and (backend.retry_delay_s, backend.max_attempts) == (600.0, 3)
    monkeypatch.setenv(ocr_cache.RETRY_DELAY_ENV, "120")
    monkeypatch.setenv(ocr_cache.MAX_ATTEMPTS_ENV, "5")
    backend = default_backend()
    assert backend is not None and (backend.retry_delay_s, backend.max_attempts) == (120.0, 5)
    monkeypatch.setenv(ocr_cache.RETRY_DELAY_ENV, "dix")
    monkeypatch.setenv(ocr_cache.MAX_ATTEMPTS_ENV, "0")
    backend = default_backend()
    assert backend is not None and (backend.retry_delay_s, backend.max_attempts) == (600.0, 3)


# ------------------------------------------------------------ D42 : un seul OCR à la fois (file d'attente)


def _sources(tmp_path: Path, count: int) -> list[Path]:
    paths = []
    for i in range(count):
        path = tmp_path / "stockage" / f"scan_{i}.pdf"
        path.parent.mkdir(exist_ok=True)
        path.write_bytes(f"%PDF fictif {i}".encode())
        paths.append(path)
    return paths


def test_only_one_ocr_runs_for_the_whole_cache_and_the_queue_is_first_come_first_served(tmp_path: Path) -> None:
    clock, process, launcher = Clock(), FakeProcess(_doc_json()), Deferred()
    cache = _cache(tmp_path, process, launcher, clock=clock)
    docs = _sources(tmp_path, 3)
    cards = [CARD, CARD, "company_999"]  # trois documents, dont un d'une autre carte
    for i, path in enumerate(docs):
        clock.now += 1
        assert cache.lookup_or_start(path, card_id=cards[i], document_id=f"doc_{i}").status == "en_cours"
    assert len(launcher.jobs) == 1 and cache.slot.exists()  # un seul OCR lancé ; les deux autres attendent

    order: list[str] = []
    for _ in range(3):
        assert len(launcher.jobs) == 1  # jamais deux lectures à la fois
        launcher.run_one()  # la lecture se termine et lance la suivante de la file
        order.append(Path(process.calls[-1][3]).name)
    assert order == ["scan_0.pdf", "scan_1.pdf", "scan_2.pdf"]
    assert launcher.jobs == [] and not cache.slot.exists()
    for i, path in enumerate(docs):
        assert cache.lookup_or_start(path, card_id=cards[i], document_id=f"doc_{i}").status == "pret"


def test_a_failure_does_not_block_the_queue(tmp_path: Path) -> None:
    process, launcher = FakeProcess(None, code=1), Deferred()
    cache = _cache(tmp_path, process, launcher)
    first, second = _sources(tmp_path, 2)
    assert cache.lookup_or_start(first, card_id=CARD, document_id="a").status == "en_cours"
    assert cache.lookup_or_start(second, card_id=CARD, document_id="b").status == "en_cours"
    launcher.run_one()  # échec de la première lecture
    process.content, process.code = _doc_json(), 0
    assert len(launcher.jobs) == 1  # la seconde a démarré quand même
    launcher.run_all()
    assert cache.lookup_or_start(first, card_id=CARD, document_id="a").status == "echec"
    assert cache.lookup_or_start(second, card_id=CARD, document_id="b").status == "pret"


def test_the_queue_survives_a_restart_and_an_abandoned_slot_is_released(tmp_path: Path) -> None:
    clock, process = Clock(), FakeProcess(_doc_json())
    first, second = _sources(tmp_path, 2)
    before = _cache(tmp_path, process, Deferred(), lock_max_age_s=60.0, clock=clock)
    assert before.lookup_or_start(first, card_id=CARD, document_id="a").status == "en_cours"  # lecture active
    clock.now += 1
    assert before.lookup_or_start(second, card_id=CARD, document_id="b").status == "en_cours"  # en attente
    # le service s'arrête : la lecture active meurt, la demande en attente reste sur disque

    after = _cache(tmp_path, process, _sync, lock_max_age_s=60.0, clock=clock)
    clock.now += 30  # verrou global encore récent : la lecture tourne peut-être ailleurs, on attend
    assert after.lookup_or_start(second, card_id=CARD, document_id="b").status == "en_cours"
    assert process.calls == []
    clock.now += 31  # verrou global abandonné : la lecture « a » est en échec, « b » démarre
    assert after.lookup_or_start(second, card_id=CARD, document_id="b").status == "en_cours"
    assert len(process.calls) == 1
    assert after.lookup_or_start(second, card_id=CARD, document_id="b").status == "pret"
    assert after.lookup_or_start(first, card_id=CARD, document_id="a").status == "echec"
    marker = json.loads(next(after.folder(CARD, "a").glob("*.echec")).read_text(encoding="utf-8"))
    assert marker["reason"] == "verrou_abandonne" and not after.slot.exists()
    clock.now += 600  # puis nouvel essai de « a »
    assert after.lookup_or_start(first, card_id=CARD, document_id="a").status == "pret"


def test_a_waiting_request_never_expires_it_starts_when_the_active_one_is_abandoned(tmp_path: Path) -> None:
    clock, process, launcher = Clock(), FakeProcess(_doc_json()), Deferred()
    cache = _cache(tmp_path, process, launcher, lock_max_age_s=60.0, clock=clock)
    first, second = _sources(tmp_path, 2)
    assert cache.lookup_or_start(first, card_id=CARD, document_id="a").status == "en_cours"
    assert cache.lookup_or_start(second, card_id=CARD, document_id="b").status == "en_cours"
    launcher.jobs.clear()  # la lecture active « a » ne se termine jamais
    clock.now += 3600  # « b » attend depuis une heure, bien au-delà de lock_max_age_s
    assert cache.lookup_or_start(second, card_id=CARD, document_id="b").status == "en_cours"  # jamais en échec
    _, b_failed, b_lock = cache.paths(second, card_id=CARD, document_id="b")
    assert cache.lock_info(b_lock).stage == "lecture" and not b_failed.exists()  # « b » a démarré
    assert len(launcher.jobs) == 1
    assert cache.lookup_or_start(first, card_id=CARD, document_id="a").status == "echec"  # « a » abandonnée


def test_waiting_request_for_a_changed_or_deleted_file_is_dropped(tmp_path: Path) -> None:
    process, launcher = FakeProcess(_doc_json()), Deferred()
    cache = _cache(tmp_path, process, launcher)
    first, second, third = _sources(tmp_path, 3)
    assert cache.lookup_or_start(first, card_id=CARD, document_id="a").status == "en_cours"
    assert cache.lookup_or_start(second, card_id=CARD, document_id="b").status == "en_cours"
    assert cache.lookup_or_start(third, card_id=CARD, document_id="c").status == "en_cours"
    second.write_bytes(b"%PDF fictif, autre version")  # modifié pendant l'attente
    third.unlink()  # supprimé pendant l'attente
    launcher.run_all()
    assert len(process.calls) == 1  # seule « a » a été lue ; « b » et « c » abandonnées sans OCR
    for doc in ("b", "c"):
        assert _leftovers(cache.folder(CARD, doc), ".lock", ".echec", ".json", ".part") == []
    assert not cache.slot.exists()


def test_a_slot_pointing_outside_the_cache_is_only_removed(tmp_path: Path, source: Path) -> None:
    clock = Clock()
    cache = _cache(tmp_path, FakeProcess(_doc_json()), clock=clock, lock_max_age_s=60.0)
    outside = tmp_path / "ailleurs.lock"
    outside.write_text("{}", encoding="utf-8")
    cache.cache_dir.mkdir(parents=True)
    cache.slot.write_text(json.dumps({"since": 0.0, "token": "x", "lock": "../ailleurs.lock"}), encoding="utf-8")
    assert cache.lookup_or_start(source, card_id=CARD, document_id=DOC).status == "pret"
    assert outside.exists() and not (tmp_path / "ailleurs.echec").exists()


def test_a_slot_held_by_someone_else_is_never_released_by_us(tmp_path: Path) -> None:
    cache = OcrCache(tmp_path)
    cache.slot.write_text(json.dumps({"since": 0, "token": "autre"}), encoding="utf-8")
    cache._release_slot("moi")
    assert cache.slot.exists()


def test_real_threads_never_run_two_ocr_at_once(tmp_path: Path) -> None:
    """Vrais fils, faux processus, synchronisés par des événements (aucun sleep)."""
    active, peak, guard = [0], [0], threading.Lock()
    gate, finished = threading.Event(), threading.Semaphore(0)

    class CountingProcess(FakeProcess):
        def __call__(self, cmd: list[str], timeout_s: float) -> int:
            with guard:
                active[0] += 1
                peak[0] = max(peak[0], active[0])
            gate.wait(5.0)
            try:
                return super().__call__(cmd, timeout_s)
            finally:
                with guard:
                    active[0] -= 1

    def launcher(job: Callable[[], None]) -> None:
        def wrapped() -> None:
            try:
                job()
            finally:
                finished.release()
        start_thread(wrapped)

    process = CountingProcess(_doc_json())
    cache = OcrCache(tmp_path / "cache", run_process=process, launcher=launcher)
    docs = _sources(tmp_path, 3)
    for i, path in enumerate(docs):
        assert cache.lookup_or_start(path, card_id=CARD, document_id=f"d{i}").status == "en_cours"
    gate.set()
    for _ in range(3):
        assert finished.acquire(timeout=10.0)
    assert peak[0] == 1 and len(process.calls) == 3
    assert all(cache.lookup_or_start(p, card_id=CARD, document_id=f"d{i}").status == "pret"
               for i, p in enumerate(docs))


def test_the_background_thread_never_blocks_the_service_shutdown() -> None:
    seen: list[bool] = []
    done = threading.Event()

    def job() -> None:
        seen.append(threading.current_thread().daemon)
        done.set()

    start_thread(job)
    assert done.wait(5.0) and seen == [True]


# ------------------------------------------------------------ relecture de la PR #60


def test_two_processes_recovering_the_same_expired_slot_start_only_one_ocr(tmp_path: Path) -> None:
    """Deux processus voient le même verrou global expiré. A le récupère et démarre un OCR ; B, qui avait lu le
    verrou expiré juste avant, ne doit pas supprimer le nouveau verrou de A (sinon deux OCR tournent à la fois)."""
    clock, process, launcher = Clock(), FakeProcess(_doc_json()), Deferred()
    first, second = _sources(tmp_path, 2)
    a = _cache(tmp_path, process, launcher, lock_max_age_s=60.0, clock=clock)
    a.cache_dir.mkdir(parents=True)
    a.slot.write_text(json.dumps({"since": clock.now, "token": "mort", "pid": 1}), encoding="utf-8")  # lecteur actif
    assert a.lookup_or_start(first, card_id=CARD, document_id="a").status == "en_cours"  # en attente
    clock.now += 1
    assert a.lookup_or_start(second, card_id=CARD, document_id="b").status == "en_cours"  # en attente
    assert launcher.jobs == []  # le verrou global est encore récent : rien ne démarre
    clock.now += 120  # le lecteur actif est mort : verrou global expiré

    armed = [True]

    def b_clock() -> float:
        """Appelée par B juste après avoir lu le verrou expiré : A fait toute sa récupération à ce moment-là."""
        if armed[0]:
            armed[0] = False
            a.pump()
        return clock.now

    b = _cache(tmp_path, process, launcher, lock_max_age_s=60.0, clock=b_clock)
    b.pump()

    assert armed == [False]  # l'entrelacement a bien eu lieu
    assert len(launcher.jobs) == 1  # un seul OCR démarré
    slot = json.loads(a.slot.read_text(encoding="utf-8"))
    assert slot["token"] != "mort" and slot["lock"].endswith(".lock")  # le nouveau verrou de A est intact
    _, _, b_lock = a.paths(second, card_id=CARD, document_id="b")
    assert a.lock_info(b_lock).stage == "attente"  # la 2e demande attend son tour
    assert [p.name for p in a.cache_dir.iterdir() if p.name.startswith("ocr_actif")] == ["ocr_actif.lock"]

    launcher.run_all()  # A finit, puis la demande suivante démarre : toujours une à la fois
    assert len(process.calls) == 2 and not a.slot.exists()
    assert a.lookup_or_start(second, card_id=CARD, document_id="b").status == "pret"


def test_an_expired_slot_is_still_recovered_by_a_single_process(tmp_path: Path) -> None:
    clock, launcher = Clock(), Deferred()
    cache = _cache(tmp_path, FakeProcess(_doc_json()), launcher, lock_max_age_s=60.0, clock=clock)
    cache.cache_dir.mkdir(parents=True)
    cache.slot.write_text(json.dumps({"since": clock.now, "token": "mort"}), encoding="utf-8")
    source = _sources(tmp_path, 1)[0]
    assert cache.lookup_or_start(source, card_id=CARD, document_id="a").status == "en_cours"
    clock.now += 61
    cache.pump()
    assert len(launcher.jobs) == 1
    assert json.loads(cache.slot.read_text(encoding="utf-8"))["token"] != "mort"
    assert [p.name for p in cache.cache_dir.iterdir() if p.name.startswith("ocr_actif")] == ["ocr_actif.lock"]


@pytest.mark.parametrize("raw", ["nan", "NaN", "inf", "-inf", "Infinity"])
def test_non_finite_settings_fall_back_to_the_documented_defaults(tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
                                                                  caplog: pytest.LogCaptureFixture,
                                                                  raw: str) -> None:
    monkeypatch.setenv(ocr_cache.CACHE_DIR_ENV, str(tmp_path))
    monkeypatch.setattr(ocr_cache.importlib.util, "find_spec", lambda name: object())
    monkeypatch.setenv(ocr_cache.RETRY_DELAY_ENV, raw)
    monkeypatch.setenv(ocr_cache.MAX_ATTEMPTS_ENV, raw)
    with caplog.at_level(logging.WARNING):
        backend = default_backend()  # pas de plantage (int(nan) lèverait ValueError, int(inf) OverflowError)
    assert backend is not None
    assert (backend.retry_delay_s, backend.max_attempts) == (ocr_cache.DEFAULT_RETRY_DELAY_S,
                                                             ocr_cache.DEFAULT_MAX_ATTEMPTS) == (600.0, 3)
    assert caplog.text.count("invalide") == 2
