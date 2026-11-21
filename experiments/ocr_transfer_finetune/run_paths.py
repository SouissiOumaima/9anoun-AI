"""Dossiers de travail d'un lancement de l'expérience (sans Paddle : testable seul).

L'essai rapide (`--quick`) écrit **tout** dans `build/quick/` : état et points de sauvegarde, meilleurs poids,
données générées, résultats. Il ne peut donc jamais écraser les meilleurs poids ni l'état de l'expérience complète
(`build/<étape>_best.pdparams`, `build/state/`). L'expérience complète garde exactement ses chemins d'avant, pour
que ses étapes déjà terminées restent reprises.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class RunPaths:
    work: Path
    """Meilleurs poids de chaque étape (`<étape>_best.pdparams`)."""
    state: Path
    """Résultats des étapes terminées et points de sauvegarde (reprise après plantage)."""
    data: Path
    """Images et textes générés."""
    out: Path
    """results.json, results.md, loss_curves.png."""


def run_paths(build: Path, *, quick: bool, seed: int, tag: str, out: Path) -> RunPaths:
    """Chemins d'un lancement. `tag` identifie la configuration ; `out` est le dossier des résultats demandé."""
    if quick:
        root = build / "quick"
        return RunPaths(work=root, state=root / "state" / f"seed{seed}_{tag}", data=root / "data" / f"seed{seed}",
                        out=root)
    return RunPaths(work=build, state=build / "state" / f"seed{seed}_{tag}", data=build / "data" / f"seed{seed}",
                    out=out)
