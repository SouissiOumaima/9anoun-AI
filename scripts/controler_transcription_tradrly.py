"""Contrôle indépendant de la transcription Tradrly par notre OCR, SANS afficher le contenu des documents.

À lancer par la personne qui détient l'archive (elle reste en dehors du dépôt) :

    .venv\\Scripts\\python scripts/controler_transcription_tradrly.py "<dossier json>" "<dossier des PDF>" \\
        --out "<dossier hors dépôt>" --pages "convention_a:3,convention_b:12"

Pour chaque page retenue :
1. rend l'image de la page du PDF indiqué par `source_file` (300 DPI) ;
2. la lit avec notre OCR (PaddleOCR PP-OCRv5, modèle arabe par défaut) ;
3. prend le texte Tradrly de la même page dans `pages_content` ;
4. normalise les deux textes (NFC, tatweel, voyelles et signes coraniques, chiffres arabes-indiens et persans en
   chiffres ASCII, espaces) et calcule le CER et le WER, avec le texte Tradrly comme référence.

Choix des pages : `--pages "<nom>:<page>,..."` (liste explicite, numéros de page à partir de 1), ou
`--echantillon N --seed S` (tirage reproductible ; avec `--strate "<nom1>,<nom2>"`, le tirage est réparti à parts
égales entre ces conventions seulement).

Contrôles de l'archive : `source_file` introuvable, `pages_content` absent, illisible ou sans une entrée par page,
page demandée hors limites : la convention ou la page est signalée, le script continue.

Sortie : `controle_tradrly.json` dans `--out` (refusé s'il est dans le dépôt) et un résumé à l'écran. **Seulement des
chiffres** : nom court de la convention (nom du fichier JSON sans extension), page, CER, WER, nombres de caractères
et de mots, et la liste des pages les plus divergentes à relire sur l'image. Jamais le texte d'une page.

Limite à connaître : le CER d'une page entière dépend aussi de l'ordre des lignes (colonnes, tableaux, en-têtes).
`rappel_mots` (part des mots Tradrly retrouvés par l'OCR, quel que soit leur ordre) aide à distinguer un problème
d'ordre (CER élevé, rappel élevé) d'un vrai écart de texte (les deux mauvais). `cer_lettres` (CER sans chiffres ni
ponctuation) sépare le défaut connu de notre modèle arabe, qui perd souvent les chiffres et la ponctuation dans les
lignes arabes (« الفصل 1 : » lu « الفصل »), d'un écart de transcription : CER élevé et CER lettres bas = surtout des
chiffres ou de la ponctuation perdus par notre OCR, pas une erreur de Tradrly.
"""

from __future__ import annotations

import argparse
import json
import random
import re
import sys
import time
import unicodedata
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Final

REPO_ROOT: Final = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import numpy as np
import pymupdf

from src.document_intelligence.reading import ocr
from src.document_intelligence.reading.ocr import Image3, LangOption, OcrEngine

OUTPUT_NAME: Final = "controle_tradrly.json"
RENDER_DPI: Final = 300
TOP_TO_REVIEW: Final = 10
VERIFICATION_SUFFIX: Final = ".verification.json"

_TATWEEL: Final = "ـ"
_HARAKAT: Final = re.compile("[ؐ-ًؚ-ٰٟۖ-ۭ]")
_DIGITS: Final = str.maketrans("٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹", "01234567890123456789")


# ---------------------------------------------------------------- normalisation et métriques


def normalize(text: str) -> str:
    """NFC, sans tatweel ni voyelles / signes coraniques, chiffres en ASCII, espaces fusionnés."""
    text = unicodedata.normalize("NFC", text)
    text = text.replace(_TATWEEL, "")
    text = _HARAKAT.sub("", text)
    text = text.translate(_DIGITS)
    return " ".join(text.split())


def letters_only(text: str) -> str:
    """Texte normalisé sans chiffres ni ponctuation : sert à `cer_lettres`.

    Notre modèle arabe perd souvent les chiffres et la ponctuation dans les lignes arabes (« الفصل 1 : » lu
    « الفصل ») : un CER sur les lettres seules sépare ce défaut connu de notre OCR d'un vrai écart de transcription.
    """
    kept = "".join(c for c in normalize(text) if c.isspace() or unicodedata.category(c).startswith(("L", "M")))
    return " ".join(kept.split())


def edit_distance(a: Sequence[Any], b: Sequence[Any]) -> int:
    """Distance de Levenshtein (rapidfuzz si disponible, sinon Python pur, même résultat)."""
    try:
        from rapidfuzz.distance import Levenshtein
    except ImportError:  # pragma: no cover - dépend du poste
        return _edit_distance_py(a, b)
    return int(Levenshtein.distance(a, b))


def _edit_distance_py(a: Sequence[Any], b: Sequence[Any]) -> int:
    if len(a) < len(b):
        a, b = b, a
    prev = list(range(len(b) + 1))
    for i, x in enumerate(a, 1):
        cur = [i]
        for j, y in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (x != y)))
        prev = cur
    return prev[-1]


def page_scores(reference: str, hypothesis: str) -> dict[str, float | int]:
    """CER, WER et totaux d'une page (référence = Tradrly, hypothèse = notre OCR), après normalisation."""
    ref, hyp = normalize(reference), normalize(hypothesis)
    ref_words, hyp_words = ref.split(), hyp.split()
    char_errors = edit_distance(ref, hyp)
    word_errors = edit_distance(ref_words, hyp_words)
    common = sum((Counter(ref_words) & Counter(hyp_words)).values())
    ref_letters, hyp_letters = letters_only(reference), letters_only(hypothesis)
    letter_errors = edit_distance(ref_letters, hyp_letters)
    return {
        "cer": round(char_errors / len(ref), 4) if ref else (0.0 if not hyp else 1.0),
        "cer_lettres": (round(letter_errors / len(ref_letters), 4) if ref_letters
                        else (0.0 if not hyp_letters else 1.0)),
        "wer": round(word_errors / len(ref_words), 4) if ref_words else (0.0 if not hyp_words else 1.0),
        "rappel_mots": round(common / len(ref_words), 4) if ref_words else 0.0,
        "caracteres_reference": len(ref),
        "caracteres_ocr": len(hyp),
        "mots_reference": len(ref_words),
        "mots_ocr": len(hyp_words),
        "erreurs_caracteres": char_errors,
        "erreurs_mots": word_errors,
    }


# ---------------------------------------------------------------- archive Tradrly


@dataclass
class Convention:
    name: str
    pdf: Path | None
    pages_text: dict[int, str]
    pdf_pages: int = 0
    problems: list[str] = field(default_factory=list)


def _pages_content(value: Any) -> dict[int, str] | None:
    """`pages_content` sous l'une des formes rencontrées : liste de textes (page 1 en premier), liste d'objets
    {page, text|content}, ou dictionnaire {"1": texte}. Renvoie None si la forme n'est pas reconnue."""
    if isinstance(value, list):
        if all(isinstance(v, str) for v in value):
            return {i: v for i, v in enumerate(value, start=1)}
        out: dict[int, str] = {}
        for k, item in enumerate(value, start=1):
            if not isinstance(item, dict):
                return None
            number = str(item.get("page", item.get("page_number", item.get("numero", k))))
            text = item.get("text", item.get("content", item.get("texte")))
            if not isinstance(text, str) or not number.isdigit():
                return None
            out[int(number)] = text
        return out
    if isinstance(value, dict) and all(str(k).isdigit() and isinstance(v, str) for k, v in value.items()):
        return {int(k): v for k, v in value.items()}
    return None


def _resolve_pdf(source: Any, pdf_dir: Path) -> Path | None:
    if not isinstance(source, str) or not source.strip():
        return None
    for candidate in (Path(source), pdf_dir / source, pdf_dir / Path(source.replace("\\", "/")).name):
        if candidate.is_file():
            return candidate
    return None


def load_archive(json_dir: Path, pdf_dir: Path) -> list[Convention]:
    """Lit chaque `<nom>.json` (pas les `.verification.json`) et vérifie la cohérence avec son PDF."""
    conventions: list[Convention] = []
    for path in sorted(json_dir.glob("*.json")):
        if path.name.endswith(VERIFICATION_SUFFIX):
            continue
        name = path.stem
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            conventions.append(Convention(name, None, {}, problems=["JSON illisible"]))
            continue
        if not isinstance(data, dict):
            conventions.append(Convention(name, None, {}, problems=["JSON sans objet principal"]))
            continue
        conv = Convention(name, _resolve_pdf(data.get("source_file"), pdf_dir), {})
        pages = _pages_content(data.get("pages_content"))
        if pages is None:
            conv.problems.append("pages_content absent ou de forme non reconnue")
        else:
            conv.pages_text = pages
        if conv.pdf is None:
            conv.problems.append("source_file introuvable dans le dossier des PDF")
        else:
            try:
                with pymupdf.open(conv.pdf) as doc:
                    conv.pdf_pages = doc.page_count
            except Exception:  # noqa: BLE001 — un PDF cassé est signalé, pas fatal
                conv.problems.append("PDF illisible")
                conv.pdf = None
        declared = data.get("pages")
        expected = conv.pdf_pages or (declared if isinstance(declared, int) else 0)
        if pages is not None and expected and set(pages) != set(range(1, expected + 1)):
            conv.problems.append(f"pages_content : {len(pages)} entrées pour {expected} pages")
        if isinstance(declared, int) and conv.pdf_pages and declared != conv.pdf_pages:
            conv.problems.append(f"pages déclarées {declared}, PDF de {conv.pdf_pages} pages")
        conventions.append(conv)
    return conventions


# ---------------------------------------------------------------- choix des pages


class SelectionError(ValueError):
    """Liste de pages ou paramètres d'échantillonnage invalides."""


def parse_pages(spec: str) -> list[tuple[str, int]]:
    """`"nom:3,autre:12"` -> [("nom", 3), ("autre", 12)] ; le nom peut contenir « : » (on coupe au dernier)."""
    out: list[tuple[str, int]] = []
    for item in (part.strip() for part in spec.split(",")):
        if not item:
            continue
        name, sep, number = item.rpartition(":")
        if not sep or not name.strip() or not number.strip().isdigit() or int(number) < 1:
            raise SelectionError(f"élément de --pages invalide : « {item} » (attendu nom:page, page >= 1)")
        out.append((name.strip(), int(number)))
    if not out:
        raise SelectionError("--pages est vide")
    return out


def _usable_pages(conv: Convention) -> list[int]:
    if conv.pdf is None:
        return []
    return [p for p in sorted(conv.pages_text) if 1 <= p <= conv.pdf_pages]


def sample_pages(conventions: list[Convention], n: int, seed: int,
                 strata: list[str] | None = None) -> list[tuple[str, int]]:
    """Tirage reproductible. Sans strates : tirage simple parmi toutes les pages utilisables. Avec strates : N
    réparti à parts égales entre les conventions listées (le reste aux premières)."""
    rng = random.Random(seed)
    by_name = {c.name: c for c in conventions}
    if not strata:
        population = [(c.name, p) for c in conventions for p in _usable_pages(c)]
        return sorted(rng.sample(population, min(n, len(population))))
    unknown = [s for s in strata if s not in by_name]
    if unknown:
        raise SelectionError(f"strates inconnues : {unknown}")
    chosen: list[tuple[str, int]] = []
    base, extra = divmod(n, len(strata))
    for k, name in enumerate(strata):
        pages = _usable_pages(by_name[name])
        chosen += [(name, p) for p in rng.sample(pages, min(base + (k < extra), len(pages)))]
    return sorted(chosen)


# ---------------------------------------------------------------- contrôle d'une page


def render_page(pdf: Path, page_number: int, dpi: int = RENDER_DPI) -> Image3:
    with pymupdf.open(pdf) as doc:
        pix = doc[page_number - 1].get_pixmap(dpi=dpi, colorspace=pymupdf.csRGB, alpha=False)
    rgb = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, pix.n)[:, :, :3]
    return np.ascontiguousarray(rgb[:, :, ::-1])


def ocr_page_text(engine: OcrEngine, image: Image3, lang: LangOption) -> str:
    """Texte OCR de la page, lignes dans l'ordre de lecture (droite à gauche pour l'arabe)."""
    boxes, _ = ocr.read_zone(engine, image, lang)
    return "\n".join(row.text for row in ocr.group_rows(boxes))


@dataclass
class PageResult:
    convention: str
    page: int
    scores: dict[str, float | int] | None = None
    probleme: str | None = None
    durees_s: dict[str, float] = field(default_factory=dict)


def check_page(conv: Convention | None, name: str, page: int, engine: OcrEngine, lang: LangOption) -> PageResult:
    result = PageResult(name, page)
    if conv is None:
        result.probleme = "convention inconnue"
        return result
    if conv.pdf is None:
        result.probleme = "PDF indisponible"
        return result
    if not 1 <= page <= conv.pdf_pages:
        result.probleme = f"page hors du PDF (1 à {conv.pdf_pages})"
        return result
    if page not in conv.pages_text:
        result.probleme = "page absente de pages_content"
        return result
    t0 = time.perf_counter()
    image = render_page(conv.pdf, page)
    t1 = time.perf_counter()
    hypothesis = ocr_page_text(engine, image, lang)
    t2 = time.perf_counter()
    result.scores = page_scores(conv.pages_text[page], hypothesis)
    t3 = time.perf_counter()
    result.durees_s = {"rendu": round(t1 - t0, 2), "ocr": round(t2 - t1, 2), "comparaison": round(t3 - t2, 2)}
    return result


def summarize(results: list[PageResult], conventions: list[Convention], top: int) -> dict[str, Any]:
    scored = [r for r in results if r.scores is not None]
    chars = sum(int(r.scores["caracteres_reference"]) for r in scored if r.scores)
    words = sum(int(r.scores["mots_reference"]) for r in scored if r.scores)
    char_err = sum(int(r.scores["erreurs_caracteres"]) for r in scored if r.scores)
    word_err = sum(int(r.scores["erreurs_mots"]) for r in scored if r.scores)
    cers = sorted(float(r.scores["cer"]) for r in scored if r.scores)
    worst = sorted(scored, key=lambda r: float(r.scores["cer"]) if r.scores else 0.0, reverse=True)[:top]
    return {
        "pages_demandees": len(results),
        "pages_controlees": len(scored),
        "pages_non_controlees": len(results) - len(scored),
        "cer_global_pondere": round(char_err / chars, 4) if chars else 0.0,
        "wer_global_pondere": round(word_err / words, 4) if words else 0.0,
        "cer_median": round(cers[len(cers) // 2], 4) if cers else 0.0,
        "pages_a_relire": [{"convention": r.convention, "page": r.page, "cer": r.scores["cer"],
                            "cer_lettres": r.scores["cer_lettres"], "rappel_mots": r.scores["rappel_mots"]}
                           for r in worst if r.scores],
        "conventions_signalees": [{"convention": c.name, "problemes": c.problems} for c in conventions if c.problems],
    }


# ---------------------------------------------------------------- programme


def _inside(path: Path, parent: Path) -> bool:
    try:
        path.resolve().relative_to(parent.resolve())
    except ValueError:
        return False
    return True


def run(json_dir: Path, pdf_dir: Path, selection: list[tuple[str, int]] | None, *, n: int | None, seed: int,
        strata: list[str] | None, lang: LangOption, engine: OcrEngine, top: int = TOP_TO_REVIEW,
        profile: bool = False) -> dict[str, Any]:
    conventions = load_archive(json_dir, pdf_dir)
    by_name = {c.name: c for c in conventions}
    pages = selection if selection is not None else sample_pages(conventions, n or 0, seed, strata)
    results: list[PageResult] = []
    for name, page in pages:
        result = check_page(by_name.get(name), name, page, engine, lang)
        results.append(result)
        if profile and result.durees_s:
            d = result.durees_s
            print(f"  {name} p.{page} : rendu {d['rendu']:.1f} s, OCR {d['ocr']:.1f} s, "
                  f"comparaison {d['comparaison']:.1f} s")
    report = {
        "format": "ds3.controle_tradrly.v1",
        "parametres": {"lang": lang, "seed": seed if selection is None else None, "echantillon": n,
                       "strates": strata, "dpi": RENDER_DPI},
        "resume": summarize(results, conventions, top),
        "pages": [{"convention": r.convention, "page": r.page, **(r.scores or {}),
                   **({"probleme": r.probleme} if r.probleme else {}),
                   **({"durees_s": r.durees_s} if profile and r.durees_s else {})} for r in results],
    }
    return report


def print_report(report: dict[str, Any]) -> None:
    s = report["resume"]
    print("\nRésumé (chiffres seulement) :")
    for key in ("pages_demandees", "pages_controlees", "pages_non_controlees", "cer_global_pondere",
                "wer_global_pondere", "cer_median"):
        print(f"  {key:<22} {s[key]}")
    print("\n  convention / page                         CER  CER lettres     WER   rappel  car.réf")
    for p in report["pages"]:
        label = f"{p['convention']} p.{p['page']}"
        if "cer" in p:
            print(f"  {label:<38} {p['cer']:>7.2%} {p['cer_lettres']:>12.2%} {p['wer']:>7.2%} "
                  f"{p['rappel_mots']:>7.2%} {p['caracteres_reference']:>8}")
        else:
            print(f"  {label:<38} non contrôlée : {p.get('probleme')}")
    if s["pages_a_relire"]:
        print("\nPages les plus divergentes, à relire sur l'image :")
        for p in s["pages_a_relire"]:
            print(f"  {p['convention']} p.{p['page']} : CER {p['cer']:.2%}, CER lettres {p['cer_lettres']:.2%}, "
                  f"rappel des mots {p['rappel_mots']:.2%}")
    if s["conventions_signalees"]:
        print("\nConventions signalées :")
        for c in s["conventions_signalees"]:
            print(f"  {c['convention']} : {' ; '.join(c['problemes'])}")


def main(argv: list[str] | None = None, engine: OcrEngine | None = None) -> int:
    parser = argparse.ArgumentParser(description="Contrôle de la transcription Tradrly par l'OCR (chiffres seulement).")
    parser.add_argument("json_dir", type=Path, help="Dossier json/ de l'archive Tradrly (hors dépôt).")
    parser.add_argument("pdf_dir", type=Path, help="Dossier des PDF d'origine (hors dépôt).")
    parser.add_argument("--out", type=Path, required=True, help="Dossier de sortie, EN DEHORS du dépôt.")
    choice = parser.add_mutually_exclusive_group(required=True)
    choice.add_argument("--pages", help='Liste explicite : "nom:page,nom:page" (pages à partir de 1).')
    choice.add_argument("--echantillon", type=int, help="Nombre de pages à tirer au hasard.")
    parser.add_argument("--seed", type=int, default=42, help="Graine du tirage (42 par défaut).")
    parser.add_argument("--strate", default=None, help='Conventions entre lesquelles répartir le tirage : "a,b,c".')
    parser.add_argument("--lang", choices=["ar", "fr", "auto"], default="ar", help="Langue de l'OCR (ar par défaut).")
    parser.add_argument("--top", type=int, default=TOP_TO_REVIEW, help="Nombre de pages à relire listées (10).")
    parser.add_argument("--profile", action="store_true", help="Affiche le temps par page.")
    args = parser.parse_args(argv)

    for label, folder in (("json", args.json_dir), ("PDF", args.pdf_dir)):
        if not folder.is_dir():
            print(f"Erreur : le dossier {label} n'existe pas.")
            return 2
    if _inside(args.out, REPO_ROOT):
        print("Erreur : --out doit être en dehors du dépôt 9anoun-AI (données de l'archive).")
        return 2
    if args.echantillon is not None and args.echantillon < 1:
        print("Erreur : --echantillon doit être au moins 1.")
        return 2
    strata = [s.strip() for s in args.strate.split(",") if s.strip()] if args.strate else None
    if strata and args.pages:
        print("Erreur : --strate ne s'utilise qu'avec --echantillon.")
        return 2
    try:
        selection = parse_pages(args.pages) if args.pages else None
        report = run(args.json_dir, args.pdf_dir, selection, n=args.echantillon, seed=args.seed, strata=strata,
                     lang=args.lang, engine=engine or ocr.default_engine(), top=args.top, profile=args.profile)
    except SelectionError as exc:
        print(f"Erreur : {exc}")
        return 2

    print_report(report)
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / OUTPUT_NAME).write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nChiffres écrits dans {OUTPUT_NAME}, dans le dossier de sortie.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
