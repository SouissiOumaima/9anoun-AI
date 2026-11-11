"""Démo du contrat JSON v0 : MockOrchestrator → handler Track B → MockTrackA.

Depuis la racine du dépôt :  python -m src.track_b_accounting.demo
"""
from __future__ import annotations

import io
import json
import sys
from pathlib import Path
from typing import TextIO, cast

from .contract import handle

sys.path.insert(0, str(Path(__file__).resolve().parent / "tests"))
from mocks import MockOrchestrator, MockTrackA  # noqa: E402


def main(out: TextIO | None = None) -> int:
    if out is None:  # pragma: no cover — console réelle
        cast(io.TextIOWrapper, sys.stdout).reconfigure(encoding="utf-8")
        out = sys.stdout
    track_a = MockTrackA()
    echanges = MockOrchestrator(handle).run()
    for i, (req, rep) in enumerate(echanges, 1):
        print(f"\n=== Échange {i}/{len(echanges)} — {req['request_id']} ({req['lang']}) ===", file=out)
        print("Requête  :", json.dumps(req, ensure_ascii=False), file=out)
        print("Réponse  :", json.dumps(rep, ensure_ascii=False), file=out)
        print("Track A  :", track_a.formuler(req, rep), file=out)
    statuts = [rep["status"] for _, rep in echanges]
    print(f"\nBilan : {statuts.count('ok')} ok, {statuts.count('refus')} refus, "
          f"{statuts.count('erreur')} erreur(s).", file=out)
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
