"""Primes METALLURGIE_BATIMENT (p.16, art. 50/51 nouveaux).
Lancer depuis la racine du dépôt : pytest src/track_b_accounting/tests/test_calc_primes.py
"""
from decimal import Decimal

import pytest
from conftest import lire_json

from track_b_accounting.calc import Refus, prime

S = "METALLURGIE_BATIMENT"
PRIMES = {p["code"]: p for p in lire_json("data/processed/salary_grids/metallurgie_batiment.json")["primes"]}


def refus(code, *a, **k):
    with pytest.raises(Refus) as e:
        prime(*a, **k)
    assert e.value.code == code and e.value.message_fr and e.value.message_ar
    return e.value


# --- montants datés -------------------------------------------------------------------------------

@pytest.mark.parametrize("code", ["prime_presence", "prime_logement"])
@pytest.mark.parametrize("i", [0, 1, 2])
def test_montant_date_egal_au_json(code, i, ok):
    ligne = PRIMES[code]["montants"][i]
    r = ok(prime(S, code, ligne["effective_date"]))
    assert r.montant == ligne["montant"] and r.detail["effective_date"] == ligne["effective_date"]
    assert r.citations[0].article == PRIMES[code]["source_article"] and r.citations[0].page == 16


@pytest.mark.parametrize("groupe", ["execution_et_maitrise", "cadres"])
@pytest.mark.parametrize("i", [0, 1, 2])
def test_transport_par_groupe_egal_au_json(groupe, i, ok):
    ligne = PRIMES["prime_transport"]["montants"][i]
    r = ok(prime(S, "prime_transport", ligne["effective_date"], groupe=groupe))
    assert r.montant == ligne[groupe] and r.detail["au_titre_de"] == ligne["au_titre_de"]


def test_valeurs_codees_en_dur_p16(ok):
    """Montants 2024 contrôlés sur la couche texte de la p.16 (D4, D5)."""
    assert ok(prime(S, "prime_transport", "2024-06-01", groupe="execution_et_maitrise")).montant == Decimal("92.800")
    assert ok(prime(S, "prime_transport", "2024-06-01", groupe="cadres")).montant == Decimal("100.533")
    assert ok(prime(S, "prime_presence", "2025-01-01")).montant == Decimal("7.856")
    assert ok(prime(S, "prime_logement", "2024-01-01")).montant == Decimal("26.293")


@pytest.mark.parametrize("date,attendu", [
    ("2022-06-01", "6.894"), ("2022-12-31", "6.894"), ("2023-01-01", "7.359"), ("2023-12-31", "7.359"),
])
def test_choix_par_date(date, attendu, ok):
    assert ok(prime(S, "prime_presence", date)).montant == Decimal(attendu)


def test_avant_premiere_date_refusee():
    refus(Refus.SOURCE_MANQUANTE, S, "prime_presence", "2021-11-30")
    refus(Refus.SOURCE_MANQUANTE, S, "prime_transport", "2021-11-30", groupe="cadres")


def test_complement_logement(ok):
    for ligne in PRIMES["prime_logement"]["complement_si_prime_superieure"]:
        r = ok(prime(S, "prime_logement", ligne["effective_date"], variante="complement_si_prime_superieure"))
        assert r.montant == ligne["montant"] and r.detail["variante"] == "complement_si_prime_superieure"
    assert ok(prime(S, "prime_logement", "2024-01-01", variante="base")).montant == Decimal("26.293")


def test_variante_inconnue():
    refus(Refus.PARAM_INVALIDE, S, "prime_logement", "2024-01-01", variante="double")


@pytest.mark.parametrize("groupe", [None, "maitrise", ""])
def test_transport_groupe_obligatoire(groupe):
    kwargs = {} if groupe is None else {"groupe": groupe}
    refus(Refus.PARAM_INVALIDE, S, "prime_transport", "2024-01-01", **kwargs)


# --- montant unique et variante réduite ------------------------------------------------------------

def test_panier_montant_unique(ok):
    r = ok(prime(S, "prime_panier_qefa", "2023-05-01", transport_assure=False))
    assert r.montant == Decimal("0.560") == PRIMES["prime_panier_qefa"]["montant"]
    assert r.unite == "TND/jour" and r.detail["effective_date"] is None and "note" in r.detail


def test_panier_variante_reduite(ok):
    r = ok(prime(S, "prime_panier_qefa", "2023-05-01", transport_assure=True))
    assert r.montant == Decimal("0.160") == PRIMES["prime_panier_qefa"]["montant_reduit_si_transport_assure"]


@pytest.mark.parametrize("val", [None, "oui", 1])
def test_panier_transport_assure_obligatoire(val):
    kwargs = {} if val is None else {"transport_assure": val}
    refus(Refus.PARAM_INVALIDE, S, "prime_panier_qefa", "2023-05-01", **kwargs)


@pytest.mark.parametrize("code,montant,unite", [
    ("prime_deplacement_chantier", "0.750", "TND/jour"),
    ("prime_travail_en_hauteur", "0.015", "TND/heure"),
])
def test_prime_conditionnelle(code, montant, unite, ok):
    r = ok(prime(S, code, "2023-05-01", condition_remplie=True))
    assert r.montant == Decimal(montant) and r.unite == unite
    assert r.detail["condition"] == PRIMES[code]["condition"]
    e = refus(Refus.HORS_SCOPE, S, code, "2023-05-01", condition_remplie=False)
    assert "condition" in e.message_fr
    refus(Refus.PARAM_INVALIDE, S, code, "2023-05-01")


# --- refus divers ----------------------------------------------------------------------------------

def test_prime_inconnue():
    refus(Refus.SOURCE_MANQUANTE, S, "prime_rendement", "2023-05-01")


def test_secteur_inconnu():
    refus(Refus.SOURCE_MANQUANTE, "BTP", "prime_presence", "2023-05-01")


def test_parametre_non_prevu():
    e = refus(Refus.PARAM_INVALIDE, S, "prime_presence", "2023-05-01", groupe="cadres")
    assert "groupe" in e.message_fr


def test_date_invalide():
    refus(Refus.PARAM_INVALIDE, S, "prime_presence", "2023-13-01")


def test_toutes_les_primes_couvertes():
    assert set(PRIMES) == {"prime_transport", "prime_presence", "prime_logement", "prime_panier_qefa",
                           "prime_deplacement_chantier", "prime_travail_en_hauteur"}
