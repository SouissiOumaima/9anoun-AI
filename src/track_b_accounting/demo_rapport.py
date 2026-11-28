"""Démo du rapport de conformité (contrat v1, D108, D109) : chaque requête de track_b_rapport_demo.v1.json passe par
le handler, puis le rendu FR ou AR (selon lang) est affiché tel quel.

Séparée de demo.py, dont la sortie (séries v0 et v1) ne change pas.

Depuis la racine du dépôt :  python -m src.track_b_accounting.demo_rapport
"""

from __future__ import annotations

import io
import json
import sys
from pathlib import Path
from typing import TextIO, cast

from .contract import handle

DEMO_FILE_RAPPORT = Path(__file__).resolve().parents[2] / "data" / "mock_cards" / "track_b_rapport_demo.v1.json"


def main(out: TextIO | None = None) -> int:
    if out is None:  # pragma: no cover — console réelle
        cast(io.TextIOWrapper, sys.stdout).reconfigure(encoding="utf-8")
        out = sys.stdout
    requetes = json.loads(DEMO_FILE_RAPPORT.read_text(encoding="utf-8"))
    statuts = []
    for i, req in enumerate(requetes, 1):
        rep = json.loads(json.dumps(handle(req), ensure_ascii=False))  # telle qu'elle circule en JSON
        statuts.append(rep["status"])
        print(f"\n=== Rapport {i}/{len(requetes)} — {req['request_id']} ({req['lang']}) ===", file=out)
        if rep["status"] == "ok":
            print(rep["texte_ar"] if req["lang"] == "ar" else rep["texte_fr"], end="", file=out)
        elif rep["status"] == "refus":
            r = rep["refus"]
            print(f"Refus {r['code']} : {r['message_ar'] if req['lang'] == 'ar' else r['message_fr']}", file=out)
        else:
            print(f"Erreur : {rep['erreur']['message_fr']}", file=out)
    print(
        f"\nBilan rapports : {statuts.count('ok')} ok, {statuts.count('refus')} refus, "
        f"{statuts.count('erreur')} erreur(s).",
        file=out,
    )
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
