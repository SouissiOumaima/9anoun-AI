"""Tests de `scripts/annoter_lignes.py` et `scripts/evaluer_cer_reel.py` sur des documents FICTIFS.

Faux moteur d'OCR et faux lecteurs de lignes : aucun modèle chargé, aucune donnée réelle. On vérifie surtout
qu'aucun texte lu ni aucun nom de fichier n'est affiché.
"""

from __future__ import annotations

import csv
import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType

import pymupdf
import pytest

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
    first, second, other = (_read_csv(tmp_path / o / "annotation.csv") for o in ("o1", "o2", "o3"))
    key = [(r["document"], r["page"], r["lecture_ocr"]) for r in first]
    assert key == [(r["document"], r["page"], r["lecture_ocr"]) for r in second]
    assert key != [(r["document"], r["page"], r["lecture_ocr"]) for r in other]


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


def _annotated_csv(folder: Path) -> Path:
    """CSV fictif déjà annoté : 2 lignes FR, 2 AR, 1 mixte, 1 illisible, 1 non annotée."""
    folder.mkdir(parents=True, exist_ok=True)
    rows = [
        ("0001", "Salaire de base 424.100", "Salaire de base 424.100"),
        ("0002", "Prime de transport 56.000", "Prime de transport 56,000"),
        ("0003", "الأجر الأساسي", "الأجر الأساسي"),
        ("0004", "الصنف", "الصنف 3"),
        ("0005", "Catégorie الصنف", "Catégorie 3 الصنف"),
        ("0006", "???", "#ILLISIBLE"),
        ("0007", "Net à payer", ""),
    ]
    path = folder / "annotation.csv"
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.writer(handle, delimiter=";")
        writer.writerow(["id", "image", "document", "page", "langue_ocr", "confiance", "lecture_ocr", "texte_correct"])
        for i, lecture, correct in rows:
            writer.writerow([i, f"lignes/ligne_{i}.png", "doc_001", 1, "fr", "0.9", lecture, correct])
    return path


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
    assert results["fine_tune"]["global"] == {"n": 5, "cer": 0.0, "wer": 0.0, "lignes_exactes": 1.0}


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
    assert evaluer.main([str(csv_path)]) == 0
    assert "expérience non préparée" in capsys.readouterr().out
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
    assert evaluer.find_finetuned_weights(build) == build / "state" / "complet" / evaluer.FT_FILE
    assert evaluer.find_finetuned_weights(tmp_path / "rien") is None
