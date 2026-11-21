"""Évalue l'OCR (partie A) sur les PDF réels, SANS jamais afficher leur contenu.

À lancer par la personne qui détient les données (elles restent en dehors du dépôt) :

    .venv\\Scripts\\python scripts/evaluer_donnees_reelles.py "<dossier des PDF>" --out "<dossier de sortie>" --limit 5

- lit chaque PDF : texte natif (partie B) puis OCR des zones en attente (partie A) ;
- écrit, pour chaque document, la représentation intermédiaire complète dans `--out`
  (`doc_001.json`, `doc_002.json`… : les noms de fichiers d'origine ne sont pas repris) ;
- `--out` doit être EN DEHORS du dépôt (le script refuse sinon) ;
- n'affiche QUE des chiffres agrégés : documents, pages, zones, lignes, confiance moyenne, durée.
  Aucun texte, aucun nom de fichier n'est affiché.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.document_intelligence.reading.ocr import ocr_pending_zones
from src.document_intelligence.reading.pdf_natif import read_pdf


@dataclass
class Totals:
    documents: int = 0
    documents_en_echec: int = 0
    pages: int = 0
    zones_a_lire: int = 0
    zones_lues: int = 0
    zones_restees_en_attente: int = 0
    lignes_natives: int = 0
    lignes_ocr: int = 0
    lignes_ocr_ar: int = 0
    lignes_ocr_fr: int = 0
    lignes_ocr_mixte_ou_inconnu: int = 0
    confiances_ocr: list[float] = field(default_factory=list)
    duree_s: float = 0.0

    def summary(self) -> dict[str, float | int]:
        conf = sorted(self.confiances_ocr)
        out: dict[str, float | int] = {k: v for k, v in asdict(self).items() if k != "confiances_ocr"}
        out["duree_s"] = round(self.duree_s, 1)
        out["confiance_ocr_moyenne"] = round(sum(conf) / len(conf), 4) if conf else 0.0
        out["confiance_ocr_mediane"] = round(conf[len(conf) // 2], 4) if conf else 0.0
        out["lignes_ocr_confiance_sous_0_90"] = sum(1 for c in conf if c < 0.90)
        out["part_zones_lues"] = round(self.zones_lues / self.zones_a_lire, 4) if self.zones_a_lire else 0.0
        return out


def _inside(path: Path, parent: Path) -> bool:
    try:
        path.resolve().relative_to(parent.resolve())
    except ValueError:
        return False
    return True


def evaluate(source: Path, out_dir: Path, limit: int | None) -> Totals:
    pdfs = sorted(p for p in source.iterdir() if p.suffix.lower() == ".pdf")
    if limit is not None:
        pdfs = pdfs[:limit]
    out_dir.mkdir(parents=True, exist_ok=True)
    totals = Totals()
    start = time.perf_counter()
    for k, pdf in enumerate(pdfs, start=1):
        totals.documents += 1
        try:
            natif = read_pdf(pdf, document_id=f"doc_{k:03d}")
            doc = ocr_pending_zones(natif, pdf)
        except Exception:  # noqa: BLE001 — un document cassé ne doit pas arrêter l'évaluation
            totals.documents_en_echec += 1
            print(f"  document {k}/{len(pdfs)} : échec de lecture")
            continue
        before = sum(len(p.pending_zones) for p in natif.pages)
        after = sum(len(p.pending_zones) for p in doc.pages)
        ocr = [line for page in doc.pages for line in page.lines if line.source == "ocr"]
        totals.pages += doc.page_count
        totals.zones_a_lire += before
        totals.zones_restees_en_attente += after
        totals.zones_lues += before - after
        totals.lignes_natives += sum(1 for p in doc.pages for line in p.lines if line.source == "natif")
        totals.lignes_ocr += len(ocr)
        totals.lignes_ocr_ar += sum(1 for line in ocr if line.language == "ar")
        totals.lignes_ocr_fr += sum(1 for line in ocr if line.language == "fr")
        totals.lignes_ocr_mixte_ou_inconnu += sum(1 for line in ocr if line.language in ("mixte", "inconnu"))
        totals.confiances_ocr.extend(line.confidence for line in ocr)
        (out_dir / f"doc_{k:03d}.json").write_text(doc.model_dump_json(indent=2), encoding="utf-8")
        print(f"  document {k}/{len(pdfs)} : {doc.page_count} page(s), {before - after}/{before} zone(s) lue(s), "
              f"{len(ocr)} ligne(s) OCR")
    totals.duree_s = time.perf_counter() - start
    return totals


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Évaluation agrégée de l'OCR sur des PDF réels (aucun texte affiché).")
    parser.add_argument("source", type=Path, help="Dossier contenant les PDF réels (hors dépôt).")
    parser.add_argument("--out", type=Path, required=True, help="Dossier de sortie, EN DEHORS du dépôt.")
    parser.add_argument("--limit", type=int, default=None, help="Nombre maximal de PDF à traiter.")
    args = parser.parse_args(argv)

    if not args.source.is_dir():
        print("Erreur : le dossier source n'existe pas.")
        return 2
    if _inside(args.out, REPO_ROOT):
        print("Erreur : --out doit être en dehors du dépôt 9anoun-AI (données confidentielles).")
        return 2
    if args.limit is not None and args.limit < 1:
        print("Erreur : --limit doit être au moins 1.")
        return 2

    totals = evaluate(args.source, args.out, args.limit)
    summary = totals.summary()
    (args.out / "resume_agrege.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print("\nRésumé agrégé :")
    for key, value in summary.items():
        print(f"  {key:<32} {value}")
    print(f"\nDétails écrits dans le dossier de sortie ({totals.documents - totals.documents_en_echec} JSON).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
