"""Tests du cache OCR en arrière-plan (`reading/ocr_cache.py`) sur des documents FICTIFS.

Aucun vrai modèle : le processus OCR est remplacé par une fonction qui écrit (ou non) le JSON attendu, et le
lancement en arrière-plan par un appel direct ou différé. Seuls deux tests lancent un vrai sous-processus Python,
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
        for job in self.jobs:
            job()
        self.jobs.clear()


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
