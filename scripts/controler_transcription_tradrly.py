"""Contrôle indépendant de la transcription Tradrly par notre OCR, SANS afficher le contenu des documents.

À lancer par la personne qui détient l'archive (elle reste en dehors du dépôt) :

    .venv\\Scripts\\python scripts/controler_transcription_tradrly.py "<dossier json>" "<dossier des PDF>" \\
        --out "<dossier hors dépôt>" --pages "convention_a:3,convention_b:12"

Pour chaque page retenue :
1. rend l'image de la page du PDF indiqué par `source_file` (300 DPI) ;
2. la lit avec notre OCR (PaddleOCR PP-OCRv5, modèle arabe par défaut) ;
3. prend le texte Tradrly de la même page dans `pages_content` ;
4. normalise les deux textes (formes de présentation arabes ramenées aux lettres de base, NFC, tatweel, voyelles et
   signes coraniques, chiffres arabes-indiens et persans en chiffres ASCII, espaces) et calcule le CER et le WER,
   avec le texte Tradrly comme référence.

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
chiffres ou de la ponctuation perdus par notre OCR, pas une erreur de Tradrly. `cer_souple` (même calcul que le CER,
après avoir ramené أ / إ / آ à ا, ى à ي et ة à ه) sépare les variantes d'orthographe courantes, que l'arabe tolère, des
vraies erreurs de lettres : CER élevé et CER souple bas = surtout des hamzas, des alif maqsura ou des ta marbuta écrits
autrement.
"""

from __future__ import annotations

import argparse
import json
import random
import re
import statistics
import sys
import time
import unicodedata
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Final, Literal

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
_PRESENTATION_FORMS: Final = re.compile("[ﭐ-﷿ﹰ-﻿]")
"""Formes de présentation arabes A (U+FB50–U+FDFF) et B (U+FE70–U+FEFF) : glyphes positionnels (ﺍﻟﻔﺼﻞ), ligatures
(ﻻ, ﷲ) que certains PDF ou OCR produisent à la place des lettres de base."""
_ZWNBSP: Final = "﻿"
_SOFT_LETTERS: Final = str.maketrans({"أ": "ا", "إ": "ا", "آ": "ا", "ى": "ي", "ة": "ه"})
"""Variantes d'orthographe ramenées à une seule lettre pour `cer_souple` (un caractère pour un caractère)."""


# ---------------------------------------------------------------- normalisation et métriques


def _base_letters(match: re.Match[str]) -> str:
    """Une forme de présentation -> ses lettres de base (NFKC sur ce seul caractère).

    Une voyelle isolée (par ex. U+FE70) devient « espace + voyelle » en NFKC : l'espace est retiré, pour ne pas couper
    un mot (la voyelle est ensuite supprimée comme les autres). U+FEFF (espace insécable invisible) est supprimé.
    """
    char = match.group()
    if char == _ZWNBSP:
        return ""
    base = unicodedata.normalize("NFKC", char)
    if base.startswith(" ") and all(unicodedata.combining(c) for c in base[1:]):
        return base[1:]
    return base


def normalize(text: str) -> str:
    """Formes de présentation arabes -> lettres de base, NFC, sans tatweel ni voyelles / signes coraniques, chiffres
    en ASCII, espaces fusionnés. Seuls les caractères des formes de présentation passent par NFKC : le reste du texte
    (chiffres arabes-indiens compris) est traité comme avant."""
    text = _PRESENTATION_FORMS.sub(_base_letters, text)
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


def soft_normalize(text: str) -> str:
    """Texte normalisé où أ / إ / آ deviennent ا, ى devient ي et ة devient ه : sert à `cer_souple`.

    Ces variantes d'orthographe sont courantes et tolérées en arabe (hamza souvent omise, ى / ي et ة / ه confondus) :
    un CER après les avoir unifiées sépare ces écarts des vraies erreurs de lettres.
    """
    return normalize(text).translate(_SOFT_LETTERS)


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
    ref_soft, hyp_soft = soft_normalize(reference), soft_normalize(hypothesis)
    soft_errors = edit_distance(ref_soft, hyp_soft)
    return {
        "cer": round(char_errors / len(ref), 4) if ref else (0.0 if not hyp else 1.0),
        "cer_lettres": (round(letter_errors / len(ref_letters), 4) if ref_letters
                        else (0.0 if not hyp_letters else 1.0)),
        "cer_souple": round(soft_errors / len(ref_soft), 4) if ref_soft else (0.0 if not hyp_soft else 1.0),
        "wer": round(word_errors / len(ref_words), 4) if ref_words else (0.0 if not hyp_words else 1.0),
        "rappel_mots": round(common / len(ref_words), 4) if ref_words else 0.0,
        "caracteres_reference": len(ref),
        "caracteres_ocr": len(hyp),
        "mots_reference": len(ref_words),
        "mots_ocr": len(hyp_words),
        "erreurs_caracteres": char_errors,
        "erreurs_caracteres_souple": soft_errors,
        "erreurs_mots": word_errors,
    }


# ---------------------------------------------------------------- archive Tradrly


Association = Literal["explicite", "content_pages", "position"]
"""Comment une page du PDF est associée à son texte Tradrly :
- « explicite » : numéro de page dans chaque entrée (`page`, `page_number`, `numero`) ou clé d'un dictionnaire ;
- « content_pages » : `pages_content[i]` est le texte de la page `content_pages[i]` ;
- « position » : `pages_content[i]` est le texte de la page i + 1 (seulement fiable si la liste couvre TOUTES les
  pages : sinon l'association est incertaine et ces pages ne sont pas comparées)."""

PAGE_KEYS: Final = ("page", "page_number", "numero")
TEXT_KEYS: Final = ("text", "content", "texte")


@dataclass
class Convention:
    name: str
    pdf: Path | None
    pages_text: dict[int, str]
    pdf_pages: int = 0
    problems: list[str] = field(default_factory=list)
    association: Association | None = None
    association_incertaine: bool = False
    excluded_pages: set[int] = field(default_factory=set)
    page_types: dict[int, str] = field(default_factory=dict)


@dataclass(frozen=True)
class PagesMapping:
    pages: dict[int, str]
    association: Association
    entries: int
    duplicates: int = 0
    content_pages_mismatch: str | None = None
    page_types: dict[int, str] = field(default_factory=dict)


PAGE_TYPE_MAX_LEN: Final = 40
"""`page_type` est une étiquette courte (valeur affichée) ; une valeur plus longue ressemblerait à du texte de
document et n'est pas reprise."""


def _is_page_number(value: Any) -> bool:
    return not isinstance(value, bool) and str(value).strip().isdigit()


def _page_list(value: Any) -> list[int] | None:
    if isinstance(value, list) and value and all(_is_page_number(v) for v in value):
        return [int(str(v).strip()) for v in value]
    return None


def _content_pages(value: Any) -> list[int] | None:
    """Pages qui ont un texte, d'après `content_pages` : liste de numéros, ou objet avec une liste `included`
    (forme de l'archive : {from, to, included, excluded_salary_pages})."""
    if isinstance(value, dict):
        return _page_list(value.get("included"))
    return _page_list(value)


def _excluded_pages(value: Any) -> set[int]:
    """Pages exclues volontairement par Tradrly (`content_pages.excluded_salary_pages`, ou toute liste `excluded*`)."""
    if not isinstance(value, dict):
        return set()
    excluded: set[int] = set()
    for key, pages in value.items():
        if str(key).startswith("excluded"):
            excluded.update(_page_list(pages) or [])
    return excluded


def _page_type(item: dict[str, Any]) -> str | None:
    value = item.get("page_type")
    if isinstance(value, str) and value.strip() and len(value.strip()) <= PAGE_TYPE_MAX_LEN:
        return value.strip()
    return None


def _first(item: dict[str, Any], keys: tuple[str, ...]) -> Any:
    return next((item[k] for k in keys if k in item), None)


def _pages_content(value: Any, content_pages: Any = None) -> PagesMapping | None:
    """Associe chaque texte de `pages_content` à son vrai numéro de page (voir `Association`).

    Formes reconnues : liste de textes, liste d'objets {page?, text|content|texte}, dictionnaire {"12": texte}.
    Renvoie None si la forme n'est pas reconnue.
    """
    if isinstance(value, dict):
        if value and all(_is_page_number(k) and isinstance(v, str) for k, v in value.items()):
            return PagesMapping({int(str(k)): v for k, v in value.items()}, "explicite", len(value))
        return None
    if not isinstance(value, list):
        return None
    texts: list[str] = []
    explicit: list[int | None] = []
    types: list[str | None] = []
    for item in value:
        if isinstance(item, str):
            texts.append(item)
            explicit.append(None)
            types.append(None)
        elif isinstance(item, dict):
            text, number = _first(item, TEXT_KEYS), _first(item, PAGE_KEYS)
            if not isinstance(text, str) or (number is not None and not _is_page_number(number)):
                return None
            texts.append(text)
            explicit.append(int(str(number).strip()) if number is not None else None)
            types.append(_page_type(item))
        else:
            return None
    numbers = _content_pages(content_pages)
    mismatch = None
    association: Association
    if texts and all(n is not None for n in explicit):
        pages_numbers, association = [n for n in explicit if n is not None], "explicite"
    elif numbers is not None and len(numbers) == len(texts):
        pages_numbers, association = numbers, "content_pages"
    else:
        if numbers is not None:
            mismatch = f"content_pages a {len(numbers)} numéros pour {len(texts)} textes"
        pages_numbers, association = list(range(1, len(texts) + 1)), "position"
    mapping: dict[int, str] = {}
    page_types: dict[int, str] = {}
    for number, text, kind in zip(pages_numbers, texts, types, strict=True):
        if number in mapping:
            continue  # en cas de doublon, la première entrée est gardée (et signalée)
        mapping[number] = text
        if kind is not None:
            page_types[number] = kind
    return PagesMapping(mapping, association, len(texts), duplicates=len(texts) - len(mapping),
                        content_pages_mismatch=mismatch, page_types=page_types)


def _resolve_pdf(source: Any, pdf_dir: Path) -> Path | None:
    if not isinstance(source, str) or not source.strip():
        return None
    for candidate in (Path(source), pdf_dir / source, pdf_dir / Path(source.replace("\\", "/")).name):
        if candidate.is_file():
            return candidate
    return None


def _mapping_problems(mapping: PagesMapping, expected: int) -> list[str]:
    """Anomalies de l'association page ↔ texte. Avec des numéros de page (explicites ou `content_pages`), des pages
    sans contenu sont normales : seuls les numéros hors du PDF et les doublons sont signalés."""
    problems: list[str] = []
    if mapping.content_pages_mismatch:
        problems.append(mapping.content_pages_mismatch)
    if mapping.duplicates:
        problems.append(f"{mapping.duplicates} numéro(s) de page en double dans pages_content")
    if mapping.association == "position":
        if expected and mapping.entries != expected:
            problems.append(f"association page ↔ texte incertaine : {mapping.entries} textes pour {expected} pages, "
                            "sans numéro de page ni content_pages utilisable (pages non comparées)")
    elif expected:
        outside = sum(1 for p in mapping.pages if not 1 <= p <= expected)
        if outside:
            problems.append(f"{outside} numéro(s) de page hors du PDF (1 à {expected})")
    return problems


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
        mapping = _pages_content(data.get("pages_content"), data.get("content_pages"))
        conv.excluded_pages = _excluded_pages(data.get("content_pages"))
        if mapping is None:
            conv.problems.append("pages_content absent ou de forme non reconnue")
        else:
            conv.pages_text, conv.association = mapping.pages, mapping.association
            conv.page_types = mapping.page_types
            both = sorted(set(mapping.pages) & conv.excluded_pages)
            if both:
                conv.problems.append(f"{len(both)} page(s) à la fois exclue(s) et présente(s) dans pages_content")
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
        if mapping is not None:
            conv.problems += _mapping_problems(mapping, expected)
            conv.association_incertaine = mapping.association == "position" and mapping.entries != expected
        if isinstance(declared, int) and conv.pdf_pages and declared != conv.pdf_pages:
            conv.problems.append(f"pages déclarées {declared}, PDF de {conv.pdf_pages} pages")
        conventions.append(conv)
    return conventions


def describe_structure(json_dir: Path) -> list[dict[str, Any]]:
    """Forme de `pages_content` et `content_pages` de chaque convention : types, clés, longueurs et numéros de page.
    Jamais de texte (seuls les NOMS des clés et des nombres sont rapportés)."""
    out: list[dict[str, Any]] = []
    for path in sorted(json_dir.glob("*.json")):
        if path.name.endswith(VERIFICATION_SUFFIX):
            continue
        entry: dict[str, Any] = {"convention": path.stem}
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            out.append({**entry, "erreur": "JSON illisible"})
            continue
        if not isinstance(data, dict):
            out.append({**entry, "erreur": "JSON sans objet principal"})
            continue
        pc, cp = data.get("pages_content"), data.get("content_pages")
        entry["cles_principales"] = sorted(data)
        entry["pages"] = data["pages"] if isinstance(data.get("pages"), int) else type(data.get("pages")).__name__
        entry["pages_content_type"] = type(pc).__name__
        if isinstance(pc, (list, dict)):
            entry["pages_content_entrees"] = len(pc)
        if isinstance(pc, list):
            entry["types_elements"] = sorted({type(v).__name__ for v in pc})
            entry["cles_elements"] = sorted({str(k) for v in pc if isinstance(v, dict) for k in v})
        elif isinstance(pc, dict):
            keys = [k for k in pc if _is_page_number(k)]
            entry["cles_numeriques"] = len(keys)
            entry["premieres_cles"] = sorted(int(str(k)) for k in keys)[:5]
        entry["content_pages_type"] = type(cp).__name__
        if isinstance(cp, int) and not isinstance(cp, bool):
            entry["content_pages"] = cp
        if isinstance(cp, dict):
            entry["content_pages_cles"] = sorted(str(k) for k in cp)
            entry["pages_exclues"] = sorted(_excluded_pages(cp))
        numbers = _content_pages(cp)
        if numbers is not None:
            entry["content_pages_n"] = len(numbers)
            entry["content_pages_min_max"] = [min(numbers), max(numbers)]
            entry["content_pages_premiers"] = numbers[:5]
        out.append(entry)
    return out


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
    """Pages tirables : présentes dans pages_content, dans le PDF, et non exclues par Tradrly."""
    if conv.pdf is None or conv.association_incertaine:
        return []
    return [p for p in sorted(conv.pages_text) if 1 <= p <= conv.pdf_pages and p not in conv.excluded_pages]


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
    page_type: str | None = None


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
    if conv.association_incertaine:  # citation ou silence : on ne compare pas une page à un texte peut-être décalé
        result.probleme = "association page ↔ texte incertaine (voir conventions signalées)"
        return result
    result.page_type = conv.page_types.get(page)
    if page in conv.excluded_pages:
        result.probleme = "page exclue par Tradrly"
        return result
    if page not in conv.pages_text:
        result.probleme = "pas de texte Tradrly"
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
    soft_err = sum(int(r.scores["erreurs_caracteres_souple"]) for r in scored if r.scores)
    word_err = sum(int(r.scores["erreurs_mots"]) for r in scored if r.scores)
    cers = sorted(float(r.scores["cer"]) for r in scored if r.scores)
    worst = sorted(scored, key=lambda r: float(r.scores["cer"]) if r.scores else 0.0, reverse=True)[:top]
    return {
        "pages_demandees": len(results),
        "pages_controlees": len(scored),
        "pages_non_controlees": len(results) - len(scored),
        "cer_global_pondere": round(char_err / chars, 4) if chars else 0.0,
        # même dénominateur : ramener une variante à une seule lettre ne change pas la longueur du texte
        "cer_souple_global_pondere": round(soft_err / chars, 4) if chars else 0.0,
        "wer_global_pondere": round(word_err / words, 4) if words else 0.0,
        "cer_median": round(statistics.median(cers), 4) if cers else 0.0,  # pair : moyenne des 2 du milieu
        "pages_a_relire": [{"convention": r.convention, "page": r.page, "cer": r.scores["cer"],
                            "cer_lettres": r.scores["cer_lettres"], "cer_souple": r.scores["cer_souple"],
                            "rappel_mots": r.scores["rappel_mots"]}
                           for r in worst if r.scores],
        "conventions_signalees": [{"convention": c.name, "problemes": c.problems} for c in conventions if c.problems],
        "conventions": [{"convention": c.name, "association": c.association, "pages_pdf": c.pdf_pages,
                         "pages_avec_contenu": len(c.pages_text),
                         "pages_exclues": len(c.excluded_pages),
                         "pages_sans_contenu": max(0, c.pdf_pages - len([p for p in c.pages_text
                                                                         if 1 <= p <= c.pdf_pages]))}
                        for c in conventions],
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
        "pages": [{"convention": r.convention, "page": r.page, "page_type": r.page_type, **(r.scores or {}),
                   **({"probleme": r.probleme} if r.probleme else {}),
                   **({"durees_s": r.durees_s} if profile and r.durees_s else {})} for r in results],
    }
    return report


def print_report(report: dict[str, Any]) -> None:
    s = report["resume"]
    print("\nRésumé (chiffres seulement) :")
    for key in ("pages_demandees", "pages_controlees", "pages_non_controlees", "cer_global_pondere",
                "cer_souple_global_pondere", "wer_global_pondere", "cer_median"):
        print(f"  {key:<26} {s[key]}")
    print("\n  convention / page                         CER  CER lettres  CER souple     WER   rappel  car.réf")
    for p in report["pages"]:
        label = f"{p['convention']} p.{p['page']}"
        kind = f"  [page_type : {p['page_type']}]" if p.get("page_type") else ""
        if "cer" in p:
            print(f"  {label:<38} {p['cer']:>7.2%} {p['cer_lettres']:>12.2%} {p['cer_souple']:>11.2%} "
                  f"{p['wer']:>7.2%} {p['rappel_mots']:>7.2%} {p['caracteres_reference']:>8}{kind}")
        else:
            print(f"  {label:<38} non contrôlée : {p.get('probleme')}{kind}")
    if s["pages_a_relire"]:
        print("\nPages les plus divergentes, à relire sur l'image :")
        for p in s["pages_a_relire"]:
            print(f"  {p['convention']} p.{p['page']} : CER {p['cer']:.2%}, CER lettres {p['cer_lettres']:.2%}, "
                  f"CER souple {p['cer_souple']:.2%}, rappel des mots {p['rappel_mots']:.2%}")
    print("\nAssociation page ↔ texte Tradrly :")
    for c in s["conventions"]:
        print(f"  {c['convention']} : {c['association'] or '-'} ; {c['pages_avec_contenu']} pages avec contenu, "
              f"{c['pages_sans_contenu']} sans contenu dont {c['pages_exclues']} exclues par Tradrly, "
              f"PDF de {c['pages_pdf']} pages")
    if s["conventions_signalees"]:
        print("\nConventions signalées :")
        for c in s["conventions_signalees"]:
            print(f"  {c['convention']} : {' ; '.join(c['problemes'])}")


def main(argv: list[str] | None = None, engine: OcrEngine | None = None) -> int:
    parser = argparse.ArgumentParser(description="Contrôle de la transcription Tradrly par l'OCR (chiffres seulement).")
    parser.add_argument("json_dir", type=Path, help="Dossier json/ de l'archive Tradrly (hors dépôt).")
    parser.add_argument("pdf_dir", type=Path, help="Dossier des PDF d'origine (hors dépôt).")
    parser.add_argument("--out", type=Path, default=None,
                        help="Dossier de sortie, EN DEHORS du dépôt (obligatoire sauf avec --structure).")
    choice = parser.add_mutually_exclusive_group(required=True)
    choice.add_argument("--pages", help='Liste explicite : "nom:page,nom:page" (pages à partir de 1).')
    choice.add_argument("--echantillon", type=int, help="Nombre de pages à tirer au hasard.")
    choice.add_argument("--structure", action="store_true",
                        help="Affiche seulement la forme de pages_content et content_pages (aucun texte, aucun OCR).")
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
    if args.structure:
        print("Structure de l'archive (noms de clés et nombres seulement, aucun texte) :")
        for entry in describe_structure(args.json_dir):
            print("  " + json.dumps(entry, ensure_ascii=False))
        return 0
    if args.out is None:
        print("Erreur : --out est obligatoire (dossier de sortie en dehors du dépôt).")
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
