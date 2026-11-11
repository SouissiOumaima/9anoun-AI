"""Grilles de la vague 1 (D49 à D54) : torréfaction du café, agences de voyages, hôtels touristiques, confiserie,
pâtes alimentaires et couscous, cosmétiques et parfums.
Lancer depuis la racine du dépôt : pytest src/track_b_accounting/tests/test_vague1.py

Les valeurs attendues viennent de la double lecture des tableaux et des articles de primes (lots validés par DS5) ;
elles sont écrites ici, pas relues dans data/processed/. Fichiers réels (activés par D49 à D54).
"""

import copy
from decimal import Decimal

import pytest
from conftest import lire_json

from track_b_accounting.calc import Refus, loaders, prime, salaire_base

CAFE, VOY, HOT = "TORREFACTION_CAFE", "AGENCES_VOYAGES", "HOTELS_TOURISTIQUES"
CONF, PAT, COSM = "CONFISERIE_BISCUITERIE_CHOCOLATERIE", "PATES_ALIMENTAIRES_COUSCOUS", "COSMETIQUES_PARFUMS"
FICHIERS = {
    CAFE: ("torrefaction_cafe.json", "D49", 195, 3),
    VOY: ("agences_voyages.json", "D50", 260, 2),
    HOT: ("hotels_touristiques.json", "D51", 260, 2),
    CONF: ("confiserie_biscuiterie.json", "D52", 450, 6),
    PAT: ("pates_alimentaires.json", "D53", 504, 6),
    COSM: ("cosmetiques_parfums.json", "D54", 507, 9),
}
REEL = {s: lire_json(f"data/processed/salary_grids/{f}") for s, (f, *_) in FICHIERS.items()}


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
    assert (
        g["_meta"]["source_file"].startswith("data/raw/pdf/")
        and (loaders.REPO_ROOT / g["_meta"]["source_file"]).is_file()
    )


@pytest.mark.parametrize("s", FICHIERS)
def test_nombre_de_cellules_et_de_tables_imprimees(s):
    _, _, n, tables = FICHIERS[s]
    g = REEL[s]
    cellules = sum(len(v) if isinstance(v, list) else 1 for t in g["grilles"] for v in t["valeurs"].values())
    assert cellules == n and len({t["numero_imprime"] for t in g["grilles"]}) == (6 if s == COSM else tables)


def test_seules_les_cases_illisibles_sont_null():
    nulles = {
        s: sorted(
            (t["table_id"], c, i)
            for t in g["grilles"]
            for c, v in t["valeurs"].items()
            if isinstance(v, list)
            for i, x in enumerate(v, 1)
            if x is None
        )
        for s, g in REEL.items()
    }
    assert nulles == {
        CAFE: [],
        VOY: [],
        HOT: [],
        PAT: [],
        CONF: [
            ("CONF_MENSUELS_2021-12-01", "2", 8),
            ("CONF_MENSUELS_2021-12-01", "3", 8),
            ("CONF_MENSUELS_2021-12-01", "5", 8),
            ("CONF_MENSUELS_2024-01-01", "2", 8),
            ("CONF_MENSUELS_2024-01-01", "3", 8),
            ("CONF_MENSUELS_2024-01-01", "6", 8),
        ],
        COSM: [("COSM_ADMINISTRATIFS_2021-12-01", "6", 8)],
    }


def test_champs_optionnels_seulement_ou_decides():
    """anciennetes_refusees : confiserie seule ; cases_refusees : confiserie, mensuels, une case ; null : 7 cases."""
    assert [s for s, g in REEL.items() if "anciennetes_refusees" in g] == [CONF]
    cases = [
        (s, p, c["table_id"], c["categorie"])
        for s, g in REEL.items()
        for p, b in g["au_dela_dernier_degre"].items()
        for c in b.get("cases_refusees", [])
    ]
    assert cases == [(CONF, "mensuels", "CONF_MENSUELS_2021-12-01", "2")]


# --- montants lus (ligne depuis le haut, degré depuis la droite) ---------------------------------------------


@pytest.mark.parametrize(
    "s,pop,cat,sous,anc,date,attendu,unite",
    [
        (CAFE, None, "1", None, 1, "2021-12-01", "2.961", "TND/heure"),  # T1 p.17 l.1 d.1
        (CAFE, "ouvriers_horaires", "5", None, 25, "2023-06-01", "4.565", "TND/heure"),  # T2 p.17 l.5 d.13
        (CAFE, None, "3", None, 5, "2024-06-01", "4.073", "TND/heure"),  # T3 p.18 l.3 d.3
        (VOY, None, "1", None, 0.5, "2022-05-01", "504.153", "TND/mois"),  # T1 p.18 l.1 d.1
        (VOY, None, "10", None, 27, "2022-06-01", "1252.375", "TND/mois"),  # T1 p.18 l.10 d.12
        (VOY, "tous_agents", "6", None, 30, "2023-06-01", "1046.082", "TND/mois"),  # T2 p.19 l.6 d.13 (ouvert)
        (HOT, None, "direction_1", None, 0.5, "2022-05-01", "1068.292", "TND/mois"),  # T1 p.43 l.1 d.1
        (HOT, None, "services", None, 2, "2022-06-01", "516.375", "TND/mois"),  # T1 p.43 l.10 d.2
        (HOT, None, "cadre_1", None, 10, "2023-06-01", "1319.652", "TND/mois"),  # T2 p.44 l.1 d.6 (alias)
        (CONF, "mensuels", "1", None, 0.5, "2021-12-01", "609.208", "TND/mois"),  # T1 p.21 l.1 d.1
        (CONF, "mensuels", "2", None, 27, "2022-06-01", "590.535", "TND/mois"),  # T1 p.21 l.2 d.15 (anomalie)
        (CONF, "horaires", "4", None, 25, "2022-06-01", "3.849", "TND/heure"),  # T2 p.21 l.4 d.14
        (CONF, "horaires", "2", None, 11, "2023-06-01", "3.417", "TND/heure"),  # T4 p.22 l.2 d.7
        (PAT, "horaires", "I", "1", 0.5, "2021-12-01", "3.492", "TND/heure"),  # T1 p.19 l.1 d.1
        (PAT, "mensuels", "III", "a", 0.5, "2021-12-01", "684.958", "TND/mois"),  # T2 p.19 l.1 d.1
        (PAT, "mensuels", "V", "III", 23, "2021-12-01", "986.195", "TND/mois"),  # T2 p.19 l.8 d.12
        (PAT, "horaires", "III", "2", 6, "2024-06-01", "4.715", "TND/heure"),  # T5 p.21 l.6 d.4
        (COSM, "administratifs", "1", None, 0.5, "2021-12-01", "506.799", "TND/mois"),  # T1 p.21 l.1 d.1
        (COSM, "administratifs", "9", None, 27, "2021-12-01", "1080.809", "TND/mois"),  # T1 p.21 l.9 d.12
        (COSM, "production", "2", None, 0.5, "2021-12-01", "551.453", "TND/mois"),  # T2 p.21 l.2 d.1
        (COSM, "production_categorie_1", "1", None, 0.5, "2021-12-01", "505.233", "TND/mois"),  # T2 p.21 l.1 unique
        (COSM, "administratifs", "9", None, 30, "2024-06-01", "1216.807", "TND/mois"),  # T5 p.23 l.9 d.12 (ouvert)
    ],
)
def test_montants_lus(ok, s, pop, cat, sous, anc, date, attendu, unite):
    r = ok(salaire_base(s, pop, cat, anc, date, sous_categorie=sous))
    assert (r.montant, r.unite) == (Decimal(attendu), unite)
    assert r.citations[0].decision_ref == FICHIERS[s][1]


# --- règles ---------------------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "s,pop,cat,sous,a",
    [
        (CAFE, None, "3", None, 4),
        (CAFE, None, "3", None, 24),
        (VOY, None, "2", None, 1),
        (VOY, None, "2", None, 28),
        (HOT, None, "services", None, 3),
        (HOT, None, "services", None, 27),
        (CONF, "mensuels", "1", None, 2),
        (CONF, "horaires", "1", None, 4),
        (PAT, "horaires", "I", "1", 19),
        (COSM, "production", "2", None, 26),
    ],
)
def test_bornes_exactes_refusees(s, pop, cat, sous, a):
    refus(Refus.PARAM_INVALIDE, salaire_base, s, pop, cat, a, "2024-06-01", sous_categorie=sous)


@pytest.mark.parametrize("s,a", [(CAFE, 26), (CAFE, 40), (HOT, 30), (HOT, 35)])
def test_refus_au_dela_du_dernier_degre(s, a):
    cat = "1" if s == CAFE else "services"
    e = refus(Refus.SOURCE_MANQUANTE, salaire_base, s, None, cat, a, "2024-06-01")
    assert f"Ancienneté de {a} ans" in e.message_fr


@pytest.mark.parametrize(
    "s,pop,cat,anc", [(VOY, None, "1", 45), (COSM, "administratifs", "1", 45), (COSM, "production", "6", 45)]
)
def test_dernier_degre_ouvert_servi(ok, s, pop, cat, anc):
    r = ok(salaire_base(s, pop, cat, anc, "2024-06-01"))
    assert r.detail["degre"] == len(REEL[s]["degres"][pop or "tous_agents"])


@pytest.mark.parametrize(
    "s,pop,cat,sous,date",
    [
        (CAFE, None, "1", None, "2021-11-30"),
        (VOY, None, "1", None, "2022-04-30"),
        (HOT, None, "services", None, "2022-04-30"),
        (CONF, "mensuels", "1", None, "2021-11-30"),
        (CONF, "horaires", "1", None, "2021-11-30"),
        (PAT, "horaires", "I", "1", "2021-11-30"),
        (PAT, "mensuels", "IV", "I", "2021-11-30"),
        (COSM, "administratifs", "1", None, "2021-11-30"),
        (COSM, "production", "2", None, "2021-11-30"),
        (COSM, "production_categorie_1", "1", None, "2021-11-30"),
    ],
)
def test_avant_la_premiere_table_refuse(s, pop, cat, sous, date):
    e = refus(Refus.SOURCE_MANQUANTE, salaire_base, s, pop, cat, 0.5, date, sous_categorie=sous)
    assert "première date d'effet disponible" in e.message_fr


@pytest.mark.parametrize("s,cat", [(CONF, "1"), (PAT, "III"), (COSM, "2")])
def test_population_obligatoire(s, cat):
    e = refus(Refus.PARAM_INVALIDE, salaire_base, s, None, cat, 0.5, "2024-06-01")
    assert e.message_fr.startswith(f"Population obligatoire pour le secteur {s}")


@pytest.mark.parametrize("s", [CAFE, VOY, HOT])
def test_population_unique_facultative(s):
    pop, cat = next(iter(REEL[s]["categories"].items()))
    assert (
        salaire_base(s, None, cat[0], 0.5, "2024-06-01").montant
        == salaire_base(s, pop, cat[0], 0.5, "2024-06-01").montant
    )


def test_cafe_employes_mensuels_non_couverts_et_hypothese_d_unite():
    e = refus(Refus.SOURCE_MANQUANTE, salaire_base, CAFE, "employes_mensuels", "3", 5, "2024-06-01")
    assert "page 16" in e.message_fr and "aucun tableau de salaires mensuels" in e.message_fr
    r = salaire_base(CAFE, None, "3", 5, "2024-06-01")
    assert r.unite == "TND/heure" and any("TND/heure" in h for h in r.detail["hypotheses"])


def test_voyages_regime_48h_et_hypothese_article_13():
    r = salaire_base(VOY, None, "6", 30, "2023-06-01")
    assert r.detail["regime_hebdomadaire_heures"] == 48 and any("13 (جديد)" in h for h in r.detail["hypotheses"])


def test_hotels_alias_et_5_etoiles():
    a = salaire_base(HOT, None, "cadre_2", 4, "2023-06-01")
    assert a.montant == salaire_base(HOT, None, "direction_2", 4, "2023-06-01").montant
    assert a.detail["categorie_demandee"] == "cadre_2"
    e = refus(Refus.SOURCE_MANQUANTE, salaire_base, HOT, "hotels_5_etoiles", "services", 2, "2023-06-01")
    assert "pages 43 et 44" in e.message_fr and "10 %" in e.message_fr


@pytest.mark.parametrize(
    "pop,cat,a,attendu",
    [
        ("mensuels", "4", 31, "922.919"),  # T5 p.23 l.4 : 917.717 + 2 × (917.717 − 915.116)
        ("mensuels", "1", 28.5, "716.512"),  # T5 p.23 l.1 : 714.525 + 1 × (714.525 − 712.538)
    ],
)
def test_confiserie_ecart_art_14(ok, pop, cat, a, attendu):
    r = ok(salaire_base(CONF, pop, cat, a, "2024-06-01"))
    assert r.montant == Decimal(attendu) and len(r.citations) == 2 and r.citations[1].page == 7
    refus(Refus.PARAM_INVALIDE, salaire_base, CONF, pop, cat, 28, "2024-06-01")  # palier


@pytest.mark.parametrize("pop", ["mensuels", "horaires"])
@pytest.mark.parametrize("a", [4.01, 4.5, 5])
def test_confiserie_art_53_de_4_a_5_ans_refuse(pop, a):
    e = refus(Refus.SOURCE_MANQUANTE, salaire_base, CONF, pop, "1", a, "2023-06-01")
    assert "article 53 (page 14)" in e.message_fr and "pages 21 à 23" in e.message_fr


def test_confiserie_art_53_bornes():
    refus(Refus.PARAM_INVALIDE, salaire_base, CONF, "mensuels", "1", 4, "2023-06-01")  # borne imprimée
    assert salaire_base(CONF, "mensuels", "1", 3.9, "2023-06-01").detail["degre"] == 3
    assert salaire_base(CONF, "mensuels", "1", 5.1, "2023-06-01").detail["degre"] == 4


@pytest.mark.parametrize(
    "table_date,cat",
    [
        ("2022-06-01", "2"),
        ("2022-06-01", "3"),
        ("2022-06-01", "5"),
        ("2024-06-01", "2"),
        ("2024-06-01", "3"),
        ("2024-06-01", "6"),
    ],
)
def test_confiserie_cases_illisibles(table_date, cat):
    e = refus(Refus.SOURCE_MANQUANTE, salaire_base, CONF, "mensuels", cat, 13, table_date)
    assert f"catégorie {cat}, degré 8" in e.message_fr and "page" in e.message_fr
    assert salaire_base(CONF, "mensuels", cat, 13, "2023-06-01").montant > 0  # même case en 2023 : lue


def test_confiserie_ecart_negatif_refuse_pour_une_seule_case():
    e = refus(Refus.SOURCE_MANQUANTE, salaire_base, CONF, "mensuels", "2", 29, "2022-06-01")
    assert "page 21" in e.message_fr and "590,535" in e.message_fr
    assert salaire_base(CONF, "mensuels", "2", 29, "2023-06-01").detail["n_paliers"] == 1
    assert salaire_base(CONF, "mensuels", "3", 29, "2022-06-01").detail["n_paliers"] == 1


def test_pates_ecart_art_14_et_sous_categorie():
    r = salaire_base(PAT, "mensuels", "V", 28.5, "2023-06-01", sous_categorie="III")
    assert r.montant == Decimal("1057.025") and r.detail["n_paliers"] == 2 and r.citations[1].page == 8
    refus(Refus.PARAM_INVALIDE, salaire_base, PAT, "mensuels", "IV", 6, "2023-06-01")
    refus(Refus.PARAM_INVALIDE, salaire_base, PAT, "horaires", "I", 25, "2024-06-01", sous_categorie="1")


def test_cosmetiques_categorie_1_production():
    assert salaire_base(COSM, "production_categorie_1", "1", 0.9, "2024-06-01").montant > 0
    for a in (1, 2):
        e = refus(Refus.SOURCE_MANQUANTE, salaire_base, COSM, "production_categorie_1", "1", a, "2024-06-01")
        assert "article 49 (page 15)" in e.message_fr
    refus(Refus.PARAM_INVALIDE, salaire_base, COSM, "production", "1", 0.5, "2024-06-01")


def test_cosmetiques_case_illisible():
    e = refus(Refus.SOURCE_MANQUANTE, salaire_base, COSM, "administratifs", "6", 15, "2022-06-01")
    assert "catégorie 6, degré 8" in e.message_fr and "page 21" in e.message_fr


# --- primes ---------------------------------------------------------------------------------------------------

PRIMES = [
    (CAFE, "prime_presence", "2022-06-01", {}, "9.364"),
    (CAFE, "prime_presence", "2024-06-01", {}, "10.671"),
    (CAFE, "prime_transport", "2023-06-01", {}, "60.610"),
    (CAFE, "prime_panier", "2024-06-01", {}, "0.533"),
    (CAFE, "prime_chaleur_salete_poussiere_groupe_a", "2024-06-01", {"condition_remplie": True}, "8.333"),
    (CAFE, "prime_chaleur_salete_poussiere_groupe_b", "2024-06-01", {"condition_remplie": True}, "6.333"),
    (CAFE, "prime_scolaire_enseignement_base", "2024-06-01", {"condition_remplie": True}, "21.666"),
    (CAFE, "prime_scolaire_enseignement_secondaire", "2024-06-01", {"condition_remplie": True}, "26.666"),
    (CAFE, "prime_scolaire_enseignement_superieur", "2024-06-01", {"condition_remplie": True}, "31.666"),
    (CAFE, "prime_deces", "2024-06-01", {"condition_remplie": True}, "110.000"),
    (VOY, "prime_transport", "2022-06-01", {"groupe": "execution_gestion"}, "75.089"),
    (VOY, "prime_transport", "2023-06-01", {"groupe": "cadres"}, "86.463"),
    (VOY, "prime_presence_par_jour", "2022-06-01", {}, "0.452"),
    (VOY, "prime_presence_mensuelle", "2023-06-01", {}, "3.607"),
    (VOY, "prime_entretien", "2023-06-01", {"condition_remplie": True}, "15.000"),
    (VOY, "prime_risque", "2023-06-01", {"condition_remplie": True}, "15.000"),
    (HOT, "prime_transport", "2022-06-01", {"groupe": "services_a_superieur_2", "condition_remplie": True}, "81.952"),
    (HOT, "prime_transport", "2023-06-01", {"groupe": "superieur_1_et_cadres", "condition_remplie": True}, "93.290"),
    (HOT, "prime_presence", "2022-06-01", {}, "29.957"),
    (HOT, "prime_presence", "2023-06-01", {}, "31.905"),
    (HOT, "prime_caisse_premiers_caissiers", "2023-06-01", {"condition_remplie": True}, "21.666"),
    (HOT, "prime_caisse_caissiers", "2023-06-01", {"condition_remplie": True}, "16.666"),
    (CONF, "prime_panier", "2023-06-01", {}, "0.200"),
    (CONF, "prime_deplacement_plus_12h", "2023-06-01", {"condition_remplie": True}, "1.800"),
    (CONF, "prime_deplacement_plus_18h", "2023-06-01", {"condition_remplie": True}, "4.000"),
    (CONF, "prime_caisse", "2023-06-01", {"condition_remplie": True}, "7.000"),
    (CONF, "prime_presence", "2022-06-01", {}, "4.071"),
    (CONF, "prime_presence", "2023-06-01", {}, "4.346"),
    (CONF, "prime_presence", "2024-06-01", {}, "4.639"),
    (CONF, "prime_transport", "2022-06-01", {}, "52.479"),
    (CONF, "prime_transport", "2023-06-01", {}, "56.022"),
    (CONF, "prime_transport", "2024-06-01", {}, "59.803"),
    (PAT, "prime_deplacement_repas", "2023-06-01", {"condition_remplie": True}, "1.000"),
    (PAT, "prime_deplacement_deux_repas", "2023-06-01", {"condition_remplie": True}, "2.000"),
    (PAT, "prime_deplacement_nuitee", "2023-06-01", {"condition_remplie": True}, "2.000"),
    (PAT, "prime_panier", "2023-06-01", {}, "0.280"),
    (PAT, "prime_presence", "2024-06-01", {}, "7.856"),
    (PAT, "prime_transport", "2022-06-01", {"groupe": "categorie_1"}, "67.866"),
    (PAT, "prime_transport", "2024-06-01", {"groupe": "categorie_5"}, "92.804"),
    (PAT, "prime_logement", "2023-06-01", {"groupe": "categorie_3"}, "26.084"),
    (PAT, "prime_logement", "2024-06-01", {"groupe": "categorie_5"}, "38.145"),
    (COSM, "prime_transport", "2021-12-01", {"groupe": "execution_gestion"}, "80.981"),
    (COSM, "prime_transport", "2024-06-01", {"groupe": "execution_gestion"}, "92.283"),
    (COSM, "prime_panier", "2023-06-01", {"condition_remplie": True}, "0.875"),
    (COSM, "prime_deplacement_retour_20h", "2023-06-01", {"condition_remplie": True}, "2.000"),
    (COSM, "prime_deplacement_avec_nuitee", "2023-06-01", {"condition_remplie": True}, "7.000"),
    (COSM, "prime_scolaire", "2023-06-01", {"condition_remplie": True}, "19.833"),
    (COSM, "prime_risque", "2023-06-01", {"condition_remplie": True}, "4.000"),
    (COSM, "prime_salete", "2023-06-01", {"condition_remplie": True}, "3.500"),
    (COSM, "prime_presence", "2022-06-01", {}, "10.179"),
    (COSM, "prime_presence", "2024-06-01", {}, "11.600"),
    (COSM, "prime_caisse_caissier", "2023-06-01", {"condition_remplie": True}, "15.333"),
    (COSM, "prime_caisse_aide_caissier", "2023-06-01", {"condition_remplie": True}, "5.000"),
]


@pytest.mark.parametrize("s,code,date,params,attendu", PRIMES, ids=[f"{p[0]}-{p[1]}-{p[2]}" for p in PRIMES])
def test_prime_couverte(ok, s, code, date, params, attendu):
    r = ok(prime(s, code, date, **params))
    assert r.montant == Decimal(attendu) and r.citations[0].decision_ref == FICHIERS[s][1]
    assert r.detail["label_ar"] and r.detail["label_fr"]


def test_chaque_prime_couverte_est_testee():
    testees = {(s, c) for s, c, *_ in PRIMES}
    assert testees == {(s, p["code"]) for s, g in REEL.items() for p in g["primes"]}


@pytest.mark.parametrize("s,code", [(s, c) for s, g in REEL.items() for c in g["primes_non_couvertes"]])
def test_prime_non_couverte_refusee_avec_article_et_page(s, code):
    b = REEL[s]["primes_non_couvertes"][code]
    e = refus(Refus.SOURCE_MANQUANTE, prime, s, code, "2024-06-01")
    assert f"article {b['source_article']}, page {b['source_pdf_page']}" in e.message_fr


@pytest.mark.parametrize(
    "s,code,params",
    [
        (CAFE, "prime_deces", {"condition_remplie": False}),
        (VOY, "prime_entretien", {"condition_remplie": False}),
        (HOT, "prime_transport", {"groupe": "superieur_1_et_cadres", "condition_remplie": False}),
        (COSM, "prime_panier", {"condition_remplie": False}),
    ],
)
def test_condition_non_remplie_hors_scope(s, code, params):
    refus(Refus.HORS_SCOPE, prime, s, code, "2023-06-01", **params)


@pytest.mark.parametrize(
    "s,code,params",
    [(PAT, "prime_transport", {"groupe": "niveau_salaire_minimum"}), (COSM, "prime_transport", {"groupe": "cadres"})],
)
def test_groupe_refuse_absent_des_groupes_servis(s, code, params):
    refus(Refus.PARAM_INVALIDE, prime, s, code, "2023-06-01", **params)


def test_primes_datees_avant_la_premiere_date():
    refus(Refus.SOURCE_MANQUANTE, prime, CAFE, "prime_transport", "2021-11-30")
    refus(Refus.SOURCE_MANQUANTE, prime, PAT, "prime_panier", "2005-04-30")


def test_table_des_secteurs_inchangee():
    """Décision Q1 : les six secteurs ne sont pas ajoutés à la table des secteurs (en attente des noms DS2)."""
    table = lire_json("src/shared/sectors/sectors.v0.json")
    assert not {s.get("ds5_code") for s in table["sectors"]} & set(FICHIERS)
