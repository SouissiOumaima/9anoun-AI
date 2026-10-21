"""Lecteur de PDF natif (partie B) : texte natif -> représentation intermédiaire.

Pour chaque page :
- les lignes de texte natif lisibles sont gardées avec leur bbox (confiance 1.0) ;
- les morceaux posés sur la même ligne visuelle sont regroupés en une seule ligne
  (« Salaire de base » et « 424,100 » dans deux colonnes -> « Salaire de base  424,100 ») ;
- les lignes de texte natif ILLISIBLES (arabe en caractères « Private Use » U+F2xx, glyphes
  sans code…) ne sont pas gardées comme texte : elles deviennent des zones à passer à l'OCR ;
- les zones image (tableaux en image, scans, tampons) ne sont pas lues ici non plus.

Toutes ces zones sont listées dans `pending_zones` pour l'OCR de la partie A.

Règle page entière : si au moins la moitié des lignes d'une page est illisible, on ne garde
aucune ligne native de cette page et la page entière part à l'OCR. On évite ainsi de mélanger,
sur une même page, du texte natif et du texte OCR qui se recouvrent.

Usage (depuis la racine du dépôt) :
    python -m src.document_intelligence.reading.pdf_natif document.pdf
"""

from __future__ import annotations

import argparse
import re
import unicodedata
from pathlib import Path
from typing import Any, Final

import pymupdf

from src.document_intelligence.intermediate import (
    BBox,
    IntermediateDocument,
    PageContent,
    PendingZone,
    TextLine,
    detect_language,
    is_unreadable_line,
)
from src.document_intelligence.reading.inventory import inspect_page

READER_NAME: Final = "pdf_natif-0.3"

WHOLE_PAGE_RATIO: Final = 0.5
"""À partir de cette part de lignes illisibles, la page entière part à l'OCR."""

SAME_ROW_OVERLAP: Final = 0.5
"""Deux morceaux sont sur la même ligne visuelle s'ils se recouvrent verticalement d'au moins 50 %."""

ROW_SEPARATOR: Final = "  "

# Formes de présentation arabes (lettres déjà « dessinées » : début, milieu, fin de mot).
_AR_PRESENTATION: Final = re.compile("[ﭐ-﷿ﹰ-﻿]")


def _clean(text: str) -> str:
    """Remplace les formes de présentation arabes (U+FExx) par les lettres normales.

    Beaucoup de PDF arabes stockent ces formes : « ﺍﻟﺼﻨﻒ » devient « الصنف », comparable et lisible par Gemini.
    """
    return _AR_PRESENTATION.sub(lambda m: unicodedata.normalize("NFKC", m.group()), text)


def _line_text(line: dict[str, Any]) -> str:
    return _clean("".join(span["text"] for span in line["spans"])).strip()


def _raw_lines(page: pymupdf.Page) -> list[tuple[str, BBox]]:
    """Tous les morceaux de texte natif de la page, avec leur bbox (une « ligne » au sens de MuPDF)."""
    out: list[tuple[str, BBox]] = []
    for block in page.get_text("dict")["blocks"]:
        if block.get("type") != 0:  # 0 = bloc de texte, 1 = bloc image
            continue
        for line in block["lines"]:
            text = _line_text(line)
            if text:
                x0, y0, x1, y1 = (round(v, 1) for v in line["bbox"])
                out.append((text, (x0, y0, x1, y1)))
    return out


def _same_row(a: BBox, b: BBox) -> bool:
    overlap = min(a[3], b[3]) - max(a[1], b[1])
    smaller = min(a[3] - a[1], b[3] - b[1])
    return smaller > 0 and overlap / smaller >= SAME_ROW_OVERLAP


def merge_rows(parts: list[tuple[str, BBox]]) -> list[tuple[str, BBox]]:
    """Regroupe les morceaux d'une même ligne visuelle, de haut en bas.

    Dans une ligne, les morceaux sont lus de gauche à droite, ou de droite à gauche si la ligne
    a plus de morceaux arabes que français.
    """
    rows: list[list[tuple[str, BBox]]] = []
    for part in sorted(parts, key=lambda p: (p[1][1], p[1][0])):
        for row in rows:
            if any(_same_row(part[1], other[1]) for other in row):
                row.append(part)
                break
        else:
            rows.append([part])

    merged: list[tuple[str, BBox]] = []
    for row in rows:
        langs = [detect_language(text) for text, _ in row]
        arabic = langs.count("ar") > langs.count("fr")  # les morceaux sans lettres (montants) ne comptent pas
        row.sort(key=lambda p: p[1][0], reverse=arabic)
        text = ROW_SEPARATOR.join(t for t, _ in row)
        bbox = (min(b[0] for _, b in row), min(b[1] for _, b in row),
                max(b[2] for _, b in row), max(b[3] for _, b in row))
        merged.append((text, bbox))
    merged.sort(key=lambda m: (m[1][1], m[1][0]))
    return merged


def read_page(page: pymupdf.Page) -> PageContent:
    """Lit le texte natif d'une page et liste les zones à passer à l'OCR."""
    info = inspect_page(page)
    number = page.number + 1
    raw = _raw_lines(page)
    unreadable = [(text, bbox) for text, bbox in raw if is_unreadable_line(text)]

    lines: list[TextLine] = []
    zones: list[PendingZone] = []

    if raw and len(unreadable) / len(raw) >= WHOLE_PAGE_RATIO:
        r = page.rect
        zones.append(
            PendingZone(
                zone_id=f"p{number}_u1",
                page=number,
                bbox=(round(r.x0, 1), round(r.y0, 1), round(r.x1, 1), round(r.y1, 1)),
                reason="texte_illisible",
            )
        )
    else:
        for k, (_, bbox) in enumerate(unreadable, start=1):
            zones.append(PendingZone(zone_id=f"p{number}_u{k}", page=number, bbox=bbox, reason="texte_illisible"))
        readable = [(text, bbox) for text, bbox in raw if not is_unreadable_line(text)]
        for text, bbox in merge_rows(readable):
            lines.append(
                TextLine(
                    line_id=f"p{number}_l{len(lines) + 1}",
                    page=number,
                    text=text,
                    bbox=bbox,
                    confidence=1.0,
                    source="natif",
                    language=detect_language(text),
                )
            )

    zones.extend(
        PendingZone(zone_id=f"p{number}_z{zone.index + 1}", page=number, bbox=zone.bbox, reason="image")
        for zone in info.images
    )
    return PageContent(
        page=number,
        width=round(page.rect.width, 1),
        height=round(page.rect.height, 1),
        kind=info.kind,
        lines=lines,
        pending_zones=zones,
    )


def read_pdf(path: Path, document_id: str | None = None) -> IntermediateDocument:
    """Convertit un PDF en représentation intermédiaire (texte natif + zones à OCR)."""
    with pymupdf.open(path) as doc:
        pages = [read_page(page) for page in doc]
    warnings: list[str] = []
    image_pages = [p.page for p in pages if any(z.reason == "image" for z in p.pending_zones)]
    broken_pages = [p.page for p in pages if any(z.reason == "texte_illisible" for z in p.pending_zones)]
    if image_pages:
        warnings.append(f"Zones image à passer à l'OCR (partie A) : pages {image_pages}.")
    if broken_pages:
        warnings.append(
            "Texte natif illisible (caractères Private Use ou glyphes sans code), "
            f"envoyé à l'OCR : pages {broken_pages}."
        )
    return IntermediateDocument(
        document_id=document_id or path.stem,
        file_name=path.name,
        page_count=len(pages),
        reader=READER_NAME,
        pages=pages,
        warnings=warnings,
    )


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Lit le texte natif d'un PDF.")
    parser.add_argument("pdf", type=Path)
    parser.add_argument("--json", type=Path, help="Écrit la représentation complète dans ce fichier.")
    args = parser.parse_args(argv)

    doc = read_pdf(args.pdf)
    print(doc.full_text())
    for warning in doc.warnings:
        print(f"\n⚠ {warning}")
    if args.json:
        args.json.write_text(doc.model_dump_json(indent=2), encoding="utf-8")
        print(f"\nReprésentation complète écrite dans {args.json}")


if __name__ == "__main__":
    main()
