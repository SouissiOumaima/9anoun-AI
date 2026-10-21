"""Étape 1 de l'OCR : inventaire des PDF et export des images à lire.

Pour chaque page d'un PDF, on regarde :
- combien de caractères on peut extraire directement (couche texte native) ;
- combien d'images il y a, et quelle part de la page elles couvrent.

On en déduit le type de la page :
- "texte" : texte natif seulement, pas besoin d'OCR ;
- "mixte" : texte natif + images (ex. un tableau de salaires collé en image),
            on fait l'OCR seulement sur les images ;
- "image" : une image couvre au moins la moitié de la page et il n'y a (presque) pas de texte :
            c'est un scan, on fait l'OCR sur toute la page ;
- "vide"  : rien à lire.

Les images à lire sont exportées en PNG à 300 DPI, avec leur position (bbox en points PDF)
pour pouvoir citer « page 21, zone [x0, y0, x1, y1] » plus tard.

Usage :
    python -m src.document_intelligence.reading.inventory dossier_pdfs/ --out images/
"""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Literal

import pymupdf

PageKind = Literal["texte", "mixte", "image", "vide"]

MIN_CHARS_TEXT = 50
"""En dessous de ce nombre de caractères, une page couverte d'images est considérée comme un scan."""

MIN_COVERAGE_SCAN = 0.5
"""Part minimale de la page couverte par des images pour parler de page scannée."""

MIN_IMAGE_SIDE_PT = 20.0
"""Les images plus petites que ça (logos, puces, traits) sont ignorées."""

DEFAULT_DPI = 300


@dataclass(frozen=True)
class ImageZone:
    index: int
    bbox: tuple[float, float, float, float]


@dataclass(frozen=True)
class PageInfo:
    page: int
    kind: PageKind
    n_chars: int
    n_images: int
    image_coverage: float
    images: tuple[ImageZone, ...]


@dataclass(frozen=True)
class ExportedImage:
    document: str
    page: int
    index: int
    bbox: tuple[float, float, float, float]
    path: str
    whole_page: bool


def _image_zones(page: pymupdf.Page) -> list[ImageZone]:
    zones: list[ImageZone] = []
    for info in page.get_image_info():
        rect = pymupdf.Rect(info["bbox"]) & page.rect
        if rect.is_empty or rect.width < MIN_IMAGE_SIDE_PT or rect.height < MIN_IMAGE_SIDE_PT:
            continue
        bbox = (round(rect.x0, 1), round(rect.y0, 1), round(rect.x1, 1), round(rect.y1, 1))
        zones.append(ImageZone(index=len(zones), bbox=bbox))
    return zones


def classify(n_chars: int, n_images: int, image_coverage: float) -> PageKind:
    """Décide du type de page à partir du texte natif, des images et de leur surface.

    Une page n'est un scan ("image") que si les images couvrent une grande partie de la page
    ET qu'il n'y a presque pas de texte natif. Un titre court au-dessus d'un petit tableau
    en image reste une page "mixte".
    """
    if n_images == 0:
        return "texte" if n_chars > 0 else "vide"
    if image_coverage >= MIN_COVERAGE_SCAN and n_chars < MIN_CHARS_TEXT:
        return "image"
    return "mixte"


def inspect_page(page: pymupdf.Page) -> PageInfo:
    n_chars = len(page.get_text("text").strip())
    zones = _image_zones(page)
    page_area = page.rect.width * page.rect.height
    covered = sum((z.bbox[2] - z.bbox[0]) * (z.bbox[3] - z.bbox[1]) for z in zones)
    coverage = min(1.0, covered / page_area) if page_area else 0.0
    return PageInfo(
        page=page.number + 1,
        kind=classify(n_chars, len(zones), coverage),
        n_chars=n_chars,
        n_images=len(zones),
        image_coverage=round(coverage, 3),
        images=tuple(zones),
    )


def inventory(pdf_path: Path) -> list[PageInfo]:
    """Renvoie le type de chaque page du PDF (pages numérotées à partir de 1)."""
    with pymupdf.open(pdf_path) as doc:
        return [inspect_page(page) for page in doc]


def export_images(pdf_path: Path, out_dir: Path, dpi: int = DEFAULT_DPI) -> list[ExportedImage]:
    """Exporte en PNG tout ce qui doit passer à l'OCR.

    - page "image" : la page entière ;
    - page "mixte" : chaque zone d'image, découpée dans la page (le rendu respecte la rotation
      et la taille réelle de l'image sur la page, contrairement à l'extraction brute).
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    exported: list[ExportedImage] = []
    with pymupdf.open(pdf_path) as doc:
        for page in doc:
            info = inspect_page(page)
            if info.kind == "image":
                r = page.rect
                targets = [(0, (r.x0, r.y0, r.x1, r.y1), True)]
            elif info.kind == "mixte":
                targets = [(z.index, z.bbox, False) for z in info.images]
            else:
                continue
            for index, bbox, whole in targets:
                name = f"{pdf_path.stem}_p{info.page:03d}_img{index}.png"
                pix = page.get_pixmap(dpi=dpi, clip=pymupdf.Rect(bbox))
                pix.save(out_dir / name)
                exported.append(
                    ExportedImage(
                        document=pdf_path.name,
                        page=info.page,
                        index=index,
                        bbox=bbox,
                        path=str(out_dir / name),
                        whole_page=whole,
                    )
                )
    return exported


def _print_table(pdf_path: Path, pages: list[PageInfo]) -> None:
    to_ocr = [p for p in pages if p.kind in ("image", "mixte")]
    print(f"\n{pdf_path.name} — {len(pages)} pages, {len(to_ocr)} à passer à l'OCR")
    for p in to_ocr:
        print(f"  page {p.page:>3}  {p.kind:<6}  {p.n_images} image(s)  "
              f"couverture {p.image_coverage:.0%}  texte natif {p.n_chars} car.")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Inventaire des PDF et export des images à OCR.")
    parser.add_argument("source", type=Path, help="Un fichier PDF ou un dossier de PDF.")
    parser.add_argument("--out", type=Path, default=Path("images"), help="Dossier de sortie.")
    parser.add_argument("--dpi", type=int, default=DEFAULT_DPI)
    args = parser.parse_args(argv)

    pdfs = sorted(args.source.glob("*.pdf")) if args.source.is_dir() else [args.source]
    report: dict[str, object] = {}
    for pdf in pdfs:
        pages = inventory(pdf)
        _print_table(pdf, pages)
        images = export_images(pdf, args.out, dpi=args.dpi)
        report[pdf.name] = {
            "pages": [asdict(p) for p in pages],
            "images_exportees": [asdict(i) for i in images],
        }
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "inventory.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"\nImages et inventory.json écrits dans {args.out}/")


if __name__ == "__main__":
    main()
