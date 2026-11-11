"""Grilles de la vague 2 (D55 à D60) : savonnerie, distribution du pétrole, plasturgie, minoteries, teintureries,
boissons gazeuses.
Lancer depuis la racine du dépôt : pytest src/track_b_accounting/tests/test_vague2.py

Les valeurs attendues viennent de la double lecture des tableaux et des articles de primes (lots validés par DS5) ;
elles sont écrites ici, pas relues dans data/processed/. Fichiers réels (activés par D55 à D60).
"""
import copy
from decimal import Decimal

import pytest
from conftest import lire_json

from track_b_accounting.calc import Refus, loaders, prime, salaire_base

SAV, PET, PLA = "SAVONNERIE_RAFFINAGE_GRIGNONS", "COMMERCE_DISTRIBUTION_PETROLE", "PLASTURGIE"
MIN, TEI, BOI = "MINOTERIES", "TEINTURERIES_PRESSINGS", "BOISSONS_GAZEUSES"
FICHIERS = {SAV: ("savonnerie_raffinage.json", "D55", 468, 3), PET: ("distribution_petrole.json", "D56", 588, 3),
            PLA: ("plasturgie.json", "D57", 672, 6), MIN: ("minoteries.json", "D58", 672, 6),
            TEI: ("teintureries_pressings.json", "D59", 672, 6), BOI: ("boissons_gazeuses.json", "D60", 675, 6)}
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
    assert (loaders.REPO_ROOT / g["_meta"]["source_file"]).is_file()


@pytest.mark.parametrize("s", FICHIERS)
def test_nombre_de_cellules_et_de_tableaux_imprimes(s):
    _, _, n, tables = FICHIERS[s]
    g = REEL[s]
    assert sum(len(v) for t in g["grilles"] for v in t["valeurs"].values()) == n
    assert len({t["numero_imprime"] for t in g["grilles"]}) == tables


def test_seules_les_six_cases_illisibles_des_boissons_sont_null():
    nulles = sorted((s, t["table_id"], c, i) for s, g in REEL.items() for t in g["grilles"] for c, v in t["valeurs"].items()
                    for i, x in enumerate(v, 1) if x is None)
    assert nulles == sorted([(BOI, "BOI_HORAIRES_2021-12-01", "5", 8), (BOI, "BOI_HORAIRES_2023-01-01", "2", 8),
                             (BOI, "BOI_MENSUELS_2023-01-01", "1", 8), (BOI, "BOI_HORAIRES_2024-01-01", "5", 8),
                             (BOI, "BOI_MENSUELS_2024-01-01", "4", 8), (BOI, "BOI_MENSUELS_2024-01-01", "7", 8)])


def test_champs_d48_utilises_seulement_ou_decides():
    assert not any("anciennetes_refusees" in g for g in REEL.values())
    cases = [(s, p, len(b["cases_refusees"])) for s, g in REEL.items() for p, b in g["au_dela_dernier_degre"].items()
             if "cases_refusees" in b]
    assert cases == [(MIN, "horaires", 12), (MIN, "mensuels", 30)]


# --- montants lus (ligne depuis le haut, degré depuis la droite) ---------------------------------------------

@pytest.mark.parametrize("s,pop,cat,sous,anc,date,attendu,unite", [
    (SAV, "horaires", "I", None, 0.5, "2021-12-01", "2.985", "TND/heure"),          # T1 p.20 l.1 d.1
    (SAV, "horaires", "V_bis", None, 4, "2024-06-01", "4.873", "TND/heure"),        # T3 p.22 l.6 d.4
    (SAV, "mensuels", "VI", None, 0.5, "2021-12-01", "737.509", "TND/mois"),        # T1 p.20 l.7 d.1
    (SAV, "mensuels", "XII", None, 20, "2023-06-01", "1747.713", "TND/mois"),       # T2 p.21 l.13 d.12
    (PET, None, "1", "1", 0.5, "2021-12-01", "1285.125", "TND/mois"),               # T1 p.19 l.1 col « - »
    (PET, "tous_agents", "5", "4", 0.5, "2022-06-01", "3013.173", "TND/mois"),      # T1 p.19 l.14 col « - »
    (PET, None, "1", "2", 31, "2024-06-01", "1569.669", "TND/mois"),                # T3 p.20 l.2 col 14
    (PLA, "employes_maitrise", "1", None, 1, "2021-12-01", "546.928", "TND/mois"),  # T1 p.22 l.1 d.1
    (PLA, "employes_maitrise", "8", None, 31, "2024-06-01", "1234.048", "TND/mois"),  # T5 p.24 l.8 d.16
    (PLA, "ouvriers_horaires", "1", None, 1, "2021-12-01", "2.572", "TND/heure"),   # T2 p.22 l.1 d.1
    (MIN, "horaires", "I", None, 0.5, "2021-12-01", "3.552", "TND/heure"),          # T1 p.20 l.1 d.0
    (MIN, "mensuels", "11", None, 0.5, "2022-06-01", "1156.011", "TND/mois"),       # T2 p.20 l.11 d.0
    (MIN, "mensuels", "1", None, 26, "2024-06-01", "747.160", "TND/mois"),          # T6 p.22 l.1 d.13
    (TEI, "execution", "1", None, 0.5, "2021-12-01", "2.658", "TND/heure"),         # T1 p.20 l.1 d.1
    (TEI, "execution", "6", None, 40, "2024-06-01", "3.595", "TND/heure"),          # T5 p.22 l.6 d.14 (ouvert)
    (TEI, "administratifs_techniciens", "10", None, 2.5, "2023-06-01", "888.497", "TND/mois"),  # T4 p.21 l.10 d.3
    (BOI, "horaires", "1", None, 0.5, "2021-12-01", "3.000", "TND/heure"),          # T1 p.20 l.1 d.1
    (BOI, "mensuels", "9", None, 1.5, "2022-06-01", "1251.990", "TND/mois"),        # T2 p.20 l.9 d.2
    (BOI, "horaires", "6", None, 28, "2024-06-01", "5.069", "TND/heure"),           # T5 p.22 l.6 d.15
])
def test_montants_lus(ok, s, pop, cat, sous, anc, date, attendu, unite):
    r = ok(salaire_base(s, pop, cat, anc, date, sous_categorie=sous))
    assert (r.montant, r.unite) == (Decimal(attendu), unite) and r.citations[0].decision_ref == FICHIERS[s][1]


# --- règles ---------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("s,pop,cat,sous,a", [
    (SAV, "horaires", "I", None, 3), (SAV, "mensuels", "VI", None, 19), (PET, None, "1", "1", 1), (PET, None, "1", "1", 29),
    (PLA, "ouvriers_horaires", "1", None, 2), (MIN, "horaires", "I", None, 1), (MIN, "mensuels", "1", None, 25),
    (TEI, "execution", "1", None, 3), (TEI, "execution", "1", None, 23), (BOI, "mensuels", "1", None, 24)])
def test_bornes_exactes_refusees(s, pop, cat, sous, a):
    refus(Refus.PARAM_INVALIDE, salaire_base, s, pop, cat, a, "2024-06-01", sous_categorie=sous)


@pytest.mark.parametrize("s,pop,cat,sous,a,limite", [
    (SAV, "mensuels", "VI", None, 21, 21), (PET, None, "1", "1", 32, 32), (PLA, "ouvriers_horaires", "3", None, 32.5, 32),
    (BOI, "mensuels", "1", None, 30, 30)])
def test_refus_au_dela_du_dernier_degre(s, pop, cat, sous, a, limite):
    e = refus(Refus.SOURCE_MANQUANTE, salaire_base, s, pop, cat, a, "2024-06-01", sous_categorie=sous)
    assert f"moins de {limite} ans" in e.message_fr


def test_petrole_colonne_entree_et_hypotheses():
    r = salaire_base(PET, None, "3", 0.5, "2024-06-01", sous_categorie="1")
    assert r.detail["degre"] == 1 and r.unite == "TND/mois"
    assert any("Colonne « - »" in h for h in r.detail["hypotheses"]) and any("mensuels" in h for h in r.detail["hypotheses"])
    refus(Refus.PARAM_INVALIDE, salaire_base, PET, None, "3", 5, "2024-06-01")              # sous-catégorie obligatoire


def test_savonnerie_unite_par_ligne():
    assert salaire_base(SAV, "horaires", "V", 5.5, "2024-06-01").unite == "TND/heure"
    assert salaire_base(SAV, "mensuels", "VI", 5.5, "2024-06-01").unite == "TND/mois"
    refus(Refus.PARAM_INVALIDE, salaire_base, SAV, "horaires", "VI", 5.5, "2024-06-01")
    refus(Refus.PARAM_INVALIDE, salaire_base, SAV, None, "VI", 5.5, "2024-06-01")


@pytest.mark.parametrize("pop,cat,a,attendu", [
    ("horaires", "V", 30, "5.495"),          # T5 p.22 l.5 : 5.469 + 2 × (5.469 − 5.456)
    ("mensuels", "11", 25.5, "1404.551"),    # T6 p.22 l.11 d.13, n = 0
])
def test_minoteries_ecart_categories_v_et_11(ok, pop, cat, a, attendu):
    r = ok(salaire_base(MIN, pop, cat, a, "2024-06-01"))
    assert r.montant == Decimal(attendu)


def test_minoteries_autres_categories_refusees_apres_27_ans():
    for pop, cat in (("horaires", "I"), ("horaires", "IV"), ("mensuels", "1"), ("mensuels", "10")):
        assert salaire_base(MIN, pop, cat, 26, "2024-06-01").detail["degre"] == 14
        e = refus(Refus.SOURCE_MANQUANTE, salaire_base, MIN, pop, cat, 28, "2024-06-01")
        assert "article 14 (جديد) أ (page 8)" in e.message_fr
    refus(Refus.PARAM_INVALIDE, salaire_base, MIN, "mensuels", "11", 27, "2024-06-01")


@pytest.mark.parametrize("date,pop,cat", [("2022-06-01", "horaires", "5"), ("2023-06-01", "horaires", "2"),
                                          ("2023-06-01", "mensuels", "1"), ("2024-06-01", "horaires", "5"),
                                          ("2024-06-01", "mensuels", "4"), ("2024-06-01", "mensuels", "7")])
def test_boissons_cases_illisibles(date, pop, cat):
    e = refus(Refus.SOURCE_MANQUANTE, salaire_base, BOI, pop, cat, 13, date)
    assert f"catégorie {cat}, degré 8" in e.message_fr and "page" in e.message_fr


@pytest.mark.parametrize("s,pop,cat,sous", [(SAV, "horaires", "I", None), (PET, None, "1", "1"), (PLA, "employes_maitrise", "1", None),
                                            (MIN, "horaires", "I", None), (TEI, "execution", "1", None), (BOI, "horaires", "1", None)])
def test_avant_la_premiere_table_refuse(s, pop, cat, sous):
    e = refus(Refus.SOURCE_MANQUANTE, salaire_base, s, pop, cat, 0.5, "2021-11-30", sous_categorie=sous)
    assert "première date d'effet disponible : 2021-12-01" in e.message_fr


@pytest.mark.parametrize("s,cat", [(SAV, "VI"), (PLA, "1"), (MIN, "1"), (TEI, "1"), (BOI, "1")])
def test_population_obligatoire(s, cat):
    refus(Refus.PARAM_INVALIDE, salaire_base, s, None, cat, 0.5, "2024-06-01")


# --- primes ---------------------------------------------------------------------------------------------------

C = {"condition_remplie": True}
PRIMES = [
    (SAV, "prime_transport", "2022-06-01", {"groupe": "execution_gestion"}, "101.250"),
    (SAV, "prime_transport", "2024-06-01", {"groupe": "cadres"}, "123.113"),
    (SAV, "prime_presence", "2023-06-01", {}, "11.654"), (SAV, "prime_salete", "2023-06-01", C, "0.022"),
    (SAV, "prime_caisse", "2023-06-01", C, "48.333"), (SAV, "prime_risque", "2023-06-01", C, "10.000"),
    (SAV, "prime_scolaire_enseignement_base", "2023-06-01", C, "22.666"),
    (SAV, "prime_scolaire_enseignement_secondaire", "2023-06-01", C, "24.666"),
    (SAV, "prime_scolaire_etudiant", "2023-06-01", C, "26.666"),
    (SAV, "prime_aid_el_fitr", "2023-06-01", {}, "16.666"), (SAV, "prime_aid_el_adha", "2023-06-01", {}, "46.666"),
    (PET, "prime_transport", "2023-06-01", {}, "79.690"), (PET, "prime_presence", "2024-06-01", {}, "7.856"),
    (PET, "prime_caisse_chauffeurs", "2023-06-01", C, "10.000"), (PET, "prime_caisse_caissiers", "2023-06-01", C, "20.000"),
    (PET, "prime_scolaire_base_1_6", "2023-06-01", C, "32.000"), (PET, "prime_scolaire_base_7_9", "2023-06-01", C, "37.000"),
    (PET, "prime_scolaire_secondaire", "2023-06-01", C, "42.000"), (PET, "prime_scolaire_superieur", "2023-06-01", C, "52.000"),
    (PET, "prime_risque", "2023-06-01", {}, "15.000"), (PET, "prime_standard_telephonique", "2023-06-01", C, "10.000"),
    (PLA, "prime_presence", "2022-06-01", {}, "9.608"), (PLA, "prime_presence_complement_sans_panier", "2023-06-01", C, "2.000"),
    (PLA, "prime_panier", "2023-06-01", C, "13.086"), (PLA, "prime_caisse", "2023-06-01", C, "22.000"),
    (PLA, "prime_transport", "2024-06-01", {"groupe": "execution_gestion"}, "96.667"),
    (PLA, "prime_transport", "2024-06-01", {"groupe": "cadres"}, "104.400"),
    (PLA, "prime_deplacement_dejeuner", "2023-06-01", C, "5.466"), (PLA, "prime_deplacement_diner", "2023-06-01", C, "5.466"),
    (PLA, "prime_deplacement_logement", "2023-06-01", C, "5.600"), (PLA, "prime_scolaire", "2023-06-01", C, "10.000"),
    (MIN, "prime_productivite", "2023-06-01", {}, "10.000"), (MIN, "prime_production", "2023-06-01", {}, "10.000"),
    (MIN, "prime_presence", "2022-06-01", {}, "6.894"), (MIN, "prime_panier", "2023-06-01", {}, "0.362"),
    (MIN, "prime_transport", "2024-06-01", {}, "57.226"), (MIN, "prime_logement", "2022-06-01", {}, "13.573"),
    (TEI, "prime_transport", "2023-06-01", {"groupe": "cadres"}, "91.759"), (TEI, "prime_panier", "2023-06-01", C, "0.700"),
    (TEI, "prime_caisse", "2023-06-01", C, "22.000"), (TEI, "prime_presence", "2024-06-01", {}, "7.856"),
    (TEI, "prime_etudes_jardin_enfants", "2023-06-01", C, "20.000"), (TEI, "prime_etudes_enseignement_base", "2023-06-01", C, "26.666"),
    (TEI, "prime_etudes_enseignement_secondaire", "2023-06-01", C, "33.333"),
    (TEI, "prime_etudes_enseignement_superieur", "2023-06-01", C, "40.000"),
    (BOI, "prime_dix_ans_entreprise", "2023-06-01", C, "15.000"),
    (BOI, "prime_transport", "2022-06-01", {"groupe": "execution_gestion"}, "68.313"),
    (BOI, "prime_froid", "2023-06-01", C, "2.000"), (BOI, "prime_scolaire_enseignement_base", "2023-06-01", C, "26.666"),
    (BOI, "prime_scolaire_secondaire_superieur", "2023-06-01", C, "33.333"), (BOI, "prime_presence", "2023-06-01", {}, "7.359"),
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


def test_conditions_et_dates_des_primes():
    refus(Refus.HORS_SCOPE, prime, PLA, "prime_panier", "2023-06-01", condition_remplie=False)
    refus(Refus.SOURCE_MANQUANTE, prime, MIN, "prime_transport", "2021-11-30")
    refus(Refus.PARAM_INVALIDE, prime, SAV, "prime_transport", "2023-06-01")                  # groupe obligatoire


def test_table_des_secteurs_inchangee_et_exemption():
    table = lire_json("src/shared/sectors/sectors.v0.json")
    assert not {s.get("ds5_code") for s in table["sectors"]} & set(FICHIERS)
