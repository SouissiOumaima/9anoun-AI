"""Grilles de la vague 6 (D84 à D89) : clercs d'avocats, personnel des pharmacies, conserveries et conditionnement des
huiles, grossistes répartiteurs de médicaments, salles de cinéma, transport routier de marchandises.
Lancer depuis la racine du dépôt : pytest src/track_b_accounting/tests/test_vague6.py

Les valeurs attendues viennent de la double lecture des tableaux et des articles de primes (D84 à D89) ; elles sont
écrites ici, pas relues dans data/processed/.

Contrôle de lecture permanent des grilles à une seule date (GRILLES_UNE_SEULE_TABLE du contrôle de hausse) : chaque
cellule croît le long des degrés de sa ligne, et d'une ligne à la suivante au même degré, dans l'ordre imprimé. Une
cellule signalée n'est jamais corrigée : elle est relue sur l'image, puis inscrite dans ANOMALIES_IMPRIMEES_CONNUES si
l'image imprime bien la valeur.
"""

import copy
from decimal import Decimal

import pytest
from conftest import lire_json

from track_b_accounting.calc import Refus, loaders, prime, salaire_base

CLE, PHA, CON = "CLERCS_AVOCATS", "PERSONNEL_PHARMACIES", "CONSERVERIES_CONDITIONNEMENT_HUILES"
GRO, CIN, TRA = "GROSSISTES_REPARTITEURS_MEDICAMENTS", "SALLES_CINEMA", "TRANSPORT_ROUTIER_MARCHANDISES"
FICHIERS = {
    CLE: ("clercs_avocats.json", "D84", 36, 1),
    PHA: ("pharmacies.json", "D85", 120, 2),
    CON: ("conserveries_huiles.json", "D86", 130, 2),
    GRO: ("grossistes_medicaments.json", "D87", 165, 1),
    CIN: ("salles_cinema.json", "D88", 169, 1),
    TRA: ("transport_routier_marchandises.json", "D89", 260, 1),
}
REEL = {s: lire_json(f"data/processed/salary_grids/{f}") for s, (f, *_) in FICHIERS.items()}
D = Decimal
VERIF = (
    "J'ai vérifié les 42 points de claude-docs/vague6/verification/page.html, tous conformes : 12 montants de primes "
    "écrits en toutes lettres (7 en lettres seulement, 5 en lettres et en chiffres), les 2 anomalies des clercs et les 3 "
    "observations des grossistes au zoom, et un échantillon d'une ligne sur trois de chaque tableau. Les autres cellules "
    "reposent sur la double lecture et, pour les pharmacies, sur le contrôle de hausse."
)
SMIG = (
    "Montants de la convention en vigueur à la date d'effet de la table utilisée ; le SMIG en vigueur à la date demandée "
    "peut être supérieur, ce que Track B ne compare pas."
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
    assert all(x is not None for t in g["grilles"] for v in t["valeurs"].values() for x in v)


# --- contrôle de croissance permanent (grilles à une seule date) --------------------------------------------------

UNE_SEULE_DATE = [CLE, CON, GRO, CIN, TRA]

# Cellules non croissantes imprimées telles quelles, relues sur l'image au zoom à 400 dpi :
# (secteur, table_id, catégorie, degré) -> justification.
ANOMALIES_IMPRIMEES_CONNUES = {
    (CLE, "CLERCS_2014-05-01", "1", 2): "335.555 < degré 1 (337.758), nettement imprimé (annexe 1, p.12, ligne 1)",
    (CLE, "CLERCS_2014-05-01", "1", 5): "348.380 < degré 4 (348.804), nettement imprimé (annexe 1, p.12, ligne 1)",
}


def non_croissantes(secteur: str, grille: dict) -> list[tuple[str, str, str, int, str]]:
    """Cellules qui ne croissent pas le long des degrés de leur ligne, ou d'une ligne à la suivante (ordre imprimé,
    au même degré), table par table."""
    out = []
    for t in grille["grilles"]:
        lignes = list(t["valeurs"].items())
        for cat, v in lignes:
            for j in range(1, len(v)):
                if v[j] <= v[j - 1]:
                    out.append((secteur, t["table_id"], cat, j + 1, "degres"))
        for (_, a), (cat, b) in zip(lignes, lignes[1:]):
            for j, (x, y) in enumerate(zip(a, b), 1):
                if y <= x:
                    out.append((secteur, t["table_id"], cat, j, "categories"))
    return out


@pytest.mark.parametrize("s", UNE_SEULE_DATE)
def test_croissance_le_long_des_degres_et_entre_categories(s):
    signalees = [c for c in non_croissantes(s, loaders.charger_grille(s)) if c[:4] not in ANOMALIES_IMPRIMEES_CONNUES]
    assert signalees == []


@pytest.mark.parametrize("cle", sorted(ANOMALIES_IMPRIMEES_CONNUES))
def test_chaque_anomalie_connue_est_encore_signalee_et_declaree(cle):
    s, tid, cat, degre = cle
    assert any(c[:4] == cle for c in non_croissantes(s, loaders.charger_grille(s)))
    t = next(t for t in REEL[s]["grilles"] if t["table_id"] == tid)
    assert any((a["categorie"], a["degre"]) == (cat, degre) for a in t["anomalies_imprimees"])


def test_les_grilles_a_une_seule_date_sont_celles_du_controle_de_hausse():
    from test_controle_hausse import GRILLES_UNE_SEULE_TABLE

    assert set(UNE_SEULE_DATE) <= GRILLES_UNE_SEULE_TABLE
    assert PHA not in GRILLES_UNE_SEULE_TABLE


@pytest.mark.parametrize(
    "s, tid, cat, degre, delta",
    [
        (TRA, "TRANSPORT_2017-05-01", "12", 7, D("-50")),  # chiffre des dizaines mal lu : sous le degré 6
        (CIN, "CINEMA_2011-05-01", "III_3", 13, D("-1000")),
        (GRO, "GROSS_2010-05-01", "IV_2", 4, D("10")),  # au-dessus du degré 5
        (CON, "CONS_HORAIRES_2019-06-01", "3", 1, D("0.300")),  # au-dessus de la ligne 4
        (CLE, "CLERCS_2014-05-01", "2", 12, D("-100")),
    ],
)
def test_sensibilite_une_cellule_modifiee_est_detectee(s, tid, cat, degre, delta):
    g = copy.deepcopy(loaders.charger_grille(s))
    assert [c for c in non_croissantes(s, g) if c[:4] not in ANOMALIES_IMPRIMEES_CONNUES] == []
    t = next(t for t in g["grilles"] if t["table_id"] == tid)
    t["valeurs"][cat][degre - 1] += delta
    assert [c for c in non_croissantes(s, g) if c[:4] not in ANOMALIES_IMPRIMEES_CONNUES] != []


def test_observations_des_grossistes_conservees_et_notees():
    t = REEL[GRO]["grilles"][0]
    obs = {(o["categorie"], o["degre"]): o["valeur_imprimee"] for o in t["observations_imprimees"]}
    assert obs == {("IV_2", 9): D("550.618"), ("I_1", 12): D("400.006"), ("I_2", 11): D("399.445")}
    assert all("nettement imprimée" in o["note"] for o in t["observations_imprimees"])
    assert "550.618" in REEL[GRO]["_meta"]["note_observations"]


# --- salaires servis -------------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "s, pop, cat, sous, annees, date, montant, unite, page",
    [
        (CLE, None, "1", None, D("1.5"), "2024-06-01", "335.555", "TND/mois", 12),
        (CLE, "clercs", "3", None, 29, "2014-05-01", "545.736", "TND/mois", 12),
        (PHA, None, "V", None, 28, "2021-12-31", "1431.378", "TND/mois", 15),
        (PHA, None, "I", None, D("0.5"), "2021-01-01", "578.749", "TND/mois", 15),
        (CON, "horaires", "1", None, 1, "2024-06-01", "2.445", "TND/heure", 20),
        (CON, "mensuels", "5", None, 25, "2024-06-01", "1069.021", "TND/mois", 20),
        (GRO, None, "IV", "2", D("17.5"), "2020-01-01", "557.487", "TND/mois", 19),
        (GRO, None, "VI", None, D("0.5"), "2010-05-01", "598.450", "TND/mois", 19),
        (CIN, None, "III_6", None, 25, "2020-01-01", "452.878", "TND/mois", 17),
        (TRA, None, "20", None, 40, "2024-06-01", "854.523", "TND/mois", 18),
        (TRA, None, "1", None, D("0.5"), "2017-05-01", "397.893", "TND/mois", 18),
    ],
)
def test_salaires_servis(s, pop, cat, sous, annees, date, montant, unite, page):
    r = salaire_base(s, pop, cat, annees, date, sous_categorie=sous)
    assert (r.montant, r.unite, r.citations[0].page) == (D(montant), unite, page)


@pytest.mark.parametrize("s, cat, sous", [(CLE, "2", None), (GRO, "I", "1"), (CIN, "I_1", None), (TRA, "5", None)])
def test_hypothese_smig_dans_chaque_reponse_de_salaire(s, cat, sous):
    r = salaire_base(s, None, cat, D("2.5"), "2024-06-01", sous_categorie=sous)
    assert SMIG in r.detail["hypotheses"]
    r1 = salaire_base(s, None, cat, None, "2024-06-01", None, sous, degre=2)
    assert SMIG in r1.detail["hypotheses"]


@pytest.mark.parametrize("s, pop, cat", [(PHA, None, "I"), (CON, "mensuels", "1")])
def test_pas_d_hypothese_smig_hors_des_quatre_secteurs(s, pop, cat):
    assert SMIG not in salaire_base(s, pop, cat, 3, "2021-06-01" if s == PHA else "2024-06-01").detail["hypotheses"]


def test_transport_cite_la_note_2():
    h = " ".join(salaire_base(TRA, None, "3", D("2.5"), "2024-06-01").detail["hypotheses"])
    assert "Note 2 sous le tableau n° 2 (page 18)" in h and "48 heures" in h


def test_clercs_date_d_effet_en_hypothese_et_refus_avant():
    h = " ".join(salaire_base(CLE, None, "1", 3, "2014-05-01").detail["hypotheses"])
    assert "1er mai 2014" in h and "article 47, page 11" in h
    e = refus(Refus.SOURCE_MANQUANTE, salaire_base, CLE, None, "1", 3, "2014-04-30")
    assert "2014-05-01" in e.message_fr


def test_conserveries_ecart_cumule_toutes_categories():
    # dernier degré (24 ans) + 1 écart (degré 13 − degré 12) au-delà de 26 ans
    r = salaire_base(CON, "mensuels", "5", 27, "2024-06-01")
    assert r.montant == D("1069.021") + (D("1069.021") - D("1055.390"))
    assert r.detail["n_paliers"] == 1 and len(r.citations) == 2
    r = salaire_base(CON, "horaires", "1", D("28.5"), "2024-06-01")
    assert r.montant == D("2.645") + 2 * (D("2.645") - D("2.628"))


@pytest.mark.parametrize("annees", [26, 28, 30])
def test_conserveries_paliers_exacts(annees):
    refus(Refus.PARAM_INVALIDE, salaire_base, CON, "horaires", "3", annees, "2024-06-01")


def test_transport_dernier_degre_ouvert():
    assert salaire_base(TRA, None, "10", 60, "2024-06-01").montant == D("625.357")
    assert salaire_base(TRA, None, "10", D("24.5"), "2024-06-01").montant == D("625.357")


def test_pharmacies_fin_de_validite_et_avenant_16_cite():
    assert salaire_base(PHA, None, "III", 10, "2021-12-31").montant == D("896.892")
    e = refus(Refus.SOURCE_MANQUANTE, salaire_base, PHA, None, "III", 10, "2022-01-01")
    assert "avenant n° 16 (page 3" in e.message_fr and "2021-12-31" in e.message_fr
    e = refus(Refus.SOURCE_MANQUANTE, salaire_base, PHA, None, "III", None, "2022-01-01", degre=1)
    assert "avenant n° 16" in e.message_fr
    assert salaire_base(PHA, None, "III", 10, "2021-04-30").montant == D("842.152")


@pytest.mark.parametrize(
    "s, pop, cat, sous, annees, code, extrait",
    [
        (CLE, None, "3", None, 30, Refus.SOURCE_MANQUANTE, "article 11"),
        (PHA, None, "I", None, 29, Refus.SOURCE_MANQUANTE, "article 11 (جديد)"),
        (GRO, None, "V", "1", 29, Refus.SOURCE_MANQUANTE, "article 12"),
        (CIN, None, "I_1", None, 26, Refus.SOURCE_MANQUANTE, "ne précise pas le montant"),
        (CIN, None, "II_2", None, 40, Refus.SOURCE_MANQUANTE, "article 12 (جديد) (page 8)"),
        (TRA, None, "1", None, 4, Refus.PARAM_INVALIDE, "borne commune"),
    ],
)
def test_refus_de_degre(s, pop, cat, sous, annees, code, extrait):
    e = refus(code, salaire_base, s, pop, cat, annees, "2020-01-01" if s != PHA else "2021-06-01", sous_categorie=sous)
    assert extrait in e.message_fr


@pytest.mark.parametrize(
    "s, pop, cat, sous, avant, premiere",
    [
        (CON, "mensuels", "1", None, "2019-05-31", "2019-06-01"),
        (GRO, None, "I", "1", "2010-04-30", "2010-05-01"),
        (TRA, None, "1", None, "2017-04-30", "2017-05-01"),
        (CIN, None, "I_1", None, "2011-04-30", "2011-05-01"),
        (PHA, None, "I", None, "2020-10-31", "2020-11-01"),
    ],
)
def test_refus_avant_le_tableau_imprime(s, pop, cat, sous, avant, premiere):
    e = refus(Refus.SOURCE_MANQUANTE, salaire_base, s, pop, cat, D("2.5"), avant, sous_categorie=sous)
    assert premiere in e.message_fr


def test_grossistes_sous_ligne_obligatoire():
    refus(Refus.PARAM_INVALIDE, salaire_base, GRO, None, "II", 3, "2020-01-01")
    assert salaire_base(GRO, None, "II", 2, "2020-01-01", sous_categorie="1").montant == D("392.298")
    assert salaire_base(GRO, None, "II", 2, "2020-01-01", sous_categorie="2").montant == D("396.526")


@pytest.mark.parametrize(
    "s, cat, sous, degre, montant",
    [
        (CIN, "III_6", None, 13, "452.878"),
        (TRA, "20", None, 13, "854.523"),
        (CLE, "1", None, 2, "335.555"),
        (GRO, "IV", "2", 9, "550.618"),
    ],
)
def test_servies_par_le_degre(s, cat, sous, degre, montant):
    r = salaire_base(s, None, cat, None, "2020-01-01", None, sous, degre=degre)
    assert r.montant == D(montant) and r.detail["degre_declare"] is True


# --- primes ---------------------------------------------------------------------------------------------------------

OUI = {"condition_remplie": True}
PRIMES = [
    (PHA, "prime_travail_nuit", "2024-06-01", OUI, "10.000", "TND/mois"),
    (CON, "prime_transport", "2018-07-01", {"groupe": "categories_4_5"}, "78.777", "TND/mois"),
    (CON, "prime_transport", "2024-06-01", {"groupe": "categories_1_3"}, "73.915", "TND/mois"),
    (CON, "prime_presence", "2018-06-01", {}, "13.794", "TND/mois"),
    (CON, "prime_deplacement_repas_plus_160km", "2024-06-01", OUI, "4.166", "TND/repas"),
    (CON, "prime_etudes", "2024-06-01", {}, "25.166", "TND/enfant"),
    (CON, "prime_panier", "2024-06-01", {}, "0.500", "TND/jour"),
    (CON, "prime_nuit_equipe", "2024-06-01", OUI, "0.500", "TND/nuit"),
    (GRO, "prime_transport", "2008-06-01", {}, "4.000", "TND/mois"),
    (GRO, "prime_transport", "2024-06-01", {}, "6.000", "TND/mois"),
    (GRO, "prime_presence", "2024-06-01", {}, "0.115", "TND/jour"),
    (CIN, "prime_caisse", "2024-06-01", OUI, "4.000", "TND/mois"),
    (CIN, "prime_transport", "2024-06-01", {}, "2.000", "TND/mois"),
    (CIN, "prime_lait_salete", "2024-06-01", OUI, "4.500", "TND/mois"),
    (CIN, "prime_encouragement_salle_a_cat3", "2024-06-01", OUI, "9.500", "TND/mois"),
    (CIN, "prime_encouragement_salle_t_cat1", "2024-06-01", OUI, "4.000", "TND/mois"),
    (CIN, "prime_scolaire_superieur", "2024-06-01", {}, "50.000", "TND/enfant"),
    (CIN, "prime_aid_fitr", "2024-06-01", {}, "10.000", "TND/versement"),
    (CIN, "prime_repas", "2024-06-01", OUI, "2.000", "TND/repas"),
    (TRA, "prime_kilometrique_tunisie", "2024-06-01", OUI, "0.010", "TND/km"),
    (TRA, "prime_kilometrique_etranger", "2024-06-01", OUI, "0.007", "TND/km"),
    (TRA, "prime_transport", "2016-09-01", {"groupe": "cadres"}, "58.300", "TND/mois"),
    (TRA, "prime_transport", "2024-06-01", {"groupe": "execution"}, "50.562", "TND/mois"),
    (TRA, "prime_travail_sans_accompagnateur", "2024-06-01", OUI, "50.000", "TND/mois"),
    (TRA, "prime_presence", "2017-05-01", {}, "8.988", "TND/mois"),
    (TRA, "prime_fonction_sous_directeur", "2024-06-01", OUI, "157.000", "TND/mois"),
    (TRA, "prime_panier", "2024-06-01", OUI, "3.000", "TND/jour"),
    (TRA, "prime_aid_adha", "2024-06-01", {}, "50.000", "TND/versement"),
    (TRA, "prime_scolaire_base", "2024-06-01", {}, "15.000", "TND/enfant"),
    (TRA, "prime_scolaire_secondaire", "2024-06-01", {}, "20.000", "TND/enfant"),
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
    assert n == {CLE: 0, PHA: 1, CON: 13, GRO: 4, CIN: 17, TRA: 22}


def test_cinema_encouragement_en_neuf_codes():
    codes = [p["code"] for p in REEL[CIN]["primes"] if p["code"].startswith("prime_encouragement_")]
    assert len(codes) == 9


@pytest.mark.parametrize("s, code", [(CON, "prime_etudes"), (CIN, "prime_scolaire_creche_ecole")])
def test_primes_scolaires_par_versement(s, code):
    r = prime(s, code, "2024-06-01")
    assert r.unite == "TND/enfant" and any("fréquence du versement" in h for h in r.detail["hypotheses"])


def test_plafond_et_minimum_en_note_non_appliques():
    assert "quatre enfants" in prime(CON, "prime_etudes", "2024-06-01").detail["note"]
    note = prime(TRA, "prime_kilometrique_tunisie", "2024-06-01", **OUI).detail["note"]
    assert "30 dinars" in note and "non appliqué" in note
    note = prime(TRA, "prime_travail_sans_accompagnateur", "2024-06-01", **OUI).detail["note"]
    assert "26" in note and "non calculée" in note


def test_primes_datees_avant_la_grille():
    refus(Refus.SOURCE_MANQUANTE, salaire_base, CON, "horaires", "1", 1, "2018-07-01")
    assert prime(CON, "prime_presence", "2018-07-01").montant == D("13.794")
    refus(Refus.SOURCE_MANQUANTE, prime, GRO, "prime_transport", "2008-04-30")


@pytest.mark.parametrize(
    "s, code, motif",
    [
        (CLE, "indemnite_perte_emploi", "un jour de salaire"),
        (CON, "avantages_nature", "en nature"),
        (CIN, "majoration_deux_longs_metrages", "45 %"),
        (TRA, "prime_production_annuelle", "mois de salaire"),
    ],
)
def test_primes_non_couvertes(s, code, motif):
    e = refus(Refus.SOURCE_MANQUANTE, prime, s, code, "2024-06-01")
    assert motif in e.message_fr
