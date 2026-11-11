"""Lit une requête JSON (ou une liste de requêtes) depuis un fichier ou stdin, écrit la réponse sur stdout.

Depuis la racine du dépôt :
    python -m src.track_b_accounting.contract.cli data/mock_cards/track_b_requests_demo.json
    echo '{...}' | python -m src.track_b_accounting.contract.cli
"""
from __future__ import annotations

import io
import json
import sys
from typing import TextIO, cast

from .handler import handle, reponse_erreur


def main(argv: list[str] | None = None, stdin: TextIO | None = None, stdout: TextIO | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if stdin is None and not argv:  # pragma: no cover — flux réels de la console
        cast(io.TextIOWrapper, sys.stdin).reconfigure(encoding="utf-8")
        stdin = sys.stdin
    if stdout is None:  # pragma: no cover
        cast(io.TextIOWrapper, sys.stdout).reconfigure(encoding="utf-8")   # arabe lisible même sous une console cp1252
        stdout = sys.stdout
    reponse: dict | list[dict]
    try:
        if argv:
            with open(argv[0], encoding="utf-8") as f:
                texte = f.read()
        else:
            texte = cast(TextIO, stdin).read()  # stdin vaut sys.stdin quand aucun fichier n'est donné
        requete = json.loads(texte)
    except (OSError, json.JSONDecodeError) as exc:
        reponse, code = reponse_erreur(None, exc), 1
    else:
        reponse = [handle(r) for r in requete] if isinstance(requete, list) else handle(requete)
        code = 0
    json.dump(reponse, stdout, ensure_ascii=False, indent=2)
    stdout.write("\n")
    stdout.flush()
    return code


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
