"""Tests de `scripts/annoter_lignes.py` et `scripts/evaluer_cer_reel.py` sur des documents FICTIFS.

Faux moteur d'OCR et faux lecteurs de lignes : aucun modèle chargé, aucune donnée réelle. On vérifie surtout
qu'aucun texte lu ni aucun nom de fichier n'est affiché.
"""

from __future__ import annotations

import csv
import importlib.util
import json
import os
import sys
from collections.abc import Callable
from pathlib import Path
from types import ModuleType

import pymupdf
import pytest

pytest.importorskip("numpy")
pytest.importorskip("PIL")

from src.document_intelligence.reading.ocr import Image3, OcrBox, OcrLang

SCRIPTS = Path(__file__).resolve().parents[3] / "scripts"
SECRET = "SECRET"


def _load(name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / f"{name}.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module  # nécessaire aux dataclasses des scripts
    spec.loader.exec_module(module)
    return module


class TwoLinesEngine:
    """Faux moteur : deux lignes par zone, une française et une arabe."""

    name = "fake"

    def __init__(self) -> None:
        self.calls = 0

    def recognize(self, image: Image3, lang: OcrLang) -> list[OcrBox]:
        self.calls += 1
        k = self.calls
        return [OcrBox(f"Salaire {SECRET} {k}.000", 0.95, (10, 10, 400, 60)),
                OcrBox(f"الأجر {k}", 0.88, (10, 120, 300, 170))]


def _png(width: int = 600, height: int = 220) -> bytes:
    pix = pymupdf.Pixmap(pymupdf.csRGB, pymupdf.IRect(0, 0, width, height), False)
    pix.clear_with(230)
    return bytes(pix.tobytes("png"))


@pytest.fixture()
def pdf_dir(tmp_path: Path) -> Path:
    """Deux PDF fictifs ; chacun : 2 pages, une image (zone en attente) par page."""
    folder = tmp_path / "pdfs"
    folder.mkdir()
    for name in ("a_fictif.pdf", "b_fictif.pdf"):
        doc = pymupdf.open()
        for _ in range(2):
            doc.new_page().insert_image(pymupdf.Rect(72, 100, 372, 210), stream=_png())
        doc.save(folder / name)
        doc.close()
    return folder


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle, delimiter=";"))


def _lectures(folder: Path) -> dict[str, str]:
    data = json.loads((folder / "lectures_ocr.json").read_text(encoding="utf-8"))
    assert data["format"] == "ds3.lectures_ocr.v1"
    return dict(data["lectures"])


# ------------------------------------------------------------ annoter_lignes.py


def test_prepare_draws_lines_writes_images_and_an_empty_annotation_column(pdf_dir: Path, tmp_path: Path) -> None:
    annoter = _load("annoter_lignes")
    out = tmp_path / "out"
    summary = annoter.prepare(pdf_dir, out, 5, 42, engine=TwoLinesEngine())

    assert summary["documents"] == 2 and summary["lignes_ocr_disponibles"] == 8 and summary["lignes_tirees"] == 5
    assert summary["lignes_ar"] + summary["lignes_fr"] + summary["lignes_mixte_ou_inconnu"] == 5
    rows = _read_csv(out / "annotation.csv")
    assert list(rows[0]) == list(annoter.COLUMNS)
    assert [r["id"] for r in rows] == ["0001", "0002", "0003", "0004", "0005"]
    assert all(r["texte_correct"] == "" for r in rows)  # à remplir à la main
    assert {r["document"] for r in rows} <= {"doc_001", "doc_002"}  # noms d'origine jamais repris
    for r in rows:
        image = out / r["image"]
        assert image.exists() and image.stat().st_size > 0
        with pymupdf.open(image) as img:
            assert img[0].rect.width > 0
    assert all(0.0 <= float(r["confiance"]) <= 1.0 for r in rows)


def test_the_draw_is_reproducible_with_the_same_seed(pdf_dir: Path, tmp_path: Path) -> None:
    annoter = _load("annoter_lignes")
    annoter.prepare(pdf_dir, tmp_path / "o1", 4, 7, engine=TwoLinesEngine())
    annoter.prepare(pdf_dir, tmp_path / "o2", 4, 7, engine=TwoLinesEngine())
    annoter.prepare(pdf_dir, tmp_path / "o3", 4, 8, engine=TwoLinesEngine())
    def key(out: str) -> list[tuple[str, str, str]]:
        lectures = _lectures(tmp_path / out)
        return [(r["document"], r["page"], lectures[r["id"]]) for r in _read_csv(tmp_path / out / "annotation.csv")]

    assert key("o1") == key("o2")
    assert key("o1") != key("o3")


def test_n_larger_than_available_takes_every_line_and_options_limit_the_reading(pdf_dir: Path,
                                                                               tmp_path: Path) -> None:
    annoter = _load("annoter_lignes")
    assert annoter.prepare(pdf_dir, tmp_path / "all", 100, 42, engine=TwoLinesEngine())["lignes_tirees"] == 8
    small = annoter.prepare(pdf_dir, tmp_path / "small", 100, 42, limit=1, max_pages=1, engine=TwoLinesEngine())
    assert (small["documents"], small["lignes_tirees"]) == (1, 2)


def test_crop_line_matches_the_line_box(pdf_dir: Path, tmp_path: Path) -> None:
    from src.document_intelligence.intermediate import TextLine

    annoter = _load("annoter_lignes")
    line = TextLine(line_id="p1_l1", page=1, text="x", bbox=(100.0, 120.0, 244.0, 132.0), confidence=0.9,
                    source="ocr", language="fr")
    width, height = annoter.crop_line(pdf_dir / "a_fictif.pdf", line, tmp_path / "l.png")
    # (144 + 2 x 2 points de marge) et (12 + 2 x 2) points, à 300 DPI
    assert abs(width - round(148 * 300 / 72)) <= 1 and abs(height - round(16 * 300 / 72)) <= 1


def test_a_broken_pdf_is_counted_without_stopping(pdf_dir: Path, tmp_path: Path) -> None:
    (pdf_dir / "c_abime.pdf").write_bytes(b"pas un PDF")
    annoter = _load("annoter_lignes")
    summary = annoter.prepare(pdf_dir, tmp_path / "out", 3, 42, engine=TwoLinesEngine())
    assert (summary["documents"], summary["documents_en_echec"], summary["lignes_tirees"]) == (3, 1, 3)


def test_main_prints_numbers_only_and_refuses_unsafe_outputs(pdf_dir: Path, tmp_path: Path,
                                                             monkeypatch: pytest.MonkeyPatch,
                                                             capsys: pytest.CaptureFixture[str]) -> None:
    from src.document_intelligence.reading import ocr

    monkeypatch.setattr(ocr, "default_engine", TwoLinesEngine)
    annoter = _load("annoter_lignes")
    out = tmp_path / "out"
    assert annoter.main([str(pdf_dir), "--out", str(out), "--n", "3"]) == 0
    printed = capsys.readouterr().out
    assert "Résumé agrégé" in printed and SECRET not in printed and "fictif" not in printed and "الأجر" not in printed

    assert annoter.main([str(pdf_dir), "--out", str(out)]) == 2  # le CSV existe : on n'écrase pas une annotation
    assert "existe déjà" in capsys.readouterr().out
    assert annoter.main([str(pdf_dir), "--out", str(SCRIPTS.parent / "build" / "x")]) == 2
    assert annoter.main([str(tmp_path / "absent"), "--out", str(tmp_path / "o")]) == 2
    assert annoter.main([str(pdf_dir), "--out", str(tmp_path / "o"), "--n", "0"]) == 2


# ------------------------------------------------------------ evaluer_cer_reel.py


def _write_annotation(folder: Path, rows: list[tuple[str, str, str]], *, legacy: bool = False) -> Path:
    """Écrit `annotation.csv` et, sauf ancien format (`legacy`), `lectures_ocr.json` : (id, lecture, correct)."""
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / "annotation.csv"
    header = ["id", "image", "document", "page", "langue_ocr", "confiance", "texte_correct"]
    if legacy:
        header.insert(6, "lecture_ocr")  # ancien CSV : lecture de l'OCR visible pendant l'annotation
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.writer(handle, delimiter=";")
        writer.writerow(header)
        for i, lecture, correct in rows:
            cells = [i, f"lignes/ligne_{i}.png", "doc_001", 1, "fr", "0.9", correct]
            if legacy:
                cells.insert(6, lecture)
            writer.writerow(cells)
    if not legacy:
        (folder / "lectures_ocr.json").write_text(
            json.dumps({"format": "ds3.lectures_ocr.v1", "lectures": {i: lecture for i, lecture, _ in rows}},
                       ensure_ascii=False), encoding="utf-8")
    return path


def _annotated_csv(folder: Path, *, legacy: bool = False) -> Path:
    """CSV fictif déjà annoté : 2 lignes FR, 2 AR, 1 mixte, 1 illisible, 1 non annotée."""
    rows = [
        ("0001", "Salaire de base 424.100", "Salaire de base 424.100"),
        ("0002", "Prime de transport 56.000", "Prime de transport 56,000"),
        ("0003", "الأجر الأساسي", "الأجر الأساسي"),
        ("0004", "الصنف", "الصنف 3"),
        ("0005", "Catégorie الصنف", "Catégorie 3 الصنف"),
        ("0006", "???", "#ILLISIBLE"),
        ("0007", "Net à payer", ""),
    ]
    return _write_annotation(folder, rows, legacy=legacy)


def test_read_annotations_counts_skipped_and_illegible_lines(tmp_path: Path) -> None:
    evaluer = _load("evaluer_cer_reel")
    rows, counts = evaluer.read_annotations(_annotated_csv(tmp_path / "ann"))
    assert counts == {"lignes_dans_le_csv": 7, "lignes_annotees": 5, "lignes_illisibles": 1, "lignes_non_annotees": 1}
    assert rows[0].image == tmp_path / "ann" / "lignes" / "ligne_0001.png"


def test_evaluate_compares_methods_on_the_same_lines_and_by_language(tmp_path: Path) -> None:
    evaluer = _load("evaluer_cer_reel")
    rows, _ = evaluer.read_annotations(_annotated_csv(tmp_path / "ann"))
    perfect = [row.reference for row in rows]
    results = evaluer.evaluate(rows, {"fine_tune": lambda paths: list(perfect)})

    prod = results["ocr_production"]
    assert prod["global"]["n"] == 5 and prod["global"]["cer"] > 0 and prod["global"]["lignes_exactes"] == 0.4
    assert prod["fr"]["n"] == 2 and prod["ar"]["n"] == 2 and prod["mixte"]["n"] == 1
    # une seule erreur (« . » au lieu de « , ») sur tous les caractères des deux références françaises
    assert prod["fr"]["cer"] == round(1 / (len("Salaire de base 424.100") + len("Prime de transport 56,000")), 4)
    perfect_global = results["fine_tune"]["global"]
    assert (perfect_global["n"], perfect_global["cer"], perfect_global["wer"], perfect_global["lignes_exactes"]) \
        == (5, 0.0, 0.0, 1.0)
    assert perfect_global["erreurs_caracteres"] == 0 and perfect_global["nb_lignes_exactes"] == 5


def test_totals_allow_recomputing_rates_and_languages_add_up_to_global(tmp_path: Path) -> None:
    evaluer = _load("evaluer_cer_reel")
    rows, _ = evaluer.read_annotations(_annotated_csv(tmp_path / "ann"))
    results = evaluer.evaluate(rows, {})
    prod = results["ocr_production"]
    g = prod["global"]
    assert g["cer"] == round(g["erreurs_caracteres"] / g["caracteres_reference"], 4)
    assert g["wer"] == round(g["erreurs_mots"] / g["mots_reference"], 4)
    assert g["lignes_exactes"] == round(g["nb_lignes_exactes"] / g["n"], 4)
    for key in ("n", "caracteres_reference", "erreurs_caracteres", "mots_reference", "erreurs_mots",
                "nb_lignes_exactes"):
        assert sum(prod[lang][key] for lang in evaluer.LANGS if lang in prod) == g[key], key
        assert sum(prod[t][key] for t in evaluer.TRANCHES if t in prod) == g[key], key  # tranches aussi


def _walk_strings(value: object) -> list[str]:
    """Toutes les chaînes d'un JSON : clés comprises, pour vérifier qu'aucun texte ne s'y trouve."""
    if isinstance(value, dict):
        return [s for k, v in value.items() for s in [str(k), *_walk_strings(v)]]
    if isinstance(value, list):
        return [s for v in value for s in _walk_strings(v)]
    return [value] if isinstance(value, str) else []


def test_results_json_contains_no_document_text_and_no_file_name(tmp_path: Path) -> None:
    """Le fichier partagé entre annotatrices ne contient que des nombres : ni texte lu, ni texte corrigé, ni nom."""
    evaluer = _load("evaluer_cer_reel")
    folder = tmp_path / "Paie_SECRETE_societe_X"
    path = _write_annotation(folder, [("0001", f"Salaire {SECRET} 999.999", f"Salaire {SECRET} 999.000"),
                                      ("0002", "الأجر السري", "الأجر السري 5"),
                                      ("0003", "424.100", "424.700")])
    assert evaluer.main([str(path)], recognizers={"fine_tune": lambda paths: [f"Ben {SECRET}"] * len(paths)}) == 0

    saved = json.loads((folder / "resultats_cer_reel.json").read_text(encoding="utf-8"))
    raw = (folder / "resultats_cer_reel.json").read_text(encoding="utf-8")
    for forbidden in (SECRET, "Salaire", "الأجر", "424.100", "424.700", "999", "Ben", ".png", "ligne_", "doc_00",
                      "Paie_SECRETE", "annotation.csv"):
        assert forbidden not in raw, forbidden
    allowed_keys = {"format", "lignes", "resultats", "global", "fr", "ar", "mixte", "inconnu", "ocr_production",
                    "fine_tune", "n", "cer", "wer", "lignes_exactes", "caracteres_reference", "erreurs_caracteres",
                    "mots_reference", "erreurs_mots", "nb_lignes_exactes", "lignes_dans_le_csv", "lignes_annotees",
                    "lignes_illisibles", "lignes_non_annotees", "lancement_fine_tune", "graine", "identifiant",
                    "parametres", "largeur_max_px", "tranche_caracteres", "<=44c", ">44c"}
    assert set(_walk_strings(saved)) <= allowed_keys | {evaluer.RESULTS_FORMAT}


def test_sans_modeles_never_loads_paddle_or_the_finetuned_model(tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
                                                                capsys: pytest.CaptureFixture[str]) -> None:
    """Cas de Hadil : pas de modèle fine-tuné, seulement la lecture de production."""
    evaluer = _load("evaluer_cer_reel")

    def must_not_run(*args: object, **kwargs: object) -> None:
        raise AssertionError("Paddle ne doit pas être chargé avec --sans-modeles")

    monkeypatch.setattr(evaluer, "experiment_models", must_not_run)
    monkeypatch.setattr(evaluer, "production_models", must_not_run)
    monkeypatch.setattr(evaluer, "find_finetuned_run", must_not_run)
    csv_path = _annotated_csv(tmp_path / "hadil")
    assert evaluer.main([str(csv_path), "--sans-modeles"]) == 0
    saved = json.loads((tmp_path / "hadil" / "resultats_cer_reel.json").read_text(encoding="utf-8"))
    assert saved["format"] == evaluer.RESULTS_FORMAT
    assert list(saved["resultats"]) == ["ocr_production"]
    assert "expérience non préparée" not in capsys.readouterr().out


def test_main_prints_numbers_only_and_writes_the_json(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    evaluer = _load("evaluer_cer_reel")
    csv_path = _annotated_csv(tmp_path / "ann")
    seen: list[int] = []

    def fake(paths: list[Path]) -> list[str]:
        seen.append(len(paths))
        return ["x"] * len(paths)

    assert evaluer.main([str(csv_path)], recognizers={"pre_entraine": fake, "fine_tune": fake}) == 0
    printed = capsys.readouterr().out
    assert seen == [5, 5]  # les deux modèles lisent les mêmes 5 lignes annotées
    for text in ("Salaire", "الأجر", "Catégorie", "lignes/ligne"):
        assert text not in printed
    saved = json.loads((tmp_path / "ann" / "resultats_cer_reel.json").read_text(encoding="utf-8"))
    assert set(saved["resultats"]) == {"ocr_production", "pre_entraine", "fine_tune"}
    assert saved["lignes"]["lignes_annotees"] == 5
    assert "Salaire" not in json.dumps(saved, ensure_ascii=False)


def test_main_refuses_bad_inputs(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    evaluer = _load("evaluer_cer_reel")
    assert evaluer.main([str(tmp_path / "absent.csv")], recognizers={}) == 2
    inside = SCRIPTS.parent / "scripts" / "evaluer_cer_reel.py"  # un fichier du dépôt : refusé
    assert evaluer.main([str(inside)], recognizers={}) == 2
    bad = tmp_path / "bad.csv"
    bad.write_text("id;image\n1;x.png\n", encoding="utf-8")
    assert evaluer.main([str(bad)], recognizers={}) == 2
    assert "colonnes manquantes" in capsys.readouterr().out
    empty = _annotated_csv(tmp_path / "vide")  # même CSV, mais aucune ligne annotée
    rows = _read_csv(empty)
    with empty.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]), delimiter=";")
        writer.writeheader()
        writer.writerows([{**r, "texte_correct": ""} for r in rows])
    assert evaluer.main([str(empty)], recognizers={}) == 1


def test_without_the_experiment_only_production_is_measured(tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
                                                            capsys: pytest.CaptureFixture[str]) -> None:
    evaluer = _load("evaluer_cer_reel")
    csv_path = _annotated_csv(tmp_path / "ann")
    monkeypatch.setattr(evaluer, "PPOCR_ROOT", tmp_path / "absent")
    monkeypatch.setattr(evaluer, "paddleocr_available", lambda: False)  # jamais de vrai Paddle dans les tests
    assert evaluer.main([str(csv_path)]) == 0
    printed = capsys.readouterr().out
    assert "expérience non préparée" in printed and "PaddleOCR absent" in printed
    saved = json.loads((tmp_path / "ann" / "resultats_cer_reel.json").read_text(encoding="utf-8"))
    assert list(saved["resultats"]) == ["ocr_production"]
    assert evaluer.main([str(csv_path), "--sans-modeles"]) == 0


def test_finetuned_weights_come_from_the_full_run_never_from_the_quick_run(tmp_path: Path) -> None:
    evaluer = _load("evaluer_cer_reel")
    build = tmp_path / "build"
    for name, quick, with_weights in (("rapide", True, True), ("complet", False, True), ("vide", False, False)):
        state = build / "state" / name
        state.mkdir(parents=True)
        (state / "run.json").write_text(json.dumps({"config": {"quick": quick}}), encoding="utf-8")
        if with_weights:
            (state / evaluer.FT_FILE).write_bytes(b"poids")
    (build / "state" / "casse").mkdir()
    (build / "state" / "casse" / "run.json").write_text("{pas du json", encoding="utf-8")
    run = evaluer.find_finetuned_run(build)
    assert run is not None and run.weights == build / "state" / "complet" / evaluer.FT_FILE
    assert evaluer.find_finetuned_run(tmp_path / "rien") is None


def test_the_chosen_run_is_printed_and_saved_by_seed_and_id_without_any_path(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    """Le lancement retenu est affiché et écrit dans le JSON (graine, identifiant), sans aucun chemin."""
    evaluer = _load("evaluer_cer_reel")
    build = tmp_path / "exp_build"
    for name, seed in (("seed7_aaaa", 7), ("seed42_bbbb", 42)):
        state = build / "state" / name
        state.mkdir(parents=True)
        (state / "run.json").write_text(json.dumps({"config": {"quick": False, "seed": seed}}), encoding="utf-8")
        (state / evaluer.FT_FILE).write_bytes(b"poids")
    old = build / "state" / "seed7_aaaa" / evaluer.FT_FILE
    os.utime(old, (1_000_000, 1_000_000))  # le plus ancien : c'est seed42 qui doit être retenu
    run = evaluer.find_finetuned_run(build)
    assert run is not None and (run.seed, run.run_id) == (42, "seed42_bbbb")

    loaded: list[Path | None] = []

    def fake_models(ft: Path | None) -> tuple[dict[str, object], dict[str, object]]:
        loaded.append(ft)
        return {"fine_tune": lambda paths: ["x"] * len(paths)}, {}

    monkeypatch.setattr(evaluer, "PPOCR_ROOT", tmp_path)  # « expérience prête » sans Paddle
    monkeypatch.setattr(evaluer, "PRETRAINED", build / "state" / "seed42_bbbb" / "run.json")
    monkeypatch.setattr(evaluer, "find_finetuned_run", lambda: run)
    monkeypatch.setattr(evaluer, "experiment_models", fake_models)
    monkeypatch.setattr(evaluer, "paddleocr_available", lambda: False)
    csv_path = _annotated_csv(tmp_path / "ann")
    assert evaluer.main([str(csv_path)]) == 0
    printed = capsys.readouterr().out
    assert loaded == [run.weights]
    assert "graine 42" in printed and "seed42_bbbb" in printed
    saved_text = (tmp_path / "ann" / "resultats_cer_reel.json").read_text(encoding="utf-8")
    assert json.loads(saved_text)["lancement_fine_tune"] == {"graine": 42, "identifiant": "seed42_bbbb"}
    for forbidden in (str(tmp_path), "exp_build", "state", evaluer.FT_FILE, ".pdparams"):
        assert forbidden not in printed and forbidden not in saved_text

    # Poids donnés à la main : ni graine ni chemin, seulement la mention de l'option.
    assert evaluer.main([str(csv_path), "--poids-finetune", str(run.weights)]) == 0
    saved_text = (tmp_path / "ann" / "resultats_cer_reel.json").read_text(encoding="utf-8")
    assert json.loads(saved_text)["lancement_fine_tune"] == {"graine": None,
                                                              "identifiant": "poids fournis par --poids-finetune"}
    assert str(tmp_path) not in capsys.readouterr().out and "exp_build" not in saved_text

    # Sans modèle fine-tuné (ni trouvé, ni fourni) : rien n'est inventé.
    monkeypatch.setattr(evaluer, "find_finetuned_run", lambda: None)
    assert evaluer.main([str(csv_path)]) == 0
    saved = json.loads((tmp_path / "ann" / "resultats_cer_reel.json").read_text(encoding="utf-8"))
    assert saved["lancement_fine_tune"] is None
    assert "introuvables" in capsys.readouterr().out


# ------------------------------------------------------------ combiner_resultats_cer.py


def _totals(n: int, chars: int, char_err: int, words: int, word_err: int, exact: int) -> dict[str, int]:
    return {"n": n, "caracteres_reference": chars, "erreurs_caracteres": char_err, "mots_reference": words,
            "erreurs_mots": word_err, "nb_lignes_exactes": exact}


def _results_file(path: Path, resultats: dict[str, dict[str, dict[str, int]]], annotated: int) -> Path:
    path.write_text(json.dumps({"format": "ds3.cer_reel.v2",
                                "lignes": {"lignes_dans_le_csv": annotated + 1, "lignes_annotees": annotated,
                                           "lignes_illisibles": 1, "lignes_non_annotees": 0},
                                "resultats": resultats}), encoding="utf-8")
    return path


def test_combination_is_weighted_by_totals_not_a_simple_mean(tmp_path: Path) -> None:
    combiner = _load("combiner_resultats_cer")
    big = combiner.load_results(_results_file(tmp_path / "a.json", {"ocr_production": {
        "global": _totals(300, 6000, 600, 1000, 200, 150), "ar": _totals(300, 6000, 600, 1000, 200, 150)}}, 300),
        "fichier 1")
    small = combiner.load_results(_results_file(tmp_path / "b.json", {"ocr_production": {
        "global": _totals(50, 1000, 10, 200, 4, 45), "fr": _totals(50, 1000, 10, 200, 4, 45)}}, 50), "fichier 2")
    result = combiner.combine([big, small])

    g = result["resultats"]["ocr_production"]["global"]
    assert g["n"] == 350 and g["cer"] == round(610 / 7000, 4)  # 8,71 % ; la moyenne simple donnerait 5,5 %
    assert g["cer"] != round((600 / 6000 + 10 / 1000) / 2, 4)
    assert g["wer"] == round(204 / 1200, 4) and g["lignes_exactes"] == round(195 / 350, 4)
    assert result["resultats"]["ocr_production"]["ar"]["n"] == 300  # langue présente dans un seul fichier
    assert result["resultats"]["ocr_production"]["fr"]["n"] == 50
    assert result["lignes"]["lignes_annotees"] == 350 and result["methodes_partielles"] == {}


def test_a_method_missing_from_one_file_is_reported_apart(tmp_path: Path,
                                                         capsys: pytest.CaptureFixture[str]) -> None:
    combiner = _load("combiner_resultats_cer")
    wiem = _results_file(tmp_path / "wiem.json", {
        "ocr_production": {"global": _totals(10, 200, 20, 40, 8, 5)},
        "pre_entraine": {"global": _totals(10, 200, 30, 40, 10, 3)},
        "fine_tune": {"global": _totals(10, 200, 4, 40, 2, 8)}}, 10)
    hadil = _results_file(tmp_path / "hadil.json", {"ocr_production": {"global": _totals(30, 600, 30, 120, 12, 20)}},
                          30)
    out = tmp_path / "combine.json"
    assert combiner.main([str(wiem), str(hadil), "--out", str(out)]) == 0
    printed = capsys.readouterr().out
    assert "« fine_tune » n'est présente que dans le(s) fichier(s) 1" in printed
    assert "« pre_entraine » n'est présente que dans le(s) fichier(s) 1" in printed
    assert "wiem" not in printed and "hadil" not in printed  # fichiers désignés par leur numéro seulement
    saved = json.loads(out.read_text(encoding="utf-8"))
    assert list(saved["resultats"]) == ["ocr_production"]
    assert saved["resultats"]["ocr_production"]["global"]["cer"] == round(50 / 800, 4)
    assert saved["methodes_partielles"]["fine_tune"]["fichiers"] == [1]
    assert saved["methodes_partielles"]["fine_tune"]["resultats"]["global"]["n"] == 10


def test_combiner_refuses_old_or_incomplete_files_and_unsafe_outputs(tmp_path: Path,
                                                                     capsys: pytest.CaptureFixture[str]) -> None:
    combiner = _load("combiner_resultats_cer")
    good = _results_file(tmp_path / "ok.json", {"ocr_production": {"global": _totals(1, 10, 1, 2, 1, 0)}}, 1)
    old = tmp_path / "ancien.json"
    old.write_text(json.dumps({"lignes": {}, "resultats": {"ocr_production": {"global": {"n": 1, "cer": 0.1}}}}),
                   encoding="utf-8")
    incomplete = tmp_path / "incomplet.json"
    incomplete.write_text(json.dumps({"format": "ds3.cer_reel.v2", "resultats": {
        "ocr_production": {"global": {"n": 1, "cer": 0.1}}}}), encoding="utf-8")
    broken = tmp_path / "casse.json"
    broken.write_text("{pas du json", encoding="utf-8")

    assert combiner.main([str(good)]) == 2  # une seule annotatrice : rien à combiner
    assert combiner.main([str(good), str(old)]) == 2
    assert "format non reconnu" in capsys.readouterr().out
    assert combiner.main([str(good), str(incomplete)]) == 2
    assert "totaux manquants" in capsys.readouterr().out
    assert combiner.main([str(good), str(broken)]) == 2
    assert combiner.main([str(good), str(good), "--out", str(SCRIPTS.parent / "build" / "c.json")]) == 2
    assert not (SCRIPTS.parent / "build" / "c.json").exists()


def test_end_to_end_two_annotators_with_and_without_the_finetuned_model(tmp_path: Path,
                                                                       capsys: pytest.CaptureFixture[str]) -> None:
    """Wiem (avec le modèle fine-tuné) et Hadil (--sans-modeles) : seuls les JSON de chiffres sont combinés."""
    evaluer, combiner = _load("evaluer_cer_reel"), _load("combiner_resultats_cer")
    wiem_csv, hadil_csv = _annotated_csv(tmp_path / "wiem"), _annotated_csv(tmp_path / "hadil")
    assert evaluer.main([str(wiem_csv)], recognizers={"fine_tune": lambda paths: ["x"] * len(paths)}) == 0
    assert evaluer.main([str(hadil_csv), "--sans-modeles"], recognizers={}) == 0
    capsys.readouterr()
    files = [tmp_path / "wiem" / "resultats_cer_reel.json", tmp_path / "hadil" / "resultats_cer_reel.json"]
    assert combiner.main([str(f) for f in files]) == 0
    printed = capsys.readouterr().out
    one = json.loads(files[0].read_text(encoding="utf-8"))["resultats"]["ocr_production"]["global"]
    assert f"ocr_production   global      {2 * one['n']}" in printed  # deux fois les mêmes lignes fictives
    assert "fine_tune" in printed and "fichier(s) 1" in printed
    assert "Salaire" not in printed and "الأجر" not in printed


# ------------------------------------------------------------ annotation sans biais : lecture OCR à part


def test_the_csv_contains_no_ocr_text_and_the_readings_are_in_a_separate_utf8_json(pdf_dir: Path,
                                                                                  tmp_path: Path) -> None:
    annoter = _load("annoter_lignes")
    out = tmp_path / "out"
    annoter.prepare(pdf_dir, out, 8, 42, engine=TwoLinesEngine())

    csv_text = (out / "annotation.csv").read_text(encoding="utf-8-sig")
    assert "lecture_ocr" not in csv_text and SECRET not in csv_text and "الأجر" not in csv_text
    rows = _read_csv(out / "annotation.csv")
    assert list(rows[0]) == ["id", "image", "document", "page", "langue_ocr", "confiance", "texte_correct"]

    raw = (out / "lectures_ocr.json").read_bytes()
    assert not raw.startswith(b"\xef\xbb\xbf")  # UTF-8 sans BOM
    assert "الأجر".encode() in raw  # arabe écrit tel quel, pas en \uXXXX
    lectures = _lectures(out)
    assert sorted(lectures) == [r["id"] for r in rows]  # une lecture par id de ligne du CSV
    assert sum(SECRET in text for text in lectures.values()) == 4 and sum("الأجر" in t for t in lectures.values()) == 4


def test_annoter_docstring_says_to_look_only_at_the_image() -> None:
    annoter = _load("annoter_lignes")
    assert annoter.__doc__ is not None and "annoter en regardant seulement l'image" in annoter.__doc__.lower()
    assert "lectures_ocr.json" in annoter.__doc__ and "Excel" in annoter.__doc__


def test_main_refuses_an_existing_readings_file_and_says_not_to_open_it(pdf_dir: Path, tmp_path: Path,
                                                                        monkeypatch: pytest.MonkeyPatch,
                                                                        capsys: pytest.CaptureFixture[str]) -> None:
    from src.document_intelligence.reading import ocr

    monkeypatch.setattr(ocr, "default_engine", TwoLinesEngine)
    annoter = _load("annoter_lignes")
    out = tmp_path / "out"
    assert annoter.main([str(pdf_dir), "--out", str(out), "--n", "2"]) == 0
    printed = capsys.readouterr().out
    assert "seulement l'image" in printed and "N'ouvrez pas lectures_ocr.json" in printed
    (out / "annotation.csv").unlink()  # seul le fichier de lectures reste : on ne l'écrase pas non plus
    assert annoter.main([str(pdf_dir), "--out", str(out)]) == 2
    assert "lectures_ocr.json existe déjà" in capsys.readouterr().out


def test_evaluation_reads_the_ocr_reading_from_the_json_by_line_id(tmp_path: Path,
                                                                   capsys: pytest.CaptureFixture[str]) -> None:
    evaluer = _load("evaluer_cer_reel")
    rows, counts = evaluer.read_annotations(_annotated_csv(tmp_path / "ann"))
    assert [row.lecture_ocr for row in rows] == ["Salaire de base 424.100", "Prime de transport 56.000",
                                                 "الأجر الأساسي", "الصنف", "Catégorie الصنف"]
    assert counts["lignes_annotees"] == 5
    assert "Avertissement" not in capsys.readouterr().out


def test_prepare_then_evaluate_end_to_end(pdf_dir: Path, tmp_path: Path) -> None:
    """Chaîne complète sur données fictives : préparation, annotation « parfaite », évaluation."""
    annoter, evaluer = _load("annoter_lignes"), _load("evaluer_cer_reel")
    out = tmp_path / "out"
    annoter.prepare(pdf_dir, out, 4, 42, engine=TwoLinesEngine())
    lectures = _lectures(out)
    rows = _read_csv(out / "annotation.csv")
    with (out / "annotation.csv").open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]), delimiter=";")
        writer.writeheader()
        writer.writerows([{**r, "texte_correct": lectures[r["id"]]} for r in rows])
    assert evaluer.main([str(out / "annotation.csv"), "--sans-modeles"], recognizers={}) == 0
    saved = json.loads((out / "resultats_cer_reel.json").read_text(encoding="utf-8"))
    assert saved["resultats"]["ocr_production"]["global"]["cer"] == 0.0
    assert saved["lignes"]["lignes_annotees"] == 4


def test_an_old_csv_with_the_ocr_column_still_works_with_a_warning(tmp_path: Path,
                                                                   capsys: pytest.CaptureFixture[str]) -> None:
    evaluer = _load("evaluer_cer_reel")
    old = _annotated_csv(tmp_path / "ancien", legacy=True)
    assert not (tmp_path / "ancien" / "lectures_ocr.json").exists()
    new_rows, _ = evaluer.read_annotations(_annotated_csv(tmp_path / "nouveau"))
    capsys.readouterr()

    old_rows, counts = evaluer.read_annotations(old)
    printed = capsys.readouterr().out
    assert "Avertissement" in printed and "lecture_ocr" in printed and "trop optimiste" in printed
    assert "Salaire" not in printed and "الأجر" not in printed  # l'avertissement ne cite aucun texte
    assert [r.lecture_ocr for r in old_rows] == [r.lecture_ocr for r in new_rows]
    assert counts["lignes_annotees"] == 5
    assert evaluer.main([str(old), "--sans-modeles"], recognizers={}) == 0
    old_results = json.loads((tmp_path / "ancien" / "resultats_cer_reel.json").read_text(encoding="utf-8"))
    assert evaluer.main([str(tmp_path / "nouveau" / "annotation.csv"), "--sans-modeles"], recognizers={}) == 0
    new_results = json.loads((tmp_path / "nouveau" / "resultats_cer_reel.json").read_text(encoding="utf-8"))
    assert old_results["resultats"] == new_results["resultats"]  # mêmes chiffres, ancien ou nouveau format


def test_missing_or_bad_readings_file_is_refused_without_quoting_any_text(tmp_path: Path,
                                                                          capsys: pytest.CaptureFixture[str]) -> None:
    evaluer = _load("evaluer_cer_reel")
    csv_path = _annotated_csv(tmp_path / "ann")
    readings = tmp_path / "ann" / "lectures_ocr.json"
    good = readings.read_text(encoding="utf-8")

    readings.unlink()
    assert evaluer.main([str(csv_path)], recognizers={}) == 2
    assert "lectures_ocr.json introuvable" in capsys.readouterr().out

    for content in ("{pas du json", json.dumps({"lectures": {"0001": "x"}}),
                    json.dumps({"format": "ds3.lectures_ocr.v1", "lectures": ["x"]}),
                    json.dumps({"format": "ds3.lectures_ocr.v1", "lectures": {"0001": 3}})):
        readings.write_text(content, encoding="utf-8")
        assert evaluer.main([str(csv_path)], recognizers={}) == 2
        assert "lectures_ocr.json" in capsys.readouterr().out
    readings.write_bytes("Salaire".encode("utf-16"))  # pas de l'UTF-8 (fichier réenregistré par un autre outil)
    assert evaluer.main([str(csv_path)], recognizers={}) == 2
    assert "UTF-8 attendu" in capsys.readouterr().out

    data = json.loads(good)
    del data["lectures"]["0003"]  # une ligne annotée sans lecture : refus, jamais de devinette
    readings.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    assert evaluer.main([str(csv_path)], recognizers={}) == 2
    printed = capsys.readouterr().out
    assert "1 ligne(s) annotée(s) sans lecture" in printed and "الأجر" not in printed

    no_id = tmp_path / "sans_id"
    no_id.mkdir()
    (no_id / "annotation.csv").write_text("image;texte_correct\nx.png;y\n", encoding="utf-8")
    assert evaluer.main([str(no_id / "annotation.csv")], recognizers={}) == 2
    assert "colonnes manquantes" in capsys.readouterr().out


def test_a_readings_file_with_a_bom_is_still_read_as_utf8(tmp_path: Path) -> None:
    evaluer = _load("evaluer_cer_reel")
    csv_path = _annotated_csv(tmp_path / "ann")
    readings = tmp_path / "ann" / "lectures_ocr.json"
    readings.write_text(readings.read_text(encoding="utf-8"), encoding="utf-8-sig")
    rows, _ = evaluer.read_annotations(csv_path)
    assert rows[2].lecture_ocr == "الأجر الأساسي"


# ------------------------------------------------------------ relecture de la PR #61


def _rewrite_csv(path: Path, change: Callable[[list[dict[str, str]]], list[dict[str, str]]]) -> None:
    """Réécrit le CSV comme le ferait une annotatrice (mêmes colonnes, contenu modifié)."""
    rows = _read_csv(path)
    columns = list(rows[0])
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, delimiter=";")
        writer.writeheader()
        writer.writerows(change(rows))


def test_ids_match_even_after_excel_removed_the_leading_zeros(tmp_path: Path) -> None:
    """Excel enregistre « 0001 » comme le nombre 1 : le CSV contient alors « 1 », « 2 »…, le JSON « 0001 »…"""
    evaluer = _load("evaluer_cer_reel")
    csv_path = _annotated_csv(tmp_path / "ann")
    expected, _ = evaluer.read_annotations(csv_path)
    _rewrite_csv(csv_path, lambda rows: [{**r, "id": str(int(r["id"]))} for r in rows])
    assert [r["id"] for r in _read_csv(csv_path)][:3] == ["1", "2", "3"]

    rows, counts = evaluer.read_annotations(csv_path)
    assert [r.lecture_ocr for r in rows] == [r.lecture_ocr for r in expected]
    assert counts["lignes_annotees"] == 5
    assert evaluer.main([str(csv_path), "--sans-modeles"], recognizers={}) == 0


def test_id_normalization_ignores_leading_zeros_and_spaces_only() -> None:
    evaluer = _load("evaluer_cer_reel")
    assert {evaluer.normalize_id(v) for v in ("0001", "001", "1", " 1 ", "1\t")} == {"1"}
    assert evaluer.normalize_id("0010") == "10" and evaluer.normalize_id("0") == "0"
    assert evaluer.normalize_id("L0001") == "L0001"  # un id non numérique est gardé tel quel
    assert evaluer.normalize_id("٠١") == "٠١"  # chiffres arabes : pas convertis en nombre
    assert evaluer.normalize_id(None) == "" and evaluer.normalize_id("") == ""


def test_duplicate_ids_in_the_csv_are_refused_without_quoting_any_text(tmp_path: Path,
                                                                       capsys: pytest.CaptureFixture[str]) -> None:
    evaluer = _load("evaluer_cer_reel")
    csv_path = _annotated_csv(tmp_path / "ann")
    # deux lignes copiées-collées sous l'id « 0001 » et deux sous « 0003 » (dont une écrite « 3 » par Excel)
    _rewrite_csv(csv_path, lambda rows: [{**r, "id": {"0002": "0001", "0004": "3"}.get(r["id"], r["id"])}
                                         for r in rows])
    with pytest.raises(ValueError, match="2 id en double dans le CSV"):
        evaluer.read_annotations(csv_path)
    assert evaluer.main([str(csv_path)], recognizers={}) == 2
    printed = capsys.readouterr().out
    assert "2 id en double" in printed and "Salaire" not in printed and "الأجر" not in printed


def test_duplicate_ids_in_the_readings_file_are_refused(tmp_path: Path) -> None:
    evaluer = _load("evaluer_cer_reel")
    csv_path = _annotated_csv(tmp_path / "ann")
    readings = tmp_path / "ann" / "lectures_ocr.json"
    data = json.loads(readings.read_text(encoding="utf-8"))
    data["lectures"]["1"] = "autre"  # même ligne que « 0001 » une fois les zéros ignorés
    readings.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    with pytest.raises(ValueError, match="1 id en double"):
        evaluer.read_annotations(csv_path)


def test_an_empty_image_cell_on_an_annotated_line_gives_a_clear_message(tmp_path: Path,
                                                                        capsys: pytest.CaptureFixture[str]) -> None:
    evaluer = _load("evaluer_cer_reel")
    csv_path = _annotated_csv(tmp_path / "ann")
    # image effacée sur une ligne annotée (0001) et sur une ligne non annotée (0007, sans effet)
    _rewrite_csv(csv_path, lambda rows: [{**r, "image": "  "} if r["id"] in {"0001", "0007"} else r for r in rows])
    with pytest.raises(ValueError, match="1 ligne\\(s\\) annotée\\(s\\) sans image"):
        evaluer.read_annotations(csv_path)
    assert evaluer.main([str(csv_path)], recognizers={}) == 2
    assert "sans image (colonne image vide)" in capsys.readouterr().out

    short = tmp_path / "court"  # ligne coupée : la cellule image manque complètement (None, plus de TypeError)
    short.mkdir()
    (short / "annotation.csv").write_text("id;texte_correct;image\n0001;Salaire\n", encoding="utf-8")
    (short / "lectures_ocr.json").write_text(
        json.dumps({"format": "ds3.lectures_ocr.v1", "lectures": {"0001": "Salaire"}}), encoding="utf-8")
    with pytest.raises(ValueError, match="sans image"):
        evaluer.read_annotations(short / "annotation.csv")

    old = _annotated_csv(tmp_path / "ancien", legacy=True)  # même contrôle pour un ancien CSV
    _rewrite_csv(old, lambda rows: [{**r, "image": ""} if r["id"] == "0002" else r for r in rows])
    with pytest.raises(ValueError, match="sans image"):
        evaluer.read_annotations(old)


def test_a_failed_readings_write_removes_the_csv(pdf_dir: Path, tmp_path: Path,
                                                 monkeypatch: pytest.MonkeyPatch) -> None:
    """Disque plein (ou autre erreur) en écrivant lectures_ocr.json : pas de dossier à moitié écrit."""
    annoter = _load("annoter_lignes")
    out = tmp_path / "out"
    real_write_text = Path.write_text

    def failing_write_text(self: Path, data: str, *args: object, **kwargs: object) -> int:
        if self.name == "lectures_ocr.json":
            real_write_text(self, data[:10], encoding="utf-8")  # écrit à moitié, puis échoue
            raise OSError("disque plein")
        return real_write_text(self, data, *args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(Path, "write_text", failing_write_text)
    with pytest.raises(OSError, match="disque plein"):
        annoter.prepare(pdf_dir, out, 3, 42, engine=TwoLinesEngine())
    assert not (out / "annotation.csv").exists() and not (out / "lectures_ocr.json").exists()

    monkeypatch.setattr(Path, "write_text", real_write_text)  # le relancement dans le même dossier marche
    assert annoter.prepare(pdf_dir, out, 3, 42, engine=TwoLinesEngine())["lignes_tirees"] == 3
    assert sorted(_lectures(out)) == [r["id"] for r in _read_csv(out / "annotation.csv")]


# ------------------------------------------------------------ comparaison équitable (lignes entières / morceaux)


def _line_images(folder: Path, ids: list[str], size: tuple[int, int] = (600, 60),
                 color: tuple[int, int, int] = (230, 230, 230)) -> None:
    """Images fictives des lignes (`lignes/ligne_<id>.png`), unies : aucun texte réel."""
    from PIL import Image

    (folder / "lignes").mkdir(parents=True, exist_ok=True)
    for i in ids:
        Image.new("RGB", size, color).save(folder / "lignes" / f"ligne_{i}.png")


def _box(text: str, bbox: tuple[float, float, float, float], score: float = 0.9) -> OcrBox:
    return OcrBox(text, score, bbox)


class WidthReader:
    """Faux lecteur de morceaux : le texte dépend seulement de la largeur du morceau (aucun modèle)."""

    def __init__(self, by_width: dict[int, str]) -> None:
        self.by_width = by_width
        self.calls: list[list[tuple[int, ...]]] = []

    def __call__(self, pieces: list[object]) -> list[str]:
        shapes = [tuple(p.shape) for p in pieces]  # type: ignore[attr-defined]
        self.calls.append(shapes)
        return [self.by_width.get(s[1], "?") for s in shapes]


def test_cer_is_also_given_by_length_tranche(tmp_path: Path) -> None:
    evaluer = _load("evaluer_cer_reel")
    assert evaluer.TRANCHE_CHARS == 44 and evaluer.EVAL_MAX_W == 3200
    import vocab  # experiments/ocr_transfer_finetune/vocab.py (sans dépendance lourde)

    assert evaluer.TRANCHE_CHARS == vocab.MAX_LEN  # même limite que les lignes d'entraînement
    long_ref = "الفصل الأول تنطبق هذه الاتفاقية على جميع العمال" + " والمؤسسات"  # plus de 44 caractères
    assert len(long_ref) > 44
    path = _write_annotation(tmp_path / "ann", [("0001", "الأجر", "الأجر"), ("0002", "x" * 44, "x" * 44),
                                                ("0003", long_ref[:30], long_ref)])
    rows, _ = evaluer.read_annotations(path)
    prod = evaluer.evaluate(rows, {})["ocr_production"]
    assert (prod["<=44c"]["n"], prod[">44c"]["n"]) == (2, 1)  # 44 caractères tout juste : tranche courte
    assert prod["<=44c"]["cer"] == 0.0 and prod[">44c"]["cer"] > 0
    assert evaluer.tranche(" " + "x" * 44 + "  ") == "<=44c"  # longueur après normalisation (espaces)


def test_pieces_are_cropped_read_once_and_assembled_right_to_left(tmp_path: Path) -> None:
    """Le détecteur donne deux morceaux arabes : ils sont lus en un seul appel, puis assemblés de droite à gauche."""
    evaluer = _load("evaluer_cer_reel")
    folder = tmp_path / "ann"
    path = _write_annotation(folder, [("0001", "lecture d'origine", "الأجر الأساسي")])
    _line_images(folder, ["0001"])
    seen_paths: list[list[Path]] = []

    def detector(paths: list[Path]) -> list[list[OcrBox]]:
        seen_paths.append(list(paths))
        # « الأجر » à droite (x 300-500), « الأساسي » à gauche (x 0-150) ; un doublon contenu dans le premier
        return [[_box("الأجر", (300, 5, 500, 55)), _box("الأساسي", (0, 5, 150, 55)), _box("ء", (350, 5, 360, 15))]]

    good, bad = WidthReader({200: "الأجر", 150: "الأساسي"}), WidthReader({200: "الامر", 150: "الأساسي"})
    rows, _ = evaluer.read_annotations(path)
    results = evaluer.evaluate(rows, {}, detector=detector, piece_recognizers={"pre_entraine": good,
                                                                              "fine_tune": bad})
    assert seen_paths == [[folder / "lignes" / "ligne_0001.png"]]  # mêmes images de ligne entière
    assert results["production_relue"]["global"]["cer"] == 0.0
    assert results["pre_entraine_morceaux"]["global"]["cer"] == 0.0  # ordre droite-gauche respecté
    assert results["fine_tune_morceaux"]["global"]["cer"] > 0
    assert results["ocr_production"]["global"]["cer"] > 0  # la lecture d'origine reste mesurée à part
    assert good.calls == [[(50, 200), (50, 150)]]  # un seul appel, morceaux en niveaux de gris, doublon retiré
    assert "pre_entraine" not in results and "production_rec_seule" not in results


def test_crop_pieces_clamps_boxes_and_skips_empty_ones(tmp_path: Path) -> None:
    evaluer = _load("evaluer_cer_reel")
    _line_images(tmp_path, ["0001"], size=(100, 50))
    image = tmp_path / "lignes" / "ligne_0001.png"
    pieces = evaluer.crop_pieces(image, [_box("a", (-10.0, -10.0, 20.4, 20.0)), _box("b", (200, 0, 300, 10)),
                                         _box("c", (10.2, 10.0, 10.2, 30.0)), _box("d", (0.5, 0.5, 99.5, 49.5))])
    assert [p.shape for p in pieces] == [(20, 21), (0, 0), (0, 0), (50, 100)]
    assert all(p.ndim == 2 and str(p.dtype) == "uint8" for p in pieces)

    reader = WidthReader({21: "الأجر"})
    texts = evaluer.read_pieces([[_box("a", (-10.0, -10.0, 20.4, 20.0)), _box("b", (200, 0, 300, 10))]], [image],
                                reader)
    assert texts == ["الأجر"] and reader.calls == [[(20, 21)]]  # le morceau vide n'est pas lu
    assert evaluer.read_pieces([[]], [image], reader) == [""]  # aucune boîte détectée : texte vide


def test_main_writes_the_fair_comparison_as_numbers_only(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    evaluer = _load("evaluer_cer_reel")
    folder = tmp_path / "Paie_SECRETE"
    path = _write_annotation(folder, [("0001", f"Salaire {SECRET}", f"Salaire {SECRET} 424.100"),
                                      ("0002", "الأجر السري", "الأجر السري 5")])
    _line_images(folder, ["0001", "0002"])

    def detector(paths: list[Path]) -> list[list[OcrBox]]:
        return [[_box(f"Salaire {SECRET}", (0, 5, 300, 55))], [_box("الأجر السري", (100, 5, 400, 55))]]

    lines = {"production_rec_seule": lambda paths: [f"Ben {SECRET}"] * len(paths),
             "pre_entraine": lambda paths: ["x"] * len(paths)}
    assert evaluer.main([str(path)], recognizers=lines, detector=detector,
                        piece_recognizers={"pre_entraine": WidthReader({300: "الأجر"})}) == 0
    printed = capsys.readouterr().out
    raw = (folder / "resultats_cer_reel.json").read_text(encoding="utf-8")
    saved = json.loads(raw)
    assert list(saved["resultats"]) == ["ocr_production", "production_rec_seule", "pre_entraine",
                                        "production_relue", "pre_entraine_morceaux"]
    assert saved["parametres"] == {"largeur_max_px": 3200, "tranche_caracteres": 44}
    assert all("<=44c" in entry for entry in saved["resultats"].values())
    for name in ("production_rec_seule", "production_relue", "pre_entraine_morceaux", "<=44c"):
        assert name in printed
    for forbidden in (SECRET, "Salaire", "الأجر", "424.100", "Ben", ".png", "ligne_", "Paie_SECRETE"):
        assert forbidden not in printed, forbidden
        assert forbidden not in raw, forbidden


def test_production_models_use_the_paddlex_recognizer_alone_and_the_production_pipeline(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Branchement vérifié avec de faux modules : aucun modèle n'est chargé."""
    from types import SimpleNamespace

    from src.document_intelligence.reading import ocr

    evaluer = _load("evaluer_cer_reel")
    created: list[dict[str, object]] = []
    predicted: list[tuple[list[str], int]] = []

    class FakeTextRecognition:
        def __init__(self, **kwargs: object) -> None:
            created.append(kwargs)

        def predict(self, inputs: list[str], batch_size: int) -> list[dict[str, object]]:
            predicted.append((inputs, batch_size))
            return [{"rec_text": "الأجر", "rec_score": 0.9} for _ in inputs]

    seen: list[tuple[tuple[int, ...], int, OcrLang]] = []

    class FakeEngine:
        name = "fake"

        def recognize(self, image: Image3, lang: OcrLang) -> list[OcrBox]:
            seen.append((tuple(image.shape), int(image[0, 0, 2]), lang))
            return [_box("الأجر", (0, 0, 50, 20)), _box(" ", (60, 0, 70, 20))]

    monkeypatch.setitem(sys.modules, "paddleocr", SimpleNamespace(TextRecognition=FakeTextRecognition))
    monkeypatch.setattr(ocr, "default_engine", FakeEngine)
    _line_images(tmp_path, ["0001"], size=(80, 30), color=(255, 0, 0))  # rouge en RGB
    image = tmp_path / "lignes" / "ligne_0001.png"

    recognize, detect = evaluer.production_models()
    assert created == [{"model_name": "arabic_PP-OCRv5_mobile_rec", "device": "cpu", "enable_mkldnn": False}]
    assert recognize([image]) == ["الأجر"] and predicted == [([str(image)], 1)]  # reconnaissance seule, ligne entière
    boxes = detect([image])
    assert seen == [((30, 80, 3), 255, "ar")]  # image BGR (rouge dans le 3e canal), langue « auto » : arabe d'abord
    assert [b.text for b in boxes[0]] == ["الأجر"]  # boîtes nettoyées comme en production


def test_experiment_models_lift_the_width_cap_and_share_the_networks(tmp_path: Path,
                                                                    monkeypatch: pytest.MonkeyPatch) -> None:
    """Faux modules `model` et `paddle` : vérifie le plafond de 3200 px et le partage des réseaux."""
    from types import SimpleNamespace

    import numpy as np

    evaluer = _load("evaluer_cer_reel")
    built: list[object] = []
    widths_seen: list[int] = []
    loaded: list[str] = []

    class Net:
        def __init__(self) -> None:
            self.state: object = None

        def set_state_dict(self, state: object) -> None:
            self.state = state

    fake_model = SimpleNamespace(MAX_W=640, DICT_REL=Path("dict.txt"), Charset=lambda path: "charset")

    def build(root: Path, weights: Path, charset: object) -> Net:
        net = Net()
        built.append(net)
        return net

    def preprocess(gray: object) -> object:
        widths_seen.append(fake_model.MAX_W)
        return gray

    def predict(net: Net, images: list[object], charset: object) -> list[str]:
        return [f"lu {'ft' if net.state else 'pre'}" for _ in images]

    fake_model.build, fake_model.preprocess, fake_model.predict = build, preprocess, predict
    fake_model.read_gray = lambda path: np.zeros((48, 100), dtype=np.uint8)
    monkeypatch.setitem(sys.modules, "model", fake_model)
    def load(weights: str) -> dict[str, int]:
        loaded.append(weights)
        return {"w": 1}

    monkeypatch.setitem(sys.modules, "paddle", SimpleNamespace(load=load))

    lines, pieces = evaluer.experiment_models(tmp_path / "ft.pdparams")
    assert fake_model.MAX_W == 3200  # plafond relevé avant toute lecture
    assert set(lines) == set(pieces) == {"pre_entraine", "fine_tune"} and len(built) == 2  # chargés une fois
    assert lines["pre_entraine"]([tmp_path / "a.png", tmp_path / "b.png"]) == ["lu pre", "lu pre"]
    assert pieces["fine_tune"]([np.zeros((20, 30), dtype=np.uint8)]) == ["lu ft"]
    assert widths_seen and set(widths_seen) == {3200} and loaded == [str(tmp_path / "ft.pdparams")]
    lines_only, _ = evaluer.experiment_models(None)
    assert set(lines_only) == {"pre_entraine"}
