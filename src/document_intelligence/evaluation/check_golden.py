"""Vérifie le jeu de référence DS3 et le registre des sources avant de les partager.

Usage (depuis la racine du dépôt) :
    python -m src.document_intelligence.evaluation.check_golden
    python -m src.document_intelligence.evaluation.check_golden --golden <fichier.json> --sources <fichier.csv>

Contrôles :
- registre : identifiants uniques, valeurs autorisées, date au bon format,
  et tout document avec des données personnelles doit être anonymisé ;
- jeu de référence : identifiants uniques, chaque doc_id existe dans le registre,
  montants à 3 décimales, dates AAAA-MM-JJ, cohérence des cas « partiel » et « refus ».
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from pathlib import Path
from typing import Any

GOLDEN_DIR = Path(__file__).resolve().parent / "golden_sets"
MONTANT = re.compile(r"^-?[0-9]+\.[0-9]{3}$")
DATE = re.compile(r"^[0-9]{4}-[0-9]{2}-[0-9]{2}$")
MONTANT_FIELDS = {"base_salary", "gross_salary", "net_salary", "cnss_employee"}
DATE_FIELDS = {"period_start", "period_end", "hire_date"}
ISSUES = {"ok", "partiel", "refus"}
CATEGORIES = {"ok", "partiel", "refus", "piege"}
CERTITUDES = {"L", "C", "I"}

REGISTRY_ALLOWED = {
    "langue": {"fr", "ar", "mixte"},
    "format": {"pdf_natif", "pdf_scanne", "image", "docx", "xlsx", "csv"},
    "source": {"kaggle", "google", "scribd", "fictif", "autre"},
    "donnees_personnelles": {"oui", "non"},
    "anonymise": {"oui", "non", "na"},
}


def check_registry(path: Path) -> tuple[set[str], list[str]]:
    errors: list[str] = []
    ids: set[str] = set()
    with path.open(encoding="utf-8", newline="") as f:
        for n, row in enumerate(csv.DictReader(f), start=2):
            doc_id = row["doc_id"].strip()
            where = f"{path.name} ligne {n} ({doc_id})"
            if not doc_id:
                errors.append(f"{where} : doc_id vide")
            elif doc_id in ids:
                errors.append(f"{where} : doc_id en double")
            ids.add(doc_id)
            for column, allowed in REGISTRY_ALLOWED.items():
                if row[column].strip() not in allowed:
                    errors.append(f"{where} : {column} = {row[column]!r}, attendu {sorted(allowed)}")
            if not DATE.match(row["date_telechargement"].strip()):
                errors.append(f"{where} : date_telechargement doit être AAAA-MM-JJ")
            if row["donnees_personnelles"].strip() == "oui" and row["anonymise"].strip() != "oui":
                errors.append(f"{where} : données personnelles non anonymisées, à masquer avant tout partage")
            if row["source"].strip() != "fictif" and not row["licence"].strip():
                errors.append(f"{where} : licence manquante pour un document externe")
    return ids, errors


def _check_fields(where: str, fields: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    for name, value in fields.items():
        if value is None:
            continue
        if name in MONTANT_FIELDS and not MONTANT.match(str(value)):
            errors.append(f"{where} : {name} = {value!r} n'est pas un montant à 3 décimales")
        if name in DATE_FIELDS and not DATE.match(str(value)):
            errors.append(f"{where} : {name} = {value!r} n'est pas une date AAAA-MM-JJ")
    return errors


def check_golden(path: Path, registry_ids: set[str]) -> tuple[int, list[str]]:
    errors: list[str] = []
    data = json.loads(path.read_text(encoding="utf-8"))
    seen: set[str] = set()
    cases = data.get("cases", [])
    for case in cases:
        cid = case.get("id", "?")
        where = f"{path.name} cas {cid}"
        if cid in seen:
            errors.append(f"{where} : id en double")
        seen.add(cid)
        if case.get("categorie") not in CATEGORIES:
            errors.append(f"{where} : categorie inconnue {case.get('categorie')!r}")
        if case.get("certitude") not in CERTITUDES:
            errors.append(f"{where} : certitude doit être L, C ou I")
        if case.get("certitude") == "I" and not case.get("decision"):
            errors.append(f"{where} : une interprétation (I) doit citer sa décision (Dn)")
        if case.get("doc_id") not in registry_ids:
            errors.append(f"{where} : doc_id {case.get('doc_id')!r} absent du registre des sources")
        attendu = case.get("attendu", {})
        issue = attendu.get("issue")
        if issue not in ISSUES:
            errors.append(f"{where} : attendu.issue doit être ok, partiel ou refus")
            continue
        fields = attendu.get("fields", {})
        errors += _check_fields(where, fields)
        nulls = {k for k, v in fields.items() if v is None}
        if issue == "ok" and nulls:
            errors.append(f"{where} : issue ok mais champs à null {sorted(nulls)} (utiliser « partiel »)")
        if issue == "partiel":
            if not nulls:
                errors.append(f"{where} : issue partiel sans aucun champ à null")
            missing = nulls - set(attendu.get("unreadable", {}))
            if missing:
                errors.append(f"{where} : raison d'illisibilité manquante pour {sorted(missing)}")
        if issue == "refus" and not (attendu.get("code_v1") or attendu.get("code_v2")):
            errors.append(f"{where} : un refus doit indiquer son code attendu")
    return len(cases), errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Vérifie le jeu de référence DS3.")
    parser.add_argument("--golden", type=Path, default=GOLDEN_DIR / "ds3_golden.v0.json")
    parser.add_argument("--sources", type=Path, default=GOLDEN_DIR / "sources_documents.csv")
    args = parser.parse_args(argv)

    ids, errors = check_registry(args.sources)
    n_cases, golden_errors = check_golden(args.golden, ids)
    errors += golden_errors
    print(f"Registre : {len(ids)} documents · Jeu de référence : {n_cases} cas")
    if errors:
        print(f"\n{len(errors)} problème(s) :")
        for e in errors:
            print(f"  - {e}")
        return 1
    print("Tout est cohérent.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
