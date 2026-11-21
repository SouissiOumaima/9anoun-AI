"""Combine plusieurs `resultats_cer_reel.json` (une annotatrice chacun) en un seul CER réel, SANS échanger de texte.

Chaque personne annote ses propres lignes avec `scripts/annoter_lignes.py` puis lance `scripts/evaluer_cer_reel.py` :
seul le fichier `resultats_cer_reel.json` (des nombres) est partagé. Ce script additionne les totaux et recalcule :

    CER = somme des erreurs de caractères / somme des caractères de référence
    WER = somme des erreurs de mots / somme des mots de référence
    lignes exactes = somme des lignes exactes / somme des lignes

C'est une moyenne pondérée par les totaux, pas une moyenne simple des taux : un fichier de 300 lignes pèse plus
qu'un fichier de 50. Une méthode absente d'au moins un fichier (par exemple `fine_tune`, si une personne n'a pas
le modèle) est signalée et affichée à part, combinée seulement sur les fichiers qui la contiennent.

Usage :

    .venv\\Scripts\\python scripts/combiner_resultats_cer.py <resultats_1.json> <resultats_2.json> [--out combine.json]

Les fichiers sont désignés par leur numéro (« fichier 1 », « fichier 2 »…), jamais par leur chemin.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Final

REPO_ROOT: Final = Path(__file__).resolve().parents[1]
ACCEPTED_FORMAT: Final = "ds3.cer_reel.v2"
TOTAL_KEYS: Final = ("n", "caracteres_reference", "erreurs_caracteres", "mots_reference", "erreurs_mots",
                     "nb_lignes_exactes")
COUNT_KEYS: Final = ("lignes_dans_le_csv", "lignes_annotees", "lignes_illisibles", "lignes_non_annotees")
SCOPE_ORDER: Final = ("global", "fr", "ar", "mixte", "inconnu")


class ResultsError(ValueError):
    """Fichier de résultats illisible, ancien format ou totaux manquants."""


def _inside(path: Path, parent: Path) -> bool:
    try:
        path.resolve().relative_to(parent.resolve())
    except ValueError:
        return False
    return True


def load_results(path: Path, label: str) -> dict[str, Any]:
    """Lit un fichier de résultats et vérifie qu'il contient les totaux nécessaires (format v2)."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise ResultsError(f"{label} : illisible ({type(exc).__name__}).") from exc
    if not isinstance(data, dict) or data.get("format") != ACCEPTED_FORMAT:
        raise ResultsError(f"{label} : format non reconnu (attendu {ACCEPTED_FORMAT}). Relancez "
                           "scripts/evaluer_cer_reel.py avec la version à jour pour produire les totaux.")
    for method, entry in data.get("resultats", {}).items():
        for scope, totals in entry.items():
            missing = [k for k in TOTAL_KEYS if not isinstance(totals.get(k), int)]
            if missing:
                raise ResultsError(f"{label} : totaux manquants pour {method}/{scope} : {missing}.")
    return data


def rates(totals: dict[str, int]) -> dict[str, float | int]:
    """Taux recalculés à partir des totaux additionnés."""
    chars, words, n = totals["caracteres_reference"], totals["mots_reference"], totals["n"]
    return {
        **totals,
        "cer": round(totals["erreurs_caracteres"] / chars, 4) if chars else 0.0,
        "wer": round(totals["erreurs_mots"] / words, 4) if words else 0.0,
        "lignes_exactes": round(totals["nb_lignes_exactes"] / n, 4) if n else 0.0,
    }


def combine(files: list[dict[str, Any]]) -> dict[str, Any]:
    """Additionne les totaux par méthode et par portée (global, langue). Sépare les méthodes partielles."""
    methods = sorted({m for data in files for m in data.get("resultats", {})},
                     key=lambda m: (m != "ocr_production", m != "pre_entraine", m))
    combined: dict[str, Any] = {}
    partial: dict[str, Any] = {}
    for method in methods:
        present = [i for i, data in enumerate(files) if method in data.get("resultats", {})]
        sums: dict[str, dict[str, int]] = {}
        for i in present:
            for scope, totals in files[i]["resultats"][method].items():
                acc = sums.setdefault(scope, dict.fromkeys(TOTAL_KEYS, 0))
                for key in TOTAL_KEYS:
                    acc[key] += int(totals[key])
        entry = {scope: rates(sums[scope]) for scope in sorted(sums, key=_scope_rank)}
        if len(present) == len(files):
            combined[method] = entry
        else:
            partial[method] = {"fichiers": [i + 1 for i in present], "resultats": entry}
    counts = {key: sum(int(data.get("lignes", {}).get(key, 0)) for data in files) for key in COUNT_KEYS}
    return {"format": "ds3.cer_reel_combine.v1", "fichiers": len(files), "lignes": counts,
            "resultats": combined, "methodes_partielles": partial}


def _scope_rank(scope: str) -> tuple[int, str]:
    return (SCOPE_ORDER.index(scope) if scope in SCOPE_ORDER else len(SCOPE_ORDER), scope)


def _print_table(results: dict[str, dict[str, Any]]) -> None:
    print(f"  {'méthode':<16} {'portée':<8} {'n':>5} {'CER':>8} {'WER':>8} {'exactes':>8}")
    for name, entry in results.items():
        for scope, s in entry.items():
            print(f"  {name:<16} {scope:<8} {s['n']:>5} {s['cer']:>8.2%} {s['wer']:>8.2%} {s['lignes_exactes']:>8.2%}")


def print_combined(result: dict[str, Any]) -> None:
    print(f"\nFichiers combinés : {result['fichiers']}")
    for key, value in result["lignes"].items():
        print(f"  {key:<22} {value}")
    print("\nRésultats combinés (pondérés par les totaux ; CER et WER : plus bas = mieux) :")
    _print_table(result["resultats"])
    for method, info in result["methodes_partielles"].items():
        files = ", ".join(str(i) for i in info["fichiers"])
        print(f"\nAttention : « {method} » n'est présente que dans le(s) fichier(s) {files} : "
              "combinée seulement sur ces fichiers, à ne pas comparer directement aux lignes ci-dessus.")
        _print_table({method: info["resultats"]})


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Combine plusieurs resultats_cer_reel.json (chiffres seulement).")
    parser.add_argument("fichiers", type=Path, nargs="+", help="Fichiers resultats_cer_reel.json à combiner.")
    parser.add_argument("--out", type=Path, default=None, help="Écrit aussi le résultat combiné dans ce fichier JSON.")
    args = parser.parse_args(argv)

    if len(args.fichiers) < 2:
        print("Erreur : donnez au moins deux fichiers à combiner.")
        return 2
    try:
        files = [load_results(path, f"fichier {i}") for i, path in enumerate(args.fichiers, start=1)]
    except ResultsError as exc:
        print(f"Erreur : {exc}")
        return 2
    if args.out is not None and _inside(args.out, REPO_ROOT):
        print("Erreur : --out doit être en dehors du dépôt 9anoun-AI (résultats sur données réelles).")
        return 2

    result = combine(files)
    print_combined(result)
    if args.out is not None:
        args.out.write_text(json.dumps(result, indent=2), encoding="utf-8")
        print("\nRésultat combiné écrit dans le fichier --out.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
