"""Calcul de bout en bout du secteur ASSOCIATIONS_PERSONNES_HANDICAPEES (D23) par handle(), comme l'orchestrateur.

Les montants attendus sont recopiés de la lecture des pages du PDF (forme imprimée « 1 126,405 », virgule décimale,
espace des milliers), jamais d'une exécution du module. Les textes de refus et d'hypothèses sont lus dans le JSON
du secteur. Les tests de structure et de valeurs de la grille sont dans test_grid_associations.py.
Lancer depuis la racine du dépôt : pytest src/track_b_accounting/tests/test_calc_associations.py
"""

import json

import pytest
from conftest import REPO_ROOT, lire_json
from jsonschema import Draft202012Validator

from track_b_accounting.contract import handle

APH = "ASSOCIATIONS_PERSONNES_HANDICAPEES"
DATA_FILE = "data/processed/salary_grids/associations_personnes_handicapees.json"
GRID = lire_json(DATA_FILE)
SOURCE_PDF = GRID["_meta"]["source_file"]
V_TB = Draft202012Validator(
    json.loads((REPO_ROOT / "data/mock_cards/schemas/track_b_response.v0.schema.json").read_text(encoding="utf-8"))
)
V_COMMUN = Draft202012Validator(
    json.loads((REPO_ROOT / "src/shared/schemas/common.v0.schema.json").read_text(encoding="utf-8"))
)


def imprime(texte: str) -> str:
    """« 1 126,405 » (forme imprimée dans le PDF) → « 1126.405 » (forme du contrat)."""
    return texte.replace(" ", "").replace(",", ".")


def appel(operation: str, lang: str = "fr", **params) -> dict:
    """handle() tel que l'appelle l'orchestrateur ; toute réponse est contrôlée contre les deux schémas."""
    req = {
        "contract_version": "track_b.v0",
        "request_id": "aph",
        "operation": operation,
        "params": params,
        "lang": lang,
    }
    rep = json.loads(json.dumps(handle(req), ensure_ascii=False))
    assert not list(V_TB.iter_errors(rep)) and not list(V_COMMUN.iter_errors(rep)), rep
    if rep["status"] == "ok":
        assert rep["citations"] and rep["refus"] is None
    else:
        assert rep["result"] is None and rep["citations"] == []
        assert rep["refus"]["code"] and rep["refus"]["message_fr"] and rep["refus"]["message_ar"]
    return rep


def salaire(population, categorie, anciennete, date, **kw):
    return appel(
        "salaire_base",
        secteur=APH,
        population=population,
        categorie=categorie,
        anciennete_annees=anciennete,
        date=date,
        **kw,
    )


def prime(code, date, **kw):
    return appel("prime", secteur=APH, code=code, date=date, **kw)


def citation(rep, page):
    (c,) = rep["citations"]
    assert (c["source_file"], c["page"], c["data_file"], c["decision_ref"]) == (SOURCE_PDF, page, DATA_FILE, "D23")


# --- date d'effet : chaque date d'une grille s'applique de son premier jour à la veille de la suivante ---------------


# education_specialisee, ligne I, degré 3 (4 à 6 ans) : tables 1, 6 et 11 (lecture des pages 21, 24 et 27).
@pytest.mark.parametrize(
    "date, attendu, page, effet",
    [
        ("2021-12-01", "847,251", 21, "2021-12-01"),  # date d'effet exacte
        ("2022-12-31", "847,251", 21, "2021-12-01"),  # veille du 1er janvier 2023 : grille 2021
        ("2023-01-01", "904,441", 24, "2023-01-01"),  # date d'effet exacte
        ("2023-12-31", "904,441", 24, "2023-01-01"),  # veille du 1er janvier 2024
        ("2024-01-01", "965,490", 27, "2024-01-01"),  # date d'effet exacte
        ("2026-10-13", "965,490", 27, "2024-01-01"),  # après la dernière date : grille 2024
    ],
)
def test_date_d_effet(date, attendu, page, effet):
    rep = salaire("education_specialisee", "I", 5, date)
    assert rep["status"] == "ok" and rep["result"]["montant"] == imprime(attendu)
    assert rep["result"]["detail"]["effective_date"] == effet
    citation(rep, page)


def test_avant_la_premiere_date_refuse():
    rep = salaire("education_specialisee", "I", 5, "2021-11-30")
    assert rep["refus"]["code"] == "SOURCE_MANQUANTE" and "2021-12-01" in rep["refus"]["message_fr"]


# --- ancienneté : degré k de 2k−2 à 2k ans (D23), bornes exactes refusées (D6), refus à partir de 32 ans -------------

# sport, ligne II, table 12 (page 27), 16 degrés lus sur le PDF.
SPORT_II_2024 = [
    "1 082,666",
    "1 104,319",
    "1 126,405",
    "1 148,934",
    "1 171,913",
    "1 195,351",
    "1 219,258",
    "1 243,643",
    "1 268,516",
    "1 293,886",
    "1 319,763",
    "1 346,159",
    "1 373,081",
    "1 400,544",
    "1 428,554",
    "1 457,126",
]


@pytest.mark.parametrize("degre", range(1, 17))
def test_valeur_intermediaire_acceptee_a_chaque_degre(degre):
    rep = salaire("sport", "II", 2 * degre - 1, "2024-06-01")
    assert rep["result"]["montant"] == imprime(SPORT_II_2024[degre - 1]) and rep["result"]["detail"]["degre"] == degre
    citation(rep, 27)


@pytest.mark.parametrize("borne", range(2, 31, 2))
def test_borne_exacte_refusee(borne):
    rep = salaire("sport", "II", borne, "2024-06-01")
    assert rep["refus"]["code"] == "PARAM_INVALIDE" and f"{borne} ans" in rep["refus"]["message_fr"]


@pytest.mark.parametrize("annees, texte", [(32, "32"), (33, "33"), (40, "40")])
def test_a_partir_de_32_ans_refuse_avec_le_texte_du_json(annees, texte):
    """32 ans est la fin du dernier degré (« 30-32 ») : la convention ne prévoit rien à partir de là (D23)."""
    bloc = GRID["au_dela_dernier_degre"]["sport"]
    rep = salaire("sport", "II", annees, "2024-06-01")
    assert rep["refus"]["code"] == "SOURCE_MANQUANTE"
    assert rep["refus"]["message_fr"] == bloc["message_fr"].format(a=texte)
    assert rep["refus"]["message_ar"] == bloc["message_ar"].format(a=texte)


# --- catégorie et population inconnues --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "population, categorie", [("sport", "IV"), ("sport", "4"), ("techniciens", "2"), ("formateurs_professionnels", "V")]
)
def test_categorie_inconnue(population, categorie):
    assert salaire(population, categorie, 5, "2024-06-01")["refus"]["code"] == "PARAM_INVALIDE"


@pytest.mark.parametrize("population", ["education", "admin_tech", "ouvriers_occasionnels", "SPORT"])
def test_population_inconnue(population):
    assert salaire(population, "I", 5, "2024-06-01")["refus"]["code"] == "PARAM_INVALIDE"


# --- unité et hypothèses de la grille dans detail ----------------------------------------------------------------


@pytest.mark.parametrize("population", list(GRID["categories"]))
def test_unite_et_hypotheses_de_grille(population):
    rep = salaire(population, "I", 5, "2024-06-01")
    assert rep["result"]["unite"] == "TND/mois"
    d, h = rep["result"]["detail"], GRID["hypotheses_grille"][population]
    assert d["hypotheses"][: len(h["fr"])] == h["fr"] and d["hypotheses_ar"][: len(h["ar"])] == h["ar"]


# --- primes datées de l'article 42 (جديد), page 14 ---------------------------------------------------------------

DATES_PRIMES = [
    ("2022-06-01", "2021-12-01", 2022),
    ("2023-06-01", "2023-01-01", 2023),
    ("2024-06-01", "2024-01-01", 2024),
]
TRANSPORT = {"execution_et_gestion": ["30,199", "32,238", "34,414"], "cadres": ["36,239", "38,685", "41,296"]}
LIBELLES = {
    "execution_et_gestion": ("agents d'exécution et de gestion", "أعوان التنفيذ والتسيير"),
    "cadres": ("cadres", "الإطارات"),
}
P_TRANSPORT = next(p for p in GRID["primes"] if p["code"] == "prime_transport")


@pytest.mark.parametrize("groupe", list(TRANSPORT))
@pytest.mark.parametrize("i", range(3))
def test_prime_transport(groupe, i):
    jour, effet, titre = DATES_PRIMES[i]
    rep = prime("prime_transport", jour, groupe=groupe)
    r, d = rep["result"], rep["result"]["detail"]
    assert (r["montant"], r["unite"]) == (imprime(TRANSPORT[groupe][i]), "TND/mois")
    assert (d["effective_date"], d["au_titre_de"], d["groupe"]) == (effet, titre, groupe)
    assert (d["groupe_libelle"], d["groupe_libelle_ar"]) == LIBELLES[groupe]
    assert (d["note"], d["note_ar"]) == (P_TRANSPORT["note"], P_TRANSPORT["note_ar"])
    assert rep["citations"][0]["article"] == "42 (جديد) 1"
    citation(rep, 14)


@pytest.mark.parametrize(
    "code, montants",
    [("prime_presence", ["6,281", "6,705", "7,158"]), ("prime_specifique_handicap", ["54,358", "58,027", "61,944"])],
)
@pytest.mark.parametrize("i", range(3))
def test_primes_presence_et_specifique(code, montants, i):
    jour, effet, titre = DATES_PRIMES[i]
    rep = prime(code, jour)
    d = rep["result"]["detail"]
    assert rep["result"]["montant"] == imprime(montants[i]) and (d["effective_date"], d["au_titre_de"]) == (
        effet,
        titre,
    )
    p = next(x for x in GRID["primes"] if x["code"] == code)
    assert (d["hypotheses"], d["hypotheses_ar"]) == (p["hypotheses"]["fr"], p["hypotheses"]["ar"])
    citation(rep, 14)


def test_prime_transport_sans_groupe_ou_groupe_de_la_metallurgie_refuse():
    assert prime("prime_transport", "2024-06-01")["refus"]["code"] == "PARAM_INVALIDE"
    assert prime("prime_transport", "2024-06-01", groupe="execution_et_maitrise")["refus"]["code"] == "PARAM_INVALIDE"


def test_prime_avant_la_premiere_date_refusee():
    assert prime("prime_presence", "2021-11-30")["refus"]["code"] == "SOURCE_MANQUANTE"


@pytest.mark.parametrize(
    "code",
    [
        "prime_frais_scolaires",
        "prime_pedagogique",
        "prime_sante",
        "prime_fonctionnelle",
        "prime_chauffeurs",
        "prime_production",
    ],
)
@pytest.mark.parametrize("lang", ["fr", "ar"])
def test_primes_non_couvertes_refusees(code, lang):
    bloc = GRID["primes_non_couvertes"][code]
    rep = prime(code, "2024-06-01", lang=lang)
    assert rep["refus"] == {
        "code": "SOURCE_MANQUANTE",
        "message_fr": bloc["message_fr"],
        "message_ar": bloc["message_ar"],
    }


# --- handle() ne lève jamais, même sur des entrées absurdes --------------------------------------------------------


@pytest.mark.parametrize(
    "params",
    [
        {"secteur": APH, "categorie": "I", "anciennete_annees": 5, "date": "2024-06-01"},  # population absente
        {"secteur": APH, "population": "sport", "categorie": "I", "anciennete_annees": -3, "date": "2024-06-01"},
        {"secteur": APH, "population": "sport", "categorie": "I", "anciennete_annees": "cinq", "date": "2024-06-01"},
        {"secteur": APH, "population": "sport", "categorie": "I", "anciennete_annees": "5", "date": "2024-06-01"},
        {"secteur": APH, "population": "sport", "categorie": 1, "anciennete_annees": 5, "date": "2024-06-01"},
        {"secteur": APH, "population": "sport", "categorie": "I", "anciennete_annees": 1e9, "date": "2024-06-01"},
        {"secteur": APH, "population": "sport", "categorie": "I", "anciennete_annees": 5, "date": "2024-13-45"},
        {"secteur": APH, "population": "sport", "categorie": "I", "anciennete_annees": 5, "date": "demain"},
        {"secteur": APH, "population": None, "categorie": None, "anciennete_annees": None, "date": None},
        {"secteur": APH, "population": ["sport"], "categorie": {"x": 1}, "anciennete_annees": True, "date": 2024},
        {
            "secteur": APH,
            "population": "techniciens",
            "categorie": "III+II",
            "anciennete_annees": 5,
            "date": "2024-06-01",
            "sous_categorie": "II",
        },
        {},
    ],
)
def test_handle_ne_leve_jamais_salaire(params):
    rep = appel("salaire_base", **params)
    assert rep["status"] in ("refus", "ok")
    assert rep["status"] == "refus" or rep["result"]["montant"]


@pytest.mark.parametrize(
    "params",
    [
        {"secteur": APH, "code": "prime_transport", "date": "2024-06-01", "groupe": ""},
        {"secteur": APH, "code": "prime_transport", "date": "2024-06-01", "groupe": "cadres", "population": "sport"},
        {"secteur": APH, "code": "", "date": "2024-06-01"},
        {"secteur": APH, "code": "prime_presence", "date": "1900-01-01"},
        {"secteur": APH, "code": "prime_presence", "date": "2024-06-01", "condition_remplie": True},
        {"secteur": APH, "code": None, "date": None},
    ],
)
def test_handle_ne_leve_jamais_prime(params):
    assert appel("prime", **params)["status"] == "refus"


def test_reponses_identiques_en_francais_et_en_arabe():
    """lang ne change que la présentation par Track A : le contrat renvoie les deux langues dans tous les cas."""
    assert salaire("sport", "II", 5, "2024-06-01") == appel(
        "salaire_base",
        lang="ar",
        secteur=APH,
        population="sport",
        categorie="II",
        anciennete_annees=5,
        date="2024-06-01",
    )
