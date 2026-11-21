"""OCR (partie A) : lit les zones laissées en attente par le lecteur natif, avec PaddleOCR (PP-OCRv5).

Entrées :
- `ocr_pending_zones(doc, pdf_path)` : un `IntermediateDocument` produit par `pdf_natif.read_pdf` ;
  chaque `PendingZone` (image, scan, texte natif illisible) est rendue en image puis lue ;
- `read_image(path)` : une image PNG/JPG, lue en entier comme une page.

Règles :
- « citation ou silence » : on ne devine jamais un texte. Une zone où l'OCR ne lit rien reste dans
  `pending_zones`, avec un avertissement ; aucune ligne n'est inventée ;
- aucune confiance n'est filtrée par seuil (le consommateur décide, voir D39) : chaque ligne porte la
  vraie confiance de l'OCR (le minimum de ses morceaux quand plusieurs boîtes forment une ligne) ;
- bbox en points PDF : `zone.x0 + px * 72 / dpi`, `zone.y0 + py * 72 / dpi` ;
- les identifiants `p{page}_l{n}` continuent la numérotation de la page, sans doublon ;
- ordre de lecture : une ligne surtout arabe est lue de droite à gauche (PP-OCRv5 rend chaque mot
  arabe en ordre logique, mais le détecteur découpe la ligne en mots : on les remet dans le bon ordre).

Usage (depuis la racine du dépôt) :
    python -m src.document_intelligence.reading.ocr document.pdf [--json sortie.json]
    python -m src.document_intelligence.reading.ocr scan.png
"""

from __future__ import annotations

import argparse
import functools
import os
import re
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Final, Literal, Protocol

import numpy as np
import pymupdf
from numpy.typing import NDArray
from PIL import Image

from src.document_intelligence.intermediate import (
    BBox,
    IntermediateDocument,
    PageContent,
    PendingZone,
    TextLine,
    detect_language,
)
from src.document_intelligence.reading.inventory import DEFAULT_DPI
from src.document_intelligence.reading.pdf_natif import (
    ROW_SEPARATOR,
    SAME_ROW_OVERLAP,
    read_pdf,
)

READER_SUFFIX: Final = "ocr_paddle-0.1"
IMAGE_READER_NAME: Final = "ocr_image-0.1"

OCR_DPI: Final = DEFAULT_DPI
"""Résolution constante de rendu des zones PDF (300 DPI, comme l'export de l'inventaire)."""

CONTAINED_RATIO: Final = 0.8
"""Une boîte dont au moins 80 % de la surface est dans une boîte plus grande est un doublon de détection
(ex. la hamza « ء » détectée à part au-dessus d'un mot déjà lu) : elle est ignorée."""

IMAGE_EXTENSIONS: Final = frozenset({".png", ".jpg", ".jpeg"})

OcrLang = Literal["ar", "fr"]
LangOption = Literal["ar", "fr", "auto"]
Image3 = NDArray[np.uint8]
"""Image H x W x 3, canaux BGR (convention OpenCV attendue par PaddleOCR)."""

_LINE_ID: Final = re.compile(r"^p(\d+)_l(\d+)$")

REC_MODELS: Final[dict[OcrLang, str]] = {
    "ar": "arabic_PP-OCRv5_mobile_rec",  # arabe + lettres latines + chiffres
    "fr": "latin_PP-OCRv5_mobile_rec",  # alphabet latin avec accents
}
"""Modèles de reconnaissance nommés explicitement : quand le détecteur est nommé, PaddleOCR ignore
`lang` et prendrait son modèle par défaut (PP-OCRv6, pas arabe)."""

DET_MODEL: Final = "PP-OCRv5_mobile_det"
"""Détecteur de texte (voir `PaddleEngine` : le modèle server plante sur les pages A4 entières)."""


@dataclass(frozen=True)
class OcrBox:
    """Un morceau de texte lu par l'OCR, bbox en pixels de l'image lue."""

    text: str
    score: float
    bbox: BBox


class OcrEngine(Protocol):
    """Moteur d'OCR : détecte et reconnaît le texte d'une image."""

    name: str

    def recognize(self, image: Image3, lang: OcrLang) -> list[OcrBox]: ...


class PaddleEngine:
    """PaddleOCR 3.x (détection PP-OCRv5 + reconnaissance PP-OCRv5 arabe ou latine), sur CPU.

    - un pipeline par langue, créé à la première utilisation puis gardé ;
    - oneDNN désactivé : Paddle 3.3 sous Windows plante avec oneDNN sur PP-OCRv5
      (« ConvertPirAttribute2RuntimeAttribute not support ») ;
    - pas de redressement de document ni de classification d'orientation : les zones viennent de
      PDF déjà droits ; ça évite aussi deux modèles de plus ;
    - détecteur `PP-OCRv5_mobile_det` : `PP-OCRv5_server_det` plante (access violation native, sans
      exception Python) sur une page A4 entière à 300 DPI (2480 x 3508 px). Le mobile lit la même page fictive
      en ~35 s, avec les mêmes nombres retrouvés que le server limité à 2000 px (lui ~4 min par page).
    """

    name = "paddleocr-ppocrv5"

    def __init__(self, det_model: str = DET_MODEL) -> None:
        self.det_model = det_model
        self._pipelines: dict[OcrLang, Any] = {}

    def _pipeline(self, lang: OcrLang) -> Any:
        if lang not in self._pipelines:
            os.environ.setdefault("PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK", "True")
            from paddleocr import PaddleOCR  # type: ignore[import-untyped]

            self._pipelines[lang] = PaddleOCR(
                text_detection_model_name=self.det_model,
                text_recognition_model_name=REC_MODELS[lang],
                use_doc_orientation_classify=False,
                use_doc_unwarping=False,
                use_textline_orientation=False,
                device="cpu",
                enable_mkldnn=False,
            )
        return self._pipelines[lang]

    def recognize(self, image: Image3, lang: OcrLang) -> list[OcrBox]:
        boxes: list[OcrBox] = []
        for result in self._pipeline(lang).predict(image):
            for text, score, box in zip(result["rec_texts"], result["rec_scores"], result["rec_boxes"], strict=True):
                x0, y0, x1, y1 = (float(v) for v in box)
                boxes.append(OcrBox(text=str(text), score=float(score), bbox=(x0, y0, x1, y1)))
        return boxes


@functools.cache
def default_engine() -> PaddleEngine:
    """Moteur partagé par défaut (les modèles ne sont chargés qu'une fois par processus)."""
    return PaddleEngine()


# ---------------------------------------------------------------- boîtes -> lignes


def _area(b: BBox) -> float:
    return max(0.0, b[2] - b[0]) * max(0.0, b[3] - b[1])


def _inside_ratio(small: BBox, big: BBox) -> float:
    inter = (max(small[0], big[0]), max(small[1], big[1]), min(small[2], big[2]), min(small[3], big[3]))
    a = _area(small)
    return _area(inter) / a if a > 0 else 1.0


def clean_boxes(boxes: Sequence[OcrBox]) -> list[OcrBox]:
    """Enlève les textes vides et les doublons de détection contenus dans une boîte plus grande."""
    kept = [OcrBox(b.text.strip(), b.score, b.bbox) for b in boxes if b.text.strip()]
    return [
        b
        for b in kept
        if not any(
            o is not b and _area(o.bbox) > _area(b.bbox) and _inside_ratio(b.bbox, o.bbox) >= CONTAINED_RATIO
            for o in kept
        )
    ]


def _same_row(a: BBox, b: BBox) -> bool:
    overlap = min(a[3], b[3]) - max(a[1], b[1])
    smaller = min(a[3] - a[1], b[3] - b[1])
    return smaller > 0 and overlap / smaller >= SAME_ROW_OVERLAP


@dataclass(frozen=True)
class OcrRow:
    text: str
    bbox: BBox
    confidence: float


def group_rows(boxes: Sequence[OcrBox]) -> list[OcrRow]:
    """Regroupe les boîtes en lignes visuelles, de haut en bas.

    Dans une ligne, les morceaux sont lus de gauche à droite, ou de droite à gauche si la ligne a plus
    de morceaux arabes que français (les montants, sans lettres, ne comptent pas). Même règle que
    `pdf_natif.merge_rows`, avec en plus la confiance : le minimum des morceaux (choix prudent).
    """
    rows: list[list[OcrBox]] = []
    for box in sorted(boxes, key=lambda b: (b.bbox[1], b.bbox[0])):
        for row in rows:
            if any(_same_row(box.bbox, other.bbox) for other in row):
                row.append(box)
                break
        else:
            rows.append([box])

    out: list[OcrRow] = []
    for row in rows:
        langs = [detect_language(b.text) for b in row]
        rtl = langs.count("ar") > langs.count("fr")
        row.sort(key=lambda b: b.bbox[0], reverse=rtl)
        bbox = (
            min(b.bbox[0] for b in row),
            min(b.bbox[1] for b in row),
            max(b.bbox[2] for b in row),
            max(b.bbox[3] for b in row),
        )
        out.append(OcrRow(ROW_SEPARATOR.join(b.text for b in row), bbox, min(b.score for b in row)))
    out.sort(key=lambda r: (r.bbox[1], r.bbox[0]))
    return out


def _mean_score(boxes: Sequence[OcrBox]) -> float:
    return sum(b.score for b in boxes) / len(boxes) if boxes else 0.0


LATIN_SURE: Final = 0.95
"""Confiance moyenne minimale pour garder une lecture du modèle latin sans relire la zone en arabe, quand le
document a été retenu « français ». Le modèle latin ne connaît pas les lettres arabes : sur une zone arabe, il
écrit du latin sans sens. Mesuré sur 15 lignes fictives de chaque langue : lignes françaises lues par le modèle
latin, confiance moyenne de 0,983 à 1,000 ; lignes arabes lues par le modèle latin, 0,000 à 0,904, dont 2 sur 15
quand même détectées « fr ». La langue détectée seule ne suffit donc pas ; avec ce seuil, les deux cas sont séparés."""


def _text_of(boxes: Sequence[OcrBox]) -> str:
    return " ".join(b.text for b in boxes)


def read_zone(engine: OcrEngine, image: Image3, lang: LangOption,
              preferred: OcrLang = "ar") -> tuple[list[OcrBox], OcrLang]:
    """Lit une image et renvoie les boîtes avec la langue du modèle retenu.

    Mode « auto » : on lit d'abord avec le modèle de la langue **retenue pour le document** (`preferred`) :
    - `preferred = "ar"` (par défaut) : le modèle arabe connaît aussi les lettres latines et les chiffres ; si le
      texte lu est surtout latin, on relit avec le modèle latin (accents français) et on garde la lecture dont la
      confiance moyenne est la plus haute ;
    - `preferred = "fr"` : on garde la lecture latine si elle est détectée « fr » avec une confiance moyenne d'au
      moins `LATIN_SURE` ; sinon la zone est peut-être de l'autre langue, et on la relit avec le modèle arabe.
    Une seule lecture par zone dans le cas courant ; une relecture seulement si la zone semble de l'autre langue.
    """
    if lang != "auto":
        return clean_boxes(engine.recognize(image, lang)), lang
    if preferred == "fr":
        latin = clean_boxes(engine.recognize(image, "fr"))
        if detect_language(_text_of(latin)) == "fr" and _mean_score(latin) >= LATIN_SURE:
            return latin, "fr"
        arabic = clean_boxes(engine.recognize(image, "ar"))
    else:
        arabic = clean_boxes(engine.recognize(image, "ar"))
        if detect_language(_text_of(arabic)) != "fr":
            return arabic, "ar"
        latin = clean_boxes(engine.recognize(image, "fr"))
    if detect_language(_text_of(arabic)) != "fr":  # zone arabe (ou vide) : le modèle arabe gagne
        return arabic, "ar"
    return (latin, "fr") if _mean_score(latin) > _mean_score(arabic) else (arabic, "ar")


def read_zone_boxes(engine: OcrEngine, image: Image3, lang: LangOption) -> list[OcrBox]:
    """Lit une image seule (langue retenue : arabe d'abord). Voir `read_zone`."""
    return read_zone(engine, image, lang)[0]


# ---------------------------------------------------------------- cœur commun


def _next_line_number(page: PageContent) -> int:
    numbers = [int(m.group(2)) for line in page.lines if (m := _LINE_ID.match(line.line_id))]
    return max(numbers, default=0) + 1


def to_pdf_bbox(zone: BBox, pixel_bbox: BBox, dpi: float) -> BBox:
    """Pixels de l'image rendue -> points PDF de la page."""
    scale = 72.0 / dpi
    x0, y0, x1, y1 = pixel_bbox
    return (
        round(zone[0] + x0 * scale, 1),
        round(zone[1] + y0 * scale, 1),
        round(zone[0] + x1 * scale, 1),
        round(zone[1] + y1 * scale, 1),
    )


def merge_by_position(existing: Sequence[TextLine], added: Sequence[TextLine]) -> list[TextLine]:
    """Insère les lignes OCR à leur place verticale parmi les lignes déjà présentes (texte natif).

    Gemini reçoit ainsi le texte de la page dans l'ordre de lecture, de haut en bas. L'ordre des lignes existantes
    entre elles n'est jamais modifié (le lecteur natif a déjà rangé les siennes), et aucun `line_id` ne change :
    les citations restent justes. À hauteur égale, la ligne existante passe en premier.
    """
    pending = sorted(added, key=lambda line: (line.bbox[1], line.bbox[0]))
    out: list[TextLine] = []
    i = 0
    for line in existing:
        while i < len(pending) and pending[i].bbox[1] < line.bbox[1]:
            out.append(pending[i])
            i += 1
        out.append(line)
    out.extend(pending[i:])
    return out


@dataclass
class _Stats:
    zones_read: int = 0
    lines_added: int = 0
    empty_zones: list[str] = field(default_factory=list)
    failed_zones: list[str] = field(default_factory=list)
    document_lang: OcrLang | None = None


Renderer = Callable[[PendingZone], tuple[Image3, float]]


def _ocr_pages(doc: IntermediateDocument, render: Renderer, engine: OcrEngine, lang: LangOption) -> _Stats:
    """Lit toutes les zones en attente de `doc` (modifié en place) et renvoie le bilan.

    Mode « auto » : la langue est retenue **une fois par document**, d'après la première zone où l'OCR lit du
    texte ; les zones suivantes sont lues d'abord dans cette langue (voir `read_zone`). Un document français ne
    paie donc la double lecture que sur sa première zone, au lieu de toutes.
    """
    stats = _Stats()
    preferred: OcrLang = "ar"
    for page in doc.pages:
        remaining: list[PendingZone] = []
        added: list[TextLine] = []
        number = _next_line_number(page)
        for zone in sorted(page.pending_zones, key=lambda z: (z.bbox[1], z.bbox[0])):
            try:
                image, dpi = render(zone)
                boxes, used = read_zone(engine, image, lang, preferred)
            except Exception as exc:  # noqa: BLE001 — un échec d'OCR ne doit pas faire perdre le reste du document
                stats.failed_zones.append(f"{zone.zone_id} ({type(exc).__name__})")
                remaining.append(zone)
                continue
            rows = group_rows(boxes)
            if not rows:
                stats.empty_zones.append(zone.zone_id)
                remaining.append(zone)
                continue
            if lang == "auto" and stats.document_lang is None:
                stats.document_lang = preferred = used
            for row in rows:
                added.append(
                    TextLine(
                        line_id=f"p{page.page}_l{number}",
                        page=page.page,
                        text=row.text,
                        bbox=to_pdf_bbox(zone.bbox, row.bbox, dpi),
                        confidence=round(min(1.0, max(0.0, row.confidence)), 4),
                        source="ocr",
                        language=detect_language(row.text),
                    )
                )
                number += 1
                stats.lines_added += 1
            stats.zones_read += 1
        page.lines = merge_by_position(page.lines, added)  # ordre de lecture, line_id inchangés
        page.pending_zones = [z for z in page.pending_zones if z in remaining]

    retained = f" ; langue retenue pour le document : {stats.document_lang}" if stats.document_lang else ""
    doc.warnings.append(
        f"OCR ({engine.name}) : {stats.zones_read} zone(s) lue(s), {stats.lines_added} ligne(s) ajoutée(s){retained}."
    )
    if stats.empty_zones:
        doc.warnings.append(
            f"OCR : aucun texte lu dans les zones {stats.empty_zones} ; elles restent en attente (rien n'est deviné)."
        )
    if stats.failed_zones:
        doc.warnings.append(f"OCR : échec de lecture des zones {stats.failed_zones} ; elles restent en attente.")
    return stats


def _pixmap_to_bgr(pix: pymupdf.Pixmap) -> Image3:
    rgb = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, pix.n)[:, :, :3]
    return np.ascontiguousarray(rgb[:, :, ::-1])


def render_zone(page: pymupdf.Page, zone: PendingZone, dpi: int = OCR_DPI) -> Image3:
    """Rend une zone de page PDF en image BGR, à DPI constant."""
    pix = page.get_pixmap(dpi=dpi, clip=pymupdf.Rect(zone.bbox), colorspace=pymupdf.csRGB, alpha=False)
    return _pixmap_to_bgr(pix)


# ---------------------------------------------------------------- API publique


def ocr_pending_zones(
    doc: IntermediateDocument,
    pdf_path: Path,
    engine: OcrEngine | None = None,
    lang: LangOption = "auto",
    dpi: int = OCR_DPI,
) -> IntermediateDocument:
    """Passe à l'OCR toutes les zones en attente d'un document PDF ; renvoie un nouveau document.

    Le document d'entrée n'est pas modifié. Les zones lues sont retirées de `pending_zones`, les zones
    vides y restent avec un avertissement.
    """
    out = doc.model_copy(deep=True)
    engine = engine or default_engine()
    if not any(page.pending_zones for page in out.pages):
        return out
    with pymupdf.open(pdf_path) as pdf:

        def render(zone: PendingZone) -> tuple[Image3, float]:
            return render_zone(pdf[zone.page - 1], zone, dpi), float(dpi)

        _ocr_pages(out, render, engine, lang)
    out.reader = f"{out.reader}+{READER_SUFFIX}"
    return out


def _image_dpi(img: Image.Image) -> float:
    dpi = img.info.get("dpi")
    if isinstance(dpi, tuple) and dpi and float(dpi[0]) >= 50:
        return float(dpi[0])
    return float(DEFAULT_DPI)


def read_image(
    path: Path,
    engine: OcrEngine | None = None,
    lang: LangOption = "auto",
    document_id: str | None = None,
) -> IntermediateDocument:
    """Lit une image PNG/JPG comme une page entière.

    La page mesure `pixels * 72 / dpi` points (DPI lu dans le fichier, 300 par défaut), pour que les
    bbox soient dans la même unité que pour un PDF.
    """
    if path.suffix.lower() not in IMAGE_EXTENSIONS:
        raise ValueError(f"Extension non supportée par read_image : {path.suffix}")
    with Image.open(path) as img:
        dpi = _image_dpi(img)
        rgb = np.asarray(img.convert("RGB"), dtype=np.uint8)
    bgr: Image3 = np.ascontiguousarray(rgb[:, :, ::-1])
    height_px, width_px = bgr.shape[:2]
    width, height = round(width_px * 72 / dpi, 1), round(height_px * 72 / dpi, 1)
    zone = PendingZone(zone_id="p1_z1", page=1, bbox=(0.0, 0.0, width, height), reason="image")
    doc = IntermediateDocument(
        document_id=document_id or path.stem,
        file_name=path.name,
        page_count=1,
        reader=f"{IMAGE_READER_NAME}+{READER_SUFFIX}",
        pages=[PageContent(page=1, width=width, height=height, kind="image", pending_zones=[zone])],
    )
    _ocr_pages(doc, lambda _zone: (bgr, dpi), engine or default_engine(), lang)
    return doc


def read_document(path: Path, lang: LangOption = "auto", engine: OcrEngine | None = None) -> IntermediateDocument:
    """PDF : texte natif (partie B) puis OCR des zones en attente ; image : OCR de toute l'image."""
    if path.suffix.lower() in IMAGE_EXTENSIONS:
        return read_image(path, engine=engine, lang=lang)
    return ocr_pending_zones(read_pdf(path), path, engine=engine, lang=lang)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Lit un PDF (natif + OCR) ou une image (OCR).")
    parser.add_argument("source", type=Path)
    parser.add_argument("--lang", choices=["auto", "ar", "fr"], default="auto")
    parser.add_argument("--json", type=Path, help="Écrit la représentation complète dans ce fichier.")
    args = parser.parse_args(argv)

    doc = read_document(args.source, lang=args.lang)
    print(doc.full_text())
    for warning in doc.warnings:
        print(f"\n⚠ {warning}")
    if args.json:
        args.json.write_text(doc.model_dump_json(indent=2), encoding="utf-8")
        print(f"\nReprésentation complète écrite dans {args.json}")


if __name__ == "__main__":
    main()
