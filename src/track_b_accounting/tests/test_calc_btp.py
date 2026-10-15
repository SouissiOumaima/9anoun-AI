"""BATIMENT_TRAVAUX_PUBLICS : refus, sous-catégories, degrés par population (D9) et textes de l'article 13 (D10).
Les montants BTP eux-mêmes (657 cellules, règle entre années, calcul de bout en bout) : test_grid_btp.py.
Lancer depuis la racine du dépôt : pytest src/track_b_accounting/tests/test_calc_btp.py
"""
import copy
import json
from decimal import Decimal

import pytest
from conftest import lire_json
from jsonschema import Draft202012Validator
from conftest import REPO_ROOT

from track_b_accounting.calc import Refus, degre_from_anciennete, prime, salaire_base, table_applicable
from track_b_accounting.calc import loaders
from track_b_accounting.contract import handle

BTP = "BATIMENT_TRAVAUX_PUBLICS"
BM_S = "METALLURGIE_BATIMENT"
BTP_FILE = "data/processed/salary_grids/batiment_travaux_publics.json"
G = lire_json(BTP_FILE)
BM = lire_json("data/processed/salary_grids/metallurgie_batiment.json")
OCC = "ouvriers_occasionnels"
REQ_V = Draft202012Validator(json.loads(
    (REPO_ROOT / "data/mock_cards/schemas/track_b_request.v0.schema.json").read_text(encoding="utf-8")))


def refus(code, f, *a, **k):
    with pytest.raises(Refus) as e:
        f(*a, **k)
    assert e.value.code == code and e.value.message_fr and e.value.message_ar
    return e.value


# --- fichier BTP : tables transcrites (D9), aucune prime servie --------------------------------------

def test_btp_enregistre_avec_tables():
    assert loaders.GRILLES[BTP] == BTP_FILE
    g = loaders.charger_grille(BTP)
    assert g["_meta"]["tables_transcrites"] is True and g["_meta"]["decision_ref"] == "D9"
    assert len(g["grilles"]) == 6 and g["primes"] == []
    assert set(g["categories"]) == {"admin_tech", OCC}
    assert g["degres"][OCC] == [] and len(g["degres"]["admin_tech"]) == 11
    assert set(g["au_dela_dernier_degre"]) == {"admin_tech"}


def test_secteurs_disponibles():
    assert loaders.secteurs_disponibles() == [BM_S, BTP, "ASSOCIATIONS_PERSONNES_HANDICAPEES"]


def test_secteur_non_transcrit_absent_des_disponibles(monkeypatch):
    """Un secteur enregistré sans tables reste refusé comme un secteur inconnu (D9)."""
    g = copy.deepcopy(G)
    g["_meta"]["tables_transcrites"] = False
    g["grilles"] = []
    g = loaders.valider_grille(g, "x.json")
    monkeypatch.setattr("track_b_accounting.calc.salary.charger_grille", lambda s: g)
    e = refus(Refus.SOURCE_MANQUANTE, salaire_base, BTP, OCC, 6, None, "2024-01-01", sous_categorie="II")
    assert e.message_fr.startswith(f"Aucune grille vérifiée pour le secteur {BTP!r}")


def test_sous_categories_btp_libelles_du_pdf():
    sc = G["sous_categories"][OCC]
    assert sc["source_pdf_page"] == 23
    assert {s["cle"] for v in sc["par_categorie"].values() for s in v.values()} == {"6_I", "6_II", "7_1", "7_2", "7_3"}
    assert sc["par_categorie"]["7"]["2"]["libelle_ar"] == "رئيس فريق درجة ثانية"
    assert "degré" in sc["par_categorie"]["7"]["1"]["libelle_fr"]


# --- secteur absent : PARAM_INVALIDE (plus de secteur par défaut) -------------------------------------

@pytest.mark.parametrize("secteur", [None, "", "  ", 42])
def test_secteur_absent(secteur):
    refus(Refus.PARAM_INVALIDE, salaire_base, secteur, "admin_tech", "4", 5, "2024-01-01")
    refus(Refus.PARAM_INVALIDE, degre_from_anciennete, 5, secteur, "admin_tech")
    refus(Refus.PARAM_INVALIDE, table_applicable, secteur, "admin_tech", "2024-01-01")
    refus(Refus.PARAM_INVALIDE, prime, secteur, "prime_presence", "2024-01-01")


def test_degre_sans_secteur_refuse():
    e = refus(Refus.PARAM_INVALIDE, degre_from_anciennete, 5)
    assert "Secteur absent" in e.message_fr


# --- populations ------------------------------------------------------------------------------------

def test_ouvriers_permanents_refus_lu_dans_le_json():
    bloc = G["populations_non_couvertes"]["ouvriers_permanents"]
    for f, a in [(salaire_base, (BTP, "ouvriers_permanents", "1", None, "2024-01-01")),
                 (table_applicable, (BTP, "ouvriers_permanents", "2024-01-01")),
                 (degre_from_anciennete, (5, BTP, "ouvriers_permanents"))]:
        e = refus(Refus.SOURCE_MANQUANTE, f, *a)
        assert (e.message_fr, e.message_ar) == (bloc["message_fr"], bloc["message_ar"])
    assert "annexe 4" in bloc["message_fr"] and "article 56" in bloc["message_fr"] and "page 16" in bloc["message_fr"]
    assert "الملحق عدد 4" in bloc["message_ar"] and "الفصل 56" in bloc["message_ar"]


def test_population_inconnue_btp():
    e = refus(Refus.PARAM_INVALIDE, salaire_base, BTP, "execution", "1", None, "2024-01-01")
    assert "admin_tech, ouvriers_occasionnels" in e.message_fr


# --- sous-catégories --------------------------------------------------------------------------------

@pytest.mark.parametrize("cat,valeurs", [(6, "I, II"), ("7", "1, 2, 3")])
def test_sous_categorie_manquante(cat, valeurs):
    e = refus(Refus.PARAM_INVALIDE, salaire_base, BTP, OCC, cat, None, "2024-01-01")
    assert "sous_categorie obligatoire" in e.message_fr and valeurs in e.message_fr and valeurs in e.message_ar


@pytest.mark.parametrize("cat,sous", [(6, "III"), (7, "4"), (7, "I"), (6, 1)])
def test_sous_categorie_inconnue(cat, sous):
    e = refus(Refus.PARAM_INVALIDE, salaire_base, BTP, OCC, cat, None, "2024-01-01", sous_categorie=sous)
    assert "Sous-catégorie inconnue" in e.message_fr


@pytest.mark.parametrize("secteur,pop,cat,anc", [(BTP, OCC, 3, None), (BTP, "admin_tech", 4, 5), (BM_S, "admin_tech", "4", 5)])
def test_sous_categorie_inattendue(secteur, pop, cat, anc):
    e = refus(Refus.PARAM_INVALIDE, salaire_base, secteur, pop, cat, anc, "2024-01-01", sous_categorie="I")
    assert "non prévue" in e.message_fr and "n'a pas de sous-catégorie" in e.message_fr


@pytest.mark.parametrize("cat", ["6_I", "7_3", 8, "1A"])
def test_cle_technique_ou_categorie_absente_refusee(cat):
    e = refus(Refus.PARAM_INVALIDE, salaire_base, BTP, OCC, cat, None, "2024-01-01")
    assert e.message_fr.startswith("Catégorie inconnue") and "(attendu : 1, 2, 3, 4, 5, 6, 7)" in e.message_fr


def test_secteur_inconnu_liste_les_secteurs():
    e = refus(Refus.SOURCE_MANQUANTE, salaire_base, "SECTEUR_FICTIF_NON_SUPPORTE", "admin_tech", "4", 5, "2024-01-01")
    assert e.message_fr.endswith(f"(disponibles : {BM_S}, {BTP}, ASSOCIATIONS_PERSONNES_HANDICAPEES).")


# --- ancienneté : obligatoire avec degrés, interdite sans --------------------------------------------

def test_anciennete_interdite_pour_occasionnels():
    e = refus(Refus.PARAM_INVALIDE, salaire_base, BTP, OCC, 1, 3, "2024-01-01")
    assert "anciennete_annees non prévue" in e.message_fr
    refus(Refus.PARAM_INVALIDE, degre_from_anciennete, 3, BTP, OCC)


@pytest.mark.parametrize("secteur", [BTP, BM_S])
def test_anciennete_obligatoire_avec_degres(secteur):
    e = refus(Refus.PARAM_INVALIDE, salaire_base, secteur, "admin_tech", "4", None, "2024-01-01")
    assert "anciennete_annees obligatoire" in e.message_fr


# --- BTP admin_tech : degrés p.23 et borne de 27 ans (art. 13, p.8, D10) --------------------------------

@pytest.mark.parametrize("annees,degre", [(0, 1), (11.5, 6), (13, 7), (Decimal("23.9"), 10), (25, 11), (26.99, 11)])
def test_degres_btp(annees, degre):
    assert degre_from_anciennete(annees, BTP, "admin_tech") == degre


@pytest.mark.parametrize("borne", [2, 10, 12, 15, 18, 21, 24])
def test_bornes_btp_ambigues(borne):
    refus(Refus.PARAM_INVALIDE, degre_from_anciennete, borne, BTP, "admin_tech")


@pytest.mark.parametrize("annees", [27, Decimal("27.000")])
def test_btp_27_ans_pile_refuse(annees):
    """« après 3 ans » au degré 11 : 27 ans pile est une borne, comme en D6 (PARAM_INVALIDE)."""
    bloc = G["au_dela_dernier_degre"]["admin_tech"]
    e = refus(Refus.PARAM_INVALIDE, salaire_base, BTP, "admin_tech", "4", annees, "2024-01-01")
    assert e.message_fr == bloc["message_borne_fr"].replace("{a}", str(Decimal(str(annees))))
    assert e.message_ar == bloc["message_borne_ar"].replace("{a}", str(Decimal(str(annees))))
    assert "article 13 (جديد) ب" in e.message_fr and "page 8" in e.message_fr
    assert "الفصل 13 (جديد) ب" in e.message_ar and "الصفحة 8" in e.message_ar


# --- textes de refus lus dans le JSON, pour les deux secteurs ----------------------------------------

@pytest.mark.parametrize("secteur,grille,cat,annees", [(BM_S, BM, "4", 24), (BTP, G, "4", 27)])
def test_textes_borne_art13_lus_dans_le_json(secteur, grille, cat, annees, monkeypatch):
    g = copy.deepcopy(grille)
    g["au_dela_dernier_degre"]["admin_tech"]["message_borne_fr"] = "FR-TEST {a}"
    g["au_dela_dernier_degre"]["admin_tech"]["message_borne_ar"] = "AR-TEST {a}"
    monkeypatch.setattr("track_b_accounting.calc.salary.charger_grille", lambda s: g)
    e = refus(Refus.PARAM_INVALIDE, salaire_base, secteur, "admin_tech", cat, annees, "2024-06-01")
    assert (e.message_fr, e.message_ar) == (f"FR-TEST {annees}", f"AR-TEST {annees}")


def test_textes_fenetre_et_categorie_19_lus_dans_le_json(monkeypatch):
    g = copy.deepcopy(G)
    b = g["au_dela_dernier_degre"]["admin_tech"]
    b.update(message_hors_fenetre_fr="F {a} {categorie} {case} {fin}", message_hors_fenetre_ar="A {a} {categorie} {case} {fin}")
    b["categories_refusees"]["19"].update(message_fr="C19-FR", message_ar="C19-AR")
    monkeypatch.setattr("track_b_accounting.calc.salary.charger_grille", lambda s: g)
    e = refus(Refus.SOURCE_MANQUANTE, salaire_base, BTP, "admin_tech", "4", 29, "2024-06-01")
    assert (e.message_fr, e.message_ar) == ("F 29 4 5/5 29", "A 29 4 5/5 29")
    e = refus(Refus.SOURCE_MANQUANTE, salaire_base, BTP, "admin_tech", "19", 28, "2024-06-01")
    assert (e.message_fr, e.message_ar) == ("C19-FR", "C19-AR")


def test_metallurgie_25_ans_plus_de_refus_d8(ok):
    """Le refus de D8 (≥ 22 ans) est remplacé par la règle de l'article 13 (D10)."""
    r = ok(salaire_base(BM_S, "execution", "7", 25, "2024-06-01"))
    assert r.montant == Decimal("4.652") and r.detail["n_paliers"] == 2


def test_texte_permanents_et_qefa_lus_dans_le_json(monkeypatch):
    g = copy.deepcopy(G)
    g["populations_non_couvertes"]["ouvriers_permanents"].update(message_fr="P-FR", message_ar="P-AR")
    g["primes_non_couvertes"]["prime_panier_qefa"].update(message_fr="Q-FR", message_ar="Q-AR")
    monkeypatch.setattr("track_b_accounting.calc.salary.charger_grille", lambda s: g)
    monkeypatch.setattr("track_b_accounting.calc.primes.charger_grille", lambda s: g)
    e = refus(Refus.SOURCE_MANQUANTE, salaire_base, BTP, "ouvriers_permanents", "1", None, "2024-01-01")
    assert (e.message_fr, e.message_ar) == ("P-FR", "P-AR")
    e = refus(Refus.SOURCE_MANQUANTE, prime, BTP, "prime_panier_qefa", "2024-01-01")
    assert (e.message_fr, e.message_ar) == ("Q-FR", "Q-AR")


# --- prime qefa BTP : non exposée ---------------------------------------------------------------------

def test_qefa_btp_non_exposee():
    bloc = G["primes_non_couvertes"]["prime_panier_qefa"]
    for params in ({}, {"condition_remplie": True}, {"transport_assure": False}):
        e = refus(Refus.SOURCE_MANQUANTE, prime, BTP, "prime_panier_qefa", "2024-01-01", **params)
        assert (e.message_fr, e.message_ar) == (bloc["message_fr"], bloc["message_ar"])
    assert "ambiguë" in bloc["message_fr"] and "سبع سنوات" in bloc["message_fr"]
    assert "51 (جديد) أ" in bloc["message_fr"] and "page 15" in bloc["message_fr"]
    assert "غامض" in bloc["message_ar"] and "الصفحة 15" in bloc["message_ar"]


def test_qefa_metallurgie_inchangee(ok):
    assert ok(prime(BM_S, "prime_panier_qefa", "2024-06-01", transport_assure=True)).montant == Decimal("0.160")


def test_autre_prime_btp_non_transcrite():
    """Aucune prime BTP n'est transcrite : refus explicite, sans liste vide dans le message."""
    e = refus(Refus.SOURCE_MANQUANTE, prime, BTP, "prime_transport", "2024-01-01")
    assert e.message_fr == f"Prime 'prime_transport' absente des données vérifiées ({BTP} : aucune prime transcrite)."


def test_valider_grille_rejette_structures_btp_incoherentes():
    mutations = [
        lambda g: g["degres"].__setitem__(OCC, [{"degre": 1, "anciennete_label": "0+"}]),   # degrés sans au_dela
        lambda g: g["au_dela_dernier_degre"].__setitem__(OCC, g["au_dela_dernier_degre"]["admin_tech"]),
        lambda g: g["sous_categories"][OCC]["par_categorie"]["6"]["I"].__setitem__("cle", "6_X"),
        lambda g: g["sous_categories"][OCC]["par_categorie"]["6"]["I"].__setitem__("libelle_ar", ""),
        lambda g: g["categories"][OCC].append("6"),                    # catégorie parente aussi en clé
        lambda g: g["populations_non_couvertes"]["ouvriers_permanents"].pop("message_ar"),
        lambda g: g["populations_non_couvertes"].__setitem__("admin_tech", {}),
        lambda g: g["primes_non_couvertes"]["prime_panier_qefa"].__setitem__("source_pdf_page", None),
        lambda g: g["_meta"].__setitem__("tables_transcrites", False),  # tables présentes mais déclarées absentes
        # article 13 (D10) : table de correspondance cohérente avec la grille
        lambda g: g["au_dela_dernier_degre"]["admin_tech"]["table_correspondance"]["4"].__setitem__("fenetre_annees", 3),
        lambda g: g["au_dela_dernier_degre"]["admin_tech"]["table_correspondance"]["4"].__setitem__("case_imprimee", "5/4"),
        lambda g: g["au_dela_dernier_degre"]["admin_tech"]["table_correspondance"]["4"].__setitem__("degre", 12),
        lambda g: g["au_dela_dernier_degre"]["admin_tech"]["table_correspondance"]["4"].__setitem__("categorie", "20"),
        lambda g: g["au_dela_dernier_degre"]["admin_tech"]["table_correspondance"].pop("18"),
        lambda g: g["au_dela_dernier_degre"]["admin_tech"]["categories_refusees"].pop("19"),
        lambda g: g["au_dela_dernier_degre"]["admin_tech"]["categories_refusees"]["19"].__setitem__("message_ar", ""),
        lambda g: g["au_dela_dernier_degre"]["admin_tech"].__setitem__("message_hors_fenetre_fr", "sans fin {a}"),
        lambda g: g["au_dela_dernier_degre"]["admin_tech"].__setitem__("dernier_degre_atteint_a_annees", 21),
        lambda g: g["grilles"][0]["valeurs"].__setitem__("1", [Decimal("2.567")]),   # occasionnels : montant unique
        lambda g: g["grilles"][1]["valeurs"]["4"].pop(),                # admin_tech : 10 degrés au lieu de 11
    ]
    for m in mutations:
        g = copy.deepcopy(G)
        m(g)
        refus(Refus.SOURCE_MANQUANTE, loaders.valider_grille, g, "x.json")


# --- contrat : sous_categorie et anciennete_annees optionnelle ----------------------------------------

def _req(**params):
    return {"contract_version": "track_b.v0", "request_id": "t", "operation": "salaire_base", "lang": "fr",
            "params": {"secteur": BTP, "population": OCC, "date": "2024-01-01", **params}}


def test_schema_accepte_sous_categorie_sans_anciennete():
    assert REQ_V.is_valid(_req(categorie=6, sous_categorie="I"))
    assert REQ_V.is_valid(_req(categorie=3))


def test_schema_rejette_sous_categorie_vide():
    assert not REQ_V.is_valid(_req(categorie=6, sous_categorie=""))
    rep = handle(_req(categorie=6, sous_categorie=""))
    assert rep["refus"]["code"] == "PARAM_INVALIDE" and rep["computed_by"] == "track_b_accounting.contract"


def test_contrat_sous_categorie_manquante_refus_calc():
    rep = handle(_req(categorie=7))
    assert rep["status"] == "refus" and rep["refus"]["code"] == "PARAM_INVALIDE"
    assert rep["computed_by"] == "track_b_accounting.calc.salaire_base"


def test_contrat_secteur_vide_param_invalide():
    rep = handle({**_req(categorie=3), "params": {**_req(categorie=3)["params"], "secteur": ""}})
    assert rep["refus"]["code"] == "PARAM_INVALIDE" and rep["computed_by"] == "track_b_accounting.calc.salaire_base"


def test_contrat_occasionnels_sous_categorie():
    rep = handle(_req(categorie=7, sous_categorie="3"))
    assert rep["status"] == "ok" and rep["result"]["montant"] == "4.946" and rep["result"]["unite"] == "TND/heure"
    assert rep["result"]["detail"]["libelle_fr"] == "Chef d'équipe, 3e degré"
