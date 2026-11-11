"""Grille BANQUES (p.12-13, 19-23), activée par D46.
Lancer depuis la racine du dépôt : pytest src/track_b_accounting/tests/test_banques.py

Les tests de règles lisent une copie en mémoire (référence de test « D99 », charger_grille et GRILLES remplacés le
temps du test) ; le fichier réel, activé par D46, est vérifié à part.
Les valeurs attendues viennent de la double lecture des pages 22 et 23.
"""

import copy
from decimal import Decimal

import pytest
from conftest import lire_json

from track_b_accounting.calc import Refus, loaders, prime, salaire_base

S = "BANQUES"
FICHIER = "data/processed/salary_grids/banques.json"
REEL = lire_json(FICHIER)
BORNES = [1, 2, 3, 4, 5] + list(range(7, 32, 2))
STATUT = (
    "Les tables 1 et 2 ont été relues cellule par cellule sur l'image (1 292 cellules) par une seconde lecture "
    "indépendante de la double lecture initiale ; l'écart entre la table 2 et la table 1 est constant sur chaque "
    "ligne ; contrôle humain des extrémités de chaque ligne et des cellules signalées."
)


@pytest.fixture
def bq(monkeypatch):
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


def test_fichier_reel_active_d46_et_dans_le_registre():
    assert REEL["_meta"]["decision_ref"] == "D46" and REEL["_meta"]["secteur_code"] == S
    assert REEL["_meta"]["statut_verification"] == STATUT
    loaders.valider_grille(copy.deepcopy(REEL), FICHIER)
    assert loaders.GRILLES[S] == FICHIER and S in loaders.secteurs_disponibles()
    r = salaire_base(S, None, "agent_services_3", 0.5, "2020-10-01")
    assert r.montant == Decimal("1523.106") and r.citations[0].decision_ref == "D46" and r.citations[0].page == 22


def test_structure_deux_tables_1292_cellules():
    assert list(REEL["populations"]) == ["tous_agents"] and len(REEL["categories"]["tous_agents"]) == 34
    assert [(t["effective_date"], t["source_pdf_page"], t["unite"]) for t in REEL["grilles"]] == [
        ("2020-09-01", 22, "TND/mois"),
        ("2021-05-01", 23, "TND/mois"),
    ]
    for t in REEL["grilles"]:
        assert list(t["valeurs"]) == REEL["categories"]["tous_agents"]
        assert all(len(v) == 19 and all(isinstance(x, Decimal) for x in v) for v in t["valeurs"].values())
    assert sum(len(v) for t in REEL["grilles"] for v in t["valeurs"].values()) == 1292
    assert [d["anciennete_label"] for d in REEL["degres"]["tous_agents"]][:7] == [
        "0-1",
        "1-2",
        "2-3",
        "3-4",
        "4-5",
        "5-7",
        "7-9",
    ]
    assert REEL["degres"]["tous_agents"][-1]["anciennete_label"] == "31-33"


def test_ecart_table_2_moins_table_1_constant_par_ligne():
    """Contrôle de lecture seulement (aucune règle de calcul) : +164, +176, +208, +239, +298 selon la ligne."""
    t1, t2 = (t["valeurs"] for t in REEL["grilles"])
    attendu = [164] * 8 + [176] * 10 + [208] * 5 + [239] * 5 + [298] * 6
    for cle, e in zip(REEL["categories"]["tous_agents"], attendu):
        assert {b - a for a, b in zip(t1[cle], t2[cle])} == {Decimal(e)}, cle


@pytest.mark.parametrize(
    "cle,colonne,v1,v2",
    [
        ("agent_services_principal", 6, "1470.216", "1634.216"),
        ("agent_suivi_3", 6, "1470.216", "1634.216"),
        ("agent_bureau_3", 5, "1807.346", "1983.346"),
        ("commis_principal_3", 16, "1928.226", "2104.226"),
        ("commis_principal_1", 6, "1871.896", "2047.896"),
        ("commis_principal_1", 12, "1934.596", "2110.596"),
    ],
)
def test_anomalies_imprimees_conservees(cle, colonne, v1, v2):
    t1, t2 = REEL["grilles"]
    assert (t1["valeurs"][cle][colonne - 1], t2["valeurs"][cle][colonne - 1]) == (Decimal(v1), Decimal(v2))
    for t in (t1, t2):
        (a,) = [a for a in t["anomalies_imprimees"] if (a["categorie"], a["colonne"]) == (cle, colonne)]
        assert (
            a["valeur_imprimee"] == t["valeurs"][cle][colonne - 1] and a["meme_anomalie_dans_les_deux_tables"] is True
        )


def test_lignes_4_et_5_identiques_et_signalees():
    for t in REEL["grilles"]:
        assert t["valeurs"]["agent_services_principal"] == t["valeurs"]["agent_suivi_3"]
        assert len(t["anomalies_imprimees"]) == 7
    assert "même anomalie dans les deux tables" in REEL["_meta"]["remarque_anomalies"]


# --- salaire de base -----------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "cat,anc,date,attendu,page",
    [
        ("agent_services_3", 0.5, "2020-10-01", "1523.106", 22),  # table 1, ligne 1, colonne 1 (stage)
        ("redacteur_2", 10, "2020-12-01", "2289.026", 22),  # table 1, ligne 22, colonne 8 (9-11 ans)
        (
            "chef_service_principal",
            8,
            "2021-01-01",
            "2659.326",
            22,
        ),  # table 1, ligne 28, colonne 7 (écart tranché à 600 dpi)
        ("agent_services_principal", 6, "2021-04-30", "1470.216", 22),  # anomalie imprimée, veille de la table 2
        ("agent_bureau_4", 0.5, "2022-01-01", "1957.446", 23),  # table 2, ligne 9, colonne 1
        ("commis_principal_1", 18, "2021-05-01", "2110.596", 23),  # anomalie imprimée, colonne 12 (17-19 ans)
        ("directeur_1", 32, "2024-06-01", "3537.826", 23),  # table 2, ligne 34, colonne 19 (31-33 ans)
    ],
)
def test_montants_lus(bq, ok, cat, anc, date, attendu, page):
    r = ok(salaire_base(S, None, cat, anc, date))
    assert r.montant == Decimal(attendu) and r.unite == "TND/mois" and r.citations[0].page == page


def test_population_unique_facultative(bq):
    a = salaire_base(S, None, "commis_1", 12, "2022-01-01")
    assert a.montant == salaire_base(S, "tous_agents", "commis_1", 12, "2022-01-01").montant
    refus(Refus.PARAM_INVALIDE, salaire_base, S, "cadres", "commis_1", 12, "2022-01-01")


@pytest.mark.parametrize("a", BORNES)
def test_bornes_exactes_refusees(bq, a):
    refus(Refus.PARAM_INVALIDE, salaire_base, S, None, "redacteur_1", a, "2022-01-01")


@pytest.mark.parametrize("a", [33, 40])
def test_a_partir_de_33_ans_refuse(bq, a):
    e = refus(Refus.SOURCE_MANQUANTE, salaire_base, S, None, "directeur_1", a, "2022-01-01")
    assert "33" in e.message_fr and "47" in e.message_fr


def test_degre_19_juste_avant_33_ans(bq):
    assert salaire_base(S, None, "directeur_1", 32.9, "2022-01-01").detail["degre"] == 19


def test_avant_le_2020_09_01_refuse(bq):
    refus(Refus.SOURCE_MANQUANTE, salaire_base, S, None, "commis_1", 6, "2020-08-31")


def test_dates_des_deux_tables(bq):
    assert salaire_base(S, None, "commis_1", 6, "2021-04-30").detail["table_id"] == "BQ_TOUS_AGENTS_2020-09-01"
    assert salaire_base(S, None, "commis_1", 6, "2021-05-01").detail["table_id"] == "BQ_TOUS_AGENTS_2021-05-01"
    assert salaire_base(S, None, "commis_1", 6, "2030-01-01").detail["table_id"] == "BQ_TOUS_AGENTS_2021-05-01"


def test_hypotheses_affichees(bq):
    r = salaire_base(S, None, "agent_suivi_1", 0.5, "2025-01-01")
    h = r.detail["hypotheses"]
    assert len(h) == 4 == len(r.detail["hypotheses_ar"])
    assert any("2021-05-01" in x for x in h) and any("article 11 (p.8)" in x for x in h)
    assert any("renouvelable une fois" in x and "pendant le renouvellement" in x for x in h)


def test_categorie_inconnue(bq):
    e = refus(Refus.PARAM_INVALIDE, salaire_base, S, None, "agent_services_4", 5.5, "2022-01-01")
    assert e.message_fr.startswith("Catégorie inconnue")


# --- primes : toutes non couvertes ---------------------------------------------------------------------------


@pytest.mark.parametrize("code", sorted(REEL["primes_non_couvertes"]))
def test_prime_non_couverte_refusee_avec_raison(bq, code):
    bloc = REEL["primes_non_couvertes"][code]
    e = refus(Refus.SOURCE_MANQUANTE, prime, S, code, "2022-01-01")
    assert (e.message_fr, e.message_ar) == (bloc["message_fr"], bloc["message_ar"]) and bloc["motif"]


def test_liste_des_primes_non_couvertes():
    assert REEL["primes"] == []
    assert {c: (b["source_article"], b["source_pdf_page"]) for c, b in REEL["primes_non_couvertes"].items()} == {
        "prime_transport": ("49", 20),
        "prime_representation": ("50", 20),
        "prime_13e_mois": ("51", 20),
        "prime_production": ("52", 20),
        "prime_bilan": ("53", 20),
        "prime_depart_retraite": ("54 (جديد)", 21),
        "prime_fonction_superieure": ("16", 12),
        "prime_travail_sous_terre": ("21", 13),
    }
    m = REEL["primes_non_couvertes"]["prime_travail_sous_terre"]["message_fr"]
    assert "travail continu sous terre" in m and "prime fixée par décision de l'employeur" in m
    assert "l'alinéa sur les agents qui travaillent sous terre" in m and "alinéa 8" not in m and "9e" not in m
