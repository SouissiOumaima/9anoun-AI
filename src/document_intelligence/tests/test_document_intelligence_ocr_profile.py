"""Tests de `scripts/evaluer_donnees_reelles.py` (options --profile et --max-pages) sur des PDF FICTIFS.

Faux moteur d'OCR : aucun modèle n'est chargé. On vérifie surtout qu'aucun texte lu n'est affiché.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType

import pymupdf
import pytest

from src.document_intelligence.reading.ocr import Image3, OcrBox, OcrLang

SCRIPT = Path(__file__).resolve().parents[3] / "scripts" / "evaluer_donnees_reelles.py"
SECRET = "Salaire SECRET 999.999"


def _load_script() -> ModuleType:
    spec = importlib.util.spec_from_file_location("evaluer_donnees_reelles", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module  # nécessaire aux dataclasses du script
    spec.loader.exec_module(module)
    return module


class LatinEngine:
    """Lit toujours le même texte latin : le mode « auto » fait donc deux passes (ar puis fr)."""

    name = "fake"

    def recognize(self, image: Image3, lang: OcrLang) -> list[OcrBox]:
        return [OcrBox(SECRET, 0.9 if lang == "fr" else 0.8, (0, 0, image.shape[1] / 2, 30))]


def _png() -> bytes:
    pix = pymupdf.Pixmap(pymupdf.csRGB, pymupdf.IRect(0, 0, 600, 220), False)
    pix.clear_with(230)
    return bytes(pix.tobytes("png"))


@pytest.fixture()
def pdf_dir(tmp_path: Path) -> Path:
    """Un PDF fictif de 3 pages, une image (donc une zone en attente) par page."""
    folder = tmp_path / "pdfs"
    folder.mkdir()
    doc = pymupdf.open()
    for _ in range(3):
        doc.new_page().insert_image(pymupdf.Rect(72, 100, 372, 210), stream=_png())
    doc.save(folder / "fictif.pdf")
    doc.close()
    return folder


def test_profile_counts_zones_calls_and_pixels_with_max_pages(pdf_dir: Path, tmp_path: Path,
                                                               capsys: pytest.CaptureFixture[str]) -> None:
    script = _load_script()
    profile = script.Profile()
    totals = script.evaluate(pdf_dir, tmp_path / "out", None, max_pages=2, profile=profile, engine=LatinEngine())

    assert totals.pages == 2 and totals.zones_a_lire == 2 and totals.lignes_ocr == 2
    summary = profile.summary()
    assert summary["zones"] == 2
    assert (summary["appels_ocr_ar"], summary["appels_ocr_fr"], summary["zones_lues_deux_fois"]) == (2, 2, 2)
    assert summary["boites_total"] == 4  # 2 zones x 2 passes x 1 boîte
    assert summary["plus_grande_image_px"] == "1250x458" or summary["plus_grande_image_px"].startswith("1250x45")
    assert all(z.rendu_s >= 0 and z.ocr_s >= 0 for z in profile.zones)

    script.print_profile(profile)
    printed = capsys.readouterr().out
    assert "SECRET" not in printed and "fictif" not in printed  # ni texte lu, ni nom de fichier


def test_render_probe_is_removed_after_evaluation(pdf_dir: Path, tmp_path: Path) -> None:
    script = _load_script()
    from src.document_intelligence.reading import ocr

    original = ocr.render_zone
    script.evaluate(pdf_dir, tmp_path / "out", None, profile=script.Profile(), engine=LatinEngine())
    assert ocr.render_zone is original


def test_main_rejects_bad_max_pages_and_writes_no_text(pdf_dir: Path, tmp_path: Path,
                                                        capsys: pytest.CaptureFixture[str]) -> None:
    script = _load_script()
    assert script.main([str(pdf_dir), "--out", str(tmp_path / "o"), "--max-pages", "0"]) == 2
    out = tmp_path / "out"
    totals = script.evaluate(pdf_dir, out, 1, max_pages=1, engine=LatinEngine())
    assert totals.pages == 1
    summary = json.dumps(totals.summary())
    assert "SECRET" not in summary and "SECRET" not in capsys.readouterr().out


# ------------------------------------------------------------ point d'entrée main (moteur par défaut remplacé)


def test_main_full_run_with_profile_prints_numbers_only(pdf_dir: Path, tmp_path: Path,
                                                        monkeypatch: pytest.MonkeyPatch,
                                                        capsys: pytest.CaptureFixture[str]) -> None:
    from src.document_intelligence.reading import ocr

    monkeypatch.setattr(ocr, "default_engine", LatinEngine)
    script = _load_script()
    out = tmp_path / "out"
    assert script.main([str(pdf_dir), "--out", str(out), "--limit", "1", "--max-pages", "2", "--profile"]) == 0

    printed = capsys.readouterr().out
    assert "Résumé agrégé" in printed and "Profil" in printed
    assert "SECRET" not in printed and "fictif" not in printed
    summary = json.loads((out / "resume_agrege.json").read_text(encoding="utf-8"))
    assert summary["pages"] == 2 and summary["lignes_ocr"] == 2
    profil = json.loads((out / "profil.json").read_text(encoding="utf-8"))
    assert profil["zones"] == 2 and len(profil["zones_detail"]) == 2
    assert "SECRET" not in json.dumps(profil)
    assert (out / "doc_001.json").exists()  # le détail complet reste dans le dossier de sortie, hors dépôt


@pytest.mark.parametrize(
    ("args", "message"),
    [
        (["dossier_absent"], "le dossier source n'existe pas"),
        (["{pdfs}", "--limit", "0"], "--limit doit être au moins 1"),
    ],
)
def test_main_refuses_bad_arguments(pdf_dir: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str],
                                    args: list[str], message: str) -> None:
    script = _load_script()
    argv = [a.replace("{pdfs}", str(pdf_dir)) for a in args]
    if argv[0] == "dossier_absent":
        argv[0] = str(tmp_path / "absent")
    assert script.main([*argv, "--out", str(tmp_path / "out")]) == 2
    assert message in capsys.readouterr().out


def test_main_refuses_an_output_folder_inside_the_repository(pdf_dir: Path,
                                                             capsys: pytest.CaptureFixture[str]) -> None:
    script = _load_script()
    inside = SCRIPT.parents[1] / "build" / "sortie_interdite"
    assert script.main([str(pdf_dir), "--out", str(inside)]) == 2
    assert "en dehors du dépôt" in capsys.readouterr().out
    assert not inside.exists()


def test_broken_pdf_is_counted_as_failed_without_stopping(pdf_dir: Path, tmp_path: Path,
                                                          capsys: pytest.CaptureFixture[str]) -> None:
    (pdf_dir / "abime.pdf").write_bytes(b"pas un PDF")
    script = _load_script()
    totals = script.evaluate(pdf_dir, tmp_path / "out", None, engine=LatinEngine())
    assert (totals.documents, totals.documents_en_echec, totals.pages) == (2, 1, 3)
    printed = capsys.readouterr().out
    assert "échec de lecture" in printed and "abime" not in printed


# ------------------------------------------------------------ instrumentation de PaddleOCR (sans Paddle)


class _SimClock:
    """Horloge simulée : remplace `time.perf_counter` du script ; seuls les faux modèles la font avancer."""

    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now


class _FakePredictor:
    def __init__(self, clock: _SimClock, cost_s: float) -> None:
        self.calls = 0
        self.clock, self.cost_s = clock, cost_s

    def process(self, batch: object) -> str:
        self.calls += 1
        self.clock.now += self.cost_s  # durée simulée d'un lot (aucun vrai sleep)
        return "lot traité"


class _FakePipeline:
    """Même imbrication que PaddleOCR 3.x : pipeline.paddlex_pipeline._pipeline.text_det_model / text_rec_model."""

    def __init__(self, clock: _SimClock) -> None:
        inner = type("Inner", (), {})()
        inner.text_det_model = _FakePredictor(clock, 2.0)
        inner.text_rec_model = _FakePredictor(clock, 3.0)
        self.inner = inner
        self.paddlex_pipeline = type("Outer", (), {"_pipeline": inner})()


def test_instrument_paddle_times_loading_detection_and_recognition(monkeypatch: pytest.MonkeyPatch) -> None:
    """Les trois durées sont bien mesurées : le test échoue si une mesure est cassée (durée restée à 0)."""
    from types import SimpleNamespace

    from src.document_intelligence.reading.ocr import PaddleEngine

    script = _load_script()
    clock = _SimClock()
    monkeypatch.setattr(script, "time", SimpleNamespace(perf_counter=clock))
    engine = PaddleEngine()
    built: list[str] = []

    def fake_pipeline(lang: OcrLang) -> _FakePipeline:
        if lang not in engine._pipelines:
            built.append(lang)
            clock.now += 8.5  # chargement simulé des modèles
            engine._pipelines[lang] = _FakePipeline(clock)
        return engine._pipelines[lang]  # type: ignore[no-any-return]

    engine._pipeline = fake_pipeline  # type: ignore[method-assign]
    profile = script.Profile()
    script._instrument_paddle(engine, profile)

    pipe = engine._pipeline("ar")
    assert engine._pipeline("ar") is pipe and built == ["ar"]  # chargé une seule fois
    assert profile.chargement_modeles_s == 8.5  # le second appel (déjà chargé) n'ajoute rien
    assert pipe.inner.text_det_model.process("lot") == "lot traité"
    assert pipe.inner.text_det_model.process("lot") == "lot traité"
    assert pipe.inner.text_rec_model.process("lot") == "lot traité"
    assert pipe.inner.text_det_model.calls == 2 and pipe.inner.text_rec_model.calls == 1
    assert profile.chargement_modeles_s > 0 and profile.detection_s > 0 and profile.reconnaissance_s > 0
    assert (profile.chargement_modeles_s, profile.detection_s, profile.reconnaissance_s) == (8.5, 4.0, 3.0)


def test_timed_counts_time_even_when_the_function_fails() -> None:
    script = _load_script()
    spent: list[float] = []

    def boom() -> None:
        raise RuntimeError("panne")

    with pytest.raises(RuntimeError):
        script._timed(boom, spent.append)()
    assert len(spent) == 1 and spent[0] >= 0


def test_profiling_engine_records_a_call_made_outside_a_rendered_zone() -> None:
    import numpy as np

    script = _load_script()
    profile = script.Profile()
    engine = script.ProfilingEngine(LatinEngine(), profile)
    boxes = engine.recognize(np.zeros((40, 120, 3), dtype=np.uint8), "fr")
    assert len(boxes) == 1 and engine.name == "fake"
    zone = profile.zones[0]
    assert (zone.largeur_px, zone.hauteur_px, zone.appels, zone.boites) == (120, 40, ["fr"], 1)
