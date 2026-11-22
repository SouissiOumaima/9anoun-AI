"""Règle « ouvert » au-delà du dernier degré, population unique omise dans la requête, grille ASSURANCE (D29).
Données FICTIVES (montants inventés), sauf les sections qui lisent les fichiers réels (grille ASSURANCE activée
par D29, et les quatre secteurs enregistrés pour vérifier qu'ils ne changent pas).
Lancer depuis la racine du dépôt : pytest src/track_b_accounting/tests/test_dernier_degre_ouvert_population_unique.py
"""

import copy
from decimal import Decimal

import pytest
from conftest import lire_json

from track_b_accounting.calc import Refus, salaire_base
from track_b_accounting.calc import loaders
from track_b_accounting.contract import handle

S = "SECTEUR_FICTIF_OUVERT"
POP = "tous"
LABELS = ["0-1", "1-2", "2-3", "3-4", "4-6", "6-8", "8-10", "10-13", "13-16", "16-19", "19-23", "23-27", "27-30", "30+"]
BORNES = [1, 2, 3, 4, 6, 8, 10, 13, 16, 19, 23, 27, 30]
CLES = ["2", "1", "X"]
OUVERT = {"regle": "ouvert", "source_pdf_page": 9, "source_article": "16 أ", "texte_source_ar": "نص المصدر"}
HYP = {"fr": ["Hypothèse FR"], "ar": ["فرضية"]}
SECTEURS = {
    "METALLURGIE_BATIMENT": "data/processed/salary_grids/metallurgie_batiment.json",
    "BATIMENT_TRAVAUX_PUBLICS": "data/processed/salary_grids/batiment_travaux_publics.json",
    "ASSOCIATIONS_PERSONNES_HANDICAPEES": "data/processed/salary_grids/associations_personnes_handicapees.json",
    "ASSURANCE": "data/processed/salary_grids/assurance.json",
    "ENSEIGNEMENT_PRIVE": "data/processed/salary_grids/enseignement_prive.json",
    "BANQUES": "data/processed/salary_grids/banques.json",
    "GARDIENNAGE_SECURITE_TRANSPORT_FONDS": "data/processed/salary_grids/gardiennage.json",
    "TORREFACTION_CAFE": "data/processed/salary_grids/torrefaction_cafe.json",
    "AGENCES_VOYAGES": "data/processed/salary_grids/agences_voyages.json",
    "HOTELS_TOURISTIQUES": "data/processed/salary_grids/hotels_touristiques.json",
    "CONFISERIE_BISCUITERIE_CHOCOLATERIE": "data/processed/salary_grids/confiserie_biscuiterie.json",
    "PATES_ALIMENTAIRES_COUSCOUS": "data/processed/salary_grids/pates_alimentaires.json",
    "COSMETIQUES_PARFUMS": "data/processed/salary_grids/cosmetiques_parfums.json",
    "SAVONNERIE_RAFFINAGE_GRIGNONS": "data/processed/salary_grids/savonnerie_raffinage.json",
    "COMMERCE_DISTRIBUTION_PETROLE": "data/processed/salary_grids/distribution_petrole.json",
    "PLASTURGIE": "data/processed/salary_grids/plasturgie.json",
    "MINOTERIES": "data/processed/salary_grids/minoteries.json",
    "TEINTURERIES_PRESSINGS": "data/processed/salary_grids/teintureries_pressings.json",
    "BOISSONS_GAZEUSES": "data/processed/salary_grids/boissons_gazeuses.json",
    "MECANIQUE_STATIONS_SERVICE": "data/processed/salary_grids/mecanique_stations_service.json",
    "BOISSONS_ALCOOLISEES": "data/processed/salary_grids/boissons_alcoolisees.json",
    "BOIS_AMEUBLEMENT_LIEGE": "data/processed/salary_grids/bois_ameublement_liege.json",
    "GESTION_DECHETS": "data/processed/salary_grids/gestion_dechets.json",
    "HABILLEMENT": "data/processed/salary_grids/habillement.json",
    "COMMERCE_GROS_DETAIL": "data/processed/salary_grids/commerce_gros_detail.json",
    "IMPRIMERIE_EDITION_CARTONNAGE": "data/processed/salary_grids/imprimerie_edition.json",
    "VERRE_MIROIRS": "data/processed/salary_grids/verre_miroirs.json",
    "CONCESSIONNAIRES_MATERIEL_AGRICOLE": "data/processed/salary_grids/materiel_agricole.json",
    "BOULANGERIES": "data/processed/salary_grids/boulangeries.json",
    "TEXTILE": "data/processed/salary_grids/textile.json",
    "FONDERIE_METALLURGIE_MECANIQUE": "data/processed/salary_grids/fonderies_mecanique.json",
    "PRODUITS_ENTRETIEN_INSECTICIDES": "data/processed/salary_grids/produits_entretien.json",
    "CONSTRUCTEURS_CONCESSIONNAIRES_AUTOMOBILES": "data/processed/salary_grids/constructeurs_automobiles.json",
    "MATERIAUX_CONSTRUCTION": "data/processed/salary_grids/materiaux_construction.json",
    "PEINTURES": "data/processed/salary_grids/peintures.json",
    "CHAUSSURE": "data/processed/salary_grids/chaussure.json",
    "CUIRS_TANNERIE": "data/processed/salary_grids/cuirs_tannerie.json",
    "CLERCS_AVOCATS": "data/processed/salary_grids/clercs_avocats.json",
    "PERSONNEL_PHARMACIES": "data/processed/salary_grids/pharmacies.json",
    "CONSERVERIES_CONDITIONNEMENT_HUILES": "data/processed/salary_grids/conserveries_huiles.json",
    "GROSSISTES_REPARTITEURS_MEDICAMENTS": "data/processed/salary_grids/grossistes_medicaments.json",
    "SALLES_CINEMA": "data/processed/salary_grids/salles_cinema.json",
    "TRANSPORT_ROUTIER_MARCHANDISES": "data/processed/salary_grids/transport_routier_marchandises.json",
}
ASSURANCE_FILE = "data/processed/salary_grids/assurance.json"


def _table(tid, date, base):
    return {
        "table_id": tid,
        "effective_date": date,
        "source_pdf_page": 20,
        "unite": "TND/mois",
        "valeurs": {c: [Decimal(base + 1000 * i + 10 * k) for k in range(14)] for i, c in enumerate(CLES)},
    }


def grille_fictive(au_dela=None, labels=LABELS):
    g = {
        "_meta": {
            "source_file": "data/raw/pdf/fictif.pdf",
            "secteur_code": S,
            "decision_ref": "D99",
            "tables_transcrites": True,
        },
        "degres": {POP: [{"degre": k, "anciennete_label": lab} for k, lab in enumerate(labels, start=1)]},
        "au_dela_dernier_degre": {POP: copy.deepcopy(au_dela or OUVERT)},
        "categories": {POP: list(CLES)},
        "hypotheses_grille": {POP: copy.deepcopy(HYP)},
        "grilles": [_table("F_2020", "2020-10-01", 100), _table("F_2021", "2021-06-01", 200)],
    }
    return loaders.valider_grille(g, "fictif.json")


@pytest.fixture
def fictif(monkeypatch):
    g = grille_fictive()
    monkeypatch.setattr("track_b_accounting.calc.salary.charger_grille", lambda s: g)
    monkeypatch.setitem(loaders.GRILLES, S, "data/processed/salary_grids/fictif.json")
    return g


def refus(code, f, *a, **k):
    with pytest.raises(Refus) as e:
        f(*a, **k)
    assert e.value.code == code and e.value.message_fr and e.value.message_ar
    return e.value


def requete(params):
    return {
        "contract_version": "track_b.v0",
        "request_id": "t",
        "operation": "salaire_base",
        "params": params,
        "lang": "fr",
    }


# --- règle « ouvert » : validation ---------------------------------------------------------------------


def test_regle_ouvert_acceptee_avec_source():
    assert grille_fictive()["au_dela_dernier_degre"][POP]["regle"] == "ouvert"


@pytest.mark.parametrize(
    "mutation",
    [
        lambda b: b.pop("source_pdf_page"),
        lambda b: b.pop("source_article"),
        lambda b: b.pop("texte_source_ar"),
        lambda b: b.__setitem__("source_pdf_page", 0),
        lambda b: b.__setitem__("source_article", " "),
        lambda b: b.__setitem__("texte_source_ar", ""),
    ],
)
def test_regle_ouvert_refusee_sans_source(mutation):
    bloc = copy.deepcopy(OUVERT)
    mutation(bloc)
    refus(Refus.SOURCE_MANQUANTE, grille_fictive, bloc)


def test_regle_ouvert_exige_un_dernier_degre_ouvert():
    refus(Refus.SOURCE_MANQUANTE, grille_fictive, OUVERT, LABELS[:-1])


def test_regle_inconnue_toujours_refusee():
    refus(Refus.SOURCE_MANQUANTE, grille_fictive, {**OUVERT, "regle": "plafond_libre"})


# --- règle « ouvert » : calcul --------------------------------------------------------------------------


@pytest.mark.parametrize("annees", [Decimal("30.5"), 31, 33, Decimal("33.5"), 40, 60])
def test_dernier_degre_servi_sans_plafond_ni_extrapolation(fictif, annees):
    r = salaire_base(S, POP, "1", annees, "2022-01-01")
    assert r.detail["degre"] == 14 and r.montant == Decimal(200 + 1000 + 10 * 13)
    assert "regle_art13" not in r.detail and len(r.citations) == 1


@pytest.mark.parametrize("annees", BORNES)
def test_bornes_exactes_refusees(fictif, annees):
    refus(Refus.PARAM_INVALIDE, salaire_base, S, POP, "1", annees, "2022-01-01")


@pytest.mark.parametrize(
    "annees,degre",
    [(0, 1), (Decimal("0.5"), 1), (Decimal("1.5"), 2), (5, 5), (Decimal("29.9"), 13), (Decimal("30.01"), 14)],
)
def test_degres_entre_les_bornes(fictif, annees, degre):
    assert salaire_base(S, POP, "2", annees, "2022-01-01").detail["degre"] == degre


def test_dates_et_hypotheses_affichees_pour_toutes_les_dates(fictif):
    refus(Refus.SOURCE_MANQUANTE, salaire_base, S, POP, "1", 5, "2020-09-30")
    for date, table in (
        ("2020-10-01", "F_2020"),
        ("2021-05-31", "F_2020"),
        ("2021-06-01", "F_2021"),
        ("2026-01-01", "F_2021"),
    ):
        r = salaire_base(S, POP, "1", 5, date)
        assert r.detail["table_id"] == table
        assert r.detail["hypotheses"] == HYP["fr"] and r.detail["hypotheses_ar"] == HYP["ar"]


def test_secteurs_enregistres_avec_la_regle_ouvert():
    assert loaders.GRILLES == SECTEURS
    ouverts = [
        s
        for s, chemin in SECTEURS.items()
        if "ouvert" in {b.get("regle", "refus") for b in lire_json(chemin)["au_dela_dernier_degre"].values()}
    ]
    assert ouverts == [
        "ASSURANCE",
        "AGENCES_VOYAGES",
        "COSMETIQUES_PARFUMS",
        "TEINTURERIES_PRESSINGS",
        "TRANSPORT_ROUTIER_MARCHANDISES",
    ]
    assert {b["regle"] for b in lire_json(SECTEURS["ENSEIGNEMENT_PRIVE"])["au_dela_dernier_degre"].values()} == {
        "refus"
    }


# --- population unique ------------------------------------------------------------------------------------


def test_population_unique_omise(fictif):
    omise = salaire_base(S, None, "X", 5, "2022-01-01")
    donnee = salaire_base(S, POP, "X", 5, "2022-01-01")
    assert omise.detail["population"] == POP
    assert (omise.montant, omise.detail, omise.citations) == (donnee.montant, donnee.detail, donnee.citations)


def test_population_unique_omise_message_de_date_sans_none(fictif):
    e = refus(Refus.SOURCE_MANQUANTE, salaire_base, S, None, "X", 5, "2019-01-01")
    assert f"{S}/{POP}" in e.message_fr and "None" not in e.message_fr and "None" not in e.message_ar


@pytest.mark.parametrize("population", ["autre", "TOUS", "", 1])
def test_population_unique_donnee_incorrecte(fictif, population):
    refus(Refus.PARAM_INVALIDE, salaire_base, S, population, "X", 5, "2022-01-01")


def test_population_unique_omise_par_le_contrat(fictif):
    rep = handle(requete({"secteur": S, "categorie": "X", "anciennete_annees": 5, "date": "2022-01-01"}))
    assert rep["status"] == "ok" and rep["result"]["detail"]["population"] == POP


def test_multi_populations_omission_toujours_refusee():
    e = refus(Refus.PARAM_INVALIDE, salaire_base, "METALLURGIE_BATIMENT", None, "1B", 5, "2022-06-01")
    assert e.message_fr.startswith("Population obligatoire pour le secteur METALLURGIE_BATIMENT")
    assert "inconnue" not in e.message_fr and "None" not in e.message_fr + e.message_ar
    rep = handle(
        requete({"secteur": "METALLURGIE_BATIMENT", "categorie": "1B", "anciennete_annees": 5, "date": "2022-06-01"})
    )
    assert rep["status"] == "refus" and rep["refus"]["code"] == Refus.PARAM_INVALIDE


@pytest.mark.parametrize(
    "secteur", [s for s in loaders.secteurs_disponibles() if len(loaders.charger_grille(s)["categories"]) > 1]
)
def test_omission_population_cite_le_secteur_et_ses_populations(secteur):
    """Secteur à plusieurs populations : l'omission est refusée (PARAM_INVALIDE) ; FR et AR citent le code du
    secteur et toutes les populations de la grille."""
    pops = list(loaders.charger_grille(secteur)["categories"])
    rep = handle(requete({"secteur": secteur, "categorie": "1", "anciennete_annees": 5, "date": "2024-06-01"}))
    assert rep["status"] == "refus" and rep["refus"]["code"] == Refus.PARAM_INVALIDE
    for message in (rep["refus"]["message_fr"], rep["refus"]["message_ar"]):
        assert secteur in message and ", ".join(pops) in message


def test_population_unique_omission_toujours_acceptee():
    rep = handle(requete({"secteur": "ASSURANCE", "categorie": "21", "anciennete_annees": 5, "date": "2021-01-01"}))
    assert rep["status"] == "ok" and rep["result"]["detail"]["population"] == "tous_agents"


# --- grille ASSURANCE activée (D29) --------------------------------------------------------------------------

SQ = lire_json(ASSURANCE_FILE)


def test_assurance_activee_dans_le_registre_d29():
    assert SQ["_meta"]["decision_ref"] == "D29" and SQ["_meta"]["secteur_code"] == "ASSURANCE"
    assert loaders.GRILLES["ASSURANCE"] == ASSURANCE_FILE and "ASSURANCE" in loaders.secteurs_disponibles()
    rep = handle(requete({"secteur": "ASSURANCE", "categorie": "1", "anciennete_annees": 5, "date": "2021-01-01"}))
    assert rep["status"] == "ok" and rep["citations"][0]["decision_ref"] == "D29"


def test_assurance_grille_activee_structure():
    loaders.valider_grille(copy.deepcopy(SQ), ASSURANCE_FILE)
    assert SQ["_meta"]["tables_transcrites"] is True and SQ["_meta"]["decision_ref"] == "D29"
    assert [t["table_id"] for t in SQ["grilles"]] == ["ASS_2020-10-01", "ASS_2021-06-01"]
    for t in SQ["grilles"]:
        assert list(t["valeurs"]) == SQ["categories"]["tous_agents"]
        assert all(len(v) == 14 and all(isinstance(x, Decimal) for x in v) for v in t["valeurs"].values())
    assert sum(len(v) for t in SQ["grilles"] for v in t["valeurs"].values()) == 616
    assert list(SQ["populations"]) == ["tous_agents"]
    cles = SQ["categories"]["tous_agents"]
    assert cles == [str(n) for n in range(21, 3, -1)] + ["استثنائي", "3", "2", "1"]
    assert [ligne["cle"] for ligne in SQ["lignes_grille"]["tous_agents"]] == cles
    assert [d["anciennete_label"] for d in SQ["degres"]["tous_agents"]] == LABELS
    assert SQ["au_dela_dernier_degre"]["tous_agents"]["regle"] == "ouvert"
    tables = [(t["table_id"], t["effective_date"], t["source_pdf_page"], t["unite"]) for t in SQ["tables_a_transcrire"]]
    assert tables == [
        ("ASS_2020-10-01", "2020-10-01", 20, "TND/mois"),
        ("ASS_2021-06-01", "2021-06-01", 21, "TND/mois"),
    ]
    assert all("valeurs" not in t for t in SQ["tables_a_transcrire"])
