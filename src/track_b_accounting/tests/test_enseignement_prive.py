"""Grille ENSEIGNEMENT_PRIVE (p.8, 15 à 27), activée par D38.
Lancer depuis la racine du dépôt : pytest src/track_b_accounting/tests/test_enseignement_prive.py

Les tests de règles lisent une copie en mémoire (référence de test « D99 », charger_grille et GRILLES remplacés le
temps du test) ; le fichier réel, activé par D38, est vérifié à part.
Les valeurs attendues viennent de la double lecture des pages 15 à 18 et 25 à 27.
"""
import copy
from decimal import Decimal

import pytest
from conftest import lire_json

from track_b_accounting.calc import Refus, loaders, prime, salaire_base

S = "ENSEIGNEMENT_PRIVE"
FICHIER = "data/processed/salary_grids/enseignement_prive.json"
REEL = lire_json(FICHIER)
POPS = {"ouvriers": (25, 5), "administratifs_surveillants": (25, 8), "instituteurs": (26, 3),
        "secondaire_formateurs": (26, 5), "professeurs_primaire": (27, 2)}
BORNES = [1, 2, 4, 6, 8, 10, 12, 14, 16, 18, 21, 24, 27, 30, 33]


@pytest.fixture
def ep(monkeypatch):
    g = copy.deepcopy(REEL)
    g["_meta"]["decision_ref"] = "D99"
    g = loaders.valider_grille(g, FICHIER)
    monkeypatch.setattr("track_b_accounting.calc.salary.charger_grille", lambda s: g)
    monkeypatch.setattr("track_b_accounting.calc.primes.charger_grille", lambda s: g)
    monkeypatch.setitem(loaders.GRILLES, S, FICHIER)
    return g


def refus(code, f, *a, **k):
    with pytest.raises(Refus) as e:
        f(*a, **k)
    assert e.value.code == code and e.value.message_fr and e.value.message_ar
    return e.value


# --- fichier réel : structure et non-activation --------------------------------------------------------------

def test_fichier_reel_active_d38_et_dans_le_registre():
    assert REEL["_meta"]["decision_ref"] == "D38" and REEL["_meta"]["secteur_code"] == S
    loaders.valider_grille(copy.deepcopy(REEL), FICHIER)
    assert loaders.GRILLES[S] == FICHIER and S in loaders.secteurs_disponibles()
    r = salaire_base(S, "ouvriers", "ouvrier_ordinaire", 0.5, "2016-01-01")
    assert r.montant == Decimal("465.624") and r.citations[0].decision_ref == "D38"


def test_structure_cinq_tables_368_cellules():
    assert list(REEL["populations"]) == list(POPS)
    pages = {t["population"]: (t["source_pdf_page"], len(t["valeurs"])) for t in REEL["grilles"]}
    assert pages == POPS
    assert all(t["effective_date"] == "2015-09-01" and t["unite"] == "TND/mois" for t in REEL["grilles"])
    for t in REEL["grilles"]:
        assert list(t["valeurs"]) == REEL["categories"][t["population"]]
        assert all(len(v) == 16 and all(isinstance(x, Decimal) for x in v) for v in t["valeurs"].values())
    assert sum(len(v) for t in REEL["grilles"] for v in t["valeurs"].values()) == 368


def test_lignes_strictement_croissantes():
    """Contrôle de lecture seulement (aucune règle de calcul)."""
    for t in REEL["grilles"]:
        for cle, v in t["valeurs"].items():
            assert all(v[i] < v[i + 1] for i in range(15)), (t["table_id"], cle)


# --- salaire de base -----------------------------------------------------------------------------------------

@pytest.mark.parametrize("pop,cat,anc,attendu,page", [
    ("ouvriers", "ouvrier_ordinaire", 0.5, "465.624", 25),           # table 1, ligne 1, degré 1
    ("ouvriers", "5", 35, "662.153", 25),                             # alias annexe 1 → ligne 5, degré 16
    ("administratifs_surveillants", "commis", 9, "523.935", 25),      # rang → ligne 1, degré 6 (8-10 ans)
    ("administratifs_surveillants", "surveillant_general", 19, "913.608", 25),
    ("instituteurs", "instituteur", 3, "603.932", 26),                # table 3, ligne 3, degré 3
    ("secondaire_formateurs", "professeur_principal", 34, "1033.821", 26),   # espace de milliers imprimé
    ("professeurs_primaire", "professeur_ecole_primaire_2e_rang", 11, "718.786", 27),   # degré 7 (10-12 ans)
])
def test_montants_lus(ep, ok, pop, cat, anc, attendu, page):
    r = ok(salaire_base(S, pop, cat, anc, "2016-01-01"))
    assert r.montant == Decimal(attendu) and r.unite == "TND/mois" and r.citations[0].page == page


def test_rang_alias_vers_la_ligne(ep):
    r = salaire_base(S, "administratifs_surveillants", "surveillant_2e_rang", 5, "2016-01-01")
    assert r.detail["categorie"] == "comptable_surveillant_2e_rang" and r.detail["categorie_demandee"] == "surveillant_2e_rang"
    assert r.montant == salaire_base(S, "administratifs_surveillants", "comptable", 5, "2016-01-01").montant


@pytest.mark.parametrize("a", BORNES)
def test_bornes_exactes_refusees(ep, a):
    refus(Refus.PARAM_INVALIDE, salaire_base, S, "ouvriers", "ouvrier_ordinaire", a, "2016-01-01")


@pytest.mark.parametrize("a", [36, 40])
def test_au_dela_de_36_ans_refuse(ep, a):
    e = refus(Refus.SOURCE_MANQUANTE, salaire_base, S, "instituteurs", "instituteur", a, "2016-01-01")
    assert "36" in e.message_fr and "15 (جديد) ب" in e.message_fr


def test_degre_16_juste_avant_36_ans(ep):
    assert salaire_base(S, "instituteurs", "instituteur", 35.9, "2016-01-01").detail["degre"] == 16


def test_avant_le_2015_09_01_refuse(ep):
    refus(Refus.SOURCE_MANQUANTE, salaire_base, S, "ouvriers", "ouvrier_ordinaire", 5, "2015-08-31")


def test_apres_2015_grille_2015_et_hypothese(ep):
    r = salaire_base(S, "ouvriers", "ouvrier_ordinaire", 5, "2025-01-01")
    assert r.detail["table_id"] == "EP_OUVRIERS_2015-09-01"
    assert any("2015-09-01" in h for h in r.detail["hypotheses"]) and len(r.detail["hypotheses"]) == len(r.detail["hypotheses_ar"])


@pytest.mark.parametrize("pop", list(POPS))
def test_hypothese_unite_sauf_ouvriers(ep, pop):
    h = salaire_base(S, pop, REEL["categories"][pop][0], 5, "2016-01-01").detail["hypotheses"]
    assert any(x.startswith("Unité mensuelle") for x in h) == (pop != "ouvriers")


def test_population_omise_refusee(ep):
    e = refus(Refus.PARAM_INVALIDE, salaire_base, S, None, "ouvrier_ordinaire", 5, "2016-01-01")
    assert S in e.message_fr and all(p in e.message_fr for p in POPS)


def test_formateurs_adjoints_categorie_inconnue(ep):
    e = refus(Refus.PARAM_INVALIDE, salaire_base, S, "secondaire_formateurs", "formateur_adjoint", 5, "2016-01-01")
    assert e.message_fr.startswith("Catégorie inconnue")


# --- primes couvertes ----------------------------------------------------------------------------------------

TRANSPORT = [
    ("prime_transport_ouvriers", 15, "48 (جديد)", "ouvrier_competence_partielle", "48.000", False),
    ("prime_transport_administratifs", 16, "49 (جديد)", "econome_1er_rang", "78.166", True),
    ("prime_transport_surveillants", 16, "50 (جديد)", "surveillant_2e_rang", "62.666", True),
    ("prime_transport_primaire", 17, "51 (جديد)", "instituteur", "76.666", True),
    ("prime_transport_secondaire", 18, "54 (جديد)", "formateur_2e_rang", "54.166", True),
]


@pytest.mark.parametrize("code,page,art,rang,attendu,avec_691", TRANSPORT)
def test_prime_transport_par_rang(ep, ok, code, page, art, rang, attendu, avec_691):
    r = ok(prime(S, code, "2016-01-01", groupe=rang))
    assert r.montant == Decimal(attendu) and (r.citations[0].page, r.citations[0].article) == (page, art)
    assert "503" in r.detail["note"] and ("691" in r.detail["note"]) == avec_691 and r.detail["groupe"] == rang
    refus(Refus.SOURCE_MANQUANTE, prime, S, code, "2015-08-31", groupe=rang)


@pytest.mark.parametrize("code,rang,attendus", [
    ("prime_pedagogique_primaire", "instituteur", ["37.000", "38.000", "39.000", "40.000"]),
    ("prime_pedagogique_secondaire", "professeur_principal", ["82.000", "83.000", "85.000", "86.333"]),
])
def test_prime_pedagogique_quatre_dates(ep, code, rang, attendus):
    for annee, attendu in zip((2008, 2009, 2010, 2011), attendus):
        assert prime(S, code, f"{annee}-07-01", groupe=rang).montant == Decimal(attendu)
    assert prime(S, code, "2020-01-01", groupe=rang).montant == Decimal(attendus[-1])
    refus(Refus.SOURCE_MANQUANTE, prime, S, code, "2008-06-30", groupe=rang)


def test_prime_sans_rang_ou_rang_inconnu_refusee(ep):
    refus(Refus.PARAM_INVALIDE, prime, S, "prime_transport_administratifs", "2016-01-01")
    refus(Refus.PARAM_INVALIDE, prime, S, "prime_transport_administratifs", "2016-01-01", groupe="dactylographe_aide_comptable_commis")


# --- primes non couvertes ------------------------------------------------------------------------------------

@pytest.mark.parametrize("code", sorted(REEL["primes_non_couvertes"]))
def test_prime_non_couverte_refusee_avec_raison(ep, code):
    bloc = REEL["primes_non_couvertes"][code]
    e = refus(Refus.SOURCE_MANQUANTE, prime, S, code, "2016-01-01")
    assert (e.message_fr, e.message_ar) == (bloc["message_fr"], bloc["message_ar"]) and bloc["motif"]


def test_liste_des_primes():
    assert [p["code"] for p in REEL["primes"]] == [
        "prime_transport_ouvriers", "prime_transport_administratifs", "prime_transport_surveillants",
        "prime_transport_primaire", "prime_transport_secondaire", "prime_pedagogique_primaire", "prime_pedagogique_secondaire"]
    assert all(p["label_fr"] and p["label_ar"] for p in REEL["primes"])
    assert len(REEL["primes_non_couvertes"]) == 11
