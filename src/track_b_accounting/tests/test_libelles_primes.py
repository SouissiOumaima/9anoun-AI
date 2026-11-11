"""Libellés des primes : chaque prime couverte de chaque grille active renvoie label_fr et label_ar dans detail.
label_ar est le libellé imprimé ; label_fr en est une traduction (pas une citation).
Lancer depuis la racine du dépôt : pytest src/track_b_accounting/tests/test_libelles_primes.py
"""

import pytest

from track_b_accounting.calc import loaders
from track_b_accounting.contract import handle

PRIMES = [(s, p) for s in loaders.secteurs_disponibles() for p in loaders.charger_grille(s).get("primes", [])]


def params_minimaux(secteur: str, p: dict) -> dict:
    """Paramètres acceptés par la prime, lus dans son entrée JSON (première date d'effet, premier groupe)."""
    montants = p.get("montants") or []
    params = {
        "secteur": secteur,
        "code": p["code"],
        "date": montants[0]["effective_date"] if montants else (p.get("effective_date") or "2024-06-01"),
    }
    if montants and "montant" not in montants[0]:
        params["groupe"] = sorted(set(montants[0]) - {"effective_date", "au_titre_de"})[0]
    if "montant_reduit_si_transport_assure" in p:
        params["transport_assure"] = False
    if "condition" in p:
        params["condition_remplie"] = True
    return params


def test_au_moins_une_prime_par_secteur_qui_en_a():
    assert {s for s, _ in PRIMES} == {
        s for s in loaders.secteurs_disponibles() if loaders.charger_grille(s).get("primes")
    }


@pytest.mark.parametrize("secteur,p", PRIMES, ids=[f"{s}-{p['code']}" for s, p in PRIMES])
def test_prime_renvoie_label_fr_et_label_ar(secteur, p):
    rep = handle(
        {
            "contract_version": "track_b.v0",
            "request_id": "t",
            "operation": "prime",
            "params": params_minimaux(secteur, p),
            "lang": "fr",
        }
    )
    assert rep["status"] == "ok", rep.get("refus")
    detail = rep["result"]["detail"]
    assert isinstance(detail.get("label_fr"), str) and detail["label_fr"].strip()
    assert isinstance(detail.get("label_ar"), str) and detail["label_ar"].strip()
    assert detail["label_ar"] == p["label_ar"] and detail["label_fr"] == p["label_fr"]
