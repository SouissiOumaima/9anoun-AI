"""Grille GARDIENNAGE_SECURITE_TRANSPORT_FONDS (p.2, 8-9, 13-21), activée par D47 ; date de fin d'une table
(valide_jusqu_au).
Lancer depuis la racine du dépôt : pytest src/track_b_accounting/tests/test_gardiennage.py

Les tests de règles lisent une copie en mémoire (référence de test « D99 », charger_grille et GRILLES remplacés le
temps du test) ; le fichier réel, activé par D47, est vérifié à part.
Les valeurs attendues viennent de la double lecture de la page 21 et de la lecture de la page 14.
"""

import copy
from decimal import Decimal

import pytest
from conftest import lire_json

from track_b_accounting.calc import Refus, loaders, prime, salaire_base, table_applicable

S = "GARDIENNAGE_SECURITE_TRANSPORT_FONDS"
FICHIER = "data/processed/salary_grids/gardiennage.json"
REEL = lire_json(FICHIER)
BORNES = [1, 2] + list(range(4, 25, 2))
STATUT = (
    "Barème n° 2 (p.21) : 210 cellules lues par une double lecture indépendante (0 écart), puis relues contre "
    "l'image par une relecture indépendante (aucun écart) ; montants des primes (p.14) relus contre l'image (aucun "
    "écart) ; cas du jeu de référence TB-112 à TB-125 vérifiés à l'image."
)


@pytest.fixture
def gs(monkeypatch):
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


# --- fichier réel : structure et activation ------------------------------------------------------------------


def test_fichier_reel_active_d47_et_dans_le_registre():
    assert REEL["_meta"]["decision_ref"] == "D47" and REEL["_meta"]["secteur_code"] == S
    assert REEL["_meta"]["statut_verification"] == STATUT and STATUT.endswith("TB-112 à TB-125 vérifiés à l'image.")
    loaders.valider_grille(copy.deepcopy(REEL), FICHIER)
    assert loaders.GRILLES[S] == FICHIER and S in loaders.secteurs_disponibles()
    r = salaire_base(S, None, "1", 0.5, "2010-05-01")
    assert r.montant == Decimal("344.500") and r.citations[0].decision_ref == "D47" and r.citations[0].page == 21


def test_structure_une_table_210_cellules():
    assert list(REEL["populations"]) == ["tous_agents"] and REEL["categories"]["tous_agents"] == [
        str(c) for c in range(1, 16)
    ]
    (t,) = REEL["grilles"]
    assert (t["effective_date"], t["source_pdf_page"], t["unite"], t["numero_imprime"]) == (
        "2010-05-01",
        21,
        "TND/mois",
        2,
    )
    assert all(len(v) == 14 and all(isinstance(x, Decimal) for x in v) for v in t["valeurs"].values())
    assert sum(len(v) for v in t["valeurs"].values()) == 210
    assert [d["anciennete_label"] for d in REEL["degres"]["tous_agents"]][:4] == ["0-1", "1-2", "2-4", "4-6"]
    assert REEL["degres"]["tous_agents"][-1]["anciennete_label"] == "24-26"
    assert REEL["degres"]["tous_agents"][-1]["anciennete_imprimee"] == "24"


def test_lignes_et_colonnes_strictement_croissantes():
    """Contrôle de lecture seulement (aucune règle de calcul)."""
    v = REEL["grilles"][0]["valeurs"]
    for c in v:
        assert all(v[c][i] < v[c][i + 1] for i in range(13)), c
    for c in range(2, 16):
        assert all(v[str(c - 1)][d] < v[str(c)][d] for d in range(14)), c


# --- salaire de base -----------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "cat,anc,date,attendu",
    [
        ("1", 0.5, "2010-05-01", "344.500"),  # ligne 1, degré 1
        ("1", 21, "2010-12-01", "371.200"),  # ligne 1, degré 12 (20-22), saut isolé imprimé
        ("7", 5, "2011-01-01", "637.500"),  # ligne 7, degré 4 (4-6), saut isolé imprimé
        ("10", 9, "2010-09-01", "965.000"),  # ligne 10, degré 6 (8-10)
        ("12", 25, "2011-04-30", "1224.000"),  # ligne 12, degré 14 (24-26), veille de la fin de validité
        ("15", 1.5, "2011-02-01", "1291.000"),  # ligne 15, degré 2 (1-2)
    ],
)
def test_montants_lus(gs, ok, cat, anc, date, attendu):
    r = ok(salaire_base(S, None, cat, anc, date))
    assert r.montant == Decimal(attendu) and r.unite == "TND/mois" and r.citations[0].page == 21


def test_population_unique_facultative(gs):
    assert (
        salaire_base(S, None, "5", 3, "2010-06-01").montant
        == salaire_base(S, "tous_agents", "5", 3, "2010-06-01").montant
    )
    refus(Refus.PARAM_INVALIDE, salaire_base, S, "gardiens", "5", 3, "2010-06-01")


def test_categorie_par_numero_sans_alias(gs):
    assert salaire_base(S, None, 9, 3, "2010-06-01").montant == Decimal("813.000")
    e = refus(Refus.PARAM_INVALIDE, salaire_base, S, None, "16", 3, "2010-06-01")
    assert e.message_fr.startswith("Catégorie inconnue")
    refus(Refus.PARAM_INVALIDE, salaire_base, S, None, "agent_gardiennage", 3, "2010-06-01")


@pytest.mark.parametrize("a", BORNES)
def test_bornes_exactes_refusees(gs, a):
    refus(Refus.PARAM_INVALIDE, salaire_base, S, None, "3", a, "2010-06-01")


@pytest.mark.parametrize("a", [26, 30])
def test_a_partir_de_26_ans_refuse(gs, a):
    e = refus(Refus.SOURCE_MANQUANTE, salaire_base, S, None, "3", a, "2010-06-01")
    assert "26" in e.message_fr and "44" in e.message_fr


def test_degre_14_de_24_a_26_ans(gs):
    r = salaire_base(S, None, "3", 25.9, "2010-06-01")
    assert r.detail["degre"] == 14 and r.montant == Decimal("484.300")
    assert any("24 à 26 ans" in h for h in r.detail["hypotheses"])


def test_avant_le_2010_05_01_refuse(gs):
    refus(Refus.SOURCE_MANQUANTE, salaire_base, S, None, "3", 5, "2010-04-30")


# --- fin de validité de la table (valide_jusqu_au) -----------------------------------------------------------


def test_table_servie_jusqu_au_2011_04_30(gs):
    assert table_applicable(S, None, "2011-04-30")["table_id"] == "GS_TOUS_AGENTS_2010-05-01"


@pytest.mark.parametrize("date", ["2011-05-01", "2024-01-01"])
def test_refus_apres_la_fin_de_validite(gs, date):
    fin = REEL["grilles"][0]["valide_jusqu_au"]
    e = refus(Refus.SOURCE_MANQUANTE, salaire_base, S, None, "3", 5, date)
    assert (e.message_fr, e.message_ar) == (fin["message_fr"], fin["message_ar"])
    assert (fin["date"], fin["source_pdf_page"]) == ("2011-04-30", 2) and "avenant n° 7" in e.message_fr


@pytest.mark.parametrize(
    "modif",
    [
        lambda f: f.pop("message_ar"),
        lambda f: f.update(date="30/04/2011"),
        lambda f: f.update(date="2010-04-30"),
        lambda f: f.update(source_pdf_page=0),
    ],
)
def test_valide_jusqu_au_invalide_refuse_par_le_validateur(modif):
    g = copy.deepcopy(REEL)
    g["_meta"]["decision_ref"] = "D99"
    modif(g["grilles"][0]["valide_jusqu_au"])
    with pytest.raises(Refus) as e:
        loaders.valider_grille(g, FICHIER)
    assert e.value.code == Refus.SOURCE_MANQUANTE and "absent ou invalide" in e.value.message_fr


def test_aucune_autre_grille_ne_porte_valide_jusqu_au():
    for code, chemin in loaders.GRILLES.items():
        if code != S:
            assert all("valide_jusqu_au" not in t for t in lire_json(chemin)["grilles"]), code


# --- primes couvertes ----------------------------------------------------------------------------------------


@pytest.mark.parametrize("groupe,attendu", [("execution_gestion", "20.000"), ("cadres", "25.000")])
def test_prime_transport(gs, ok, groupe, attendu):
    r = ok(prime(S, "prime_transport", "2012-05-01", groupe=groupe))
    assert r.montant == Decimal(attendu) and (r.citations[0].page, r.citations[0].article) == (14, "46 (جديد)")
    assert "décret n° 503 du 16 mars 1982" in r.detail["note"] and "aucune addition" in r.detail["note"]
    assert r.detail["label_fr"] == "Prime de transport" and r.detail["label_ar"]
    refus(Refus.SOURCE_MANQUANTE, prime, S, "prime_transport", "2012-04-30", groupe=groupe)
    refus(Refus.PARAM_INVALIDE, prime, S, "prime_transport", "2012-05-01")


def test_prime_presence(gs, ok):
    r = ok(prime(S, "prime_presence", "2006-05-01"))
    assert r.montant == Decimal("3.120") and (r.citations[0].page, r.citations[0].article) == (14, "46-3")
    assert any("aucun recalcul" in h for h in r.detail["hypotheses"])
    refus(Refus.SOURCE_MANQUANTE, prime, S, "prime_presence", "2006-04-30")


def test_prime_panier_avec_condition(gs, ok):
    r = ok(prime(S, "prime_panier", "2015-01-01", condition_remplie=True))
    assert r.montant == Decimal("5.200") and (r.citations[0].page, r.citations[0].article) == (14, "46-4")
    assert (
        "permanent ou contractuel" in r.detail["condition"] and "plus de 7 h le jour du panier" in r.detail["condition"]
    )
    refus(Refus.HORS_SCOPE, prime, S, "prime_panier", "2015-01-01", condition_remplie=False)
    refus(Refus.PARAM_INVALIDE, prime, S, "prime_panier", "2015-01-01")


# --- primes non couvertes ------------------------------------------------------------------------------------


@pytest.mark.parametrize("code", sorted(REEL["primes_non_couvertes"]))
def test_prime_non_couverte_refusee_avec_raison(gs, code):
    bloc = REEL["primes_non_couvertes"][code]
    e = refus(Refus.SOURCE_MANQUANTE, prime, S, code, "2012-06-01")
    assert (e.message_fr, e.message_ar) == (bloc["message_fr"], bloc["message_ar"]) and bloc["motif"]


def test_liste_des_primes():
    assert [p["code"] for p in REEL["primes"]] == ["prime_transport", "prime_presence", "prime_panier"]
    assert all(p["label_fr"] and p["label_ar"] for p in REEL["primes"])
    assert {c: (b["source_article"], b["source_pdf_page"]) for c, b in REEL["primes_non_couvertes"].items()} == {
        "prime_risque_exceptionnel": ("46 مكرر", 14),
        "prime_production": ("47", 14),
        "prime_affectation_categorie_superieure": ("13", 8),
        "indemnite_fin_service": ("39 (جديد)", 13),
        "indemnite_complementaire_provisoire": ("ملاحظة", 21),
    }
