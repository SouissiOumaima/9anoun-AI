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
    (0, 1), (1.9, 1), (Decimal("2.01"), 2), (7, 4), (19.9, 10), (Decimal("20.5"), 11), (35, 11),
])
def test_degre(annees, degre):
    assert degre_from_anciennete(annees) == degre


@pytest.mark.parametrize("borne", [2, 4, 6, 8, 10, 12, 14, 16, 18, 20, Decimal("20.000"), 2.0])
def test_degre_borne_ambigue_refusee(borne):
    e = refus(Refus.PARAM_INVALIDE, degre_from_anciennete, borne)
    assert "borne" in e.message_fr


@pytest.mark.parametrize("val", [-1, -0.1, Decimal("-0.001"), float("nan"), float("inf"), "5", None, True])
def test_degre_invalide(val):
    refus(Refus.PARAM_INVALIDE, degre_from_anciennete, val)


def test_degre_libelle_illisible(monkeypatch):
    grille = copy.deepcopy(BM)
    grille["degres"][0]["anciennete_label"] = "moins de deux ans"
    monkeypatch.setattr("track_b_accounting.calc.salary.charger_grille", lambda s: grille)
    refus(Refus.SOURCE_MANQUANTE, degre_from_anciennete, 1)


def test_degre_trou_dans_les_libelles(monkeypatch):
    grille = copy.deepcopy(BM)
    grille["degres"][1]["anciennete_label"] = "3-4"            # trou entre 2 et 3 ans
    monkeypatch.setattr("track_b_accounting.calc.salary.charger_grille", lambda s: grille)
    refus(Refus.SOURCE_MANQUANTE, degre_from_anciennete, 2.5)


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
        (("admin_tech", "18", 25, "2024-03-01"), "1359.212", "TND/mois", 34),  # cat. fixe, degré 11
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


@pytest.mark.parametrize("secteur", ["BTP", "metallurgie_batiment", ""])
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
