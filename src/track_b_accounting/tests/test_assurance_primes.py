"""Primes ASSURANCE (p.11 et 17, art. 20 (جديد), 21, 22, 44, 46, 47) lues dans le fichier activé (D29).
Lancer depuis la racine du dépôt : pytest src/track_b_accounting/tests/test_assurance_primes.py

Les tests de montants lisent une copie en mémoire (référence de test « D99 », charger_grille et GRILLES
remplacés le temps du test) ; le fichier réel, activé par D29, est vérifié à part.
"""
import copy
from decimal import Decimal

import pytest
from conftest import lire_json

from track_b_accounting.calc import Refus, loaders, prime

S = "ASSURANCE"
FICHIER = "data/processed/salary_grids/assurance.json"
REEL = lire_json(FICHIER)
# Valeurs de la double lecture de la p.11 (art. 20 (جديد), 0 écart).
TRANSPORT = [("2016-06-01", Decimal("75.000")), ("2017-06-01", Decimal("85.000"))]
NON_COUVERTES = {
    "prime_13e_14e_mois": ("20 (جديد)", 11), "prime_production": ("20 (جديد)", 11),
    "prime_fonctionnelle": ("21 (جديد)", 11), "prime_sujetion_services": ("22 (جديد)", 11),
    "aide_deces": ("44", 17), "aide_scolaire": ("46", 17), "prime_depart_retraite": ("47 (جديد)", 17),
}


@pytest.fixture
def assurance(monkeypatch):
    """Copie en mémoire avec decision_ref de test ; charger_grille et GRILLES remplacés le temps du test."""
    g = copy.deepcopy(REEL)
    g["_meta"]["decision_ref"] = "D99"
    g = loaders.valider_grille(g, FICHIER)
    monkeypatch.setattr("track_b_accounting.calc.primes.charger_grille", lambda s: g)
    monkeypatch.setitem(loaders.GRILLES, S, FICHIER)
    return g


def refus(code, *a, **k):
    with pytest.raises(Refus) as e:
        prime(*a, **k)
    assert e.value.code == code and e.value.message_fr and e.value.message_ar
    return e.value


# --- fichier réel : grille non activée ------------------------------------------------------------

def test_fichier_reel_active_d29_et_dans_le_registre(ok):
    assert REEL["_meta"]["decision_ref"] == "D29"
    loaders.valider_grille(copy.deepcopy(REEL), FICHIER)
    assert loaders.GRILLES[S] == FICHIER and S in loaders.secteurs_disponibles()
    r = ok(prime(S, "prime_transport", "2018-01-01"))
    assert r.montant == Decimal("85.000") and r.citations[0].decision_ref == "D29"


def test_prime_transport_dans_le_fichier():
    (p,) = REEL["primes"]
    assert (p["code"], p["source_article"], p["source_pdf_page"], p["unite"]) == (
        "prime_transport", "20 (جديد)", 11, "TND/mois")
    assert [(m["effective_date"], m["montant"]) for m in p["montants"]] == TRANSPORT
    assert "texte_source_ar" not in p


# --- montants datés --------------------------------------------------------------------------------

def test_avant_le_2016_06_01_aucun_montant(assurance):
    e = refus(Refus.SOURCE_MANQUANTE, S, "prime_transport", "2016-05-31")
    assert "2016-06-01" in e.message_fr


@pytest.mark.parametrize("jour,attendu", [
    ("2016-06-01", Decimal("75.000")), ("2017-05-31", Decimal("75.000")),
    ("2017-06-01", Decimal("85.000")), ("2025-01-01", Decimal("85.000")),
])
def test_montant_transport_par_date(assurance, ok, jour, attendu):
    r = ok(prime(S, "prime_transport", jour))
    assert r.montant == attendu and r.unite == "TND/mois"
    assert (r.citations[0].page, r.citations[0].article) == (11, "20 (جديد)")


def test_notes_et_hypotheses_affichees(assurance, ok):
    r = ok(prime(S, "prime_transport", "2017-06-01"))
    assert "503" in r.detail["note"] and "16 mars 1982" in r.detail["note"] and "Note 11" in r.detail["note"]
    assert "503" in r.detail["note_ar"] and "1982" in r.detail["note_ar"]
    assert any("2017-06-01" in h and "dernier transcrit" in h for h in r.detail["hypotheses"])
    assert len(r.detail["hypotheses"]) == len(r.detail["hypotheses_ar"])
    assert any("2017-06-01" in h for h in r.detail["hypotheses_ar"])


def test_aucun_parametre_de_groupe(assurance):
    refus(Refus.PARAM_INVALIDE, S, "prime_transport", "2017-06-01", groupe="cadres")


# --- primes non couvertes -------------------------------------------------------------------------

def test_liste_des_primes_non_couvertes():
    assert set(REEL["primes_non_couvertes"]) == set(NON_COUVERTES)
    assert [p["code"] for p in REEL["primes"]] == ["prime_transport"]


@pytest.mark.parametrize("code", sorted(NON_COUVERTES))
def test_prime_non_couverte_refusee_avec_raison(assurance, code):
    bloc = REEL["primes_non_couvertes"][code]
    article, page = NON_COUVERTES[code]
    assert (bloc["source_article"], bloc["source_pdf_page"]) == (article, page)
    assert bloc["motif"] and "texte_source_ar" not in bloc
    e = refus(Refus.SOURCE_MANQUANTE, S, code, "2020-01-01")
    assert (e.message_fr, e.message_ar) == (bloc["message_fr"], bloc["message_ar"])
    assert f"page {page}" in e.message_fr
