"""Grilles de la vague 4 (D67 à D72) : imprimerie et édition, verre et miroirs, concessionnaires de matériel agricole,
boulangeries, textile, fonderie et constructions mécaniques.
Lancer depuis la racine du dépôt : pytest src/track_b_accounting/tests/test_vague4.py

Les valeurs attendues viennent de la double lecture des tableaux et des articles de primes (cas de référence vérifiés
par DS5 sur les images, voir D67 à D72) ; elles sont écrites ici, pas relues dans data/processed/.
"""

import copy
from decimal import Decimal

import pytest
from conftest import lire_json
from test_controle_hausse import ecarts_de_hausse

from track_b_accounting.calc import Refus, loaders, prime, salaire_base

IMP, VER, AGR = "IMPRIMERIE_EDITION_CARTONNAGE", "VERRE_MIROIRS", "CONCESSIONNAIRES_MATERIEL_AGRICOLE"
BOU, TEX, FON = "BOULANGERIES", "TEXTILE", "FONDERIE_METALLURGIE_MECANIQUE"
FICHIERS = {
    IMP: ("imprimerie_edition.json", "D67", 855, 6),
    VER: ("verre_miroirs.json", "D68", 900, 6),
    AGR: ("materiel_agricole.json", "D69", 912, 3),
    BOU: ("boulangeries.json", "D70", 1014, 9),
    TEX: ("textile.json", "D71", 950, 4),
    FON: ("fonderies_mecanique.json", "D72", 1092, 6),
}
REEL = {s: lire_json(f"data/processed/salary_grids/{f}") for s, (f, *_) in FICHIERS.items()}
D = Decimal


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
    assert "Vérifié par DS5 sur les images" in g["_meta"]["statut_verification"]
    assert "double lecture et le contrôle de hausse" in g["_meta"]["statut_verification"]


@pytest.mark.parametrize("s", FICHIERS)
def test_nombre_de_cellules_servies_et_de_tableaux_imprimes(s):
    _, _, n, tables = FICHIERS[s]
    g = REEL[s]
    assert sum(len(v) for t in g["grilles"] for v in t["valeurs"].values()) == n
    assert len({t["numero_imprime"] for t in g["grilles"]}) == tables


def nulles(s):
    return sorted(
        (t["table_id"], c, i)
        for t in REEL[s]["grilles"]
        for c, v in t["valeurs"].items()
        for i, x in enumerate(v, 1)
        if x is None
    )


def test_cases_illisibles_declarees_et_seules_nulles():
    assert nulles(IMP) == nulles(VER) == []
    assert nulles(AGR) == sorted(
        [("AGRI_TOUS_AGENTS_2021-12-01", "16", 17), ("AGRI_TOUS_AGENTS_2023-01-01", "11", 19)]
        + [("AGRI_TOUS_AGENTS_2024-01-01", c, 8) for c in ("1", "2", "4", "6", "12", "14")]
    )
    assert nulles(BOU) == sorted(
        [
            ("BOUL_ADMINISTRATIFS_2023-01-01", "3", 2),
            ("BOUL_TRADITIONNELLES_HORAIRES_2023-01-01", "peseur", 2),
            ("BOUL_TRADITIONNELLES_HORAIRES_2023-01-01", "petrisseur", 2),
            ("BOUL_TRADITIONNELLES_MENSUELS_2023-01-01", "petrisseur", 2),
            ("BOUL_TRADITIONNELLES_HORAIRES_2023-01-01", "chef_de_four", 2),
            ("BOUL_INDUSTRIELLES_HORAIRES_2023-01-01", "1", 2),
            ("BOUL_INDUSTRIELLES_HORAIRES_2023-01-01", "2", 2),
            ("BOUL_INDUSTRIELLES_HORAIRES_2023-01-01", "4", 2),
            ("BOUL_INDUSTRIELLES_MENSUELS_2023-01-01", "5", 2),
            ("BOUL_ADMINISTRATIFS_2024-01-01", "1", 2),
            ("BOUL_TRADITIONNELLES_MENSUELS_2024-01-01", "passeur_de_plaques", 2),
            ("BOUL_TRADITIONNELLES_MENSUELS_2024-01-01", "chef_de_four", 2),
        ]
    )
    assert nulles(FON) == [("FOND_MENSUELS_2021-12-01", "3", 10)]
    cm = ["1a", "1b"] + [str(i) for i in range(2, 18)]
    assert nulles(TEX) == sorted((f"TEX_MENSUELS_{d}", c, 1) for d in ("2021-09-01", "2022-05-01") for c in cm)
    for s in FICHIERS:
        for t in REEL[s]["grilles"]:
            declarees = {(c["categorie"], c["degre"]) for c in t.get("cellules_source_manquante", [])}
            assert declarees == {(c, i) for (tid, c, i) in nulles(s) if tid == t["table_id"]}
            assert all(
                c["source_pdf_page"] == t["source_pdf_page"] and c["raison"]
                for c in t.get("cellules_source_manquante", [])
            )


def test_cellule_illisible_refusee_avec_page():
    e = refus(Refus.SOURCE_MANQUANTE, salaire_base, AGR, None, "12", 12, "2024-06-01")
    assert "page 25" in e.message_fr and "3 ou 8" in e.message_fr
    e = refus(Refus.SOURCE_MANQUANTE, salaire_base, BOU, "traditionnelles_horaires", "petrisseur", 1.5, "2023-06-01")
    assert "page 20" in e.message_fr
    e = refus(Refus.SOURCE_MANQUANTE, salaire_base, FON, "mensuels", "3", 21, "2021-12-15")
    assert "page 25" in e.message_fr


# --- salaires servis (valeurs de la double lecture) ---------------------------------------------------------------


@pytest.mark.parametrize(
    "s, pop, cat, sous, annees, date, montant, unite, page",
    [
        (IMP, "administratifs_mensuels", "5", None, 3, "2024-06-01", "851.882", "TND/mois", 26),
        (IMP, "administratifs_mensuels", "3-4-5-6", None, 3, "2024-06-01", "851.882", "TND/mois", 26),
        (IMP, "administratifs_mensuels", "1", None, 0.5, "2021-12-01", "684.201", "TND/mois", 22),
        (IMP, "horaires", "II", "2", 3, "2024-06-01", "4.122", "TND/heure", 27),
        (IMP, "horaires", "I", "1", 30, "2022-06-01", "3.250", "TND/heure", 23),
        (IMP, "techniciens_mensuels", "IV", "3", 30, "2023-06-01", "2065.586", "TND/mois", 25),
        (AGR, None, "1", None, 0.5, "2021-12-01", "594.410", "TND/mois", 23),
        (AGR, "tous_agents", "16", None, 38, "2024-06-01", "1894.675", "TND/mois", 25),
        (AGR, None, "12", None, 15.5, "2024-06-01", "1305.387", "TND/mois", 25),
        (BOU, "administratifs", "8", None, 23, "2024-06-01", "1180.430", "TND/mois", 22),
        (BOU, "traditionnelles_horaires", "chef_de_four", None, 0.5, "2022-06-01", "4.067", "TND/heure", 18),
        (BOU, "traditionnelles_mensuels", "peseur", None, 1.5, "2023-06-01", "877.901", "TND/mois", 20),
        (BOU, "industrielles_mensuels", "5", None, 11, "2023-06-01", "898.518", "TND/mois", 21),
        (TEX, "horaires", "I", None, 0.5, "2021-09-01", "2.501", "TND/heure", 29),
        (TEX, "horaires", "IV", "2", 34, "2022-06-01", "4.060", "TND/heure", 31),
        (TEX, "mensuels", "1", "b", 20.5, "2022-06-01", "586.044", "TND/mois", 32),
        (TEX, "mensuels", "17", None, 1.5, "2021-09-01", "1064.819", "TND/mois", 30),
        (FON, "mensuels", "1", "a", 1, "2021-12-01", "540.491", "TND/mois", 25),
        (FON, "mensuels", "18", None, 30, "2023-06-01", "1592.070", "TND/mois", 27),
        (FON, "horaires", "7", None, 33, "2024-06-01", "5.363", "TND/heure", 30),
        (FON, "horaires", "7", None, 34.99, "2024-06-01", "5.363", "TND/heure", 30),
    ],
)
def test_salaires_servis(ok, s, pop, cat, sous, annees, date, montant, unite, page):
    r = ok(salaire_base(s, pop, cat, annees, date, sous_categorie=sous))
    assert (r.montant, r.unite, r.citations[0].page) == (D(montant), unite, page)
    assert r.citations[0].decision_ref == FICHIERS[s][1]


def test_imprimerie_hypotheses_tableau_6_et_sous_lignes(ok):
    r = ok(salaire_base(IMP, "horaires", "III", 5, "2024-06-01", sous_categorie="1"))
    assert r.detail["table_id"] == "IMP_HORAIRES_2024-01-01" and r.citations[0].page == 27
    assert any("Tableau n° 6 (page 27)" in h for h in r.detail["hypotheses"])
    assert any("position imprimée" in h for h in r.detail["hypotheses"])
    r = ok(salaire_base(IMP, "techniciens_mensuels", "IV", 5, "2024-06-01", sous_categorie="1"))
    assert any("unité TND/mois retenue en hypothèse" in h for h in r.detail["hypotheses"])
    assert r.detail["regime_hebdomadaire_heures"] == 48
    r = ok(salaire_base(IMP, "administratifs_mensuels", "14", 5, "2024-06-01"))
    assert r.detail["categorie_demandee"] == "14" and r.detail["categorie"] == "13-14-15"
    assert r.detail["regime_hebdomadaire_heures"] == 40


def test_regime_horaire_vide_pour_textile_et_fonderie(ok):
    assert ok(salaire_base(TEX, "horaires", "I", 5.5, "2022-06-01")).detail["regime_hebdomadaire_heures"] is None
    assert ok(salaire_base(FON, "horaires", "1", 5, "2022-06-01")).detail["regime_hebdomadaire_heures"] is None
    assert ok(salaire_base(BOU, "administratifs", "1", 5, "2022-06-01")).detail["regime_hebdomadaire_heures"] == 48
    assert ok(salaire_base(AGR, None, "1", 5.5, "2022-06-01")).detail["regime_hebdomadaire_heures"] == 40


# --- refus de borne, de dernier degré, de date, de population --------------------------------------------------


@pytest.mark.parametrize(
    "s, pop, cat, sous, annees, code, extrait",
    [
        (IMP, "administratifs_mensuels", "1", None, 31, Refus.SOURCE_MANQUANTE, "pages 22 à 27"),
        (IMP, "horaires", "I", "1", 45, Refus.SOURCE_MANQUANTE, "article 11 (جديد) 1) (page 8)"),
        (IMP, "horaires", "I", "1", 28, Refus.PARAM_INVALIDE, "borne commune"),
        (AGR, None, "1", None, 40, Refus.SOURCE_MANQUANTE, "40 ans"),
        (AGR, None, "1", None, 25, Refus.PARAM_INVALIDE, "borne commune"),
        (BOU, "administratifs", "1", None, 24, Refus.SOURCE_MANQUANTE, "24 ans"),
        (BOU, "industrielles_horaires", "1", None, 2, Refus.PARAM_INVALIDE, "borne commune"),
        (TEX, "horaires", "I", None, 35, Refus.SOURCE_MANQUANTE, "degré 19 commence à 35 ans"),
        (TEX, "mensuels", "2", None, 36, Refus.SOURCE_MANQUANTE, "degré 19 commence à 36 ans"),
        (TEX, "mensuels", "2", None, 0.5, Refus.SOURCE_MANQUANTE, "période de stage"),
        (TEX, "mensuels", "2", None, 1, Refus.PARAM_INVALIDE, "borne commune"),
        (FON, "horaires", "1", None, 14, Refus.PARAM_INVALIDE, "borne commune"),
        (FON, "mensuels", "2", None, 32, Refus.PARAM_INVALIDE, "borne commune"),
        (FON, "horaires", "7", None, 35, Refus.SOURCE_MANQUANTE, "note de l'article 58 (جديد) (page 17)"),
        (FON, "mensuels", "18", None, 40, Refus.SOURCE_MANQUANTE, "(pages 25 à 30)"),
    ],
)
def test_refus_de_degre(s, pop, cat, sous, annees, code, extrait):
    e = refus(code, salaire_base, s, pop, cat, annees, "2023-06-01", sous_categorie=sous)
    assert extrait in e.message_fr


@pytest.mark.parametrize(
    "s, pop, cat, date",
    [
        (IMP, "administratifs_mensuels", "1", "2021-11-30"),
        (AGR, None, "1", "2021-11-30"),
        (BOU, "administratifs", "1", "2021-11-30"),
        (TEX, "horaires", "I", "2021-08-31"),
        (FON, "horaires", "1", "2021-11-30"),
    ],
)
def test_refus_avant_la_premiere_table(s, pop, cat, date):
    refus(Refus.SOURCE_MANQUANTE, salaire_base, s, pop, cat, 5.5, date)


@pytest.mark.parametrize("s", [IMP, VER, BOU, TEX, FON])
def test_population_obligatoire(s):
    refus(Refus.PARAM_INVALIDE, salaire_base, s, None, "1", 5.5, "2024-06-01")


def test_textile_degre_18_et_table_2022_au_dela(ok):
    r = ok(salaire_base(TEX, "mensuels", "2", 35.5, "2026-01-01"))
    assert r.detail["degre"] == 19 and r.detail["table_id"] == "TEX_MENSUELS_2022-05-01"
    assert r.montant == D("622.371")


# --- verre : salaire de base refusé (D68), primes servies ---------------------------------------------------------


@pytest.mark.parametrize(
    "pop, cat, sous",
    [("horaires", "1", None), ("horaires", "7", None), ("mensuels", "1", "a"), ("mensuels", "18", None)],
)
@pytest.mark.parametrize("annees", [0, 0.5, 1, 12, 40])
def test_verre_salaire_toujours_refuse(pop, cat, sous, annees):
    e = refus(Refus.SOURCE_MANQUANTE, salaire_base, VER, pop, cat, annees, "2024-06-01", sous_categorie=sous)
    assert "article 12 (جديد) (pages 7-8)" in e.message_fr and "article 53" in e.message_fr
    assert e.message_fr.startswith(f"Ancienneté de {annees} ans")


def test_verre_seuil_zero_et_grille_transcrite():
    g = REEL[VER]
    assert {b["anciennete_max_couverte_annees"] for b in g["au_dela_dernier_degre"].values()} == {0}
    assert [len(g["degres"][p]) for p in ("horaires", "mensuels")] == [13, 11]
    t = next(t for t in g["grilles"] if t["table_id"] == "VERRE_MENSUELS_2024-01-01")
    assert t["valeurs"]["1a"][0] == D("607.383") and t["valeurs"]["18"][10] == D("1292.724")
    assert next(t for t in g["grilles"] if t["table_id"] == "VERRE_HORAIRES_2021-12-01")["valeurs"]["7"][12] == D(
        "4.800"
    )


# --- textile : valeurs gardées en champ descriptif ----------------------------------------------------------------


def test_textile_colonne_stage_gardee_en_valeur_imprimee():
    t = next(t for t in REEL[TEX]["grilles"] if t["table_id"] == "TEX_MENSUELS_2021-09-01")
    v = {c["categorie"]: c["valeur_imprimee"] for c in t["cellules_source_manquante"]}
    assert len(v) == 18 and v["1a"] == D("522.488") and v["17"] == D("1057.273")
    t = next(t for t in REEL[TEX]["grilles"] if t["table_id"] == "TEX_MENSUELS_2022-05-01")
    assert {c["categorie"]: c["valeur_imprimee"] for c in t["cellules_source_manquante"]}["5"] == D("753.866")


def test_textile_colonnes_19_et_20_non_servies():
    n = 0
    for t in REEL[TEX]["grilles"]:
        ns = t["colonnes_non_servies"]
        assert ns["colonnes_imprimees"] == ["19", "20"] and ns["source_pdf_page"] == t["source_pdf_page"]
        assert set(ns["valeurs"]) == set(t["valeurs"]) and all(len(v) == 2 for v in ns["valeurs"].values())
        assert all(len(v) == 19 for v in t["valeurs"].values())
        n += 2 * len(ns["valeurs"])
    assert n == 100
    t = next(t for t in REEL[TEX]["grilles"] if t["table_id"] == "TEX_HORAIRES_2021-09-01")
    assert t["colonnes_non_servies"]["valeurs"]["I"] == [D("2.599"), D("2.604")]
    t = next(t for t in REEL[TEX]["grilles"] if t["table_id"] == "TEX_MENSUELS_2022-05-01")
    assert t["colonnes_non_servies"]["valeurs"]["17"] == [D("1273.662"), D("1281.156")]


def test_textile_controle_de_hausse_sur_les_valeurs_gardees():
    """Copie de la grille où les 36 cellules « stage » et les 100 des degrés 19-20 sont remises en place : contrôle de
    hausse permanent (test_controle_hausse.ecarts_de_hausse), aucune cellule signalée."""
    g = copy.deepcopy(REEL[TEX])
    for t in g["grilles"]:
        for c, (v19, v20) in t["colonnes_non_servies"]["valeurs"].items():
            t["valeurs"][c] = t["valeurs"][c] + [v19, v20]
        for m in t.pop("cellules_source_manquante", []):
            t["valeurs"][m["categorie"]][0] = m["valeur_imprimee"]
    assert all(x is not None for t in g["grilles"] for v in t["valeurs"].values() for x in v)
    comparees, signalees = ecarts_de_hausse(TEX, g)
    assert comparees == 525 and signalees == []


# --- primes servies (montants lus sur l'image) -------------------------------------------------------------------

PRIMES = [
    (IMP, "prime_transport", "2022-06-01", {}, "80.980", "TND/mois", 15),
    (IMP, "prime_transport", "2023-06-01", {}, "86.447", "TND/mois", 15),
    (IMP, "prime_transport", "2024-06-01", {}, "92.282", "TND/mois", 15),
    (IMP, "prime_presence", "2022-06-01", {}, "6.894", "TND/mois", 16),
    (IMP, "prime_presence", "2024-06-01", {}, "7.856", "TND/mois", 16),
    (IMP, "prime_aid_fitr", "2024-06-01", {}, "20.000", "TND/versement", 15),
    (IMP, "prime_aid_adha", "2024-06-01", {}, "40.000", "TND/versement", 15),
    (IMP, "prime_panier", "2024-06-01", {"condition_remplie": True}, "0.350", "TND/jour", 15),
    (IMP, "prime_deces_agent", "2024-06-01", {}, "300.000", "TND/versement", 15),
    (IMP, "prime_deces_parent", "2024-06-01", {"condition_remplie": True}, "200.000", "TND/versement", 15),
    (IMP, "prime_deplacement_repas", "2024-06-01", {"condition_remplie": True}, "3.000", "TND/repas", 15),
    (IMP, "prime_deplacement_nuitee", "2024-06-01", {"condition_remplie": True}, "5.000", "TND/nuitee", 15),
    (VER, "prime_transport", "2022-06-01", {}, "114.912", "TND/mois", 14),
    (VER, "prime_transport", "2023-06-01", {}, "122.668", "TND/mois", 14),
    (VER, "prime_transport", "2024-06-01", {}, "130.948", "TND/mois", 14),
    (VER, "prime_transport", "2022-06-01", {"variante": "complement_si_prime_superieure"}, "7.013", "TND/mois", 14),
    (VER, "prime_transport", "2023-06-01", {"variante": "complement_si_prime_superieure"}, "7.757", "TND/mois", 14),
    (VER, "prime_transport", "2024-06-01", {"variante": "complement_si_prime_superieure"}, "8.280", "TND/mois", 14),
    (VER, "prime_presence", "2023-06-01", {}, "7.359", "TND/mois", 14),
    (VER, "prime_caisse", "2024-06-01", {"condition_remplie": True}, "16.666", "TND/mois", 14),
    (VER, "prime_douche", "2024-06-01", {"condition_remplie": True}, "3.000", "TND/mois", 14),
    (VER, "prime_aid_fitr", "2024-06-01", {}, "51.666", "TND/versement", 14),
    (VER, "prime_aid_adha", "2024-06-01", {}, "83.333", "TND/versement", 14),
    (VER, "prime_panier", "2024-06-01", {"condition_remplie": True}, "1.733", "TND/jour", 14),
    (VER, "prime_risque", "2024-06-01", {"condition_remplie": True}, "16.666", "TND/mois", 14),
    (VER, "prime_lait_four", "2024-06-01", {"condition_remplie": True}, "4.000", "TND/mois", 14),
    (VER, "prime_deplacement_repas", "2024-06-01", {"condition_remplie": True}, "3.000", "TND/repas", 14),
    (VER, "prime_deplacement_nuitee", "2024-06-01", {"condition_remplie": True}, "14.000", "TND/nuitee", 14),
    (AGR, "prime_fonction_directeur", "2024-06-01", {"condition_remplie": True}, "90.000", "TND/mois", 14),
    (AGR, "prime_fonction_directeur_adjoint", "2024-06-01", {"condition_remplie": True}, "75.000", "TND/mois", 14),
    (AGR, "prime_fonction_chef_service", "2024-06-01", {"condition_remplie": True}, "60.000", "TND/mois", 14),
    (AGR, "prime_fonction_responsable_section", "2024-06-01", {"condition_remplie": True}, "30.000", "TND/mois", 14),
    (AGR, "prime_demi_journee", "2022-06-01", {}, "6.894", "TND/mois", 15),
    (AGR, "prime_demi_journee", "2024-06-01", {}, "7.856", "TND/mois", 15),
    (AGR, "prime_panier", "2024-06-01", {"condition_remplie": True}, "1.000", "TND/jour", 15),
    (AGR, "prime_caisse_premier_caissier", "2024-06-01", {"condition_remplie": True}, "25.000", "TND/mois", 15),
    (AGR, "prime_caisse_caissier", "2024-06-01", {"condition_remplie": True}, "20.000", "TND/mois", 15),
    (AGR, "prime_deplacement_dejeuner", "2024-06-01", {"condition_remplie": True}, "5.000", "TND/repas", 15),
    (AGR, "prime_deplacement_diner", "2024-06-01", {"condition_remplie": True}, "5.000", "TND/repas", 15),
    (AGR, "prime_deplacement_nuitee", "2024-06-01", {"condition_remplie": True}, "10.000", "TND/nuitee", 15),
    (AGR, "prime_aid_adha", "2024-06-01", {}, "73.333", "TND/versement", 15),
    (AGR, "prime_scolaire_base", "2024-06-01", {"condition_remplie": True}, "56.666", "TND/enfant", 15),
    (AGR, "prime_scolaire_secondaire", "2024-06-01", {"condition_remplie": True}, "76.666", "TND/enfant", 15),
    (AGR, "prime_scolaire_superieur", "2024-06-01", {"condition_remplie": True}, "90.000", "TND/enfant", 15),
    (AGR, "aide_deces", "2024-06-01", {}, "150.000", "TND/versement", 15),
    (BOU, "prime_transport", "2022-06-01", {}, "67.863", "TND/mois", 15),
    (BOU, "prime_transport", "2024-06-01", {}, "77.333", "TND/mois", 15),
    (BOU, "prime_presence", "2023-06-01", {}, "13.764", "TND/mois", 15),
    (BOU, "prime_presence", "2024-06-01", {}, "14.693", "TND/mois", 15),
    (BOU, "prime_panier", "2022-06-01", {}, "0.338", "TND/jour", 15),
    (BOU, "prime_panier", "2023-06-01", {}, "0.361", "TND/jour", 15),
    (BOU, "prime_panier", "2024-06-01", {}, "0.385", "TND/jour", 15),
    (TEX, "prime_presence", "2021-09-01", {}, "6.959", "TND/mois", 15),
    (TEX, "prime_presence", "2024-06-01", {}, "7.446", "TND/mois", 15),
    (TEX, "prime_transport", "2021-09-01", {"groupe": "execution_maitrise"}, "60.281", "TND/mois", 15),
    (TEX, "prime_transport", "2021-09-01", {"groupe": "cadres"}, "67.123", "TND/mois", 15),
    (TEX, "prime_transport", "2022-06-01", {"groupe": "execution_maitrise"}, "64.500", "TND/mois", 15),
    (TEX, "prime_transport", "2022-06-01", {"groupe": "cadres"}, "71.822", "TND/mois", 15),
    (FON, "prime_presence", "2022-06-01", {}, "6.894", "TND/mois", 15),
    (FON, "prime_transport", "2022-06-01", {"groupe": "execution_maitrise"}, "81.435", "TND/mois", 15),
    (FON, "prime_transport", "2022-06-01", {"groupe": "cadres"}, "88.221", "TND/mois", 15),
    (FON, "prime_transport", "2023-06-01", {"groupe": "execution_maitrise"}, "86.932", "TND/mois", 15),
    (FON, "prime_transport", "2023-06-01", {"groupe": "cadres"}, "94.176", "TND/mois", 15),
    (FON, "prime_transport", "2024-06-01", {"groupe": "execution_maitrise"}, "92.800", "TND/mois", 15),
    (FON, "prime_transport", "2024-06-01", {"groupe": "cadres"}, "100.533", "TND/mois", 15),
    (FON, "prime_logement", "2022-06-01", {}, "20.359", "TND/mois", 16),
    (FON, "prime_logement", "2023-06-01", {}, "21.733", "TND/mois", 16),
    (FON, "prime_logement", "2024-06-01", {}, "23.200", "TND/mois", 16),
    (FON, "prime_chaleur_fumee_salete_risque", "2024-06-01", {"condition_remplie": True}, "0.055", "TND/heure", 16),
    (FON, "prime_chaleur_complement", "2024-06-01", {"condition_remplie": True}, "0.010", "TND/heure", 16),
    (FON, "prime_scolaire_base", "2024-06-01", {}, "16.666", "TND/enfant", 16),
    (FON, "prime_scolaire_secondaire", "2024-06-01", {}, "26.666", "TND/enfant", 16),
    (FON, "prime_scolaire_superieur", "2024-06-01", {}, "40.000", "TND/enfant", 16),
    (FON, "frais_funeraires", "2024-06-01", {}, "200.000", "TND/versement", 16),
]


@pytest.mark.parametrize("s, code, date, params, montant, unite, page", PRIMES)
def test_primes_servies(ok, s, code, date, params, montant, unite, page):
    r = ok(prime(s, code, date, **params))
    assert (r.montant, r.unite, r.citations[0].page) == (D(montant), unite, page)
    assert r.detail["label_fr"] and r.detail["label_ar"]


def test_chaque_prime_couverte_est_testee():
    couvertes = {(s, p["code"]) for s in FICHIERS for p in REEL[s]["primes"]}
    assert couvertes == {(s, c) for s, c, *_ in PRIMES}


def test_fonderie_transport_dates_imprimees_et_au_titre_de(ok):
    r = ok(prime(FON, "prime_transport", "2021-12-01", groupe="cadres"))
    assert r.detail["effective_date"] == "2021-12-01" and r.detail["au_titre_de"] == "2021"
    assert ok(prime(FON, "prime_transport", "2023-01-01", groupe="cadres")).detail["au_titre_de"] == "2023"
    assert ok(prime(FON, "prime_presence", "2021-12-01")).detail["au_titre_de"] == "2022"
    refus(Refus.SOURCE_MANQUANTE, prime, FON, "prime_transport", "2021-11-30", groupe="cadres")


def test_complement_chaleur_depuis_2011():
    refus(Refus.SOURCE_MANQUANTE, prime, FON, "prime_chaleur_complement", "2011-06-30", condition_remplie=True)
    refus(Refus.HORS_SCOPE, prime, FON, "prime_chaleur_complement", "2024-06-01", condition_remplie=False)


# --- primes non couvertes -----------------------------------------------------------------------------------------


@pytest.mark.parametrize("s", FICHIERS)
def test_primes_non_couvertes_refusees(s):
    for code, bloc in REEL[s]["primes_non_couvertes"].items():
        e = refus(Refus.SOURCE_MANQUANTE, prime, s, code, "2024-06-01")
        assert e.message_fr == bloc["message_fr"] and f"page {bloc['source_pdf_page']}" in e.message_fr


def test_agricole_transport_refuse_avec_les_montants_imprimes():
    e = refus(Refus.SOURCE_MANQUANTE, prime, AGR, "prime_transport", "2019-06-01")
    for x in ("78,996", "84,960", "84,131", "90,483", "avenant n° 15"):
        assert x in e.message_fr


def test_textile_assiduite_refusee_avec_les_deux_lignes():
    e = refus(Refus.SOURCE_MANQUANTE, prime, TEX, "prime_assiduite", "2021-10-01")
    for x in ("12,330", "13,193", "septembre 2021", "mai 2021", "antérieure"):
        assert x in e.message_fr


def test_fonderie_panier_plus_de_trois_decimales():
    e = refus(Refus.SOURCE_MANQUANTE, prime, FON, "prime_panier", "2024-06-01")
    assert "706.666" in e.message_fr
