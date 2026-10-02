"""Contrôles automatiques de la grille METALLURGIE_BATIMENT (anti-erreur de saisie).
Lancer depuis la racine du dépôt : pytest src/track_b_accounting/tests/test_grid_bm.py
"""
import json, statistics as S
from pathlib import Path
import pytest

# Racine du dépôt = parents[3] depuis ce fichier :
# src/track_b_accounting/tests/test_grid_bm.py -> tests -> track_b_accounting -> src -> <racine>
REPO_ROOT = Path(__file__).resolve().parents[3]
GRID_PATH = REPO_ROOT / "data" / "processed" / "salary_grids" / "metallurgie_batiment.json"
GRID = json.loads(GRID_PATH.read_text(encoding="utf-8"))
TABLES = {t["table_id"]: t for t in GRID["grilles"]}


def test_dimensions():
    assert len(TABLES) == 6
    for t in TABLES.values():
        exp = 19 if t["unite"] == "TND/mois" else 7
        assert len(t["valeurs"]) == exp
        assert all(len(v) == 11 for v in t["valeurs"].values())


@pytest.mark.parametrize("tid", list(TABLES))
def test_croissance_anciennete(tid):
    for cat, v in TABLES[tid]["valeurs"].items():
        assert all(v[i] <= v[i + 1] for i in range(10)), (tid, cat)


@pytest.mark.parametrize("tid", list(TABLES))
def test_croissance_categorie(tid):
    cats = list(TABLES[tid]["valeurs"])
    for k in range(11):
        col = [TABLES[tid]["valeurs"][c][k] for c in cats]
        assert col == sorted(col), (tid, k + 1)


@pytest.mark.parametrize("grp,prefix", [("T", "BM_T_"), ("E", "BM_E_")])
def test_ratio_inter_annees_stable(grp, prefix):
    """L'augmentation 2021->2023->2024 est quasi uniforme (~+6,6 %) : un écart > 0,5 % = erreur de saisie probable."""
    dates = ["2021-12-01", "2023-01-01", "2024-01-01"]
    for d0, d1 in zip(dates, dates[1:]):
        a, b = TABLES[prefix + d0]["valeurs"], TABLES[prefix + d1]["valeurs"]
        r = {(c, k): b[c][k] / a[c][k] for c in a for k in range(11)}
        med = S.median(r.values())
        assert all(abs(x / med - 1) < 0.005 for x in r.values())


def test_primes_croissantes():
    for p in GRID["primes"]:
        ms = p.get("montants")
        if ms and "montant" in ms[0]:
            vals = [m["montant"] for m in ms]
            assert vals == sorted(vals)