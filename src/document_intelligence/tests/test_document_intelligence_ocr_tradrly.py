"""Tests de `scripts/controler_transcription_tradrly.py` avec une archive FICTIVE (faux JSON, faux PDF, faux OCR).

Aucun modèle chargé, aucune donnée réelle. Un test vérifie qu'aucun texte de page n'apparaît dans la sortie.
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

SCRIPT = Path(__file__).resolve().parents[3] / "scripts" / "controler_transcription_tradrly.py"
SECRET = "SECRET"


def _load() -> ModuleType:
    spec = importlib.util.spec_from_file_location("controler_transcription_tradrly", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module  # nécessaire aux dataclasses du script
    spec.loader.exec_module(module)
    return module


class PageTextEngine:
    """Faux OCR : renvoie, pour chaque appel, le texte suivant de la liste (une boîte par ligne)."""

    name = "fake"

    def __init__(self, pages: list[str]) -> None:
        self.pages = list(pages)
        self.calls: list[OcrLang] = []

    def recognize(self, image: Image3, lang: OcrLang) -> list[OcrBox]:
        self.calls.append(lang)
        text = self.pages.pop(0) if self.pages else ""
        return [OcrBox(line, 0.9, (10.0, 10.0 + 40 * i, 900.0, 40.0 + 40 * i))
                for i, line in enumerate(text.split("\n")) if line]


def _pdf(path: Path, pages: int) -> None:
    doc = pymupdf.open()
    for i in range(pages):
        doc.new_page().insert_text((72, 72), f"page fictive {i + 1}", fontsize=12)
    doc.save(path)
    doc.close()


@pytest.fixture()
def archive(tmp_path: Path) -> tuple[Path, Path]:
    """Archive fictive : 3 conventions correctes ou cassées, avec leurs .verification.json."""
    json_dir, pdf_dir = tmp_path / "json", tmp_path / "pdf"
    json_dir.mkdir()
    pdf_dir.mkdir()
    _pdf(pdf_dir / "conv_a.pdf", 3)
    _pdf(pdf_dir / "conv_b.pdf", 2)
    docs = {
        # liste de textes, une entrée par page
        "conv_a": {"source_file": "conv_a.pdf", "pages": 3,
                   "pages_content": [f"الفصل الأول {SECRET} ١٢٣", "الفصل الثاني : الأجر الأساسي", "Annexe 3"]},
        # objets {page, text} avec une page manquante
        "conv_b": {"source_file": "C:/autre/chemin/conv_b.pdf", "pages": 2,
                   "pages_content": [{"page": 1, "text": "منحة النقل 56,000"}]},
        # PDF absent
        "conv_c": {"source_file": "introuvable.pdf", "pages": 1, "pages_content": {"1": "texte"}},
    }
    for name, data in docs.items():
        (json_dir / f"{name}.json").write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        (json_dir / f"{name}.verification.json").write_text("{}", encoding="utf-8")
    (json_dir / "casse.json").write_text("{pas du json", encoding="utf-8")
    return json_dir, pdf_dir


# ------------------------------------------------------------ normalisation et métriques


def test_normalize_removes_tatweel_harakat_and_unifies_digits() -> None:
    script = _load()
    assert script.normalize("الأجـــر  الأَسَاسِيّ\n١٢٣٫۴") == "الأجر الأساسي 123٫4"
    assert script.normalize("e\u0301té") == "été"  # NFC
    assert script.normalize("  a \t b  ") == "a b"


def test_page_scores_cer_wer_and_order_independent_recall() -> None:
    script = _load()
    perfect = script.page_scores("الفصل الأول", "الفَصْل   الأوّل")
    assert perfect["cer"] == 0.0 and perfect["wer"] == 0.0 and perfect["rappel_mots"] == 1.0
    swapped = script.page_scores("un deux trois", "trois deux un")  # mêmes mots, ordre différent
    assert swapped["cer"] > 0 and swapped["rappel_mots"] == 1.0
    one = script.page_scores("abcd", "abed")
    assert one["cer"] == 0.25 and one["erreurs_caracteres"] == 1 and one["caracteres_reference"] == 4
    assert script.page_scores("", "")["cer"] == 0.0 and script.page_scores("", "x")["cer"] == 1.0


def test_cer_on_letters_separates_lost_digits_from_real_differences() -> None:
    """Défaut connu de notre modèle arabe : « الفصل 1 : » lu « الفصل ». Ce n'est pas une erreur de Tradrly."""
    script = _load()
    lost_digits = script.page_scores("الفصل 1 : تنطبق الاتفاقية", "الفصل تنطبق الاتفاقية")
    assert lost_digits["cer"] > 0 and lost_digits["cer_lettres"] == 0.0
    real_gap = script.page_scores("الفصل 1 : تنطبق الاتفاقية", "الفصل 1 : تطبق الاتفاقيه")
    assert real_gap["cer_lettres"] > 0
    assert script.letters_only("Art. 12 – الأجر، ٣") == "Art الأجر"


def test_python_edit_distance_matches_rapidfuzz() -> None:
    script = _load()
    for a, b in (("kitten", "sitting"), ("", "abc"), ("الأجر", "الاجر"), (["a", "b"], ["b"])):
        assert script._edit_distance_py(a, b) == script.edit_distance(a, b)


# ------------------------------------------------------------ archive et choix des pages


def test_archive_problems_are_reported_without_crashing(archive: tuple[Path, Path]) -> None:
    script = _load()
    convs = {c.name: c for c in script.load_archive(*archive)}
    assert set(convs) == {"conv_a", "conv_b", "conv_c", "casse"}  # les .verification.json sont ignorés
    assert convs["conv_a"].problems == [] and convs["conv_a"].pdf_pages == 3
    assert convs["conv_b"].pdf is not None  # retrouvé par son nom dans le dossier des PDF
    assert convs["conv_b"].problems == ["pages_content : 1 entrées pour 2 pages"]
    assert "source_file introuvable dans le dossier des PDF" in convs["conv_c"].problems
    assert convs["casse"].problems == ["JSON illisible"]


def test_parse_pages_and_bad_specs() -> None:
    script = _load()
    assert script.parse_pages("conv_a:3, conv_b:1 ,") == [("conv_a", 3), ("conv_b", 1)]
    assert script.parse_pages("nom:avec:deux:2") == [("nom:avec:deux", 2)]
    for bad in ("conv_a", "conv_a:0", ":3", "conv_a:x", " , "):
        with pytest.raises(script.SelectionError):
            script.parse_pages(bad)


def test_sampling_is_reproducible_and_strata_split_evenly(archive: tuple[Path, Path]) -> None:
    script = _load()
    convs = script.load_archive(*archive)
    first = script.sample_pages(convs, 3, 7)
    assert first == script.sample_pages(convs, 3, 7) and len(first) == 3
    assert all(name in {"conv_a", "conv_b"} for name, _ in first)  # conv_c (PDF absent) jamais tirée
    assert script.sample_pages(convs, 100, 1) == [("conv_a", 1), ("conv_a", 2), ("conv_a", 3), ("conv_b", 1)]
    strata = script.sample_pages(convs, 2, 3, ["conv_a", "conv_b"])
    assert sorted(name for name, _ in strata) == ["conv_a", "conv_b"]
    with pytest.raises(script.SelectionError):
        script.sample_pages(convs, 2, 3, ["inconnue"])


# ------------------------------------------------------------ contrôle et sortie


def test_run_scores_pages_and_flags_unusable_ones(archive: tuple[Path, Path]) -> None:
    script = _load()
    engine = PageTextEngine([f"الفصل الأول {SECRET} 123", "Annexe 8"])
    selection = [("conv_a", 1), ("conv_a", 3), ("conv_b", 2), ("conv_c", 1), ("inconnue", 1), ("conv_a", 9)]
    report = script.run(*archive, selection, n=None, seed=42, strata=None, lang="ar", engine=engine)

    assert engine.calls == ["ar", "ar"]  # seulement les 2 pages contrôlables, modèle arabe
    pages = {(p["convention"], p["page"]): p for p in report["pages"]}
    assert pages[("conv_a", 1)]["cer"] == 0.0  # ١٢٣ et 123 : mêmes chiffres après normalisation
    assert pages[("conv_a", 3)]["cer"] == round(1 / len("Annexe 3"), 4)
    assert pages[("conv_b", 2)]["probleme"] == "page absente de pages_content"
    assert pages[("conv_c", 1)]["probleme"] == "PDF indisponible"
    assert pages[("inconnue", 1)]["probleme"] == "convention inconnue"
    assert pages[("conv_a", 9)]["probleme"] == "page hors du PDF (1 à 3)"
    summary = report["resume"]
    assert (summary["pages_demandees"], summary["pages_controlees"]) == (6, 2)
    assert summary["pages_a_relire"][0] == {"convention": "conv_a", "page": 3, "cer": pages[("conv_a", 3)]["cer"],
                                            "cer_lettres": 0.0, "rappel_mots": 0.5}
    assert {c["convention"] for c in summary["conventions_signalees"]} == {"conv_b", "conv_c", "casse"}


def test_output_contains_numbers_only_never_page_text(archive: tuple[Path, Path], tmp_path: Path,
                                                     capsys: pytest.CaptureFixture[str]) -> None:
    script = _load()
    out = tmp_path / "sortie"
    engine = PageTextEngine([f"الفصل الأول {SECRET} 123", "الفصل الثاني : الأجر", "Annexe 3"])
    code = script.main([str(archive[0]), str(archive[1]), "--out", str(out), "--pages",
                        "conv_a:1,conv_a:2,conv_a:3", "--profile"], engine=engine)
    assert code == 0
    printed = capsys.readouterr().out
    raw = (out / "controle_tradrly.json").read_text(encoding="utf-8")
    for forbidden in (SECRET, "الفصل", "الأجر", "Annexe", "منحة", ".pdf", "C:/autre", "page fictive"):
        assert forbidden not in printed, forbidden
        assert forbidden not in raw, forbidden
    assert "rendu" in printed and "OCR" in printed  # --profile : temps par page
    report = json.loads(raw)
    assert report["resume"]["pages_controlees"] == 3
    assert all("durees_s" in p for p in report["pages"])


def test_main_sampling_mode_and_argument_errors(archive: tuple[Path, Path], tmp_path: Path,
                                                capsys: pytest.CaptureFixture[str]) -> None:
    script = _load()
    out = tmp_path / "o"
    assert script.main([str(archive[0]), str(archive[1]), "--out", str(out), "--echantillon", "2", "--seed", "5",
                        "--strate", "conv_a,conv_b"], engine=PageTextEngine(["x", "y"])) == 0
    report = json.loads((out / "controle_tradrly.json").read_text(encoding="utf-8"))
    assert report["parametres"]["strates"] == ["conv_a", "conv_b"] and len(report["pages"]) == 2

    base = [str(archive[0]), str(archive[1])]
    inside = str(SCRIPT.parents[1] / "build" / "controle")
    assert script.main([*base, "--out", inside, "--pages", "conv_a:1"], engine=PageTextEngine([])) == 2
    assert not Path(inside).exists()
    assert script.main([*base, "--out", str(out), "--pages", "conv_a:0"], engine=PageTextEngine([])) == 2
    assert script.main([*base, "--out", str(out), "--echantillon", "0"], engine=PageTextEngine([])) == 2
    assert script.main([*base, "--out", str(out), "--echantillon", "1", "--strate", "zzz"],
                       engine=PageTextEngine([])) == 2
    assert script.main([str(tmp_path / "absent"), str(archive[1]), "--out", str(out), "--pages", "a:1"],
                       engine=PageTextEngine([])) == 2
    assert "Erreur" in capsys.readouterr().out
    with pytest.raises(SystemExit):  # --pages et --echantillon ensemble : refusé par argparse
        script.main([*base, "--out", str(out), "--pages", "a:1", "--echantillon", "2"], engine=PageTextEngine([]))
