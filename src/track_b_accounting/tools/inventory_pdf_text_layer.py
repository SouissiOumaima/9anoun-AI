"""
Inventaire "couche texte vs scan" des PDF du corpus (data/raw/pdf/).

Objectif :
Pour chaque page de chaque PDF, mesurer si une couche texte existe et si
elle est exploitable, afin de prioriser les secteurs dont les grilles
salariales sont a transcrire (texte natif = extraction par script,
scan = saisie manuelle).

Mesures par page :
- n_chars    : nombre de caracteres de page.get_text() (hors espaces de bord)
- statut     : "texte" si n_chars > 50, sinon "scan"
- encodage   : "unicode" (arabe Unicode standard), "pua" (glyphes arabes en
               zone a usage prive : texte non cherchable), "sans_arabe"
- n_montants : nombre de nombres au format montant (ex. 459.264, 49,500) ;
               les chiffres restent lisibles meme quand l'arabe est en PUA
- mots_cles  : mots-cles trouves parmi "جدول", "الأجور", "منحة" (apres NFKC)

Les PDF sont ouverts en lecture seule ; rien n'est ecrit dans data/raw/.
Sorties : data/processed/ocr_audit/pdf_text_layer.json et .md
"""

import json
import re
import unicodedata
from pathlib import Path

import pymupdf

REPO_ROOT = Path(__file__).resolve().parents[3]
PDF_DIR = REPO_ROOT / "data" / "raw" / "pdf"
OUT_DIR = REPO_ROOT / "data" / "processed" / "ocr_audit"

TEXT_THRESHOLD = 50
KEYWORDS = ("جدول", "الأجور", "منحة")
AMOUNT_RE = re.compile(r"\d+[.,]\d{3}")


def _is_arabic(c: str) -> bool:
    return "؀" <= c <= "ۿ" or "ﭐ" <= c <= "﻿"


def _is_pua(c: str) -> bool:
    return "" <= c <= ""


def analyse_text(text: str) -> dict:
    """Diagnostic d'un texte de page (fonction pure, testable sans PDF)."""
    n_chars = len(text.strip())
    chars = [c for c in text if not c.isspace()]
    n_arabe = sum(_is_arabic(c) for c in chars)
    n_pua = sum(_is_pua(c) for c in chars)
    if n_pua > n_arabe:
        encodage = "pua"
    elif n_arabe > 0:
        encodage = "unicode"
    else:
        encodage = "sans_arabe"
    normalized = unicodedata.normalize("NFKC", text)
    return {
        "n_chars": n_chars,
        "statut": "texte" if n_chars > TEXT_THRESHOLD else "scan",
        "encodage": encodage,
        "n_arabe": n_arabe,
        "n_pua": n_pua,
        "n_montants": len(AMOUNT_RE.findall(text)),
        "mots_cles": [k for k in KEYWORDS if k in normalized],
    }


def inventory_pdf(path: Path) -> dict:
    with pymupdf.open(path) as doc:
        pages = [{"page": i + 1, **analyse_text(page.get_text())} for i, page in enumerate(doc)]

    texte = [p for p in pages if p["statut"] == "texte"]
    encodages = {p["encodage"] for p in texte}
    try:
        source_file = path.relative_to(REPO_ROOT).as_posix()
    except ValueError:
        source_file = path.as_posix()
    return {
        "file": path.name,
        "source_file": source_file,
        "nb_pages": len(pages),
        "nb_pages_texte": len(texte),
        "nb_pages_scan": len(pages) - len(texte),
        "pages_scan": [p["page"] for p in pages if p["statut"] == "scan"],
        # Page 1 = couverture : souvent sans texte, rarement une grille.
        "pages_scan_hors_couverture": [p["page"] for p in pages if p["statut"] == "scan" and p["page"] > 1],
        "encodage_couche_texte": encodages.pop() if len(encodages) == 1 else sorted(encodages),
        "pages_mots_cles": [p["page"] for p in pages if p["mots_cles"]],
        "pages_montants": [p["page"] for p in texte if p["n_montants"] >= 3],
        "pages": pages,
    }


def build_inventory(pdf_dir: Path = PDF_DIR) -> list:
    return [inventory_pdf(p) for p in sorted(pdf_dir.glob("*.pdf"))]


def _fmt(pages: list) -> str:
    return ", ".join(map(str, pages)) if pages else "—"


def render_markdown(results: list) -> str:
    lines = [
        "# Inventaire couche texte des PDF — data/raw/pdf/",
        "",
        f"Seuil : une page est « texte » si `page.get_text()` contient plus de {TEXT_THRESHOLD} caractères, sinon « scan ».",
        "Encodage `pua` : l'arabe est encodé en zone Unicode à usage privé (police propriétaire) —",
        "les mots arabes ne sont pas cherchables, mais les chiffres restent lisibles.",
        "",
        "## Résumé par PDF",
        "",
        "| PDF | Pages | Texte | Scan | Pages scan | Encodage texte | Pages mots-clés | Pages ≥ 3 montants (texte) |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for r in results:
        enc = r["encodage_couche_texte"]
        lines.append(
            f"| {r['file']} | {r['nb_pages']} | {r['nb_pages_texte']} | {r['nb_pages_scan']} "
            f"| {_fmt(r['pages_scan'])} | {enc if isinstance(enc, str) else ', '.join(enc)} "
            f"| {_fmt(r['pages_mots_cles'])} | {_fmt(r['pages_montants'])} |"
        )

    with_scans = sorted(
        (r for r in results if r["pages_scan_hors_couverture"]),
        key=lambda r: (len(r["pages_scan_hors_couverture"]), r["file"]),
    )
    without = [r for r in results if not r["pages_scan_hors_couverture"]]
    lines += [
        "",
        "## Classement par coût de saisie (automatique)",
        "",
        "Critère : nombre de pages scannées hors couverture (page 1), croissant.",
        "Hypothèse à confirmer visuellement : ces pages contiennent les grilles salariales.",
        "",
        "| Rang | PDF | Pages scannées hors couverture | Nb |",
        "|---|---|---|---|",
    ]
    for i, r in enumerate(with_scans, 1):
        lines.append(f"| {i} | {r['file']} | {_fmt(r['pages_scan_hors_couverture'])} | {len(r['pages_scan_hors_couverture'])} |")
    if without:
        lines += ["", "Sans page scannée hors couverture : " + ", ".join(r["file"] for r in without) + "."]
    return "\n".join(lines) + "\n"


def main():
    results = build_inventory()
    if not results:
        print(f"Aucun PDF trouve dans {PDF_DIR}")
        return
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    payload = {
        "_meta": {
            "outil": "src/track_b_accounting/tools/inventory_pdf_text_layer.py",
            "source_dir": "data/raw/pdf/",
            "seuil_texte_caracteres": TEXT_THRESHOLD,
            "mots_cles": list(KEYWORDS),
            "pymupdf_version": pymupdf.VersionBind,
            "decision_log": "docs/DECISIONS.md (D5)",
        },
        "pdfs": results,
    }
    with open(OUT_DIR / "pdf_text_layer.json", "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    with open(OUT_DIR / "pdf_text_layer.md", "w", encoding="utf-8") as f:
        f.write(render_markdown(results))

    print(f"OK - {len(results)} PDF inventories.")
    print(f"Rapport : {OUT_DIR / 'pdf_text_layer.md'}")


if __name__ == "__main__":
    main()
