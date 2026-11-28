"""Grilles de la vague 8, groupe A (D97 à D100) : électricité et électronique, presse écrite, industrie laitière,
explosifs et artifices.
Lancer depuis la racine du dépôt : pytest src/track_b_accounting/tests/test_vague8a.py

Les valeurs attendues viennent de la double lecture des tableaux et des articles de primes (D97 à D100) ; elles sont
écrites ici, pas relues dans data/processed/.

Contrôle de lecture permanent : chaque cellule croît le long des degrés de sa ligne, et d'une ligne à la suivante au même
degré, dans l'ordre imprimé de chaque tableau (électricité : exécution, maîtrise et cadres comparés à part). Les cellules
à null sont sautées ; pour les explosifs, le contrôle porte sur les cellules nettes transcrites pour la trace
(valeur_imprimee). Une cellule signalée n'est jamais corrigée : elle est relue sur l'image, puis déclarée en source
manquante si le chiffre n'est pas sûr.
"""

import copy
from decimal import Decimal

import pytest
from conftest import lire_json

from track_b_accounting.calc import Refus, loaders, prime, salaire_base

ELE, PRE, LAI, EXP = "ELECTRICITE_ELECTRONIQUE", "PRESSE_ECRITE", "INDUSTRIE_LAITIERE", "EXPLOSIFS_ARTIFICES"
FICHIERS = {
    ELE: ("electricite_electronique.json", "D97", 1980, 12),
    PRE: ("presse_ecrite.json", "D98", 3864, 6),
    LAI: ("industrie_laitiere.json", "D99", 910, 3),
    EXP: ("explosifs_artifices.json", "D100", 652, 2),
}
REEL = {s: lire_json(f"data/processed/salary_grids/{f}") for s, (f, *_) in FICHIERS.items()}
D = Decimal
SMIG = (
    "Montants de la convention en vigueur à la date d'effet de la table utilisée ; le SMIG en vigueur à la date demandée "
    "peut être supérieur, ce que Track B ne compare pas."
)
D24 = "2024-06-01"
VERIF = (
    "J'ai vérifié les 347 points de claude-docs/vague8/verification/page.html, tous conformes : 8 points de primes "
    "(en toutes lettres, refusées ou citées en note), les 82 cellules non tranchées, les 7 cellules signalées, les 12 "
    "cellules tranchées au zoom, et un échantillon d'une ligne sur trois de chaque tableau. Les autres cellules reposent "
    "sur la double lecture et sur les contrôles (hausse, pas d'indice, pas de la ligne)."
)
VERIF_CAS = (
    "J'ai vérifié sur les images les 42 cas de référence TB-473 à TB-514 de "
    "claude-docs/vague8/verification/cas_A.html, tous conformes."
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
    assert f"{VERIF} {VERIF_CAS}" in g["_meta"]["statut_verification"]


@pytest.mark.parametrize("s", FICHIERS)
def test_nombre_de_cellules_et_de_tableaux(s):
    _, _, n, tables = FICHIERS[s]
    g = REEL[s]
    assert sum(len(v) for t in g["grilles"] for v in t["valeurs"].values()) == n
    assert len(g["grilles"]) == tables


# --- cellules à null (électricité) ------------------------------------------------------------------------------------

_T = {
    1: "ELEC_EXECUTION_40H_2021-12-01",
    2: "ELEC_MAITRISE_CADRES_40H_2021-12-01",
    3: "ELEC_EXECUTION_48H_2021-12-01",
    5: "ELEC_EXECUTION_40H_2023-01-01",
    6: "ELEC_MAITRISE_CADRES_40H_2023-01-01",
    7: "ELEC_EXECUTION_48H_2023-01-01",
    8: "ELEC_MAITRISE_CADRES_48H_2023-01-01",
    9: "ELEC_EXECUTION_40H_2024-01-01",
    10: "ELEC_MAITRISE_CADRES_40H_2024-01-01",
    11: "ELEC_EXECUTION_48H_2024-01-01",
    12: "ELEC_MAITRISE_CADRES_48H_2024-01-01",
}
# Degré 7, trait blanc vertical du scan (réponse 2 à l'ARRÊT 2) : données à reprendre si une meilleure copie arrive.
DEGRE_7 = {(_T[1], c, 7) for c in ("E6", "E7", "E8", "E9", "E10")} | {
    (_T[2], "M3", 7),
    (_T[2], "C5", 7),
    (_T[3], "E2", 7),
    (_T[3], "E3", 7),  # signalée : 637.545 lu deux fois, pas d'indice contraire
    (_T[3], "E8", 7),
    (_T[5], "E10", 7),
    (_T[5], "E11", 7),
    (_T[6], "M3", 7),
    (_T[6], "M4", 7),
    (_T[7], "E1", 7),
    (_T[7], "E3", 7),
    (_T[7], "E5", 7),
    (_T[8], "M2", 7),
    (_T[8], "M6", 7),
    (_T[8], "C2", 7),
    (_T[11], "E6", 7),
}
AUTRES_NON_TRANCHEES = {
    (_T[3], "E4", 3),
    (_T[3], "E7", 12),
    (_T[3], "E8", 1),
    (_T[3], "E8", 15),
    (_T[9], "E2", 11),
    (_T[10], "M2", 10),
    (_T[11], "E6", 8),
    (_T[11], "E8", 1),
    (_T[12], "C2", 11),
}
SIGNALEES_CONSTRUCTION = {(_T[1], "E4", 2): "567.553", (_T[1], "E11", 9): "941.536"}


def test_cellules_nulles_de_l_electricite():
    assert len(DEGRE_7) == 21
    nulles = {
        (t["table_id"], c, j)
        for t in REEL[ELE]["grilles"]
        for c, v in t["valeurs"].items()
        for j, x in enumerate(v, 1)
        if x is None
    }
    assert nulles == DEGRE_7 | AUTRES_NON_TRANCHEES | set(SIGNALEES_CONSTRUCTION)
    declarees = {
        (t["table_id"], m["categorie"], m["degre"])
        for t in REEL[ELE]["grilles"]
        for m in t.get("cellules_source_manquante", [])
    }
    assert declarees == nulles


def test_presse_et_lait_sans_cellule_nulle():
    for s in (PRE, LAI):
        assert all(x is not None for t in REEL[s]["grilles"] for v in t["valeurs"].values() for x in v)


def test_valeur_lue_gardee_pour_les_cellules_signalees():
    lues = {
        (t["table_id"], m["categorie"], m["degre"]): m["valeur_lue"]
        for t in REEL[ELE]["grilles"]
        for m in t.get("cellules_source_manquante", [])
        if "valeur_lue" in m
    }
    assert lues == {(_T[3], "E3", 7): D("637.545"), **{k: D(v) for k, v in SIGNALEES_CONSTRUCTION.items()}}


@pytest.mark.parametrize(
    "pop, cat, annees, date, extrait",
    [
        ("execution_40h", "E6", 13, "2022-06-01", "trait blanc"),
        ("execution_48h", "E3", 13, "2022-06-01", "637.545"),
        ("execution_40h", "E4", 3, "2022-06-01", "567.553"),
        ("execution_40h", "E11", 17, "2022-06-01", "941.536"),
    ],
)
def test_cellule_nulle_refusee_avec_la_lecture_citee(pop, cat, annees, date, extrait):
    e = refus(Refus.SOURCE_MANQUANTE, salaire_base, ELE, pop, cat, annees, date)
    assert extrait in e.message_fr


def test_cellule_du_degre_7_refusee_par_le_degre():
    refus(Refus.SOURCE_MANQUANTE, salaire_base, ELE, "maitrise_cadres_48h", "M2", None, "2023-06-01", degre=7)


# --- contrôle de croissance permanent --------------------------------------------------------------------------------


def _valeurs(s: str, t: dict) -> dict:
    """Valeurs contrôlées : celles de la table ; explosifs : cellules nettes transcrites pour la trace."""
    if s != EXP:
        return t["valeurs"]
    vals = {c: [None] * len(v) for c, v in t["valeurs"].items()}
    for m in t["cellules_source_manquante"]:
        if "valeur_imprimee" in m:
            vals[m["categorie"]][m["degre"] - 1] = m["valeur_imprimee"]
    return vals


def non_croissantes(s: str, grille: dict) -> list[tuple[str, str, str, int, str]]:
    out = []
    for t in grille["grilles"]:
        vals = _valeurs(s, t)
        for cat, v in vals.items():
            for j in range(1, len(v)):
                if v[j] is not None and v[j - 1] is not None and v[j] <= v[j - 1]:
                    out.append((s, t["table_id"], cat, j + 1, "degres"))
        cats = list(vals)
        groupes = [[c for c in cats if c[0] == k] for k in "EMC"] if s == ELE else [cats]
        for g in groupes:
            for a, b in zip(g, g[1:]):
                for j, (x, y) in enumerate(zip(vals[a], vals[b]), 1):
                    if x is not None and y is not None and y <= x:
                        out.append((s, t["table_id"], b, j, "categories"))
    return out


@pytest.mark.parametrize("s", FICHIERS)
def test_croissance_le_long_des_degres_et_entre_categories(s):
    assert non_croissantes(s, loaders.charger_grille(s)) == []


def test_explosifs_cellules_nettes_controlees():
    n = sum(1 for t in REEL[EXP]["grilles"] for m in t["cellules_source_manquante"] if "valeur_imprimee" in m)
    assert n == 566


@pytest.mark.parametrize(
    "s, tid, cat, degre, delta",
    [
        (ELE, "ELEC_MAITRISE_CADRES_40H_2024-01-01", "C1", 5, D("-500")),  # sous C1 degré 4
        (PRE, "PRESSE_MENSUELS_2023-01-01", "33", 10, D("-100")),
        (LAI, "LAIT_OUVRIERS_2019-05-01", "II_b", 6, D("1")),  # au-dessus de la ligne suivante
    ],
)
def test_sensibilite_une_cellule_modifiee_est_detectee(s, tid, cat, degre, delta):
    g = copy.deepcopy(loaders.charger_grille(s))
    assert non_croissantes(s, g) == []
    t = next(t for t in g["grilles"] if t["table_id"] == tid)
    t["valeurs"][cat][degre - 1] += delta
    assert non_croissantes(s, g) != []


def test_les_grilles_a_une_seule_date_sont_celles_du_controle_de_hausse():
    from test_controle_hausse import GRILLES_UNE_SEULE_TABLE

    assert {LAI, EXP} <= GRILLES_UNE_SEULE_TABLE
    assert not {ELE, PRE} & GRILLES_UNE_SEULE_TABLE


# --- salaires servis -------------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "s, pop, cat, annees, date, montant, unite, page",
    [
        (ELE, "execution_40h", "E6", 13, D24, "757.453", "TND/mois", 34),
        (ELE, "maitrise_cadres_48h", "C5", 29, "2023-06-01", "2490.728", "TND/mois", 33),
        (ELE, "execution_48h", "E1", D("0.5"), "2021-12-01", "573.410", "TND/mois", 28),
        (ELE, "maitrise_cadres_40h", "M1", D("0.5"), "2022-06-01", "772.216", "TND/mois", 27),
        (PRE, "horaires", "11", D("0.5"), "2022-05-01", "5.440", "TND/heure", 30),
        (PRE, "mensuels", "52", D("15.5"), D24, "1587.771", "TND/mois", 35),
        (PRE, "mensuels", "83", D("27.5"), "2023-06-01", "2003.322", "TND/mois", 33),
        (PRE, "horaires", "42", D("10.5"), D24, "8.758", "TND/heure", 34),
        (LAI, "maitrise_techniciens", "III_b", 5, "2020-06-01", "1096.179", "TND/mois", 23),
        (LAI, "ouvriers", "I_a", D("0.5"), "2019-05-01", "2.792", "TND/heure", 24),
        (LAI, "services_administratifs", "X_b", D("22.5"), "2021-11-30", "1793.245", "TND/mois", 25),
    ],
)
def test_salaires_servis(s, pop, cat, annees, date, montant, unite, page):
    r = salaire_base(s, pop, cat, annees, date)
    assert (r.montant, r.unite, r.citations[0].page) == (D(montant), unite, page)


@pytest.mark.parametrize(
    "s, pop, cat, degre, date, montant",
    [
        (ELE, "execution_48h", "E11", 15, D24, "1320.776"),
        (PRE, "mensuels", "83", 28, D24, "2126.557"),
        (LAI, "services_administratifs", "X_b", 14, "2020-06-01", "1793.245"),
    ],
)
def test_servies_par_le_degre(s, pop, cat, degre, date, montant):
    r = salaire_base(s, pop, cat, None, date, degre=degre)
    assert r.montant == D(montant) and r.detail["degre_declare"] is True


def test_hypothese_smig_pour_le_lait_seulement():
    assert SMIG in salaire_base(LAI, "ouvriers", "I_a", D("0.5"), "2020-06-01").detail["hypotheses"]
    assert SMIG in salaire_base(LAI, "ouvriers", "I_a", None, "2020-06-01", degre=2).detail["hypotheses"]
    for s, pop, cat in ((ELE, "execution_40h", "E1"), (PRE, "mensuels", "11")):
        assert SMIG not in salaire_base(s, pop, cat, D("0.5"), D24).detail["hypotheses"]


def test_electricite_regime_et_gardiens_en_hypothese():
    h = " ".join(salaire_base(ELE, "execution_48h", "E1", D("0.5"), D24).detail["hypotheses"])
    assert "article 28 (جديد)" in h and "gardiens" in h and "ne sont pas couverts" in h
    assert "indices" in h and "ne sont pas transcrits" in h


@pytest.mark.parametrize(
    "s, pop, cat, annees, extrait",
    [
        (ELE, "maitrise_cadres_40h", "M1", 30, "article 18 أ"),
        (PRE, "mensuels", "31", 28, "article 11 (جديد)"),
        (LAI, "maitrise_techniciens", "I_a", 23, "article 13 ب"),
    ],
)
def test_refus_de_degre(s, pop, cat, annees, extrait):
    date = "2020-06-01" if s == LAI else D24
    e = refus(Refus.SOURCE_MANQUANTE, salaire_base, s, pop, cat, annees, date)
    assert extrait in e.message_fr


@pytest.mark.parametrize(
    "s, pop, cat, avant, premiere",
    [
        (ELE, "execution_48h", "E2", "2021-11-30", "2021-12-01"),
        (PRE, "horaires", "21", "2022-04-30", "2022-05-01"),
        (LAI, "services_administratifs", "I_a", "2019-04-30", "2019-05-01"),
    ],
)
def test_refus_avant_le_tableau_imprime(s, pop, cat, avant, premiere):
    e = refus(Refus.SOURCE_MANQUANTE, salaire_base, s, pop, cat, D("0.5"), avant)
    assert premiere in e.message_fr


@pytest.mark.parametrize("date", ["2021-12-01", D24])
def test_lait_refuse_apres_le_2021_11_30_avec_l_avenant_16(date):
    e = refus(Refus.SOURCE_MANQUANTE, salaire_base, LAI, "ouvriers", "VI_c", 9, date)
    assert "avenant n° 16" in e.message_fr and "2021-11-30" in e.message_fr
    refus(Refus.SOURCE_MANQUANTE, salaire_base, LAI, "ouvriers", "VI_c", None, date, degre=5)


@pytest.mark.parametrize("s, cat", [(ELE, "E1"), (PRE, "11"), (LAI, "I_a"), (EXP, "1")])
def test_population_obligatoire(s, cat):
    refus(Refus.PARAM_INVALIDE, salaire_base, s, None, cat, D("0.5"), D24)


# --- explosifs : salaire refusé en entier -------------------------------------------------------------------------


@pytest.mark.parametrize(
    "pop, n_lignes, n_degres, date", [("tableau_1_2018", 17, 14, "2018-06-01"), ("tableau_2_2019", 23, 18, D24)]
)
def test_explosifs_aucune_cellule_servie(pop, n_lignes, n_degres, date):
    g = REEL[EXP]
    assert len(g["categories"][pop]) == n_lignes and len(g["degres"][pop]) == n_degres
    assert g["_meta"]["salaire_base_servi"] is False
    for cat in g["categories"][pop]:
        e = refus(Refus.SOURCE_MANQUANTE, salaire_base, EXP, pop, cat, D("0.5"), date)
        assert "colonne des" in e.message_fr and "hors du cadre" in e.message_fr
        for degre in range(1, n_degres + 1):
            refus(Refus.SOURCE_MANQUANTE, salaire_base, EXP, pop, cat, None, date, degre=degre)


def test_explosifs_cellules_coupees_sans_valeur():
    coupees = [
        (t["table_id"], m["categorie"], m["degre"])
        for t in REEL[EXP]["grilles"]
        for m in t.get("cellules_source_manquante", [])
        if "valeur_imprimee" not in m
    ]
    assert len(coupees) == 86
    assert {d for _, _, d in coupees} == {1, 2, 3}


def test_explosifs_valeurs_imprimees_lues():
    t1, t2 = REEL[EXP]["grilles"]
    v1 = {(m["categorie"], m["degre"]): m.get("valeur_imprimee") for m in t1["cellules_source_manquante"]}
    v2 = {(m["categorie"], m["degre"]): m.get("valeur_imprimee") for m in t2["cellules_source_manquante"]}
    assert v1[("3", 5)] == D("670.802") and v2[("23", 18)] == D("2077.386") and v1[("1", 1)] is None


# --- primes ---------------------------------------------------------------------------------------------------------

OUI = {"condition_remplie": True}
PRIMES = [
    (ELE, "prime_fonction_directeur_general_adjoint", D24, OUI, "50.000", "TND/mois"),
    (ELE, "prime_fonction_chef_service", D24, OUI, "25.000", "TND/mois"),
    (ELE, "prime_transport", "2022-06-01", {"groupe": "execution_maitrise_40h"}, "66.505", "TND/mois"),
    (ELE, "prime_transport", D24, {"groupe": "cadres_48h"}, "88.778", "TND/mois"),
    (ELE, "prime_transport_nuit", D24, OUI, "5.300", "TND/mois"),
    (ELE, "prime_presence", "2023-06-01", {"groupe": "cadres_40h"}, "14.603", "TND/mois"),
    (ELE, "prime_presence", D24, {"groupe": "execution_maitrise_48h"}, "15.924", "TND/mois"),
    (ELE, "prime_panier", D24, OUI, "0.300", "TND/jour"),
    (ELE, "aide_aid_el_adha", D24, {}, "70.000", "TND/an"),
    (PRE, "prime_presence", "2022-05-01", {}, "28.501", "TND/mois"),
    (PRE, "prime_presence", D24, {}, "32.478", "TND/mois"),
    (PRE, "prime_naissance", D24, OUI, "100.000", "TND/versement"),
    (PRE, "prime_transport", "2023-01-01", {"groupe": "maitrise"}, "94.118", "TND/mois"),
    (PRE, "prime_presse", D24, OUI, "100.440", "TND/mois"),
    (PRE, "prime_deplacement", D24, {}, "16.704", "TND/mois"),
    (PRE, "prime_cout_particulier", "2022-06-01", {"groupe": "cadres"}, "46.907", "TND/mois"),
    (PRE, "prime_cout_particulier", D24, {"groupe": "execution"}, "41.760", "TND/mois"),
    (LAI, "prime_transport", "2021-12-01", {"groupe": "execution_maitrise"}, "72.385", "TND/mois"),
    (LAI, "prime_transport", "2023-06-01", {"groupe": "cadres"}, "84.516", "TND/mois"),
    (LAI, "prime_deplacement_10_12h", D24, OUI, "4.000", "TND/deplacement"),
    (LAI, "prime_deplacement_nuitee", D24, OUI, "19.000", "TND/nuitee"),
    (LAI, "prime_panier", D24, {}, "1.133", "TND/jour"),
    (LAI, "prime_froid", D24, OUI, "17.666", "TND/mois"),
    (LAI, "prime_scolaire_superieur", D24, {}, "126.666", "TND/enfant"),
    (LAI, "prime_caisse", D24, OUI, "30.000", "TND/mois"),
    (LAI, "prime_presence", D24, {}, "17.025", "TND/mois"),
    (LAI, "prime_conducteur_tracteur", D24, OUI, "12.000", "TND/mois"),
    (EXP, "prime_poussiere", D24, OUI, "0.500", "TND/jour"),
    (EXP, "prime_panier", D24, OUI, "3.000", "TND/jour"),
    (EXP, "prime_risques_speciaux", "2013-05-01", {}, "150.000", "TND/mois"),
    (EXP, "prime_particularite", D24, OUI, "200.000", "TND/mois"),
    (EXP, "prime_presence", "2018-06-01", {}, "37.095", "TND/mois"),
    (EXP, "prime_presence", D24, {}, "39.506", "TND/mois"),
    (EXP, "prime_transport", "2018-06-01", {"transport_assure": False}, "58.635", "TND/mois"),
    (EXP, "prime_transport", D24, {"transport_assure": True}, "0.000", "TND/mois"),
    (EXP, "prime_etudes_secondaire", D24, {}, "80.000", "TND/enfant"),
    (EXP, "prime_fabrication_meche", D24, OUI, "0.500", "TND/jour"),
    (EXP, "prime_employe_modele_execution", D24, OUI, "350.000", "TND/an"),
    (EXP, "aide_aid_el_fitr", D24, {}, "200.000", "TND/versement"),
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
    # presse : 35 montants imprimés, 8 de la prime scolaire refusés, « 20.999 » cité en note.
    assert n == {ELE: 31, PRE: 26, LAI: 24, EXP: 17}


def test_primes_servies_avant_ou_apres_la_grille():
    assert prime(LAI, "prime_presence", "2022-01-01").montant == D("14.940")  # après la fin de la grille du lait
    refus(Refus.SOURCE_MANQUANTE, prime, EXP, "prime_risques_speciaux", "2013-04-30")


def test_presse_presence_20_999_citee_en_note_seulement():
    r = prime(PRE, "prime_presence", "2022-05-01")
    assert "20.999" in r.detail["note"]
    refus(Refus.SOURCE_MANQUANTE, prime, PRE, "prime_presence", "2022-04-30")


@pytest.mark.parametrize(
    "s, code, motif",
    [
        (PRE, "prime_scolaire", "34.199"),
        (PRE, "prime_scolaire", "31.666"),
        (PRE, "majoration_travail_nuit", "20 %"),
        (ELE, "prime_productivite", "commission"),
        (ELE, "prime_maniement_fonds", "employeur"),
        (LAI, "avantage_nature", "en nature"),
        (EXP, "prime_productivite", "deux mois"),
        (EXP, "savon", "en nature"),
    ],
)
def test_primes_non_couvertes(s, code, motif):
    e = refus(Refus.SOURCE_MANQUANTE, prime, s, code, D24)
    assert motif in e.message_fr
