"""Contrôles automatiques de la grille ASSOCIATIONS_PERSONNES_HANDICAPEES (D23) : anti-erreur de saisie + calcul de
bout en bout. Les 864 cellules et les 9 anomalies imprimées ont été vérifiées visuellement sur le PDF (p.21 à 29).

Les régularités observées entre cellules (environ 2 % d'un degré au suivant, 6,75 % d'une date à la suivante) ne sont
écrites dans aucun texte de la convention : elles servent ici UNIQUEMENT de contrôles de lecture (tolérance ±0,001),
jamais de règles de calcul. Elles ne détectent pas toute erreur de 0,001 ou 0,002 ; la double lecture et la
vérification visuelle restent les vrais contrôles.
Lancer depuis la racine du dépôt : pytest src/track_b_accounting/tests/test_grid_associations.py
"""
import json
from decimal import ROUND_HALF_UP, Decimal as D
from pathlib import Path

import pytest

from track_b_accounting.calc import Refus, salaire_base
from track_b_accounting.calc import loaders

# src/track_b_accounting/tests/test_grid_associations.py -> tests -> track_b_accounting -> src -> <racine>
REPO_ROOT = Path(__file__).resolve().parents[3]
DATA_FILE = "data/processed/salary_grids/associations_personnes_handicapees.json"
GRID = json.loads((REPO_ROOT / DATA_FILE).read_text(encoding="utf-8"), parse_float=D)
TABLES = {t["table_id"]: t for t in GRID["grilles"]}
PREVUES = {t["table_id"]: t for t in GRID["tables_prevues"]}
APH = "ASSOCIATIONS_PERSONNES_HANDICAPEES"
DATES = ["2021-12-01", "2023-01-01", "2024-01-01"]
POPS = {"EDUCATION_SPECIALISEE": "education_specialisee", "SPORT": "sport",
        "OUVRIERS_ADMINISTRATIFS_SURVEILLANTS": "ouvriers_administratifs_surveillants", "TECHNICIENS": "techniciens",
        "FORMATEURS_PROFESSIONNELS": "formateurs_professionnels"}
LIGNES = {"education_specialisee": ["I", "II", "III"], "sport": ["I", "II", "III"],
          "ouvriers_administratifs_surveillants": ["I", "II", "III", "IV", "V", "VI"],
          "techniciens": ["I", "III+II"], "formateurs_professionnels": ["I", "II", "III", "IV"]}
PAGES = {"2021-12-01": (21, 21, 22, 22, 23), "2023-01-01": (24, 24, 25, 25, 26), "2024-01-01": (27, 27, 28, 28, 29)}
MILLIME = D("0.001")


def tid(pop, date):
    return f"APH_{pop}_{date}"


# --- structure : 5 populations, 15 tables, 18 lignes, 16 degrés, 864 cellules ----------------------------------

def test_structure_et_864_cellules():
    assert GRID["_meta"]["tables_transcrites"] is True and GRID["_meta"]["decision_ref"] == "D23"
    assert GRID["categories"] == LIGNES and sum(len(v) for v in LIGNES.values()) == 18
    assert all(len(d) == 16 and [x["degre"] for x in d] == list(range(1, 17)) for d in GRID["degres"].values())
    assert sorted(TABLES) == sorted(tid(p, d) for p in POPS for d in DATES)
    n = 0
    for d in DATES:
        for (p, pop), page in zip(POPS.items(), PAGES[d]):
            t = TABLES[tid(p, d)]
            assert (t["population"], t["effective_date"], t["source_pdf_page"], t["unite"]) == (pop, d, page, "TND/mois")
            assert list(t["valeurs"]) == LIGNES[pop] == PREVUES[tid(p, d)]["categories"]
            n += sum(len(v) for v in t["valeurs"].values())
    assert n == 864
    assert [PREVUES[t]["numero_imprime"] for t in TABLES] == list(range(1, 16))


def test_aucune_cellule_vide():
    for t in TABLES.values():
        for lig, v in t["valeurs"].items():
            assert len(v) == 16 and all(isinstance(x, D) and x > 0 and x.as_tuple().exponent == -3 for x in v), (
                t["table_id"], lig)


# --- cellules relues sur le PDF ---------------------------------------------------------------------------------

# Degré 1 de chaque ligne des 15 tables (base non contrôlée par la régularité de 2 %).
DEGRE_1 = {
    "2021-12-01": {"EDUCATION_SPECIALISEE": "814.351 950.077 1085.802", "SPORT": "529.328 950.077 1085.802",
                   "OUVRIERS_ADMINISTRATIFS_SURVEILLANTS": "407.176 529.328 556.473 590.405 678.626 950.077",
                   "TECHNICIENS": "950.077 1072.229", "FORMATEURS_PROFESSIONNELS": "529.328 787.206 922.931 1058.657"},
    "2023-01-01": {"EDUCATION_SPECIALISEE": "869.320 1014.207 1159.093", "SPORT": "565.058 1014.207 1159.093",
                   "OUVRIERS_ADMINISTRATIFS_SURVEILLANTS": "434.660 565.058 594.035 630.257 724.433 1014.207",
                   "TECHNICIENS": "1014.207 1144.605", "FORMATEURS_PROFESSIONNELS": "565.058 840.343 985.229 1130.116"},
    "2024-01-01": {"EDUCATION_SPECIALISEE": "927.999 1082.666 1237.332", "SPORT": "603.199 1082.666 1237.332",
                   "OUVRIERS_ADMINISTRATIFS_SURVEILLANTS": "464.000 603.199 634.133 672.799 773.333 1082.666",
                   "TECHNICIENS": "1082.666 1221.866", "FORMATEURS_PROFESSIONNELS": "603.199 897.066 1051.732 1206.399"},
}


@pytest.mark.parametrize("date", DATES)
@pytest.mark.parametrize("pop", list(POPS))
def test_degre_1_de_chaque_table(pop, date):
    t = TABLES[tid(pop, date)]
    assert [str(v[0]) for v in t["valeurs"].values()] == DEGRE_1[date][pop].split()


# 9 cellules prises dans les 3 années et les 5 populations, puis 5 des 29 cellules qu'aucun contrôle de lecture ne
# protège (vérifiées visuellement une à une).
CELLULES = [
    ("EDUCATION_SPECIALISEE", "2021-12-01", "III", 8, "1247.246"),
    ("OUVRIERS_ADMINISTRATIFS_SURVEILLANTS", "2021-12-01", "V", 12, "843.786"),
    ("FORMATEURS_PROFESSIONNELS", "2021-12-01", "IV", 16, "1424.812"),
    ("SPORT", "2023-01-01", "I", 10, "675.296"),
    ("TECHNICIENS", "2023-01-01", "III+II", 16, "1540.487"),
    ("OUVRIERS_ADMINISTRATIFS_SURVEILLANTS", "2023-01-01", "VI", 2, "1034.491"),
    ("EDUCATION_SPECIALISEE", "2024-01-01", "I", 14, "1200.466"),
    ("TECHNICIENS", "2024-01-01", "I", 7, "1219.258"),
    ("FORMATEURS_PROFESSIONNELS", "2024-01-01", "II", 5, "971.013"),
]
NON_PROTEGEES = [
    ("EDUCATION_SPECIALISEE", "2021-12-01", "I", 16, "1096.010"),
    ("TECHNICIENS", "2021-12-01", "III+II", 8, "1231.655"),
    ("EDUCATION_SPECIALISEE", "2023-01-01", "I", 4, "922.530"),
    ("FORMATEURS_PROFESSIONNELS", "2023-01-01", "III", 16, "1325.988"),
    ("OUVRIERS_ADMINISTRATIFS_SURVEILLANTS", "2024-01-01", "IV", 16, "905.500"),
]


@pytest.mark.parametrize("pop, date, lig, deg, attendu", CELLULES + NON_PROTEGEES)
def test_cellules_relues(pop, date, lig, deg, attendu):
    assert str(TABLES[tid(pop, date)]["valeurs"][lig][deg - 1]) == attendu


def test_echantillon_couvre_annees_et_populations():
    assert {c[1] for c in CELLULES} == set(DATES) and {c[0] for c in CELLULES} == set(POPS)


# Les 9 anomalies imprimées, conservées telles quelles (aucune correction) : valeur imprimée et valeur que donnerait
# la régularité observée de 2 %.
ANOMALIES = {
    (tid("FORMATEURS_PROFESSIONNELS", "2023-01-01"), "III", 12): ("1225.010", "1225.008"),
    (tid("SPORT", "2024-01-01"), "I", 6): ("665.982", "665.980"),
    (tid("SPORT", "2024-01-01"), "I", 16): ("811.828", "811.826"),
    (tid("OUVRIERS_ADMINISTRATIFS_SURVEILLANTS", "2024-01-01"), "I", 4): ("492.399", "492.401"),
    (tid("OUVRIERS_ADMINISTRATIFS_SURVEILLANTS", "2024-01-01"), "II", 6): ("665.982", "665.980"),
    (tid("OUVRIERS_ADMINISTRATIFS_SURVEILLANTS", "2024-01-01"), "II", 16): ("811.828", "811.826"),
    (tid("FORMATEURS_PROFESSIONNELS", "2024-01-01"), "I", 6): ("665.982", "665.980"),
    (tid("FORMATEURS_PROFESSIONNELS", "2024-01-01"), "I", 16): ("811.828", "811.826"),
    (tid("FORMATEURS_PROFESSIONNELS", "2024-01-01"), "III", 14): ("1360.529", "1360.527"),
}


@pytest.mark.parametrize("cle", list(ANOMALIES), ids=lambda k: f"{k[0][4:]}-{k[1]}-deg{k[2]}")
def test_anomalies_a_leur_valeur_imprimee_exacte(cle):
    t, lig, deg = TABLES[cle[0]], cle[1], cle[2]
    imprimee = ANOMALIES[cle][0]
    assert str(t["valeurs"][lig][deg - 1]) == imprimee
    (trace,) = [a for a in t["anomalies_increment"] if (a["categorie"], a["degre"]) == (lig, deg)]
    assert str(trace["valeur_imprimee"]) == imprimee and "aucune correction" in trace["note"]


def test_anomalies_increment_seulement_les_9():
    trouvees = {(t["table_id"], a["categorie"], a["degre"]) for t in TABLES.values() for a in t.get("anomalies_increment", [])}
    assert trouvees == set(ANOMALIES)


# --- croissance et identités de lignes ----------------------------------------------------------------------------

@pytest.mark.parametrize("table_id", sorted(TABLES))
def test_croissance_des_lignes(table_id):
    for lig, v in TABLES[table_id]["valeurs"].items():
        assert all(a < b for a, b in zip(v, v[1:])), (table_id, lig)


# Lignes identiques d'une table à l'autre à la même date, chacune lue séparément sur sa page (aucune recopie).
IDENTITES = [
    [("EDUCATION_SPECIALISEE", "II"), ("SPORT", "II"), ("OUVRIERS_ADMINISTRATIFS_SURVEILLANTS", "VI"), ("TECHNICIENS", "I")],
    [("EDUCATION_SPECIALISEE", "III"), ("SPORT", "III")],
    [("SPORT", "I"), ("OUVRIERS_ADMINISTRATIFS_SURVEILLANTS", "II"), ("FORMATEURS_PROFESSIONNELS", "I")],
]


@pytest.mark.parametrize("date", DATES)
def test_identites_de_lignes_entre_tables(date):
    for groupe in IDENTITES:
        lignes = [TABLES[tid(p, date)]["valeurs"][lig] for p, lig in groupe]
        assert all(l == lignes[0] for l in lignes), (date, groupe)
    # Aucune autre paire de lignes identiques à cette date.
    toutes = [(p, lig, tuple(v)) for p in POPS for lig, v in TABLES[tid(p, date)]["valeurs"].items()]
    paires = {frozenset([(a, la), (b, lb)]) for i, (a, la, va) in enumerate(toutes) for b, lb, vb in toutes[i + 1:] if va == vb}
    attendues = {frozenset([x, y]) for g in IDENTITES for i, x in enumerate(g) for y in g[i + 1:]}
    assert paires == attendues


# --- régularités observées : contrôles de lecture SEULEMENT, jamais règles de calcul --------------------------------

@pytest.mark.parametrize("table_id", sorted(TABLES))
def test_controle_de_lecture_deux_pour_cent_par_degre(table_id):
    """Contrôle de lecture : degré k ≈ degré 1 × 1,02^(k−1) arrondi, à ±0,001 près, sauf les 9 anomalies imprimées
    (écart exact attendu). Régularité observée, qu'aucun texte de la convention ne fixe."""
    for lig, v in TABLES[table_id]["valeurs"].items():
        for k in range(2, 17):
            prevu = (v[0] * D("1.02") ** (k - 1)).quantize(MILLIME, rounding=ROUND_HALF_UP)
            anomalie = ANOMALIES.get((table_id, lig, k))
            if anomalie:
                assert (str(v[k - 1]), str(prevu)) == anomalie, (table_id, lig, k)
            else:
                assert abs(v[k - 1] - prevu) <= MILLIME, (table_id, lig, k)


@pytest.mark.parametrize("d0, d1", list(zip(DATES, DATES[1:])))
def test_controle_de_lecture_entre_dates(d0, d1):
    """Contrôle de lecture : cellule ≈ même cellule de la date précédente × 1,0675 arrondi, à ±0,001 près (288 paires,
    anomalies comprises). Régularité observée, qu'aucun texte de la convention ne fixe."""
    n = 0
    for p in POPS:
        a, b = TABLES[tid(p, d0)]["valeurs"], TABLES[tid(p, d1)]["valeurs"]
        for lig in a:
            for x, y in zip(a[lig], b[lig]):
                assert abs(y - (x * D("1.0675")).quantize(MILLIME, rounding=ROUND_HALF_UP)) <= MILLIME, (p, d1, lig)
                n += 1
    assert n == 288


# --- alias de catégories : « 1 » → « I » ; « III+II » reste une clé unique (décision 3 de D23) ----------------------

def test_alias_declares():
    assert GRID["alias_categories"]["techniciens"] == {"1": "I"}
    for pop, lignes in LIGNES.items():
        if pop != "techniciens":
            romains = ["I", "II", "III", "IV", "V", "VI"]
            assert GRID["alias_categories"][pop] == {str(i + 1): romains[i] for i in range(len(lignes))}


def test_techniciens_alias_1_donne_i(ok):
    r = ok(salaire_base(APH, "techniciens", "1", 5, "2024-06-01"))
    assert (r.detail["categorie"], r.detail["categorie_demandee"], r.montant) == ("I", "1", D("1126.405"))
    assert r.montant == TABLES[tid("TECHNICIENS", "2024-01-01")]["valeurs"]["I"][2]


@pytest.mark.parametrize("cat", ["II", "III"])
def test_techniciens_ii_et_iii_refuses(cat):
    with pytest.raises(Refus) as e:
        salaire_base(APH, "techniciens", cat, 5, "2024-06-01")
    assert e.value.code == Refus.PARAM_INVALIDE
    assert e.value.message_fr == f"Catégorie inconnue : '{cat}' pour techniciens (attendu : I, III+II ; alias : 1)."
    assert e.value.message_ar == f"صنف غير معروف: '{cat}' لفئة techniciens."


def test_techniciens_ligne_iii_ii(ok):
    r = ok(salaire_base(APH, "techniciens", "III+II", 15, "2023-06-01"))     # degré 8 (14-16 ans)
    assert r.montant == TABLES[tid("TECHNICIENS", "2023-01-01")]["valeurs"]["III+II"][7] and "categorie_demandee" not in r.detail


# --- calcul de bout en bout ---------------------------------------------------------------------------------------

@pytest.mark.parametrize("pop, cat, annees, date, attendu, page, table_id", [
    ("sport", "2", 5, "2022-06-01", "988.460", 21, tid("SPORT", "2021-12-01")),                  # degré 3 (4-6 ans)
    ("education_specialisee", "I", 31, "2022-12-31", "1096.010", 21, tid("EDUCATION_SPECIALISEE", "2021-12-01")),
    ("formateurs_professionnels", "III", 23, "2023-06-01", "1225.010", 26,                        # anomalie servie
     tid("FORMATEURS_PROFESSIONNELS", "2023-01-01")),
    ("ouvriers_administratifs_surveillants", "4", D("30.5"), "2025-01-01", "905.500", 28,
     tid("OUVRIERS_ADMINISTRATIFS_SURVEILLANTS", "2024-01-01")),
])
def test_bout_en_bout(pop, cat, annees, date, attendu, page, table_id, ok):
    r = ok(salaire_base(APH, pop, cat, annees, date))
    assert r.montant == D(attendu) and r.unite == "TND/mois" and r.detail["table_id"] == table_id
    c = r.citations[0]
    assert (c.page, c.data_file, c.decision_ref) == (page, DATA_FILE, "D23")
    assert c.source_file == GRID["_meta"]["source_file"]


def test_secteur_charge_par_le_registre():
    assert loaders.GRILLES[APH] == DATA_FILE and APH in loaders.secteurs_disponibles()
