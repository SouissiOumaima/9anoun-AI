"""Règle « refus » avec anciennete_max_couverte_annees = 0 (D68) : aucune ancienneté couverte.

Cas d'une grille imprimée sans durée de degré (seul le numéro du degré figure) : toute demande de salaire de base est
refusée avec le message lu dans le JSON, avant toute lecture des libellés de degrés ; les primes du secteur restent
servies. Grille fictive tirée de METALLURGIE_BATIMENT (population admin_tech modifiée, execution inchangée).
"""

import copy
from decimal import Decimal

import pytest
from conftest import lire_json

from track_b_accounting.calc import Refus, degre_from_anciennete, prime, salaire_base
from track_b_accounting.calc import loaders

S = "METALLURGIE_BATIMENT"
BM = lire_json("data/processed/salary_grids/metallurgie_batiment.json")
BLOC = {
    "regle": "refus",
    "anciennete_max_couverte_annees": 0,
    "source_pdf_page": 7,
    "source_article": "12 (جديد) et 53",
    "message_fr": "FR-TEST aucune durée de degré imprimée ({a} ans)",
    "message_ar": "AR-TEST {a}",
}


def grille_fictive(bloc: dict = BLOC) -> dict:
    g = copy.deepcopy(BM)
    g["au_dela_dernier_degre"]["admin_tech"] = dict(bloc)
    # Libellés non numériques, comme une grille qui n'imprime que le numéro du degré : jamais lus avec le seuil 0.
    for d in g["degres"]["admin_tech"]:
        d["anciennete_label"] = f"degré {d['degre']}"
    return g


@pytest.fixture
def fictif(monkeypatch):
    g = loaders.valider_grille(grille_fictive(), "fictif.json")
    monkeypatch.setattr("track_b_accounting.calc.salary.charger_grille", lambda s: g)
    monkeypatch.setattr("track_b_accounting.calc.primes.charger_grille", lambda s: g)
    return g


def test_seuil_zero_accepte_par_le_validateur():
    assert loaders.valider_grille(grille_fictive(), "fictif.json")["au_dela_dernier_degre"]["admin_tech"] == BLOC


@pytest.mark.parametrize("valeur", [-1, True, Decimal("1.5"), "0", None])
def test_seuil_invalide_refuse(valeur):
    with pytest.raises(Refus) as e:
        loaders.valider_grille(grille_fictive(dict(BLOC, anciennete_max_couverte_annees=valeur)), "fictif.json")
    assert e.value.code == Refus.SOURCE_MANQUANTE


@pytest.mark.parametrize("annees", [0, Decimal("0.5"), 1, 10, 40])
def test_toute_anciennete_refusee_avec_le_message_du_json(fictif, annees):
    with pytest.raises(Refus) as e:
        salaire_base(S, "admin_tech", "4", annees, "2024-06-01")
    assert e.value.code == Refus.SOURCE_MANQUANTE
    assert e.value.message_fr == f"FR-TEST aucune durée de degré imprimée ({annees} ans)"
    assert e.value.message_ar == f"AR-TEST {annees}"


def test_refus_avant_lecture_des_libelles(fictif):
    with pytest.raises(Refus) as e:
        degre_from_anciennete(3, S, "admin_tech")
    assert "Libellé de degré illisible" not in e.value.message_fr


def test_autre_population_inchangee(fictif):
    table = next(t for t in BM["grilles"] if t["table_id"] == "BM_E_2024-01-01")
    assert salaire_base(S, "execution", "1", 5, "2024-06-01").montant == table["valeurs"]["1"][2]


def test_primes_toujours_servies(fictif):
    r = prime(S, "prime_transport", "2024-06-01", groupe="cadres")
    assert r.montant > 0 and r.citations[0].page > 0


def test_seuil_positif_inchange(monkeypatch):
    """Un seuil > 0 garde son comportement (D8) : servi en dessous, refusé à partir du seuil."""
    g = copy.deepcopy(BM)
    g["au_dela_dernier_degre"]["admin_tech"] = dict(BLOC, anciennete_max_couverte_annees=30)
    g = loaders.valider_grille(g, "fictif.json")
    monkeypatch.setattr("track_b_accounting.calc.salary.charger_grille", lambda s: g)
    assert degre_from_anciennete(25, S, "admin_tech") == 11
    with pytest.raises(Refus):
        degre_from_anciennete(30, S, "admin_tech")
