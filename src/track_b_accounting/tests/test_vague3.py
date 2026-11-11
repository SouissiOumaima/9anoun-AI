"""Grilles de la vague 3 (D61 à D66) : mécanique et stations-service, boissons alcoolisées, bois et ameublement,
gestion des déchets, habillement, commerce de gros et de détail.
Lancer depuis la racine du dépôt : pytest src/track_b_accounting/tests/test_vague3.py

Les valeurs attendues viennent de la double lecture des tableaux et des articles de primes (cas vérifiés par
DS5 sur les images, voir D61 à D66) ; elles sont écrites ici, pas relues dans data/processed/. Fichiers réels (activés par D61 à D66).
"""

import copy
from decimal import Decimal

import pytest
from conftest import lire_json

from track_b_accounting.calc import Refus, loaders, prime, salaire_base

MEC, ALC, BOIS = "MECANIQUE_STATIONS_SERVICE", "BOISSONS_ALCOOLISEES", "BOIS_AMEUBLEMENT_LIEGE"
DECH, HAB, COM = "GESTION_DECHETS", "HABILLEMENT", "COMMERCE_GROS_DETAIL"
FICHIERS = {
    MEC: ("mecanique_stations_service.json", "D61", 720, 3),
    ALC: ("boissons_alcoolisees.json", "D62", 720, 6),
    BOIS: ("bois_ameublement_liege.json", "D63", 819, 6),
    DECH: ("gestion_dechets.json", "D64", 836, 4),
    HAB: ("habillement.json", "D65", 864, 4),
    COM: ("commerce_gros_detail.json", "D66", 897, 6),
}
REEL = {s: lire_json(f"data/processed/salary_grids/{f}") for s, (f, *_) in FICHIERS.items()}
OUV = "ouvrier_horaire_ligne_imprimee"


def refus(code, f, *a, **k):
    with pytest.raises(Refus) as e:
        f(*a, **k)
    assert e.value.code == code and e.value.message_fr and e.value.message_ar
    return e.value


# --- activation, structure ---------------------------------------------------------------------------------


@pytest.mark.parametrize("s", FICHIERS)
def test_activation_registre_et_decision(s):
    fichier, ref, _, _ = FICHIERS[s]
    g = REEL[s]
    assert g["_meta"]["secteur_code"] == s and g["_meta"]["decision_ref"] == ref
    assert loaders.GRILLES[s] == f"data/processed/salary_grids/{fichier}" and s in loaders.secteurs_disponibles()
    loaders.valider_grille(copy.deepcopy(g), fichier)
    assert (loaders.REPO_ROOT / g["_meta"]["source_file"]).is_file()


@pytest.mark.parametrize("s", FICHIERS)
def test_nombre_de_cellules_et_de_tableaux_imprimes(s):
    _, _, n, tables = FICHIERS[s]
    g = REEL[s]
    assert sum(len(v) for t in g["grilles"] for v in t["valeurs"].values()) == n
    assert len({t["numero_imprime"] for t in g["grilles"]}) == tables


def test_seules_les_treize_cases_illisibles_des_dechets_sont_null():
    nulles = sorted(
        (s, t["table_id"], c, i)
        for s, g in REEL.items()
        for t in g["grilles"]
        for c, v in t["valeurs"].items()
        for i, x in enumerate(v, 1)
        if x is None
    )
    attendu = [("DECH_TOUS_AGENTS_2020-05-01", c) for c in ("10", "11")]
    attendu += [("DECH_TOUS_AGENTS_2021-12-01", c) for c in ("13", "14", "16")]
    attendu += [("DECH_TOUS_AGENTS_2023-01-01", c) for c in ("3", "11", "13", "14")]
    attendu += [("DECH_TOUS_AGENTS_2024-01-01", c) for c in ("8", "13", "16", "18")]
    assert nulles == sorted((DECH, t, c, 9) for t, c in attendu)


def test_champs_d48_et_regles_au_dela():
    assert not any("anciennetes_refusees" in g for g in REEL.values())
    assert not any("valide_jusqu_au" in t for g in REEL.values() for t in g["grilles"])
    cases = [
        (s, p, len(b["cases_refusees"]))
        for s, g in REEL.items()
        for p, b in g["au_dela_dernier_degre"].items()
        if "cases_refusees" in b
    ]
    assert cases == [(COM, "agents", 36), (COM, "chefs_rayon_gerants", 30)]
    for s, debut, duree in ((BOIS, 26, 1), (DECH, 24, 2)):
        for b in REEL[s]["au_dela_dernier_degre"].values():
            assert b["regle"] == "table_correspondance" and b["table_correspondance"] == {}
            assert (b["dernier_degre_atteint_a_annees"], b["duree_au_dernier_degre_annees"]) == (debut, duree)


# --- montants lus (ligne depuis le haut, degré depuis la droite) ---------------------------------------------


@pytest.mark.parametrize(
    "s,pop,cat,sous,anc,date,attendu,unite",
    [
        (MEC, None, "1", None, 1, "2021-12-01", "2.737", "TND/heure"),  # T1 p.22 l.1 d.1
        (MEC, "tous_agents", "8", None, 9, "2023-06-01", "4.600", "TND/heure"),  # T2 p.23 l.8 d.5
        (MEC, None, "16", None, 29, "2024-06-01", "11.096", "TND/heure"),  # T3 p.24 l.16 d.15
        (ALC, "mensuels", "I", None, 0.5, "2021-12-01", "647.542", "TND/mois"),  # T1 p.21 l.1 d.1
        (ALC, "horaires", "aide_ouvrier", None, 6, "2023-06-01", "4.486", "TND/heure"),  # T4 p.22 l.3 d.4
        (ALC, "mensuels", "X", None, 33, "2024-06-01", "1735.548", "TND/mois"),  # T5 p.23 l.10 d.15
        (BOIS, "mensuels", "1", None, 0.5, "2021-12-01", "572.840", "TND/mois"),  # T1 p.24 l.1 d.1
        (BOIS, "horaires", "7", None, 8, "2023-06-01", "5.045", "TND/heure"),  # T4 p.25 l.7 d.6
        (BOIS, "mensuels", "14", None, 26.5, "2024-06-01", "2041.817", "TND/mois"),  # T5 p.26 l.14 d.13
        (DECH, None, "1", None, 1, "2020-06-01", "628.015", "TND/mois"),  # T1 p.16 l.1 d.1
        (DECH, None, "8", None, 5, "2022-01-01", "1005.925", "TND/mois"),  # T2 p.17 l.8 d.3 (imprimé tel quel)
        (DECH, None, "15", None, 19, "2022-01-01", "1367.052", "TND/mois"),  # T2 p.17 l.15 d.9 (tranché au zoom)
        (DECH, None, "10", None, 13, "2023-06-01", "1088.774", "TND/mois"),  # T3 p.18 l.10 d.7
        (DECH, None, "9", None, 19, "2024-06-01", "1149.697", "TND/mois"),  # T4 p.19 l.9 d.9 (tranché au zoom)
        (DECH, "tous_agents", "19", None, 25, "2024-06-01", "2027.015", "TND/mois"),  # T4 p.19 l.19 d.11
        (HAB, "horaires", "I", None, 0.5, "2021-09-01", "2.501", "TND/heure"),  # T1 p.26 l.1 d.1
        (HAB, "mensuels", "1", "b", 16, "2022-06-01", "596.584", "TND/mois"),  # T4 p.29 l.2 d.10
        (HAB, "mensuels", "15", None, 16, "2022-06-01", "1114.395", "TND/mois"),  # T4 p.29 l.16 d.10 (écart tranché)
        (HAB, "mensuels", "17", None, 32, "2024-06-01", "1299.625", "TND/mois"),  # T4 p.29 l.18 d.18
        (COM, "agents", OUV, None, 1, "2021-12-01", "588.841", "TND/mois"),  # T1 p.22 l.1 d.1
        (COM, "agents", "21", None, 25, "2024-06-01", "1442.120", "TND/mois"),  # T5 p.26 l.13 d.13
        (COM, "chefs_rayon_gerants", "17", "e", 1, "2023-06-01", "845.498", "TND/mois"),  # T4 p.25 l.10 d.1
        (COM, "chefs_rayon_gerants", "16", "a", 25, "2021-12-01", "880.745", "TND/mois"),  # T2 p.23 l.1 d.13
    ],
)
def test_montants_lus(ok, s, pop, cat, sous, anc, date, attendu, unite):
    r = ok(salaire_base(s, pop, cat, anc, date, sous_categorie=sous))
    assert (r.montant, r.unite) == (Decimal(attendu), unite) and r.citations[0].decision_ref == FICHIERS[s][1]


# --- règles ---------------------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "s,pop,cat,sous,a",
    [
        (MEC, None, "1", None, 2),
        (ALC, "mensuels", "I", None, 1),
        (ALC, "horaires", "aide_ouvrier", None, 31),
        (BOIS, "mensuels", "1", None, 3),
        (BOIS, "horaires", "1", None, 26),
        (DECH, None, "1", None, 12),
        (DECH, None, "1", None, 24),
        (HAB, "horaires", "I", None, 3),
        (COM, "agents", "10", None, 2),
        (COM, "chefs_rayon_gerants", "16", "a", 24),
    ],
)
def test_bornes_exactes_refusees(s, pop, cat, sous, a):
    refus(Refus.PARAM_INVALIDE, salaire_base, s, pop, cat, a, "2024-06-01", sous_categorie=sous)


@pytest.mark.parametrize(
    "s,pop,cat,a,limite",
    [
        (MEC, None, "16", 30, 30),
        (ALC, "mensuels", "X", 34, 34),
        (ALC, "horaires", "ouvrier_hautement_qualifie", 40, 34),
        (HAB, "horaires", "VI", 33, 33),
        (HAB, "mensuels", "17", 35.5, 33),
    ],
)
def test_refus_au_dela_du_dernier_degre(s, pop, cat, a, limite):
    e = refus(Refus.SOURCE_MANQUANTE, salaire_base, s, pop, cat, a, "2024-06-01")
    assert f"moins de {limite} ans" in e.message_fr


@pytest.mark.parametrize(
    "s,pop,cat,palier,pages",
    [
        (BOIS, "mensuels", "14", 27, ("page 9", "page 16", "pages 24 à 26")),
        (BOIS, "horaires", "7", 27, ("page 9", "page 16", "pages 24 à 26")),
        (DECH, None, "19", 26, ("page 6", "pages 16 à 19")),
    ],
)
def test_dernier_degre_contredit_par_l_article(s, pop, cat, palier, pages):
    assert salaire_base(s, pop, cat, palier - 0.5, "2024-06-01").detail["degre"] == len(
        REEL[s]["degres"]["tous_agents" if pop is None else pop]
    )
    refus(Refus.PARAM_INVALIDE, salaire_base, s, pop, cat, palier, "2024-06-01")
    for a in (palier + 0.5, 40):
        e = refus(Refus.SOURCE_MANQUANTE, salaire_base, s, pop, cat, a, "2024-06-01")
        assert all(p in e.message_fr for p in pages)


@pytest.mark.parametrize(
    "a,date,attendu",
    [
        (27, "2024-06-01", "1458.806"),  # T5 p.26 l.13 : 1442.120 + 1 × (1442.120 − 1425.434)
        (29.5, "2024-06-01", "1475.492"),  # n = 2
        (30.5, "2022-06-01", "1334.585"),  # T1 p.22 l.13 : 1284.527 + 3 × (1284.527 − 1267.841)
    ],
)
def test_commerce_ecart_categorie_21(ok, a, date, attendu):
    r = ok(salaire_base(COM, "agents", "21", a, date))
    assert r.montant == Decimal(attendu) and r.detail["regle_art13"] == "ecart_cumule_biennal"


def test_commerce_autres_categories_refusees_apres_26_ans():
    for pop, cat, sous in (("agents", OUV, None), ("agents", "20", None), ("chefs_rayon_gerants", "17", "a")):
        assert salaire_base(COM, pop, cat, 25, "2024-06-01", sous_categorie=sous).detail["degre"] == 13
        e = refus(Refus.SOURCE_MANQUANTE, salaire_base, COM, pop, cat, 27, "2024-06-01", sous_categorie=sous)
        assert "article 12 (جديد) أ (page 8)" in e.message_fr
    for a in (26, 28):
        refus(Refus.PARAM_INVALIDE, salaire_base, COM, "agents", "21", a, "2024-06-01")


def test_commerce_ligne_horaire_et_populations():
    r = salaire_base(COM, "agents", OUV, 1, "2024-06-01")
    assert any("شهريا" in h and "unité n'est pas imprimée" in h for h in r.detail["hypotheses"])
    refus(Refus.PARAM_INVALIDE, salaire_base, COM, None, "16", 1, "2024-06-01")
    refus(Refus.PARAM_INVALIDE, salaire_base, COM, "chefs_rayon_gerants", "16", 1, "2024-06-01")  # sous-niveau


def test_unites_non_imprimees_en_hypothese():
    for s, mot in ((MEC, "horaires"), (DECH, "mensuels"), (COM, "mensuels")):
        r = salaire_base(s, "agents" if s == COM else None, "10", 1, "2024-06-01")
        assert any("n'impriment pas l'unité" in h and mot in h for h in r.detail["hypotheses"])


@pytest.mark.parametrize(
    "date,cat,page",
    [
        ("2020-06-01", "10", 16),
        ("2020-06-01", "11", 16),
        ("2022-06-01", "13", 17),
        ("2022-06-01", "14", 17),
        ("2022-06-01", "16", 17),
        ("2023-06-01", "3", 18),
        ("2023-06-01", "11", 18),
        ("2023-06-01", "13", 18),
        ("2023-06-01", "14", 18),
        ("2024-06-01", "8", 19),
        ("2024-06-01", "13", 19),
        ("2024-06-01", "16", 19),
        ("2024-06-01", "18", 19),
    ],
)
def test_dechets_cases_illisibles(date, cat, page):
    e = refus(Refus.SOURCE_MANQUANTE, salaire_base, DECH, None, cat, 19, date)
    assert f"catégorie {cat}, degré 9" in e.message_fr and f"page {page}" in e.message_fr


@pytest.mark.parametrize(
    "s,pop,cat,sous,veille,premiere",
    [
        (MEC, None, "1", None, "2021-11-30", "2021-12-01"),
        (ALC, "mensuels", "I", None, "2021-11-30", "2021-12-01"),
        (BOIS, "horaires", "1", None, "2021-11-30", "2021-12-01"),
        (DECH, None, "1", None, "2020-04-30", "2020-05-01"),
        (HAB, "mensuels", "1", "a", "2021-08-31", "2021-09-01"),
        (COM, "agents", "10", None, "2021-11-30", "2021-12-01"),
    ],
)
def test_avant_la_premiere_table_refuse(s, pop, cat, sous, veille, premiere):
    e = refus(Refus.SOURCE_MANQUANTE, salaire_base, s, pop, cat, 0.5, veille, sous_categorie=sous)
    assert f"première date d'effet disponible : {premiere}" in e.message_fr


@pytest.mark.parametrize("s,cat", [(ALC, "I"), (BOIS, "1"), (HAB, "I"), (COM, "10")])
def test_population_obligatoire(s, cat):
    refus(Refus.PARAM_INVALIDE, salaire_base, s, None, cat, 0.5, "2024-06-01")


# --- primes ---------------------------------------------------------------------------------------------------

C = {"condition_remplie": True}
EG, CA = {"groupe": "execution_gestion"}, {"groupe": "cadres"}
PRIMES = [
    (MEC, "prime_transport", "2022-06-01", EG, "57.004"),
    (MEC, "prime_transport", "2024-06-01", CA, "72.693"),
    (MEC, "prime_presence", "2023-06-01", CA, "14.603"),
    (MEC, "prime_fonction_directeur_general_adjoint", "2023-06-01", C, "50.000"),
    (MEC, "prime_fonction_secretaire_general_directeur", "2023-06-01", C, "40.000"),
    (MEC, "prime_fonction_sous_directeur", "2023-06-01", C, "35.000"),
    (MEC, "prime_fonction_chef_service", "2023-06-01", C, "25.000"),
    (MEC, "prime_continuite_travail", "2023-06-01", C, "0.500"),
    (MEC, "prime_specifique", "2023-06-01", C, "4.000"),
    (ALC, "prime_presence", "2023-06-01", {}, "15.647"),
    (ALC, "prime_transport", "2022-06-01", {"groupe": "execution"}, "62.433"),
    (ALC, "prime_transport", "2024-06-01", {"groupe": "cadres_superieurs"}, "78.879"),
    (ALC, "prime_logement", "2023-06-01", {"groupe": "gestion_moyenne"}, "13.039"),
    (ALC, "prime_rentree_scolaire_base_1_6", "2023-06-01", C, "20.000"),
    (ALC, "prime_rentree_scolaire_base_7_secondaire", "2023-06-01", C, "30.000"),
    (ALC, "prime_rentree_scolaire_superieur", "2023-06-01", C, "30.000"),
    (ALC, "prime_responsabilite", "2023-06-01", C, "50.000"),
    (ALC, "prime_haute_specialisation", "2023-06-01", C, "15.000"),
    (BOIS, "prime_transport", "2023-06-01", {}, "100.211"),
    (BOIS, "prime_panier", "2023-06-01", C, "0.650"),
    (BOIS, "prime_presence", "2024-06-01", C, "20.106"),
    (BOIS, "prime_deplacement_transport_rayon_40km", "2023-06-01", C, "1.000"),
    (BOIS, "prime_deplacement_transport_au_dela_40km", "2023-06-01", C, "2.000"),
    (BOIS, "prime_deplacement_petit_dejeuner", "2023-06-01", C, "1.000"),
    (BOIS, "prime_deplacement_diner", "2023-06-01", C, "3.000"),
    (BOIS, "prime_deplacement_nuitee", "2023-06-01", C, "9.000"),
    (BOIS, "prime_chauffeurs_petit_dejeuner", "2023-06-01", C, "1.000"),
    (BOIS, "prime_chauffeurs_diner", "2023-06-01", C, "3.000"),
    (BOIS, "prime_chauffeurs_nuitee", "2023-06-01", C, "7.000"),
    (BOIS, "prime_caisse_degre_1", "2023-06-01", C, "6.000"),
    (BOIS, "prime_caisse_degre_2", "2023-06-01", C, "10.000"),
    (BOIS, "prime_risque", "2023-06-01", C, "11.000"),
    (DECH, "prime_presence", "2021-11-30", {}, "16.652"),
    (DECH, "prime_presence", "2024-06-01", {}, "20.210"),
    (DECH, "prime_transport", "2022-06-01", {}, "54.546"),
    (DECH, "prime_panier", "2023-06-01", C, "25.000"),
    (DECH, "prime_risque", "2023-06-01", C, "50.000"),
    (DECH, "prime_proprete_savon", "2023-06-01", C, "70.000"),
    (HAB, "prime_presence", "2022-06-01", {}, "7.446"),
    (HAB, "prime_transport", "2021-12-01", EG, "60.281"),
    (HAB, "prime_transport", "2024-06-01", CA, "71.830"),
    (COM, "prime_transport", "2023-06-01", EG, "70.269"),
    (COM, "prime_transport", "2024-06-01", CA, "82.746"),
    (COM, "prime_presence", "2022-06-01", {}, "12.400"),
    (COM, "prime_caisse_jusqu_a_5_ans", "2023-06-01", C, "5.000"),
    (COM, "prime_caisse_5_a_10_ans", "2023-06-01", C, "10.000"),
    (COM, "prime_caisse_plus_10_ans", "2023-06-01", C, "15.000"),
    (COM, "prime_scolaire_base", "2023-06-01", C, "20.000"),
    (COM, "prime_scolaire_secondaire", "2023-06-01", C, "30.000"),
    (COM, "prime_scolaire_superieur", "2023-06-01", C, "40.000"),
    (COM, "prime_deces_travailleur", "2023-06-01", C, "150.000"),
    (COM, "prime_deces_pere_mere", "2023-06-01", C, "100.000"),
]


@pytest.mark.parametrize("s,code,date,params,attendu", PRIMES, ids=[f"{p[0]}-{p[1]}-{p[2]}" for p in PRIMES])
def test_prime_couverte(ok, s, code, date, params, attendu):
    r = ok(prime(s, code, date, **params))
    assert r.montant == Decimal(attendu) and r.citations[0].decision_ref == FICHIERS[s][1]


def test_chaque_prime_couverte_est_testee():
    assert {(s, c) for s, c, *_ in PRIMES} == {(s, p["code"]) for s, g in REEL.items() for p in g["primes"]}


@pytest.mark.parametrize("s,code", [(s, c) for s, g in REEL.items() for c in g["primes_non_couvertes"]])
def test_prime_non_couverte_refusee_avec_article_et_page(s, code):
    b = REEL[s]["primes_non_couvertes"][code]
    e = refus(Refus.SOURCE_MANQUANTE, prime, s, code, "2024-06-01")
    assert f"article {b['source_article']}, page {b['source_pdf_page']}" in e.message_fr


@pytest.mark.parametrize(
    "s,code,imprime",
    [
        (ALC, "prime_panier", "416.666 م"),
        (BOIS, "aide_deces", "466.6666 د"),
        (DECH, "prime_lait", "parution de l'avenant n° 3"),
        (HAB, "prime_assiduite", "12,330 d"),
        (ALC, "prime_transport_niveau_salaire_minimum", "niveau du salaire minimum"),
        (ALC, "prime_logement_niveau_salaire_minimum", "niveau du salaire minimum"),
    ],
)
def test_primes_refusees_decidees(s, code, imprime):
    assert imprime in refus(Refus.SOURCE_MANQUANTE, prime, s, code, "2024-06-01").message_fr


def test_conditions_et_dates_des_primes():
    refus(Refus.HORS_SCOPE, prime, BOIS, "prime_panier", "2023-06-01", condition_remplie=False)
    refus(Refus.SOURCE_MANQUANTE, prime, DECH, "prime_transport", "2020-04-30")
    refus(Refus.SOURCE_MANQUANTE, prime, HAB, "prime_presence", "2021-08-31")
    refus(Refus.PARAM_INVALIDE, prime, ALC, "prime_logement", "2023-06-01", groupe="niveau_salaire_minimum")


def test_table_des_secteurs_inchangee_et_exemption():
    table = lire_json("src/shared/sectors/sectors.v0.json")
    assert not {s.get("ds5_code") for s in table["sectors"]} & set(FICHIERS)
