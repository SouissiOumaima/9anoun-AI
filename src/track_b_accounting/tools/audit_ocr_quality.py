"""
Audit de la qualite OCR des fichiers JSON du corpus legal (data/raw/txt/).

Objectif :
Reperer les sections ou l'OCR a mal reconnu des chiffres, montants ou
pourcentages -- ce sont precisement les donnees dont les outils de calcul
de paie.

"""

import json
import re
from pathlib import Path
from datetime import datetime

RAW_DIR = Path(__file__).resolve().parents[3] / "data" / "raw" / "txt"
OUT_DIR = Path(__file__).resolve().parents[3] / "data" / "processed" / "ocr_audit" / "ocr_audit"
OUT_DIR.mkdir(parents=True, exist_ok=True)

# --- Heuristiques de detection de corruption OCR sur les chiffres ---

# Un "mot-chiffre" suspect : lettres arabes collees à des chiffres sans espace
# ex: "4.155J" ou "26866دينارا" ou "39.519"دينارا"
SUSPECT_PATTERNS = [
    r"\d+[A-Za-zء-ي]",        # chiffre suivi direct d'une lettre (arabe ou latine)
    r"[A-Za-zء-ي]\d+",        # lettre suivie direct d'un chiffre
    r"\d{1,3}[.,]\d{1,3}[.,]\d{1,3}",  # triple separateur suspect (ex: 1.234.567 mal groupe)
    r"\d+J\b",                 # artefact OCR frequent "155J"
]

# Mots-cles indiquant qu'une section contient probablement des donnees
# chiffrees critiques pour la paie (à verifier en priorite)
PAYROLL_KEYWORDS = [
    "أجر", "دينار", "مليم", "نسبة", "%", "راتب", "منحة", "أقدمية",
    "اشتراك", "الصندوق الوطني للضمان الاجتماعي", "جراية",
]

suspect_re = re.compile("|".join(SUSPECT_PATTERNS))


def score_section(content: str) -> dict:
    """Retourne un diagnostic pour une section donnee."""
    suspects = suspect_re.findall(content)
    has_payroll_kw = any(kw in content for kw in PAYROLL_KEYWORDS)
    digit_count = len(re.findall(r"\d", content))
    return {
        "suspect_hits": len(suspects),
        "has_payroll_keywords": has_payroll_kw,
        "digit_count": digit_count,
        "needs_review": len(suspects) > 0 and has_payroll_kw,
    }


def audit_file(path: Path) -> dict:
    with open(path, encoding="utf-8") as f:
        data = json.load(f)

    sections = data.get("sections", [])
    flagged = []
    for sec in sections:
        content = sec.get("content", "") or ""
        diag = score_section(content)
        if diag["needs_review"]:
            flagged.append({
                "number": sec.get("number"),
                "title": (sec.get("title") or "")[:80],
                "suspect_hits": diag["suspect_hits"],
                "excerpt": content[:160].replace("\n", " "),
            })

    return {
        "file": path.name,
        "sector_ar": data.get("sector_ar"),
        "section_count": data.get("section_count", len(sections)),
        "flagged_count": len(flagged),
        "flagged_sections": flagged,
    }


def main():
    files = sorted(RAW_DIR.glob("*.json"))
    if not files:
        print(f"Aucun fichier JSON trouve dans {RAW_DIR}")
        return

    results = [audit_file(f) for f in files]

    # --- Rapport JSON (detaille, pour usage machine) ---
    with open(OUT_DIR / "quality_report.json", "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    # --- Rapport Markdown (lisible par l'equipe) ---
    lines = []
    lines.append("# Rapport d'audit qualite OCR — Corpus legal")
    lines.append(f"\nGenere le {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    lines.append(f"\nFichiers analyses : {len(results)}\n")

    total_flagged = sum(r["flagged_count"] for r in results)
    lines.append(f"**Total de sections à revoir manuellement : {total_flagged}**\n")

    lines.append("## Resume par fichier\n")
    lines.append("| Fichier | Secteur | Sections totales | Sections à revoir |")
    lines.append("|---|---|---|---|")
    for r in results:
        lines.append(
            f"| {r['file']} | {r['sector_ar']} | {r['section_count']} | {r['flagged_count']} |"
        )

    lines.append("\n## Detail des sections suspectes (priorite haute)\n")
    for r in results:
        if not r["flagged_sections"]:
            continue
        lines.append(f"### {r['sector_ar']} ({r['file']})\n")
        for sec in r["flagged_sections"]:
            lines.append(f"- **Section {sec['number']}** — *{sec['title']}*")
            lines.append(f"  - Signaux suspects : {sec['suspect_hits']}")
            lines.append(f"  - Extrait : `{sec['excerpt']}...`")
        lines.append("")

    with open(OUT_DIR / "quality_report.md", "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    print(f"OK — {len(results)} fichiers audites, {total_flagged} sections signalees.")
    print(f"Rapport : {OUT_DIR / 'quality_report.md'}")


if __name__ == "__main__":
    main()