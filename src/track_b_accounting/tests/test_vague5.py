"""Grilles de la vague 5 (D78 à D83) : produits d'entretien et insecticides, constructeurs et concessionnaires
automobiles, matériaux de construction, peintures, chaussure, cuirs et tannerie.
Lancer depuis la racine du dépôt : pytest src/track_b_accounting/tests/test_vague5.py

Les valeurs attendues viennent de la double lecture des tableaux et des articles de primes (D78 à D83) ; elles sont
écrites ici, pas relues dans data/processed/.
"""

import copy
from decimal import Decimal

import pytest
from conftest import lire_json

from track_b_accounting.calc import Refus, loaders, prime, salaire_base

ENT, AUT, MAT = (
    "PRODUITS_ENTRETIEN_INSECTICIDES",
    "CONSTRUCTEURS_CONCESSIONNAIRES_AUTOMOBILES",
    "MATERIAUX_CONSTRUCTION",
)
PEI, CHA, CUI = "PEINTURES", "CHAUSSURE", "CUIRS_TANNERIE"
FICHIERS = {
    ENT: ("produits_entretien.json", "D78", 1056, 12),
    AUT: ("constructeurs_automobiles.json", "D79", 1170, 3),
    MAT: ("materiaux_construction.json", "D80", 1215, 6),
    PEI: ("peintures.json", "D81", 1365, 6),
    CHA: ("chaussure.json", "D82", 1980, 6),
    CUI: ("cuirs_tannerie.json", "D83", 1653, 6),  # + 15 cellules de la colonne initiale des horaires, non servies
}
REEL = {s: lire_json(f"data/processed/salary_grids/{f}") for s, (f, *_) in FICHIERS.items()}
D = Decimal
VERIF = "vérification des lots faite le 21/11/2026 sur claude-docs/vague5/verification/page.html (214 points, tous conformes)"


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
def test_nombre_de_cellules_servies_et_de_tableaux_imprimes(s):
    _, _, n, tables = FICHIERS[s]
    g = REEL[s]
    assert sum(len(v) for t in g["grilles"] for v in t["valeurs"].values()) == n
    assert len({t["numero_imprime"] for t in g["grilles"]}) == tables


def test_seules_les_deux_cases_des_automobiles_sont_nulles():
    nulles = sorted(
        (s, t["table_id"], c, i)
        for s, g in REEL.items()
        for t in g["grilles"]
        for c, v in t["valeurs"].items()
        for i, x in enumerate(v, 1)
        if x is None
    )
    assert nulles == [(AUT, "AUTO_MENSUELS_2023-01-01", "12", 10), (AUT, "AUTO_MENSUELS_2023-01-01", "7", 1)]


@pytest.mark.parametrize(
    "cat, annees, extrait",
    [("7", D("0.5"), "dernier chiffre"), ("12", 18, "chiffre des dizaines")],
)
def test_cases_illisibles_des_automobiles_refusees(cat, annees, extrait):
    e = refus(Refus.SOURCE_MANQUANTE, salaire_base, AUT, "mensuels", cat, annees, "2023-06-01")
    assert extrait in e.message_fr and "page 24" in e.message_fr


def test_anomalies_imprimees_declarees_et_valeurs_conservees():
    """Cellules non croissantes, nettes, même anomalie aux trois dates : 57 cellules conservées et déclarées."""
    n = sum(len(t.get("anomalies_imprimees", [])) for g in REEL.values() for t in g["grilles"])
    assert n == 57
    t = next(t for t in REEL[CUI]["grilles"] if t["table_id"] == "CUI_MENSUELS_2021-12-01")
    assert t["valeurs"]["7"][9] == D("733.406") and t["valeurs"]["7"][10] == D("724.955")


# --- salaires servis -------------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "s, pop, cat, sous, annees, date, montant, unite, page",
    [
        (ENT, "javel_horaires", "3", None, 5, "2024-06-01", "3.931", "TND/heure", 25),
        (ENT, "detergents_mensuels", "10", None, 18, "2022-06-01", "1253.413", "TND/mois", 22),
        (AUT, "mensuels", "16", None, 28, "2024-06-01", "2163.414", "TND/mois", 25),
        (AUT, "horaires", "5", None, 4, "2023-06-01", "4.479", "TND/heure", 24),
        (MAT, "horaires", "1", None, D("0.5"), "2024-06-01", "2.970", "TND/heure", 21),
        (MAT, "mensuels", "16", None, 38, "2023-06-01", "1579.544", "TND/mois", 20),
        (MAT, "horaires", "6", None, 10, "2022-12-15", "3.365", "TND/heure", 19),
        (CUI, "mensuels", "14", None, D("28.5"), "2024-06-01", "1245.074", "TND/mois", 20),
        (CUI, "horaires", "V", None, D("0.5"), "2023-06-01", "3.946", "TND/heure", 19),
        (CUI, "mensuels", "7", None, D("9.5"), "2022-06-01", "733.406", "TND/mois", 18),
    ],
)
def test_salaires_servis(s, pop, cat, sous, annees, date, montant, unite, page):
    r = salaire_base(s, pop, cat, annees, date, sous_categorie=sous)
    assert (r.montant, r.unite, r.citations[0].page) == (D(montant), unite, page)


@pytest.mark.parametrize(
    "s, pop, cat, sous, degre, date, montant",
    [
        (PEI, "execution_horaires", "ouvrier_hautement_qualifie", None, 13, "2024-06-01", "5.668"),
        (PEI, "administratifs_techniciens", "23", None, 1, "2023-06-01", "1428.536"),
        (CHA, "horaires", "VI", None, 30, "2024-06-01", "3.881"),
        (CHA, "mensuels", "1", "b", 1, "2021-12-15", "579.170"),
    ],
)
def test_peintures_et_chaussure_servies_par_le_degre(s, pop, cat, sous, degre, date, montant):
    r = salaire_base(s, pop, cat, None, date, None, sous, degre=degre)
    assert r.montant == D(montant) and r.detail["degre_declare"] is True


@pytest.mark.parametrize(
    "s, pop, cat, sous",
    [
        (PEI, "execution_mensuels", "ouvrier", None),
        (PEI, "administratifs_techniciens", "1", None),
        (CHA, "mensuels", "1", "a"),
    ],
)
@pytest.mark.parametrize("annees", [0, D("0.5"), 12, 40])
def test_peintures_et_chaussure_refusees_par_l_anciennete(s, pop, cat, sous, annees):
    e = refus(Refus.SOURCE_MANQUANTE, salaire_base, s, pop, cat, annees, "2024-06-01", sous_categorie=sous)
    assert "n'impriment que le numéro de chaque degré" in e.message_fr


# --- refus de degré et de date ------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "s, pop, cat, annees, code",
    [
        (ENT, "detergents_horaires", "6", 22, Refus.PARAM_INVALIDE),  # palier de l'écart cumulé
        (AUT, "horaires", "1", 29, Refus.PARAM_INVALIDE),
        (MAT, "horaires", "11", 39, Refus.SOURCE_MANQUANTE),
        (CUI, "mensuels", "1", 29, Refus.SOURCE_MANQUANTE),
        (CUI, "horaires", "I", 5, Refus.PARAM_INVALIDE),  # borne exacte
    ],
)
def test_refus_de_degre(s, pop, cat, annees, code):
    refus(code, salaire_base, s, pop, cat, annees, "2024-06-01")


@pytest.mark.parametrize("pop, cat", [("horaires", "1"), ("mensuels", "16")])
@pytest.mark.parametrize("jour", ["2021-12-01", "2022-06-01", "2022-11-30"])
def test_materiaux_periode_contredite_refusee(pop, cat, jour):
    e = refus(Refus.SOURCE_MANQUANTE, salaire_base, MAT, pop, cat, 2, jour)
    assert "avenant n° 16 (page 3)" in e.message_fr and "غرة ديسمبر 2022" in e.message_fr


def test_materiaux_servi_le_2022_12_01():
    assert salaire_base(MAT, "horaires", "1", D("0.5"), "2022-12-01").montant == D("2.606")


def test_cuirs_colonne_initiale_transcrite_et_jamais_servie():
    t = next(t for t in REEL[CUI]["grilles"] if t["table_id"] == "CUI_HORAIRES_2021-12-01")
    ns = t["colonnes_non_servies"]
    assert "servies_par_degre" not in ns and ns["valeurs"]["I"] == [D("3.068")] and t["valeurs"]["I"][0] == D("3.095")
    assert salaire_base(CUI, "horaires", "I", D("0.5"), "2022-06-01").montant == D("3.095")


# --- primes ---------------------------------------------------------------------------------------------------------

PRIMES = [
    (ENT, "prime_transport", "2024-06-01", {}, "75.787", "TND/mois"),
    (ENT, "prime_logement", "2023-06-01", {}, "16.894", "TND/mois"),
    (ENT, "prime_caisse_chef", "2024-06-01", {"condition_remplie": True}, "16.000", "TND/mois"),
    (AUT, "prime_transport", "2024-06-01", {"groupe": "cadres"}, "102.336", "TND/mois"),
    (AUT, "prime_demi_journee", "2022-06-01", {}, "0.159", "TND/demi-journee"),
    (AUT, "prime_etudes", "2024-06-01", {}, "51.660", "TND/enfant"),
    (
        MAT,
        "prime_transport",
        "2024-06-01",
        {"groupe": "execution_cat1", "transport_assure": False},
        "90.479",
        "TND/mois",
    ),
    (MAT, "prime_transport", "2023-06-01", {"groupe": "autres", "transport_assure": True}, "0.000", "TND/mois"),
    (MAT, "prime_presence", "2022-06-01", {}, "6.894", "TND/mois"),
    (MAT, "prime_poussiere", "2024-06-01", {"condition_remplie": True}, "0.008", "TND/heure"),
    (
        PEI,
        "prime_transport",
        "2024-06-01",
        {"groupe": "cadres", "variante": "complement_si_prime_superieure"},
        "7.433",
        "TND/mois",
    ),
    (PEI, "prime_poussiere_savon", "2024-06-01", {}, "8.000", "TND/mois"),
    (PEI, "prime_poussiere_savon", "1997-06-01", {}, "7.000", "TND/mois"),
    (PEI, "prime_panier", "2024-06-01", {"condition_remplie": True}, "0.600", "TND/jour"),
    (PEI, "prime_deplacement_nuitee", "2024-06-01", {"condition_remplie": True}, "8.000", "TND/nuitee"),
    (CHA, "prime_transport", "2024-06-01", {"groupe": "execution_gestion"}, "62.449", "TND/mois"),
    (CHA, "prime_regroupee", "2023-06-01", {}, "16.584", "TND/mois"),
    (CUI, "prime_transport", "2024-06-01", {}, "74.239", "TND/mois"),
    (CUI, "prime_presence", "2023-06-01", {}, "7.359", "TND/mois"),
]


@pytest.mark.parametrize("s, code, date, params, montant, unite", PRIMES)
def test_primes_servies(s, code, date, params, montant, unite):
    r = prime(s, code, date, **params)
    assert (r.montant, r.unite) == (D(montant), unite)


# Matériaux, art. 37 (جديد) د (p.12) : total imprimé de la « prime de transport et de présence » (réponse Q5).
TOTAUX_MATERIAUX = {
    ("2022-06-01", "execution_cat1"): "86.293",
    ("2022-06-01", "autres"): "78.150",
    ("2023-06-01", "execution_cat1"): "92.117",
    ("2023-06-01", "autres"): "83.425",
    ("2024-06-01", "execution_cat1"): "98.335",
    ("2024-06-01", "autres"): "89.056",
}


@pytest.mark.parametrize("date, groupe", sorted(TOTAUX_MATERIAUX))
def test_materiaux_total_egal_transport_plus_presence(date, groupe):
    transport = prime(MAT, "prime_transport", date, groupe=groupe, transport_assure=False).montant
    presence = prime(MAT, "prime_presence", date).montant
    assert transport + presence == D(TOTAUX_MATERIAUX[(date, groupe)])


@pytest.mark.parametrize(
    "s, code, extraits",
    [
        (AUT, "aide_aid_adha", ["خمسة وسبعين دينارا", "82.333", "43 dinars"]),
        (PEI, "secours_deces", ["خمسمائة دينار", "533.333", "أربعمائة دينار", "433.333"]),
        (CHA, "prime_panier", ["250 مليما"]),
        (CUI, "prime_salissure", ["2 kg"]),
    ],
)
def test_primes_refusees_avec_le_texte_cite(s, code, extraits):
    e = refus(Refus.SOURCE_MANQUANTE, prime, s, code, "2024-06-01")
    assert all(x in e.message_fr for x in extraits)
