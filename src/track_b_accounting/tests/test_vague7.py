"""Grilles de la vague 7 (D91 à D96) : jardins d'enfants et crèches, cliniques privées, location de voitures, commerce des
matériaux de construction, du bois et de l'acier, cafés, restaurants et bars, chargement et déchargement dans les ports.
Lancer depuis la racine du dépôt : pytest src/track_b_accounting/tests/test_vague7.py

Les valeurs attendues viennent de la double lecture des tableaux et des articles de primes (D91 à D96) ; elles sont
écrites ici, pas relues dans data/processed/.

Contrôle de lecture permanent : chaque cellule croît le long des degrés de sa ligne, et d'une ligne à la suivante au même
degré, dans l'ordre imprimé de chaque tableau (croissant ou décroissant, à l'intérieur de groupes de lignes pour les
ports et le commerce des matériaux). Une cellule signalée n'est jamais corrigée : elle est relue sur l'image, puis inscrite
dans ANOMALIES_IMPRIMEES_CONNUES si l'image imprime bien la valeur. Les cellules non tranchées (valeur null) sont sautées.
"""

import copy
from decimal import Decimal

import pytest
from conftest import lire_json

from track_b_accounting.calc import Refus, loaders, prime, salaire_base

JAR, CLI, LOC = "JARDINS_ENFANTS_CRECHES", "CLINIQUES_PRIVEES", "LOCATION_VOITURES"
MAT, CAF, POR = "COMMERCE_MATERIAUX_BOIS_ACIER", "CAFES_RESTAURANTS_BARS", "PORTS_CHARGEMENT_DECHARGEMENT"
FICHIERS = {
    JAR: ("jardins_enfants_creches.json", "D91", 288, 4),
    CLI: ("cliniques_privees.json", "D92", 300, 2),
    LOC: ("location_voitures.json", "D93", 340, 1),
    MAT: ("commerce_materiaux_bois_acier.json", "D94", 528, 4),
    CAF: ("cafes_restaurants_bars.json", "D95", 312, 3),
    POR: ("ports_chargement_dechargement.json", "D96", 1060, 3),
}
REEL = {s: lire_json(f"data/processed/salary_grids/{f}") for s, (f, *_) in FICHIERS.items()}
D = Decimal
SMIG = (
    "Montants de la convention en vigueur à la date d'effet de la table utilisée ; le SMIG en vigueur à la date demandée "
    "peut être supérieur, ce que Track B ne compare pas."
)
D24 = "2024-06-01"
VERIF = (
    "J'ai vérifié les 97 points de claude-docs/vague7/verification/page.html, tous conformes : 5 montants de primes "
    "écrits en toutes lettres, les 11 cellules non tranchées, les 13 cellules tranchées au zoom, les lignes croisées des "
    "ports, et un échantillon d'une ligne sur trois de chaque tableau. J'ai vérifié sur les images les 64 cas de référence "
    "TB-408 à TB-471 de claude-docs/vague7/verification/cas.html, tous conformes. Les autres cellules reposent sur la "
    "double lecture et, pour les matériaux, sur le contrôle de hausse."
)


def refus(code, f, *a, **k):
    with pytest.raises(Refus) as e:
        f(*a, **k)
    assert e.value.code == code and e.value.message_fr and e.value.message_ar
    return e.value


# --- activation, structure ---------------------------------------------------------------------------------------


@pytest.mark.parametrize("s", FICHIERS)
def test_activation_registre_et_decision(s):
    fichier, ref, _, _ = FICHIERS[s]
    g = REEL[s]
    assert g["_meta"]["secteur_code"] == s and g["_meta"]["decision_ref"] == ref
    assert loaders.GRILLES[s] == f"data/processed/salary_grids/{fichier}" and s in loaders.secteurs_disponibles()
    loaders.valider_grille(copy.deepcopy(g), fichier)
    assert (loaders.REPO_ROOT / g["_meta"]["source_file"]).is_file()
    assert VERIF in g["_meta"]["statut_verification"]


@pytest.mark.parametrize("s", FICHIERS)
def test_nombre_de_cellules_et_de_tableaux(s):
    _, _, n, tables = FICHIERS[s]
    g = REEL[s]
    assert sum(len(v) for t in g["grilles"] for v in t["valeurs"].values()) == n
    assert len(g["grilles"]) == tables


# --- cellules non tranchées (ports) ---------------------------------------------------------------------------------

NON_TRANCHEES = {
    ("PORTS_MANUTENTION_2010-05-01", "2", 11),
    ("PORTS_MANUTENTION_2010-05-01", "9", 3),
    ("PORTS_MANUTENTION_2010-05-01", "16", 7),
    ("PORTS_MANUTENTION_2010-05-01", "16", 8),
    ("PORTS_MANUTENTION_2010-05-01", "18", 8),
    ("PORTS_EXPLOITATION_ADMINISTRATION_2010-05-01", "1", 1),
    ("PORTS_EXPLOITATION_ADMINISTRATION_2010-05-01", "12", 1),
    ("PORTS_EXPLOITATION_ADMINISTRATION_2010-05-01", "17", 1),
    ("PORTS_EXPLOITATION_ADMINISTRATION_2010-05-01", "23", 15),
    ("PORTS_TITULARISES_2005_2010-05-01", "16", 20),
    ("PORTS_TITULARISES_2005_2010-05-01", "19", 15),
}


def test_cellules_nulles_exactement_les_onze_non_tranchees_des_ports():
    nulles = {
        (t["table_id"], c, j)
        for s in FICHIERS
        for t in REEL[s]["grilles"]
        for c, v in t["valeurs"].items()
        for j, x in enumerate(v, 1)
        if x is None
    }
    assert nulles == NON_TRANCHEES
    declarees = {
        (t["table_id"], m["categorie"], m["degre"])
        for t in REEL[POR]["grilles"]
        for m in t.get("cellules_source_manquante", [])
    }
    assert declarees == NON_TRANCHEES


@pytest.mark.parametrize(
    "pop, cat, annees, lu",
    [
        ("manutention", "2", 27, "368.706"),
        ("exploitation_administration", "1", D("0.5"), "276.909"),
        ("titularises_2005", "19", 40, "1014.236"),
    ],
)
def test_cellule_non_tranchee_refusee_avec_la_lecture_citee(pop, cat, annees, lu):
    e = refus(Refus.SOURCE_MANQUANTE, salaire_base, POR, pop, cat, annees, D24)
    assert lu in e.message_fr and "non tranchée" in e.message_fr


def test_cellule_non_tranchee_refusee_par_le_degre():
    refus(Refus.SOURCE_MANQUANTE, salaire_base, POR, "manutention", "16", None, D24, degre=7)


# --- contrôle de croissance permanent --------------------------------------------------------------------------------


# Ordre imprimé des lignes : « + » croissant d'une ligne à la suivante, « - » décroissant ; groupes comparés entre eux
# seulement (lignes d'un même cadre aux ports ; lignes horaires et mensuelles à part au commerce des matériaux).
def _G3(n: int) -> list[list[str]]:
    return [[str(i) for i in range(a, min(a + 3, n + 1))] for a in range(1, n + 1, 3)]


ORDRE = {
    "JARDINS_OUVRIERS_2011-07-01": ("+", None),
    "JARDINS_ADMINISTRATIFS_2011-07-01": ("+", None),
    "JARDINS_CRECHES_2011-07-01": ("-", None),
    "JARDINS_JARDINS_2011-07-01": ("-", None),
    "CLINIQUES_HORS_DIALYSE_2019-05-01": ("+", None),
    "CLINIQUES_DIALYSE_2019-05-01": ("+", None),
    "LOCATION_2019-05-01": ("+", None),
    "CAFES_CAFES_CATEGORIE_1_2010-07-01": ("-", None),
    "CAFES_MOYENS_PETITS_2010-07-01": ("-", None),
    "CAFES_GRANDS_2010-07-01": ("-", None),
    "PORTS_MANUTENTION_2010-05-01": ("+", [*_G3(15), ["16", "17", "18", "19"]]),
    "PORTS_EXPLOITATION_ADMINISTRATION_2010-05-01": ("+", _G3(24)),
    "PORTS_TITULARISES_2005_2010-05-01": ("+", [["10", "11", "12"], ["13", "14", "15"], ["16", "17", "18", "19"]]),
}

# Cellules imprimées telles quelles, relues sur l'image : (secteur, table_id, catégorie, degré) -> justification.
_CROISEE = "nettement imprimée, lue de façon identique aux deux lectures (p.25, ARRÊT 2 de la vague 7, question 1)"
ANOMALIES_IMPRIMEES_CONNUES = {
    **{
        (POR, "PORTS_MANUTENTION_2010-05-01", "2", d): f"ligne 2 sous la ligne 1 au degré {d}, {_CROISEE}"
        for d in range(16, 21)
    },
    **{
        (POR, "PORTS_MANUTENTION_2010-05-01", "6", d): f"ligne 6 sous la ligne 5 au degré {d}, {_CROISEE}"
        for d in range(18, 21)
    },
}


def non_croissantes(secteur: str, grille: dict) -> list[tuple[str, str, str, int, str]]:
    """Cellules qui ne croissent pas le long des degrés de leur ligne, ou d'une ligne à la suivante (ordre imprimé, au
    même degré, dans chaque groupe), table par table ; les cellules nulles sont sautées."""
    out = []
    for t in grille["grilles"]:
        vals = t["valeurs"]
        for cat, v in vals.items():
            for j in range(1, len(v)):
                if v[j] is not None and v[j - 1] is not None and v[j] <= v[j - 1]:
                    out.append((secteur, t["table_id"], cat, j + 1, "degres"))
        sens, groupes = ORDRE.get(t["table_id"], ("+", None))
        cats = list(vals)
        if t["table_id"].startswith("MATERIAUX_COMMERCE_"):
            groupes = [cats]
        for g in groupes or [cats]:
            for a, b in zip(g, g[1:]):
                for j, (x, y) in enumerate(zip(vals[a], vals[b]), 1):
                    if x is not None and y is not None and (y <= x if sens == "+" else y >= x):
                        out.append((secteur, t["table_id"], b, j, "categories"))
    return out


@pytest.mark.parametrize("s", FICHIERS)
def test_croissance_le_long_des_degres_et_entre_categories(s):
    signalees = [c for c in non_croissantes(s, loaders.charger_grille(s)) if c[:4] not in ANOMALIES_IMPRIMEES_CONNUES]
    assert signalees == []


@pytest.mark.parametrize("cle", sorted(ANOMALIES_IMPRIMEES_CONNUES))
def test_chaque_anomalie_connue_est_encore_signalee_et_declaree(cle):
    s, tid, cat, degre = cle
    assert any(c[:4] == cle for c in non_croissantes(s, loaders.charger_grille(s)))
    t = next(t for t in REEL[s]["grilles"] if t["table_id"] == tid)
    assert any((o["categorie"], o["degre"]) == (cat, degre) for o in t["observations_imprimees"])


def test_les_grilles_a_une_seule_date_sont_celles_du_controle_de_hausse():
    from test_controle_hausse import GRILLES_UNE_SEULE_TABLE

    assert {JAR, CLI, LOC, CAF, POR} <= GRILLES_UNE_SEULE_TABLE
    assert MAT not in GRILLES_UNE_SEULE_TABLE


@pytest.mark.parametrize(
    "s, tid, cat, degre, delta",
    [
        (JAR, "JARDINS_JARDINS_2011-07-01", "3", 5, D("100")),  # au-dessus de la ligne 2 (ordre décroissant)
        (CAF, "CAFES_GRANDS_2010-07-01", "4", 13, D("-50")),
        (POR, "PORTS_TITULARISES_2005_2010-05-01", "11", 4, D("-10")),  # sous la ligne 10 du même cadre
        (MAT, "MATERIAUX_COMMERCE_MENSUELS_2019-05-01", "7", 1, D("-500")),
        (LOC, "LOCATION_2019-05-01", "9", 20, D("-100")),  # sous le degré 19
    ],
)
def test_sensibilite_une_cellule_modifiee_est_detectee(s, tid, cat, degre, delta):
    g = copy.deepcopy(loaders.charger_grille(s))
    assert [c for c in non_croissantes(s, g) if c[:4] not in ANOMALIES_IMPRIMEES_CONNUES] == []
    t = next(t for t in g["grilles"] if t["table_id"] == tid)
    t["valeurs"][cat][degre - 1] += delta
    assert [c for c in non_croissantes(s, g) if c[:4] not in ANOMALIES_IMPRIMEES_CONNUES] != []


def test_materiaux_hausse_constante_par_ligne_entre_2018_et_2019():
    t = {x["table_id"]: x["valeurs"] for x in REEL[MAT]["grilles"]}
    for pop in ("HORAIRES", "MENSUELS"):
        a, b = t[f"MATERIAUX_COMMERCE_{pop}_2018-05-01"], t[f"MATERIAUX_COMMERCE_{pop}_2019-05-01"]
        for cat in a:
            assert len({y - x for x, y in zip(a[cat], b[cat])}) == 1 and b[cat][0] > a[cat][0]


# --- salaires servis -------------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "s, pop, cat, annees, date, montant, unite, page",
    [
        (JAR, "ouvriers", "3", 9, D24, "386.185", "TND/mois", 20),
        (JAR, "jardins", "7", 35, D24, "408.763", "TND/mois", 21),
        (JAR, "creches", "2", D("0.5"), "2011-07-01", "458.808", "TND/mois", 21),
        (JAR, "administratifs", "2", 20, D24, "452.996", "TND/mois", 20),
        (CLI, "cliniques", "C2", 29, D24, "1916.763", "TND/mois", 16),
        (CLI, "centres_dialyse", "E1", D("0.5"), D24, "457.215", "TND/mois", 16),
        (CLI, "cliniques", "M3", 12, D24, "1215.735", "TND/mois", 16),
        (LOC, None, "17", 29, D24, "1723.405", "TND/mois", 19),
        (LOC, None, "17", 11, D24, "1549.933", "TND/mois", 19),
        (LOC, None, "1", D("0.5"), "2019-05-01", "521.240", "TND/mois", 19),
        (MAT, "horaires", "1", D("2.5"), D24, "3.005", "TND/heure", 21),
        (MAT, "horaires", "1", D("0.5"), "2018-06-01", "2.792", "TND/heure", 20),
        (MAT, "mensuels", "2", 10, "2018-06-01", "514.431", "TND/mois", 20),
        (MAT, "mensuels", "20", 26, D24, "1435.788", "TND/mois", 21),
        (CAF, "grands", "8", D("0.5"), D24, "301.770", "TND/mois", 31),
        (CAF, "cafes_categorie_1", "1", 40, D24, "477.332", "TND/mois", 31),
        (CAF, "moyens_petits", "4", 6, D24, "388.045", "TND/mois", 31),
        (POR, "manutention", "1", 55, D24, "394.990", "TND/mois", 25),
        (POR, "manutention", "2", 52, D24, "383.085", "TND/mois", 25),
        (POR, "manutention", "6", 4, D24, "458.250", "TND/mois", 25),  # tranchée au zoom
        (POR, "exploitation_administration", "24", D("0.5"), D24, "557.784", "TND/mois", 26),
        (POR, "titularises_2005", "10", 2, "2010-05-01", "668.535", "TND/mois", 27),
    ],
)
def test_salaires_servis(s, pop, cat, annees, date, montant, unite, page):
    r = salaire_base(s, pop, cat, annees, date)
    assert (r.montant, r.unite, r.citations[0].page) == (D(montant), unite, page)


@pytest.mark.parametrize(
    "s, pop, cat",
    [
        (JAR, "jardins", "1"),
        (CLI, "cliniques", "E1"),
        (LOC, None, "3"),
        (MAT, "mensuels", "5"),
        (CAF, "grands", "2"),
        (POR, "manutention", "4"),
    ],
)
def test_hypothese_smig_dans_chaque_reponse_de_salaire(s, pop, cat):
    r = salaire_base(s, pop, cat, D("0.5"), D24)
    assert SMIG in r.detail["hypotheses"]
    r1 = salaire_base(s, pop, cat, None, D24, degre=2)
    assert SMIG in r1.detail["hypotheses"]


def test_cafes_colonne_de_recrutement_et_dernier_degre_ouvert():
    r = salaire_base(CAF, "grands", "3", None, D24, degre="الانتداب")
    assert r.montant == D("423.227") and r.detail["degre_imprime"] == "الانتداب"
    assert salaire_base(CAF, "cafes_categorie_1", "5", None, D24, degre="12").montant == D("388.635")
    assert (
        salaire_base(CAF, "grands", "8", 60, D24).montant
        == salaire_base(CAF, "grands", "8", D("25.5"), D24).montant
        == D("317.129")
    )
    h = " ".join(salaire_base(CAF, "cafes_categorie_1", "1", D("0.5"), D24).detail["hypotheses"])
    assert "cafés de première catégorie" in h
    assert "cafés de première catégorie" not in " ".join(
        salaire_base(CAF, "grands", "1", D("0.5"), D24).detail["hypotheses"]
    )


@pytest.mark.parametrize(
    "s, pop, cat, annees, code, extrait",
    [
        (JAR, "jardins", "1", 36, Refus.SOURCE_MANQUANTE, "article 15 ب"),
        (CLI, "centres_dialyse", "C1", 30, Refus.SOURCE_MANQUANTE, "article 13 (جديد)"),
        (LOC, None, "5", 31, Refus.SOURCE_MANQUANTE, "article 17 ب (page 8)"),
        (LOC, None, "5", 38, Refus.SOURCE_MANQUANTE, "article 17 ب"),
        (MAT, "mensuels", "5", 27, Refus.SOURCE_MANQUANTE, "article 13"),
        (CAF, "grands", "2", 2, Refus.SOURCE_MANQUANTE, "article 53 (جديد) (page 14)"),
        (CAF, "grands", "2", 3, Refus.SOURCE_MANQUANTE, "de 1 an exclu à 3 ans inclus"),
        (POR, "titularises_2005", "15", 56, Refus.SOURCE_MANQUANTE, "article 12"),
    ],
)
def test_refus_de_degre(s, pop, cat, annees, code, extrait):
    e = refus(code, salaire_base, s, pop, cat, annees, D24)
    assert extrait in e.message_fr


@pytest.mark.parametrize(
    "s, pop, cat, avant, premiere",
    [
        (JAR, "ouvriers", "1", "2011-06-30", "2011-07-01"),
        (CLI, "cliniques", "E2", "2019-04-30", "2019-05-01"),
        (LOC, None, "8", "2019-04-30", "2019-05-01"),
        (MAT, "horaires", "2", "2018-04-30", "2018-05-01"),
        (CAF, "moyens_petits", "1", "2010-06-30", "2010-07-01"),
        (POR, "manutention", "3", "2010-04-30", "2010-05-01"),
    ],
)
def test_refus_avant_le_tableau_imprime(s, pop, cat, avant, premiere):
    e = refus(Refus.SOURCE_MANQUANTE, salaire_base, s, pop, cat, D("0.5"), avant)
    assert premiere in e.message_fr


@pytest.mark.parametrize("s, cat", [(JAR, "1"), (CLI, "E1"), (MAT, "1"), (CAF, "1"), (POR, "1")])
def test_population_obligatoire(s, cat):
    refus(Refus.PARAM_INVALIDE, salaire_base, s, None, cat, D("0.5"), D24)


@pytest.mark.parametrize(
    "s, pop, cat, degre, montant",
    [
        (POR, "titularises_2005", "19", 20, "1076.610"),
        (JAR, "creches", "4", 16, "467.429"),
        (MAT, "horaires", "2", 12, "3.209"),
        (LOC, None, "17", 16, "1723.405"),
    ],
)
def test_servies_par_le_degre(s, pop, cat, degre, montant):
    r = salaire_base(s, pop, cat, None, D24, degre=degre)
    assert r.montant == D(montant) and r.detail["degre_declare"] is True


def test_location_degres_17_a_20_servis_par_le_degre_avec_l_article_cite():
    r = salaire_base(LOC, None, "17", None, D24, degre=18)
    assert r.montant == D("1761.853") and r.detail["degre_declare"] is True
    phrase = (
        "l'art. 17 ب ne prévoit que 16 degrés ; les degrés 17 à 20 sont servis parce qu'ils sont imprimés à l'en-tête"
    )
    assert any(phrase in h for h in r.detail["hypotheses"])
    refus(Refus.SOURCE_MANQUANTE, salaire_base, LOC, None, "17", 33, D24)


# --- primes ---------------------------------------------------------------------------------------------------------

OUI = {"condition_remplie": True}
PRIMES = [
    (JAR, "prime_presence_ouvriers", "2003-08-01", {}, "6.080", "TND/mois"),
    (JAR, "prime_presence_ouvriers", D24, {}, "8.080", "TND/mois"),
    (JAR, "prime_transport_ouvriers_ligne_5", D24, {}, "35.613", "TND/mois"),
    (JAR, "prime_transport_admin_comptable", D24, {}, "39.000", "TND/mois"),
    (JAR, "prime_specifique_admin", "2002-07-01", {"groupe": "comptable"}, "21.400", "TND/mois"),
    (JAR, "prime_pedagogique_rang_1", D24, {}, "51.000", "TND/mois"),
    (JAR, "prime_pedagogique_rang_4", "2003-07-01", {}, "30.800", "TND/mois"),
    (JAR, "prime_transport_jardins_rang_6", D24, {}, "18.000", "TND/mois"),
    (JAR, "prime_transport_creches_rang_3", "2004-07-01", {}, "21.000", "TND/mois"),
    (JAR, "prime_specifique_creches_rang_2", D24, {}, "31.500", "TND/mois"),
    (JAR, "prime_production_creches", D24, {}, "28.000", "TND/mois"),
    (JAR, "prime_directeur_100_enfants_et_plus", D24, OUI, "100.000", "TND/mois"),
    (CLI, "prime_travail_nuit", D24, {}, "3.666", "TND/nuit"),
    (CLI, "prime_transport", "2016-09-01", {"groupe": "maitrise"}, "57.945", "TND/mois"),
    (CLI, "prime_transport", D24, {"groupe": "cadres"}, "69.287", "TND/mois"),
    (CLI, "prime_presence", "2017-05-01", {}, "3.370", "TND/mois"),
    (CLI, "prime_specialite_chef_cuisine", D24, OUI, "40.000", "TND/mois"),
    (CLI, "prime_specialite_dialyse_infirmier", D24, OUI, "15.000", "TND/mois"),
    (CLI, "prime_risque_contagion", "2016-08-01", {}, "15.900", "TND/mois"),
    (LOC, "prime_fonction_directeur_general", D24, OUI, "110.000", "TND/mois"),
    (LOC, "prime_transport", "2018-05-01", {"groupe": "execution_maitrise"}, "47.865", "TND/mois"),
    (LOC, "prime_presence", D24, {"groupe": "maitrise"}, "11.571", "TND/mois"),
    (LOC, "aide_aid_el_adha", D24, {}, "30.000", "TND/versement"),
    (LOC, "prime_scolaire_creche_jardin", D24, {}, "10.000", "TND/enfant"),
    (MAT, "prime_transport", "2018-05-01", {}, "61.029", "TND/mois"),
    (MAT, "prime_deplacement_nuitee", D24, OUI, "2.700", "TND/nuitee"),
    (MAT, "prime_panier", D24, OUI, "0.433", "TND/jour"),
    (MAT, "prime_presence", D24, {}, "6.473", "TND/mois"),
    (MAT, "prime_representation_sous_chef_service", D24, OUI, "20.000", "TND/mois"),
    (MAT, "prime_rentree_scolaire", D24, {}, "20.000", "TND/enfant"),
    (CAF, "prime_transport_cat1_3_moyens_grands", "2008-07-01", {}, "15.700", "TND/mois"),
    (CAF, "prime_transport_cat1_3_petits", "2008-09-01", {}, "15.700", "TND/mois"),
    (CAF, "prime_transport_cat4_6_petits", "2009-07-01", {}, "13.900", "TND/mois"),
    (CAF, "prime_transport_cat7_8_moyens_grands", D24, {}, "12.100", "TND/mois"),
    (CAF, "prime_caisse_moyens", D24, {}, "5.000", "TND/mois"),
    (CAF, "prime_caisse_petits", D24, OUI, "3.000", "TND/mois"),
    (POR, "prime_logement", D24, OUI, "32.736", "TND/mois"),
    (POR, "prime_risque_autres", D24, OUI, "29.000", "TND/mois"),
    (POR, "prime_rendement_complementaire", D24, {}, "12.500", "TND/mois"),
    (POR, "prime_transport_manutention", "2008-06-01", {"groupe": "encadrement"}, "12.500", "TND/mois"),
    (POR, "prime_transport_exploitation", D24, {"groupe": "execution_maitrise"}, "10.000", "TND/mois"),
    (POR, "prime_pollution_titularises_2005_entreprises_privees", D24, OUI, "29.500", "TND/mois"),
    (POR, "prime_logement_titularises_2005", D24, OUI, "52.736", "TND/mois"),
    (POR, "prime_risque_titularises_2005_conducteurs_chefs", D24, OUI, "71.500", "TND/mois"),
    (POR, "prime_risque_titularises_2005_autres", D24, OUI, "49.000", "TND/mois"),
    (POR, "prime_presence_exploitation", D24, {}, "2.080", "TND/mois"),
    (POR, "prime_productivite_exploitation", D24, {}, "7.500", "TND/mois"),
    (POR, "prime_descente_en_cale", D24, OUI, "4.000", "TND/operation"),
    (POR, "prime_tresorerie_agent", D24, OUI, "20.000", "TND/mois"),
    (POR, "aide_deces", D24, OUI, "300.000", "TND/versement"),
]


@pytest.mark.parametrize("s, code, date, params, montant, unite", PRIMES)
def test_primes_servies(s, code, date, params, montant, unite):
    r = prime(s, code, date, **params)
    assert (r.montant, r.unite) == (D(montant), unite)


def test_nombre_de_montants_de_primes():
    n = {
        s: sum(
            len(p.get("montants", [None]))
            * max(1, len(set(p.get("montants", [{}])[0]) - {"effective_date", "montant"}))
            for p in REEL[s]["primes"]
        )
        for s in FICHIERS
    }
    # jardins : 90 imprimés moins les 3 du rang 6 (« 25.7000 ») ; cafés : 12 montants imprimés, 21 entrées datées
    # (2009 et 2010 portés par les deux codes de taille de chaque groupe) ; ports : 30.
    assert n == {JAR: 87, CLI: 22, LOC: 18, MAT: 12, CAF: 21, POR: 30}


def test_ports_article_75_codes_propres_et_conditions():
    for code in ("prime_logement", "prime_risque_conducteurs_chefs", "prime_risque_autres"):
        p = next(p for p in REEL[POR]["primes"] if p["code"] == code)
        assert "tableau n° 9" in p["condition"] and "article 75 (جديد)" in p["condition"]
        e = refus(Refus.HORS_SCOPE, prime, POR, code, D24, condition_remplie=False)
        assert "tableau n° 9" in e.message_fr
    r = prime(POR, "prime_logement_titularises_2005", D24, **OUI)
    assert any("le texte ne dit pas" in h for h in r.detail["hypotheses"]) and r.citations[0].page == 22


@pytest.mark.parametrize(
    "code, art",
    [
        ("prime_logement_art43_titularises_2005", "43"),
        ("prime_risque_art47_titularises_2005_conducteurs_chefs", "47"),
        ("prime_risque_art47_titularises_2005_autres", "47"),
    ],
)
def test_ports_variantes_des_articles_43_et_47_refusees_pour_le_tableau_9(code, art):
    e = refus(Refus.SOURCE_MANQUANTE, prime, POR, code, D24)
    assert f"article {art}" in e.message_fr and "article 75 (جديد) (page 22)" in e.message_fr


def test_cafes_transport_2008_selon_la_taille():
    refus(Refus.SOURCE_MANQUANTE, prime, CAF, "prime_transport_cat1_3_petits", "2008-08-31")
    assert prime(CAF, "prime_transport_cat1_3_moyens_grands", "2008-08-31").montant == D("15.700")
    assert prime(CAF, "prime_transport_cat1_3_petits", D24).montant == D("17.100")


def test_jardins_hypothese_texte_consolide_et_articles_jamais_revises():
    h = prime(JAR, "prime_presence_ouvriers", D24).detail["hypotheses"]
    assert any("avenant n° 3" in x for x in h)
    h = prime(JAR, "prime_pedagogique_rang_2", D24).detail["hypotheses"]
    assert any("jamais révisé" in x for x in h)


def test_cliniques_deduction_de_l_article_47_en_hypothese():
    h = prime(CLI, "prime_specialite_infirmier", D24, **OUI).detail["hypotheses"]
    assert any("n'est pas calculée" in x and "article 47 (جديد)" in x.replace("Article", "article") for x in h)


@pytest.mark.parametrize(
    "s, code, motif",
    [
        (JAR, "prime_pedagogique_rang_6", "25.7000"),
        (JAR, "prime_production_ouvriers", "230 %"),
        (CLI, "prime_production", "50 %"),
        (LOC, "salaire_13e_mois", "un mois de salaire"),
        (MAT, "prime_deces", "366.666"),
        (CAF, "repas", "en nature"),
        (POR, "prime_forfaitaire_compensatoire", "STAM"),
        (POR, "complement_bon_repas", "500 millimes"),
        (POR, "prime_amarrage_navire", "entre 6 et 20"),
    ],
)
def test_primes_non_couvertes(s, code, motif):
    e = refus(Refus.SOURCE_MANQUANTE, prime, s, code, D24)
    assert motif in e.message_fr
