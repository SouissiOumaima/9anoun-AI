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

pytest.importorskip("numpy")
pytest.importorskip("PIL")

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
    # 1 entrée {page, text} pour 2 pages : normal (page sans contenu), plus signalé comme anomalie
    assert convs["conv_b"].problems == [] and convs["conv_b"].association == "explicite"
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
    assert pages[("conv_b", 2)]["probleme"] == "pas de texte Tradrly"
    assert pages[("conv_c", 1)]["probleme"] == "PDF indisponible"
    assert pages[("inconnue", 1)]["probleme"] == "convention inconnue"
    assert pages[("conv_a", 9)]["probleme"] == "page hors du PDF (1 à 3)"
    summary = report["resume"]
    assert (summary["pages_demandees"], summary["pages_controlees"]) == (6, 2)
    assert summary["pages_a_relire"][0] == {"convention": "conv_a", "page": 3, "cer": pages[("conv_a", 3)]["cer"],
                                            "cer_lettres": 0.0, "cer_souple": pages[("conv_a", 3)]["cer"],
                                            "rappel_mots": 0.5}
    assert {c["convention"] for c in summary["conventions_signalees"]} == {"conv_c", "casse"}


def test_cer_median_averages_the_two_middle_pages_when_the_count_is_even(archive: tuple[Path, Path]) -> None:
    """Nombre pair de pages contrôlées : médiane = moyenne des deux valeurs du milieu (statistics.median)."""
    script = _load()
    even = script.run(*archive, [("conv_a", 1), ("conv_a", 3)], n=None, seed=42, strata=None, lang="ar",
                      engine=PageTextEngine([f"الفصل الأول {SECRET} 123", "Annexe 8"]))
    cers = sorted(p["cer"] for p in even["pages"])
    assert cers == [0.0, round(1 / len("Annexe 3"), 4)]
    assert even["resume"]["cer_median"] == round((cers[0] + cers[1]) / 2, 4) == 0.0625  # pas 0.125 (haute)

    odd = script.run(*archive, [("conv_a", 1), ("conv_a", 2), ("conv_a", 3)], n=None, seed=42, strata=None,
                     lang="ar", engine=PageTextEngine([f"الفصل الأول {SECRET} 123", "x", "Annexe 8"]))
    odd_cers = sorted(p["cer"] for p in odd["pages"])
    assert odd["resume"]["cer_median"] == odd_cers[1]  # impair : la valeur du milieu, inchangé


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


# ------------------------------------------------------------ forme réelle de l'archive (décrite sans texte)


@pytest.fixture()
def real_shape_archive(tmp_path: Path) -> tuple[Path, Path]:
    """Forme décrite pour l'archive : pages_content = liste d'objets {page, page_type, text} (dans le désordre ici),
    content_pages = {from, to, included, excluded_salary_pages}. PDF de 6 pages : 1-4 avec texte, 5-6 exclues."""
    json_dir, pdf_dir = tmp_path / "json", tmp_path / "pdf"
    json_dir.mkdir()
    pdf_dir.mkdir()
    _pdf(pdf_dir / "conv_reelle.pdf", 6)
    texts = {1: "الفصل الأول", 2: "الفصل الثاني", 3: f"الفصل الثالث {SECRET}", 4: "الفصل الرابع"}
    data = {
        "source_file": "conv_reelle.pdf", "pages": 6,
        "content_pages": {"from": 1, "to": 4, "included": [1, 2, 3, 4], "excluded_salary_pages": [5, 6]},
        "pages_content": [{"page": p, "page_type": "articles" if p < 4 else "annexe", "text": texts[p]}
                          for p in (3, 1, 4, 2)],  # ordre volontairement différent des numéros de page
        "articles": [], "annexes": [],
    }
    (json_dir / "conv_reelle.json").write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    # même archive sans numéro de page ni content_pages exploitable : association par position incertaine
    flat = {"source_file": "conv_reelle.pdf", "pages": 6, "pages_content": ["a", "b", "c"]}
    (json_dir / "conv_position.json").write_text(json.dumps(flat), encoding="utf-8")
    # liste de textes + content_pages en liste de même longueur : association par content_pages
    listed = {"source_file": "conv_reelle.pdf", "pages": 6, "content_pages": [2, 5], "pages_content": ["x", "y"]}
    (json_dir / "conv_liste.json").write_text(json.dumps(listed), encoding="utf-8")
    return json_dir, pdf_dir


def test_text_is_matched_by_the_page_key_never_by_list_position(real_shape_archive: tuple[Path, Path]) -> None:
    script = _load()
    convs = {c.name: c for c in script.load_archive(*real_shape_archive)}
    real = convs["conv_reelle"]
    assert real.association == "explicite"
    assert real.pages_text[1] == "الفصل الأول" and real.pages_text[3].startswith("الفصل الثالث")
    assert real.excluded_pages == {5, 6}
    assert real.page_types == {1: "articles", 2: "articles", 3: "articles", 4: "annexe"}
    assert real.problems == []  # 4 entrées pour 6 pages : normal, pas une anomalie
    listed = convs["conv_liste"]
    assert listed.association == "content_pages" and listed.pages_text == {2: "x", 5: "y"}
    position = convs["conv_position"]
    assert position.association == "position" and position.association_incertaine
    assert any("association page ↔ texte incertaine" in p for p in position.problems)


def test_excluded_and_textless_pages_are_never_scored_nor_sampled(real_shape_archive: tuple[Path, Path]) -> None:
    script = _load()
    engine = PageTextEngine(["الفصل الأول", f"الفصل الثالث {SECRET}"])
    selection = [("conv_reelle", 1), ("conv_reelle", 5), ("conv_reelle", 3), ("conv_position", 1)]
    report = script.run(*real_shape_archive, selection, n=None, seed=1, strata=None, lang="ar", engine=engine)
    pages = {(p["convention"], p["page"]): p for p in report["pages"]}
    assert pages[("conv_reelle", 1)]["cer"] == 0.0 and pages[("conv_reelle", 1)]["page_type"] == "articles"
    assert pages[("conv_reelle", 3)]["cer"] == 0.0  # le bon texte (clé page = 3), pas le 3e de la liste
    assert pages[("conv_reelle", 5)]["probleme"] == "page exclue par Tradrly" and "cer" not in pages[("conv_reelle", 5)]
    assert pages[("conv_position", 1)]["probleme"].startswith("association page ↔ texte incertaine")
    assert engine.calls == ["ar", "ar"]  # ni la page exclue ni l'association incertaine ne passent à l'OCR
    assert report["resume"]["pages_controlees"] == 2 and report["resume"]["cer_global_pondere"] == 0.0

    convs = script.load_archive(*real_shape_archive)
    drawn = script.sample_pages(convs, 100, 3)
    assert ("conv_reelle", 5) not in drawn and ("conv_reelle", 6) not in drawn
    assert {p for name, p in drawn if name == "conv_reelle"} == {1, 2, 3, 4}
    assert all(name != "conv_position" for name, _ in drawn)  # association incertaine : jamais tirée
    assert ("conv_liste", 2) in drawn


def test_page_type_is_shown_but_never_page_text(real_shape_archive: tuple[Path, Path], tmp_path: Path,
                                                capsys: pytest.CaptureFixture[str]) -> None:
    script = _load()
    out = tmp_path / "s"
    assert script.main([str(real_shape_archive[0]), str(real_shape_archive[1]), "--out", str(out), "--pages",
                        "conv_reelle:3,conv_reelle:6"], engine=PageTextEngine([f"الفصل الثالث {SECRET}"])) == 0
    printed = capsys.readouterr().out
    raw = (out / "controle_tradrly.json").read_text(encoding="utf-8")
    assert "page_type : articles" in printed and "page exclue par Tradrly" in printed
    assert "exclues par Tradrly" in printed  # résumé par convention : pages exclues comptées
    for forbidden in (SECRET, "الفصل"):
        assert forbidden not in printed and forbidden not in raw


def test_structure_option_shows_shape_without_text(real_shape_archive: tuple[Path, Path],
                                                    capsys: pytest.CaptureFixture[str]) -> None:
    script = _load()
    assert script.main([str(real_shape_archive[0]), str(real_shape_archive[1]), "--structure"],
                       engine=PageTextEngine([])) == 0
    printed = capsys.readouterr().out
    assert '"cles_elements": ["page", "page_type", "text"]' in printed
    assert '"content_pages_cles": ["excluded_salary_pages", "from", "included", "to"]' in printed
    assert '"pages_exclues": [5, 6]' in printed
    assert SECRET not in printed and "الفصل" not in printed


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


# ------------------------------------------------------------ formes de présentation et CER souple (#49, Hadil)

# « الفصل » écrit en formes de présentation B : alef isolé, lam initial, feh médian, sad médian, lam final
PRESENTATION_FASL = "ﺍﻟﻔﺼﻞ"


def test_presentation_forms_become_base_letters() -> None:
    script = _load()
    assert script.normalize(PRESENTATION_FASL) == "الفصل"
    assert script.normalize("ﻻ ﻷ") == "لا لأ"  # ligatures lam-alef (forme B)
    assert script.normalize("ﷲ") == "الله"  # ligature (forme A)
    assert script.normalize("ﮎﮑ") == "کک"  # keheh (forme A) : lettre de base ک
    assert script.normalize("كﹶتب") == "كتب"  # voyelle isolée : ni espace ajouté, ni mot coupé
    assert script.normalize("﻿الأجر") == "الأجر"  # U+FEFF invisible supprimé
    assert script.page_scores("الفصل الأول", f"{PRESENTATION_FASL} ﺍﻷﻮﻝ")["cer"] == 0.0


def test_presentation_forms_keep_digits_and_leave_other_characters_alone() -> None:
    script = _load()
    assert script.normalize(f"{PRESENTATION_FASL} ١٢٣ ۴٥") == "الفصل 123 45"  # chiffres arabes-indiens et persans
    assert script.normalize("ﻻ ٣٠") == "لا 30"  # ligature puis chiffres arabes-indiens
    # seules les formes de présentation passent par NFKC : pas de NFKC sur le reste du texte
    assert script.normalize("x² ﬁn ½") == "x² ﬁn ½"
    assert script.normalize("الأجـــر  الأَسَاسِيّ\n١٢٣٫۴") == "الأجر الأساسي 123٫4"  # comportement d'avant


def test_soft_cer_ignores_common_spelling_variants_only() -> None:
    script = _load()
    assert script.soft_normalize("أإآ ى ة") == "ااا ي ه"
    variants = script.page_scores("الأجر الأساسي إلى آخر المؤسسة", "الاجر الاساسي الي اخر المؤسسه")
    assert variants["cer"] > 0 and variants["cer_souple"] == 0.0 and variants["erreurs_caracteres_souple"] == 0
    real = script.page_scores("الأجر الأساسي", "الأمر الأساسي")  # vraie erreur de lettre : pas cachée
    assert real["cer_souple"] == real["cer"] > 0
    both = script.page_scores("المؤسسة", "الموسسه")  # ؤ → و n'est pas une variante retenue
    assert both["cer_souple"] == round(1 / len("المؤسسة"), 4) < both["cer"]
    for ref, hyp in (("إلى", "الى"), ("abc", "abd"), ("", "")):  # même longueur : même dénominateur que le CER
        assert len(script.soft_normalize(ref)) == len(script.normalize(ref))
        assert script.page_scores(ref, hyp)["caracteres_reference"] == len(script.soft_normalize(ref))
    assert script.page_scores("", "")["cer_souple"] == 0.0 and script.page_scores("", "ة")["cer_souple"] == 1.0


def test_soft_cer_is_shown_and_saved_as_numbers_only(archive: tuple[Path, Path], tmp_path: Path,
                                                     capsys: pytest.CaptureFixture[str]) -> None:
    script = _load()
    out = tmp_path / "sortie"
    engine = PageTextEngine([f"{PRESENTATION_FASL} الاول {SECRET} ١٢٣",  # formes de présentation + hamza omise
                             "الفصل الثاني : الاجر الاساسي",  # hamzas omises : CER souple nul
                             "Annexe 3"])
    assert script.main([str(archive[0]), str(archive[1]), "--out", str(out), "--pages",
                        "conv_a:1,conv_a:2,conv_a:3"], engine=engine) == 0
    printed = capsys.readouterr().out
    raw = (out / "controle_tradrly.json").read_text(encoding="utf-8")
    report = json.loads(raw)

    pages = {p["page"]: p for p in report["pages"]}
    assert pages[1]["cer"] > 0 and pages[1]["cer_souple"] == 0.0  # seule la hamza diffère
    assert pages[2]["cer"] > 0 and pages[2]["cer_souple"] == 0.0
    assert pages[3]["cer_souple"] == pages[3]["cer"] == 0.0
    resume = report["resume"]
    assert resume["cer_souple_global_pondere"] == 0.0 < resume["cer_global_pondere"]
    to_review = resume["pages_a_relire"]
    # une liste vide ferait passer la boucle sans rien vérifier : les 3 pages contrôlées doivent y être (--top 10)
    assert resume["pages_controlees"] == 3 and len(to_review) == 3
    assert sorted(p["page"] for p in to_review) == [1, 2, 3]
    assert all("cer_souple" in p for p in to_review)
    assert all(p["cer_souple"] == pages[p["page"]]["cer_souple"] for p in to_review)  # même valeur que par page
    assert "cer_souple_global_pondere" in printed and "CER souple" in printed

    for forbidden in (SECRET, "الفصل", "الاول", "الأول", "الاجر", "الأجر", "الاساسي", "Annexe", PRESENTATION_FASL,
                      "ﺍ", "ﻞ", ".pdf"):
        assert forbidden not in printed, forbidden
        assert forbidden not in raw, forbidden
