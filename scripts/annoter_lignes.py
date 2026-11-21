"""Prépare l'annotation manuelle de lignes OCR réelles, pour mesurer le vrai CER, SANS afficher leur contenu.

À lancer par la personne qui détient les données (elles restent en dehors du dépôt) :

    .venv\\Scripts\\python scripts/annoter_lignes.py "<dossier des PDF>" --out "<dossier hors dépôt>" --n 200

- lit chaque PDF : texte natif (partie B) puis OCR des zones en attente (partie A) ;
- tire au hasard N lignes lues par l'OCR (graine fixée : même tirage à chaque lancement) ;
- enregistre l'image de chaque ligne (`lignes/ligne_0001.png`…) et un fichier `annotation.csv` dans `--out` :
  `id ; image ; document ; page ; langue_ocr ; confiance ; lecture_ocr ; texte_correct` (colonne
  `texte_correct` vide, à remplir à la main : le texte exact imprimé, sans rien deviner ; `#ILLISIBLE` si la ligne
  ne se lit pas ; laisser vide pour sauter la ligne) ;
- `--out` doit être EN DEHORS du dépôt (le script refuse sinon) ; les documents sont nommés `doc_001`… ;
- n'affiche QUE des chiffres agrégés. Aucun texte, aucun nom de fichier n'est affiché.

Le CSV est en UTF-8 avec BOM et séparateur « ; » : Excel l'ouvre directement, arabe compris.
"""

from __future__ import annotations

import argparse
import csv
import random
import sys
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Final

REPO_ROOT: Final = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import pymupdf

from src.document_intelligence.intermediate import TextLine
from src.document_intelligence.reading import ocr
from src.document_intelligence.reading.ocr import OcrEngine
from src.document_intelligence.reading.pdf_natif import read_pdf

CSV_NAME: Final = "annotation.csv"
IMAGES_DIR: Final = "lignes"
COLUMNS: Final = ("id", "image", "document", "page", "langue_ocr", "confiance", "lecture_ocr", "texte_correct")
CROP_DPI: Final = 300
MARGIN_PT: Final = 2.0
"""Marge autour de la ligne lue, en points PDF, pour ne pas couper les accents ni les points arabes."""


@dataclass(frozen=True)
class Candidate:
    pdf: Path
    document: str
    line: TextLine


def _inside(path: Path, parent: Path) -> bool:
    try:
        path.resolve().relative_to(parent.resolve())
    except ValueError:
        return False
    return True


def collect(pdfs: list[Path], engine: OcrEngine | None, max_pages: int | None) -> tuple[list[Candidate], int]:
    """Toutes les lignes OCR des PDF, et le nombre de documents illisibles."""
    found: list[Candidate] = []
    failed = 0
    for k, pdf in enumerate(pdfs, start=1):
        document = f"doc_{k:03d}"
        try:
            natif = read_pdf(pdf, document_id=document)
            if max_pages is not None:
                natif = natif.model_copy(update={"pages": natif.pages[:max_pages]})
            doc = ocr.ocr_pending_zones(natif, pdf, engine=engine)
        except Exception:  # noqa: BLE001 — un document cassé ne doit pas arrêter la préparation
            failed += 1
            continue
        found.extend(Candidate(pdf, document, line) for page in doc.pages for line in page.lines
                     if line.source == "ocr")
    return found, failed


def crop_line(pdf: Path, line: TextLine, target: Path) -> tuple[int, int]:
    """Enregistre l'image de la ligne (zone de la page autour de sa bbox) ; renvoie sa taille en pixels."""
    with pymupdf.open(pdf) as doc:
        page = doc[line.page - 1]
        x0, y0, x1, y1 = line.bbox
        clip = pymupdf.Rect(x0 - MARGIN_PT, y0 - MARGIN_PT, x1 + MARGIN_PT, y1 + MARGIN_PT) & page.rect
        pix = page.get_pixmap(dpi=CROP_DPI, clip=clip, colorspace=pymupdf.csRGB, alpha=False)
        pix.save(target)
        return pix.width, pix.height


def prepare(source: Path, out_dir: Path, n: int, seed: int, *, limit: int | None = None,
            max_pages: int | None = None, engine: OcrEngine | None = None) -> dict[str, int | float]:
    """Tire N lignes OCR au hasard et écrit les images et le CSV à annoter. Renvoie des chiffres agrégés."""
    pdfs = sorted(p for p in source.iterdir() if p.suffix.lower() == ".pdf")
    if limit is not None:
        pdfs = pdfs[:limit]
    candidates, failed = collect(pdfs, engine, max_pages)
    drawn = random.Random(seed).sample(candidates, min(n, len(candidates)))

    images = out_dir / IMAGES_DIR
    images.mkdir(parents=True, exist_ok=True)
    rows = []
    for i, cand in enumerate(drawn, start=1):
        name = f"ligne_{i:04d}.png"
        crop_line(cand.pdf, cand.line, images / name)
        rows.append({
            "id": f"{i:04d}", "image": f"{IMAGES_DIR}/{name}", "document": cand.document, "page": cand.line.page,
            "langue_ocr": cand.line.language, "confiance": f"{cand.line.confidence:.4f}",
            "lecture_ocr": cand.line.text, "texte_correct": "",
        })
    with (out_dir / CSV_NAME).open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=COLUMNS, delimiter=";")
        writer.writeheader()
        writer.writerows(rows)

    langs = Counter(row["langue_ocr"] for row in rows)
    return {
        "documents": len(pdfs), "documents_en_echec": failed, "lignes_ocr_disponibles": len(candidates),
        "lignes_tirees": len(rows), "lignes_ar": langs["ar"], "lignes_fr": langs["fr"],
        "lignes_mixte_ou_inconnu": langs["mixte"] + langs["inconnu"], "graine": seed,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Prépare l'annotation de lignes OCR réelles (aucun texte affiché).")
    parser.add_argument("source", type=Path, help="Dossier contenant les PDF réels (hors dépôt).")
    parser.add_argument("--out", type=Path, required=True, help="Dossier de sortie, EN DEHORS du dépôt.")
    parser.add_argument("--n", type=int, default=200, help="Nombre de lignes à tirer (200 par défaut).")
    parser.add_argument("--seed", type=int, default=42, help="Graine du tirage (42 par défaut).")
    parser.add_argument("--limit", type=int, default=None, help="Nombre maximal de PDF.")
    parser.add_argument("--max-pages", type=int, default=None, help="Seulement les N premières pages de chaque PDF.")
    args = parser.parse_args(argv)

    if not args.source.is_dir():
        print("Erreur : le dossier source n'existe pas.")
        return 2
    if _inside(args.out, REPO_ROOT):
        print("Erreur : --out doit être en dehors du dépôt 9anoun-AI (données confidentielles).")
        return 2
    for name in ("n", "limit", "max_pages"):
        value = getattr(args, name)
        if value is not None and value < 1:
            print(f"Erreur : --{name.replace('_', '-')} doit être au moins 1.")
            return 2
    if (args.out / CSV_NAME).exists():
        print(f"Erreur : {CSV_NAME} existe déjà dans le dossier de sortie (annotation en cours ?) : "
              "choisissez un autre dossier pour ne rien écraser.")
        return 2

    summary = prepare(args.source, args.out, args.n, args.seed, limit=args.limit, max_pages=args.max_pages)
    print("\nRésumé agrégé :")
    for key, value in summary.items():
        print(f"  {key:<26} {value}")
    print(f"\nÀ annoter : colonne texte_correct de {CSV_NAME}, dans le dossier de sortie.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
