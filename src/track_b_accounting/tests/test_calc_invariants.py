"""Invariants transverses du module calc : aucun float dans les Result, fonctions pures.
Lancer depuis la racine du dépôt : pytest src/track_b_accounting/tests/test_calc_invariants.py
"""

import re
from decimal import Decimal
from pathlib import Path

from conftest import _sans_float, lire_json, verifier_result

from track_b_accounting.calc import prime, salaire_base, smig

S = "METALLURGIE_BATIMENT"
CALC = Path(__file__).resolve().parents[1] / "calc"


def _tous_les_results():
    bm = lire_json("data/processed/salary_grids/metallurgie_batiment.json")
    for t in bm["grilles"]:
        pop = "admin_tech" if set(t["valeurs"]) == set(bm["categories"]["admin_tech"]) else "execution"
        for cat in t["valeurs"]:
            for anc in (0, 5, 21.5):
                yield salaire_base(S, pop, cat, anc, t["effective_date"])
    for d in ("2021-12-01", "2023-01-01", "2024-01-01"):
        yield prime(S, "prime_transport", d, groupe="cadres")
        yield prime(S, "prime_presence", d)
        yield prime(S, "prime_logement", d, variante="complement_si_prime_superieure")
    yield prime(S, "prime_panier_qefa", "2024-01-01", transport_assure=True)
    yield prime(S, "prime_deplacement_chantier", "2024-01-01", condition_remplie=True)
    yield prime(S, "prime_travail_en_hauteur", "2024-01-01", condition_remplie=True)
    for mode in ("mensuel", "horaire"):
        for regime in (40, 48):
            yield smig(mode, regime, "2024-01-01")


def test_aucun_montant_float_dans_les_result():
    results = list(_tous_les_results())
    assert len(results) > 100
    for r in results:
        assert type(r.montant) is Decimal, r
        assert _sans_float(r.detail), r.detail
        verifier_result(r)


def test_modules_calc_purs():
    """Pas d'aléatoire, pas d'heure système ; seul loaders.py lit des fichiers."""
    interdits = [r"\bimport random\b", r"\bfrom random\b", r"\.today\(", r"\.now\(", r"\btime\.time\(", r"\bfloat\("]
    for f in CALC.glob("*.py"):
        src = f.read_text(encoding="utf-8")
        for motif in interdits:
            assert not re.search(motif, src), (f.name, motif)
        if f.name != "loaders.py":
            assert not re.search(r"\bopen\(|read_text|read_bytes|\bjson\.load", src), f.name
