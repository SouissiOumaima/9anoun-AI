"""Contrôles automatiques de la grille BATIMENT_TRAVAUX_PUBLICS (D9) : anti-erreur de saisie + calcul de bout en bout.
Lancer depuis la racine du dépôt : pytest src/track_b_accounting/tests/test_grid_btp.py
"""
import json
from decimal import Decimal as D
from pathlib import Path

import pytest

from track_b_accounting.calc import Refus, salaire_base

# Racine du dépôt = parents[3] depuis ce fichier :
# src/track_b_accounting/tests/test_grid_btp.py -> tests -> track_b_accounting -> src -> <racine>
REPO_ROOT = Path(__file__).resolve().parents[3]
DATA_FILE = "data/processed/salary_grids/batiment_travaux_publics.json"
GRID_PATH = REPO_ROOT / DATA_FILE
GRID = json.loads(GRID_PATH.read_text(encoding="utf-8"), parse_float=D)
TABLES = {t["table_id"]: t for t in GRID["grilles"]}
DATES = ["2021-12-01", "2023-01-01", "2024-01-01"]
PAGES = {"2021-12-01": 23, "2023-01-01": 24, "2024-01-01": 25}
BTP, OCC = "BATIMENT_TRAVAUX_PUBLICS", "ouvriers_occasionnels"
CLES_OCC = ["1", "2", "3", "4", "5", "6_I", "6_II", "7_1", "7_2", "7_3"]
R = D("1.0675")                                   # revalorisation constatée entre deux dates (+6,75 %)


def test_racine_du_depot():
    assert (REPO_ROOT / "docs" / "DECISIONS.md").is_file() and GRID_PATH.is_file()


def test_structure_et_657_cellules():
    assert GRID["_meta"]["tables_transcrites"] is True and GRID["_meta"]["decision_ref"] == "D9"
    assert sorted(TABLES) == sorted([f"BTP_AT_{d}" for d in DATES] + [f"BTP_OCC_{d}" for d in DATES])
    n = 0
    for d in DATES:
        at, occ = TABLES[f"BTP_AT_{d}"], TABLES[f"BTP_OCC_{d}"]
        assert at["effective_date"] == occ["effective_date"] == d
        assert at["source_pdf_page"] == occ["source_pdf_page"] == PAGES[d]
        assert at["unite"] == "TND/mois" and occ["unite"] == "TND/heure"
        assert at["regime_hebdomadaire_heures"] is None and occ["regime_hebdomadaire_heures"] is None
        assert at["statut_verification"].startswith("VÉRIFIÉ") and occ["statut_verification"].startswith("VÉRIFIÉ")
        assert list(at["valeurs"]) == [str(c) for c in range(1, 20)]
        assert all(len(v) == 11 for v in at["valeurs"].values())
        assert list(occ["valeurs"]) == CLES_OCC and all(isinstance(v, D) for v in occ["valeurs"].values())
        n += sum(len(v) for v in at["valeurs"].values()) + len(occ["valeurs"])
    assert n == 3 * 209 + 3 * 10 == 657


def test_remarque_indemnite_complementaire():
    m = GRID["_meta"]
    assert "437" in m["remarque_pdf"] and "501" in m["remarque_pdf"] and "1981" in m["remarque_pdf"]
    assert "المنحة التكميلية المؤقتة" in m["remarque_pdf_ar"]


# --- cellules de référence relues sur le PDF -----------------------------------------------------------

# Les 5 anomalies d'incrément du tableau 2 (p.23), conservées telles qu'imprimées, et leur report en 2023/2024.
ANOMALIES = {
    ("1", 11): ["535.028", "570.375", "608.109"],
    ("2", 11): ["562.267", "599.828", "639.924"],
    ("3", 7): ["588.076", "627.469", "669.521"],
    ("6", 3): ["678.440", "723.903", "772.435"],
    ("14", 6): ["1220.466", "1300.939", "1386.844"],
}


@pytest.mark.parametrize("cle", list(ANOMALIES), ids=lambda k: f"cat{k[0]}-deg{k[1]}")
def test_anomalies_conservees_telles_qu_imprimees(cle):
    cat, deg = cle
    for d, attendu in zip(DATES, ANOMALIES[cle]):
        t = TABLES[f"BTP_AT_{d}"]
        assert t["valeurs"][cat][deg - 1] == D(attendu)
        trace = [a for a in t["anomalies_increment"] if (a["categorie"], a["degre"]) == cle]
        assert len(trace) == 1 and trace[0]["valeur_imprimee"] == D(attendu)
        assert trace[0]["anomalie_increment"] and "telle qu'imprimée" in trace[0]["note"]


def test_anomalies_increment_seulement_les_5():
    for d in DATES:
        assert {(a["categorie"], a["degre"]) for a in TABLES[f"BTP_AT_{d}"]["anomalies_increment"]} == set(ANOMALIES)
        assert "anomalies_increment" not in TABLES[f"BTP_OCC_{d}"]


# Tableaux 1, 3 et 5 (p.23-25), ordre 1, 2, 3, 4, 5, 6-I, 6-II, 7 1er/2e/3e degré.
OCCASIONNELS = {
    "2021-12-01": "2.567 2.675 2.830 2.961 3.103 3.280 3.516 3.766 4.006 4.340",
    "2023-01-01": "2.740 2.856 3.021 3.161 3.313 3.502 3.754 4.021 4.276 4.633",
    "2024-01-01": "2.925 3.049 3.225 3.374 3.536 3.738 4.007 4.292 4.565 4.946",
}


@pytest.mark.parametrize("date", DATES)
def test_occasionnels_30_cellules_relues(date):
    assert TABLES[f"BTP_OCC_{date}"]["valeurs"] == dict(zip(CLES_OCC, map(D, OCCASIONNELS[date].split())))


# --- règle entre années ----------------------------------------------------------------------------------

@pytest.mark.parametrize("d0,d1", list(zip(DATES, DATES[1:])))
def test_admin_revalorisation_degre1_ajoutee_a_tous_les_degres(d0, d1):
    """Chaque catégorie reçoit (degré 1 de l'année précédente) × 6,75 %, ajouté tel quel à ses 11 degrés.
    Écart maximal constaté : 0,0009 (arrondis). Seuil de détection mesuré : une erreur ≥ 0,002 dans l'une des deux
    tables échoue ; une erreur de 0,001 peut passer — la double lecture reste la vérification principale (D9).
    """
    a, b = TABLES[f"BTP_AT_{d0}"]["valeurs"], TABLES[f"BTP_AT_{d1}"]["valeurs"]
    for c in a:
        hausse = a[c][0] * (R - 1)
        for k in range(11):
            assert abs((b[c][k] - a[c][k]) - hausse) <= D("0.001"), (d0, d1, c, k + 1)


@pytest.mark.parametrize("d0,d1", list(zip(DATES, DATES[1:])))
def test_occasionnels_ratio_1_0675(d0, d1):
    """Taux horaire × 1,0675 arrondi au millime : |nouveau - ancien × r| ≤ 0,0005 × (1 + r) ≈ 0,00104."""
    a, b = TABLES[f"BTP_OCC_{d0}"]["valeurs"], TABLES[f"BTP_OCC_{d1}"]["valeurs"]
    borne = D("0.0005") * (1 + R)
    for c in a:
        assert abs(b[c] - a[c] * R) <= borne, (d0, d1, c)


# --- monotonie -------------------------------------------------------------------------------------------

@pytest.mark.parametrize("date", DATES)
def test_monotonie(date):
    at = TABLES[f"BTP_AT_{date}"]["valeurs"]
    for c, v in at.items():
        assert all(v[k] < v[k + 1] for k in range(10)), (date, c)
    for k in range(11):
        col = [at[c][k] for c in at]
        assert all(x < y for x, y in zip(col, col[1:])), (date, k + 1)
    occ = list(TABLES[f"BTP_OCC_{date}"]["valeurs"].values())
    assert all(x < y for x, y in zip(occ, occ[1:])), date


# --- calcul de bout en bout ------------------------------------------------------------------------------

def _citation(r, page):
    c = r.citations[0]
    assert c.page == page and c.data_file == DATA_FILE
    assert c.decision_ref == GRID["_meta"]["decision_ref"] == "D9"
    assert c.source_file == GRID["_meta"]["source_file"]


@pytest.mark.parametrize("annees,date,degre,attendu,page", [
    (0, "2022-01-01", 1, "605.979", 23),             # 2021-12-01 : cat. 4, degré 1
    (13, "2024-03-01", 7, "699.751", 25),            # 12-15 ans -> degré 7
    (D("23.9"), "2023-06-30", 10, "662.413", 24),
    (26.99, "2024-01-01", 11, "710.687", 25),        # dernier jour couvert avant le plafond de 27 ans
])
def test_admin_tech_bout_en_bout(annees, date, degre, attendu, page, ok):
    r = ok(salaire_base(BTP, "admin_tech", "4", annees, date))
    assert r.montant == D(attendu) and r.unite == "TND/mois" and r.detail["degre"] == degre
    assert TABLES[r.detail["table_id"]]["source_pdf_page"] == page and r.detail["table_id"].startswith("BTP_AT_")
    _citation(r, page)


def test_admin_tech_anomalie_servie_telle_qu_imprimee(ok):
    r = ok(salaire_base(BTP, "admin_tech", 6, 5, "2022-02-01"))          # cat. 6, degré 3 (4-6 ans)
    assert r.montant == D("678.440")


@pytest.mark.parametrize("cat,sous,date,attendu,page,libelle", [
    (1, None, "2021-12-01", "2.567", 23, None),
    ("6", "I", "2023-01-01", "3.502", 24, "عامل ذو كفاءة عالية I"),
    (6, "II", "2022-12-31", "3.516", 23, "عامل ذو كفاءة عالية II"),
    ("7", "1", "2024-05-01", "4.292", 25, "رئيس فريق درجة أولى"),
    (7, "3", "2023-12-31", "4.633", 24, "رئيس فريق درجة ثالثة"),
])
def test_occasionnels_bout_en_bout(cat, sous, date, attendu, page, libelle, ok):
    r = ok(salaire_base(BTP, OCC, cat, date=date, sous_categorie=sous))
    assert r.montant == D(attendu) and r.unite == "TND/heure"
    assert "degre" not in r.detail and r.detail.get("libelle_ar") == libelle
    assert r.detail["regime_hebdomadaire_heures"] is None
    _citation(r, page)


@pytest.mark.parametrize("annees", [27, 28, D("40")])
def test_plafond_27_ans(annees):
    with pytest.raises(Refus) as e:
        salaire_base(BTP, "admin_tech", "19", annees, "2024-01-01")
    assert e.value.code == Refus.SOURCE_MANQUANTE and "27 ans" in e.value.message_fr


@pytest.mark.parametrize("borne", [2, 4, 6, 8, 10, 12, 15, 18, 21, 24])
def test_bornes_ambigues(borne):
    with pytest.raises(Refus) as e:
        salaire_base(BTP, "admin_tech", "1", borne, "2024-01-01")
    assert e.value.code == Refus.PARAM_INVALIDE


def test_avant_premiere_date():
    with pytest.raises(Refus) as e:
        salaire_base(BTP, OCC, 1, date="2021-11-30")
    assert e.value.code == Refus.SOURCE_MANQUANTE and "2021-12-01" in e.value.message_fr
