"""Salaire de base METALLURGIE_BATIMENT, degrés, choix de table, loaders et modèles.
Lancer depuis la racine du dépôt : pytest src/track_b_accounting/tests/test_calc_salary.py
"""
import copy
import datetime as dt
from decimal import Decimal

import pytest
from conftest import lire_json

from track_b_accounting.calc import Citation, Refus, Result, degre_from_anciennete, salaire_base, table_applicable
from track_b_accounting.calc import loaders
from track_b_accounting.calc.models import arrondi_millime, parse_date

S = "METALLURGIE_BATIMENT"
BM = lire_json("data/processed/salary_grids/metallurgie_batiment.json")
TABLES = {t["table_id"]: t for t in BM["grilles"]}


def refus(code, f, *a, **k):
    with pytest.raises(Refus) as e:
        f(*a, **k)
    assert e.value.code == code and e.value.message_fr and e.value.message_ar
    return e.value


# --- degré d'ancienneté -------------------------------------------------------------------------

@pytest.mark.parametrize("annees,degre", [
    (0, 1), (1.9, 1), (Decimal("2.01"), 2), (7, 4), (19.9, 10), (Decimal("20.5"), 11), (21.99, 11),
])
def test_degre(annees, degre):
    assert degre_from_anciennete(annees, S, "admin_tech") == degre


@pytest.mark.parametrize("borne", [2, 4, 6, 8, 10, 12, 14, 16, 18, 20, Decimal("20.000"), 2.0])
def test_degre_borne_ambigue_refusee(borne):
    e = refus(Refus.PARAM_INVALIDE, degre_from_anciennete, borne, S, "admin_tech")
    assert "borne" in e.message_fr


@pytest.mark.parametrize("val", [-1, -0.1, Decimal("-0.001"), float("nan"), float("inf"), "5", None, True])
def test_degre_invalide(val):
    refus(Refus.PARAM_INVALIDE, degre_from_anciennete, val, S, "admin_tech")


# --- au-delà du dernier degré : art. 13 (جديد) ب, p.9, écart cumulé tous les deux ans (D10) ---------------

@pytest.mark.parametrize("pop,cat", [("admin_tech", "4"), ("execution", "7")])
@pytest.mark.parametrize("annees", [21, 21.99, Decimal("21.999")])
def test_dernier_degre_avant_22_ans(pop, cat, annees, ok):
    r = ok(salaire_base(S, pop, cat, annees, "2024-06-01"))
    table = table_applicable(S, pop, "2024-06-01")
    assert r.detail["degre"] == 11 and r.montant == table["valeurs"][cat][10]


# Calculés à la main (tables 2024, p.34 et 35) : d11 + n × (d11 − d10), n = ⌊(a − 20) / 2⌋.
#   admin_tech cat. 4 : d11 = 680.334, d10 = 678.186, écart 2.148 ; execution cat. 7 : d11 = 4.620, d10 = 4.604, écart 0.016.
@pytest.mark.parametrize("pop,cat,annees,n,ecart,attendu,page", [
    ("admin_tech", "4", Decimal("22.5"), 1, "2.148", "682.482", 34),   # 680.334 + 1 × 2.148
    ("admin_tech", "4", Decimal("24.5"), 2, "2.148", "684.630", 34),   # 680.334 + 2 × 2.148
    ("admin_tech", "4", Decimal("30.5"), 5, "2.148", "691.074", 34),   # 680.334 + 5 × 2.148
    ("execution", "7", Decimal("22.5"), 1, "0.016", "4.636", 35),      # 4.620 + 1 × 0.016
    ("execution", "7", Decimal("24.5"), 2, "0.016", "4.652", 35),      # 4.620 + 2 × 0.016
    ("execution", "7", Decimal("30.5"), 5, "0.016", "4.700", 35),      # 4.620 + 5 × 0.016
])
def test_art13_exemples_calcules_a_la_main(pop, cat, annees, n, ecart, attendu, page, ok):
    r = ok(salaire_base(S, pop, cat, annees, "2024-06-01"))
    assert r.montant == Decimal(attendu)
    assert r.detail["degre"] == 11 and r.detail["regle_art13"] == "ecart_cumule_biennal"
    assert r.detail["n_paliers"] == n and r.detail["ecart"] == Decimal(ecart)
    assert r.detail["hypotheses"] == BM["au_dela_dernier_degre"][pop]["hypotheses_fr"] and len(r.detail["hypotheses"]) == 4
    assert r.detail["hypotheses_ar"] == BM["au_dela_dernier_degre"][pop]["hypotheses_ar"]
    grille, art13 = r.citations
    assert (grille.page, grille.article, grille.decision_ref) == (page, None, "D4")
    assert (art13.page, art13.article, art13.decision_ref) == (9, "13 (جديد) ب", "D10")


@pytest.mark.parametrize("pop,cat", [("admin_tech", "4"), ("execution", "7")])
@pytest.mark.parametrize("annees", [22, Decimal("22.000"), 24, 26, 30, 40])
def test_art13_paliers_exacts_refuses(pop, cat, annees):
    e = refus(Refus.PARAM_INVALIDE, salaire_base, S, pop, cat, annees, "2024-06-01")
    bloc = BM["au_dela_dernier_degre"][pop]
    a = str(Decimal(str(annees)))
    assert e.message_fr == bloc["message_borne_fr"].replace("{a}", a)
    assert e.message_ar == bloc["message_borne_ar"].replace("{a}", a)
    assert "article 13 (جديد) ب" in e.message_fr and "page 9" in e.message_fr
    assert "الفصل 13 (جديد) ب" in e.message_ar and "الصفحة 9" in e.message_ar


@pytest.mark.parametrize("annees,n", [(Decimal("22.01"), 1), (Decimal("23.99"), 1), (Decimal("24.01"), 2), (45, 12)])
def test_art13_nombre_de_paliers(annees, n, ok):
    r = ok(salaire_base(S, "admin_tech", "4", annees, "2024-06-01"))
    assert r.detail["n_paliers"] == n and r.montant == Decimal("680.334") + n * Decimal("2.148")


def test_art13_grille_en_vigueur_a_la_date(ok):
    """d10 et d11 lus dans la table en vigueur (2022 : BM_T_2021-12-01, p.30)."""
    r = ok(salaire_base(S, "admin_tech", "4", 25, "2022-06-01"))
    v = TABLES["BM_T_2021-12-01"]["valeurs"]["4"]
    assert r.montant == v[10] + 2 * (v[10] - v[9]) and r.citations[0].page == 30


def test_regle_refus_toujours_supportee(monkeypatch):
    """Un bloc de simple refus (D8) reste accepté pour un futur secteur : plafond lu dans le JSON."""
    grille = copy.deepcopy(BM)
    grille["au_dela_dernier_degre"]["admin_tech"] = {
        "regle": "refus", "anciennete_max_couverte_annees": 30, "source_pdf_page": 9, "source_article": "13",
        "message_fr": "FR {a}", "message_ar": "AR {a}"}
    grille = loaders.valider_grille(grille, "x.json")
    monkeypatch.setattr("track_b_accounting.calc.salary.charger_grille", lambda s: grille)
    assert degre_from_anciennete(25, S, "admin_tech") == 11
    e = refus(Refus.SOURCE_MANQUANTE, degre_from_anciennete, 30, S, "admin_tech")
    assert (e.message_fr, e.message_ar) == ("FR 30", "AR 30")


def test_bloc_au_dela_dernier_degre_dans_le_json():
    for pop in ("admin_tech", "execution"):
        b = BM["au_dela_dernier_degre"][pop]
        assert b["regle"] == "ecart_cumule_biennal" and b["source_pdf_page"] == 9 and b["decision_ref"] == "D10"
        assert b["dernier_degre_atteint_a_annees"] == 20 and b["periode_annees"] == 2
        assert b["statut"].startswith("IMPLÉMENTÉ (D10)")
        assert "يواصل التمتع كل سنتين" in b["texte_source_ar"] and "17 من 20" in b["texte_source_ar"]


def test_degre_libelle_illisible(monkeypatch):
    grille = copy.deepcopy(BM)
    grille["degres"]["admin_tech"][0]["anciennete_label"] = "moins de deux ans"
    monkeypatch.setattr("track_b_accounting.calc.salary.charger_grille", lambda s: grille)
    refus(Refus.SOURCE_MANQUANTE, degre_from_anciennete, 1, S, "admin_tech")


def test_degre_trou_dans_les_libelles(monkeypatch):
    grille = copy.deepcopy(BM)
    grille["degres"]["admin_tech"][1]["anciennete_label"] = "3-4"            # trou entre 2 et 3 ans
    monkeypatch.setattr("track_b_accounting.calc.salary.charger_grille", lambda s: grille)
    refus(Refus.SOURCE_MANQUANTE, degre_from_anciennete, 2.5, S, "admin_tech")


# --- choix de la table par date ------------------------------------------------------------------

@pytest.mark.parametrize("date,table_id", [
    ("2021-12-01", "BM_T_2021-12-01"),
    ("2022-06-01", "BM_T_2021-12-01"),
    ("2022-12-31", "BM_T_2021-12-01"),
    ("2023-01-01", "BM_T_2023-01-01"),
    (dt.date(2023, 12, 31), "BM_T_2023-01-01"),
    ("2024-01-01", "BM_T_2024-01-01"),
    ("2025-05-01", "BM_T_2024-01-01"),
])
def test_table_applicable(date, table_id):
    assert table_applicable(S, "admin_tech", date)["table_id"] == table_id


def test_table_applicable_execution():
    assert table_applicable(S, "execution", "2022-06-01")["table_id"] == "BM_E_2021-12-01"


def test_veille_premiere_table_refusee():
    e = refus(Refus.SOURCE_MANQUANTE, table_applicable, S, "admin_tech", "2021-11-30")
    assert "2021-12-01" in e.message_fr


@pytest.mark.parametrize("date", ["2023-02-30", "01/01/2023", 20230101, None, dt.datetime(2023, 1, 1, 8, 0)])
def test_date_invalide(date):
    refus(Refus.PARAM_INVALIDE, table_applicable, S, "admin_tech", date)


# --- salaire de base -----------------------------------------------------------------------------

def test_valeurs_codees_en_dur_verifiees_d4(ok):
    """Cellules relues sur le PDF en D4 (p.30, 32, 34, 35), dont les 2 corrections de BM_T_2021-12-01."""
    cas = [
        (("admin_tech", "1B", 1, "2022-06-01"), "512.027", "TND/mois", 30),   # cat. fixe, degré 1
        (("admin_tech", "18", 11, "2023-06-01"), "1231.060", "TND/mois", 32),  # cat. fixe, degré 6
        (("admin_tech", "18", 21, "2024-03-01"), "1359.212", "TND/mois", 34),  # cat. fixe, degré 11
        (("admin_tech", "4", 15, "2022-01-15"), "593.873", "TND/mois", 30),    # correction D4
        (("admin_tech", "15", 19, "2022-01-15"), "1007.111", "TND/mois", 30),  # correction D4
        (("execution", "7", 21, "2024-01-01"), "4.620", "TND/heure", 35),     # cat. fixe, degré 11
    ]
    for (pop, cat, anc, date), montant, unite, page in cas:
        r = ok(salaire_base(S, pop, cat, anc, date))
        assert r.montant == Decimal(montant) and r.unite == unite
        assert r.citations[0].page == page and r.citations[0].decision_ref == "D4"


@pytest.mark.parametrize("tid", list(TABLES))
def test_toutes_cellules_egales_au_json(tid, ok):
    """Chaque cellule de chaque table, lue par le test directement dans le JSON."""
    t = TABLES[tid]
    pop = "admin_tech" if set(t["valeurs"]) == set(BM["categories"]["admin_tech"]) else "execution"
    for cat, vals in t["valeurs"].items():
        for k, attendu in enumerate(vals):
            anc = 2 * k + 1                                    # milieu de l'intervalle du degré k+1
            r = ok(salaire_base(S, pop, cat, anc, t["effective_date"]))
            assert r.montant == attendu and r.unite == t["unite"]
            assert r.detail["degre"] == k + 1 and r.detail["table_id"] == tid
            assert r.citations[0].page == t["source_pdf_page"]
            assert r.citations[0].source_file == BM["_meta"]["source_file"]


def test_categorie_entiere_acceptee(ok):
    assert ok(salaire_base(S, "execution", 3, 0, "2023-01-01")).montant == Decimal("3.284")


@pytest.mark.parametrize("cat", ["19", "1C", "", None, 1.0, True])
def test_categorie_inconnue(cat):
    refus(Refus.PARAM_INVALIDE, salaire_base, S, "admin_tech", cat, 3, "2023-01-01")


def test_categorie_execution_absente_des_admin():
    refus(Refus.PARAM_INVALIDE, salaire_base, S, "execution", "1A", 3, "2023-01-01")


def test_population_inconnue():
    refus(Refus.PARAM_INVALIDE, salaire_base, S, "cadres", "1", 3, "2023-01-01")


@pytest.mark.parametrize("secteur", ["BTP", "metallurgie_batiment"])
def test_secteur_inconnu(secteur):
    refus(Refus.SOURCE_MANQUANTE, salaire_base, secteur, "admin_tech", "1A", 3, "2023-01-01")


def test_conversion_horaire_mensuel_refusee(ok):
    e = refus(Refus.HORS_SCOPE, salaire_base, S, "execution", "1", 3, "2023-01-01", unite_souhaitee="TND/mois")
    assert e.message_ar
    ok(salaire_base(S, "execution", "1", 3, "2023-01-01", unite_souhaitee="TND/heure"))


def test_borne_ambigue_dans_salaire_base():
    refus(Refus.PARAM_INVALIDE, salaire_base, S, "admin_tech", "5", 10, "2023-01-01")


def test_deterministe():
    a = salaire_base(S, "admin_tech", "9", 5.5, "2024-02-02")
    assert a == salaire_base(S, "admin_tech", "9", 5.5, "2024-02-02")


# --- loaders -------------------------------------------------------------------------------------

def test_loaders_ne_lisent_que_data_processed():
    assert all(p.startswith("data/processed/") for p in loaders.GRILLES.values())
    assert loaders.SMIG_FILE.startswith("data/processed/")


def test_loader_cache():
    assert loaders.charger_grille(S) is loaders.charger_grille(S)


def test_loader_nombres_en_decimal():
    g = loaders.charger_grille(S)
    assert type(g["grilles"][0]["valeurs"]["1A"][0]) is Decimal


@pytest.mark.parametrize("mutation", [
    lambda g: g["_meta"].pop("source_file"),
    lambda g: g.__setitem__("degres", []),
    lambda g: g.pop("au_dela_dernier_degre"),
    lambda g: g["au_dela_dernier_degre"]["admin_tech"].__setitem__("regle", "inconnue"),
    lambda g: g["au_dela_dernier_degre"]["admin_tech"].__setitem__("periode_annees", 0),
    lambda g: g["au_dela_dernier_degre"]["admin_tech"].pop("source_pdf_page"),
    lambda g: g["au_dela_dernier_degre"]["admin_tech"].__setitem__("source_article", ""),
    lambda g: g["au_dela_dernier_degre"]["admin_tech"].__setitem__("message_borne_ar", ""),
    lambda g: g["au_dela_dernier_degre"]["execution"].__setitem__("message_borne_fr", "sans ancienneté"),
    lambda g: g["au_dela_dernier_degre"]["execution"]["hypotheses_ar"].pop(),
    lambda g: g["au_dela_dernier_degre"]["execution"].__setitem__("decision_ref", "D-10"),
    lambda g: g["au_dela_dernier_degre"]["execution"].__setitem__("dernier_degre_atteint_a_annees", 18),
    lambda g: g["au_dela_dernier_degre"].pop("execution"),
    lambda g: g["degres"].pop("execution"),
    lambda g: g["_meta"].__setitem__("tables_transcrites", False),
    lambda g: g["categories"].__setitem__("execution", []),
    lambda g: g.__setitem__("grilles", []),
    lambda g: g["grilles"][0].pop("source_pdf_page"),
    lambda g: g["grilles"][0]["valeurs"]["1A"].pop(),
    lambda g: g["grilles"][0]["valeurs"]["1A"].__setitem__(0, 497.324),
    lambda g: g["primes"][0].pop("source_article"),
])
def test_valider_grille_rejette(mutation):
    g = copy.deepcopy(BM)
    mutation(g)
    refus(Refus.SOURCE_MANQUANTE, loaders.valider_grille, g, "x.json")


def test_valider_grille_accepte():
    assert loaders.valider_grille(copy.deepcopy(BM), "x.json")


def test_lire_fichier_absent_ou_mal_forme(tmp_path, monkeypatch):
    monkeypatch.setattr(loaders, "REPO_ROOT", tmp_path)
    refus(Refus.SOURCE_MANQUANTE, loaders._lire, "absent.json")
    (tmp_path / "casse.json").write_text("{pas du json", encoding="utf-8")
    refus(Refus.SOURCE_MANQUANTE, loaders._lire, "casse.json")


# --- modèles -------------------------------------------------------------------------------------

CIT = Citation("data/raw/pdf/x.pdf", 1, None, "data/processed/x.json", "D4")


def test_result_refuse_float_et_absence_de_citation():
    with pytest.raises(TypeError):
        Result(montant=1.5, unite="TND/mois", citations=[CIT])
    with pytest.raises(ValueError):
        Result(montant=Decimal("1.500"), unite="TND/mois", citations=[])
    with pytest.raises(ValueError):
        Result(montant=Decimal("1.500"), unite="TND/mois", citations=["D4"])


def test_refus_code_inconnu():
    with pytest.raises(ValueError):
        Refus("AUTRE", "x", "x")


@pytest.mark.parametrize("x,attendu", [
    ("1.0005", "1.001"), ("1.0004", "1.000"), ("2.2085", "2.209"), ("0.56", "0.560"), ("-1.0005", "-1.001"),
])
def test_arrondi_millime_half_up(x, attendu):
    assert str(arrondi_millime(Decimal(x))) == attendu


def test_arrondi_refuse_float():
    with pytest.raises(TypeError):
        arrondi_millime(1.0005)


def test_parse_date():
    assert parse_date("2023-01-01") == dt.date(2023, 1, 1)
    assert parse_date(dt.date(2023, 1, 1)) == dt.date(2023, 1, 1)


# --- référence de vérification (_meta.decision_ref) -------------------------------------------------

def test_decision_ref_lue_dans_le_json(ok):
    r = ok(salaire_base(S, "admin_tech", "4", 15, "2022-06-01"))
    assert r.citations[0].decision_ref == BM["_meta"]["decision_ref"] == "D4"


def test_decision_ref_pas_en_dur(monkeypatch, ok):
    grille = copy.deepcopy(BM)
    grille["_meta"]["decision_ref"] = "D99"
    monkeypatch.setattr("track_b_accounting.calc.salary.charger_grille", lambda s: grille)
    assert ok(salaire_base(S, "admin_tech", "4", 15, "2022-06-01")).citations[0].decision_ref == "D99"


@pytest.mark.parametrize("valeur", ["absent", None, "", "4", "D4 bis", 4])
def test_decision_ref_absente_refusee(valeur, monkeypatch):
    grille = copy.deepcopy(BM)
    if valeur == "absent":
        grille["_meta"].pop("decision_ref")
    else:
        grille["_meta"]["decision_ref"] = valeur
    monkeypatch.setattr("track_b_accounting.calc.salary.charger_grille", lambda s: grille)
    e = refus(Refus.SOURCE_MANQUANTE, salaire_base, S, "admin_tech", "4", 15, "2022-06-01")
    assert "decision_ref" in e.message_fr
