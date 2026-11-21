"""Champs optionnels d'une grille sectorielle : cellules_source_manquante (case illisible), anciennetes_refusees
(intervalle refusé au milieu de la grille) et cases_refusees (case exclue de l'écart cumulé).
Données FICTIVES (montants inventés) : chaque champ présent, absent, valeur refusée, borne exacte.
Lancer depuis la racine du dépôt : pytest src/track_b_accounting/tests/test_champs_optionnels_grille.py
"""

import copy
from decimal import Decimal

import pytest

from track_b_accounting.calc import Refus, salaire_base
from track_b_accounting.calc import loaders

S = "SECTEUR_FICTIF_CHAMPS"
POP, AUTRE = "mensuels", "horaires"
LABELS = ["0-1", "1-2", "2-4", "4-6", "6+"]
ECART = {
    "regle": "ecart_cumule_biennal",
    "periode_annees": 2,
    "dernier_degre_atteint_a_annees": 6,
    "source_pdf_page": 7,
    "source_article": "14",
    "texte_source_ar": "نص المصدر",
    "decision_ref": "D99",
    "hypotheses_fr": ["Hypothèse FR"],
    "hypotheses_ar": ["فرضية"],
    "message_borne_fr": "Borne {a}",
    "message_borne_ar": "حد {a}",
}
CASE_MANQUANTE = {
    "categorie": "2",
    "degre": 3,
    "source_pdf_page": 21,
    "source_article": "grille",
    "raison": "chiffre abîmé",
    "message_fr": "Case illisible p.21",
    "message_ar": "خانة غير مقروءة",
}
INTERVALLE = {
    "au_dela_de": 4,
    "jusqu_a_inclus": 5,
    "source_pdf_page": 14,
    "source_article": "53",
    "message_fr": "Ancienneté {a} refusée (art. 53)",
    "message_ar": "أقدمية {a} مرفوضة",
}
CASE_ECART = {
    "table_id": "F_M_2021",
    "categorie": "2",
    "source_pdf_page": 21,
    "source_article": "14",
    "message_fr": "Écart refusé à {a} ans",
    "message_ar": "الفارق مرفوض {a}",
}


def _valeurs(cles, base):
    return {c: [Decimal(base + 100 * i + 10 * k) for k in range(len(LABELS))] for i, c in enumerate(cles)}


def grille(manquantes=None, intervalles=None, cases=None, valeur_nulle=True):
    t1 = {
        "table_id": "F_M_2021",
        "population": POP,
        "effective_date": "2021-01-01",
        "source_pdf_page": 21,
        "unite": "TND/mois",
        "valeurs": _valeurs(["1", "2"], 500),
    }
    t2 = {
        "table_id": "F_M_2023",
        "population": POP,
        "effective_date": "2023-01-01",
        "source_pdf_page": 22,
        "unite": "TND/mois",
        "valeurs": _valeurs(["1", "2"], 600),
    }
    t3 = {
        "table_id": "F_H_2021",
        "population": AUTRE,
        "effective_date": "2021-01-01",
        "source_pdf_page": 21,
        "unite": "TND/heure",
        "valeurs": _valeurs(["1", "2"], 3),
    }
    if manquantes is not None:
        t1["cellules_source_manquante"] = copy.deepcopy(manquantes)
        if valeur_nulle:
            for c in manquantes:
                if c["categorie"] in t1["valeurs"] and 1 <= c["degre"] <= len(LABELS):
                    t1["valeurs"][c["categorie"]][c["degre"] - 1] = None
    au_dela = copy.deepcopy(ECART)
    if cases is not None:
        au_dela["cases_refusees"] = copy.deepcopy(cases)
    g = {
        "_meta": {"source_file": "data/raw/pdf/fictif.pdf", "secteur_code": S, "decision_ref": "D99"},
        "degres": {p: [{"degre": k, "anciennete_label": lab} for k, lab in enumerate(LABELS, 1)] for p in (POP, AUTRE)},
        "au_dela_dernier_degre": {POP: au_dela, AUTRE: copy.deepcopy(ECART)},
        "categories": {POP: ["1", "2"], AUTRE: ["1", "2"]},
        "grilles": [t1, t2, t3],
    }
    if intervalles is not None:
        g["anciennetes_refusees"] = copy.deepcopy(intervalles)
    return g


def charger(g):
    return loaders.valider_grille(g, "fictif.json")


@pytest.fixture
def installer(monkeypatch):
    def _installer(g):
        g = charger(g)
        monkeypatch.setattr("track_b_accounting.calc.salary.charger_grille", lambda s: g)
        monkeypatch.setitem(loaders.GRILLES, S, "data/processed/salary_grids/fictif.json")
        return g

    return _installer


def refus(code, *a):
    with pytest.raises(Refus) as e:
        salaire_base(*a)
    assert e.value.code == code
    return e.value


def invalide(g):
    with pytest.raises(Refus) as e:
        charger(g)
    assert e.value.code == Refus.SOURCE_MANQUANTE and "absent ou invalide" in e.value.message_fr


# --- A. cellules_source_manquante -----------------------------------------------------------------------


def test_case_manquante_refusee_avec_le_message_du_json(installer):
    installer(grille(manquantes=[CASE_MANQUANTE]))
    e = refus(Refus.SOURCE_MANQUANTE, S, POP, "2", 3, "2021-06-01")
    assert (e.message_fr, e.message_ar) == ("Case illisible p.21", "خانة غير مقروءة")


def test_case_manquante_n_affecte_ni_les_voisines_ni_les_autres_tables(installer):
    installer(grille(manquantes=[CASE_MANQUANTE]))
    assert salaire_base(S, POP, "2", 1.5, "2021-06-01").montant == Decimal("610.000")
    assert salaire_base(S, POP, "1", 3, "2021-06-01").montant == Decimal("520.000")
    assert salaire_base(S, POP, "2", 3, "2023-06-01").montant == Decimal("720.000")


def test_case_manquante_borne_exacte_reste_param_invalide(installer):
    installer(grille(manquantes=[CASE_MANQUANTE]))
    refus(Refus.PARAM_INVALIDE, S, POP, "2", 2, "2021-06-01")  # 2 ans : borne commune aux degrés 2 et 3


def test_case_manquante_dans_l_ecart_cumule_refusee(installer):
    case = dict(CASE_MANQUANTE, degre=4)  # avant-dernier degré, utilisé par l'écart
    installer(grille(manquantes=[case]))
    assert salaire_base(S, POP, "2", 7, "2021-06-01").montant == Decimal("640.000")  # n = 0 : écart non utilisé
    e = refus(Refus.SOURCE_MANQUANTE, S, POP, "2", 9, "2021-06-01")
    assert e.message_fr == "Case illisible p.21"


def test_champ_absent_aucun_effet_et_null_non_declare_refuse(installer):
    installer(grille())
    assert salaire_base(S, POP, "2", 3, "2021-06-01").montant == Decimal("620.000")
    g = grille(manquantes=[CASE_MANQUANTE])
    del g["grilles"][0]["cellules_source_manquante"]
    invalide(g)


@pytest.mark.parametrize(
    "mutation",
    [
        {"categorie": "9"},
        {"degre": 0},
        {"degre": 6},
        {"degre": True},
        {"raison": ""},
        {"source_pdf_page": 0},
        {"message_ar": ""},
    ],
)
def test_case_manquante_invalide(mutation):
    invalide(grille(manquantes=[dict(CASE_MANQUANTE, **mutation)]))


def test_case_declaree_mais_imprimee_refusee_et_doublon_refuse():
    invalide(grille(manquantes=[CASE_MANQUANTE], valeur_nulle=False))
    invalide(grille(manquantes=[CASE_MANQUANTE, CASE_MANQUANTE]))


# --- B. anciennetes_refusees ----------------------------------------------------------------------------


@pytest.mark.parametrize("a", [4.01, 4.5, 5])
def test_intervalle_refuse(installer, a):
    installer(grille(intervalles={POP: [INTERVALLE]}))
    e = refus(Refus.SOURCE_MANQUANTE, S, POP, "1", a, "2021-06-01")
    assert e.message_fr == f"Ancienneté {a} refusée (art. 53)" and e.message_ar == f"أقدمية {a} مرفوضة"


def test_intervalle_bornes(installer):
    installer(grille(intervalles={POP: [INTERVALLE]}))
    refus(Refus.PARAM_INVALIDE, S, POP, "1", 4, "2021-06-01")  # 4 ans pile : borne imprimée (D6)
    assert salaire_base(S, POP, "1", 3.5, "2021-06-01").detail["degre"] == 3
    assert salaire_base(S, POP, "1", 5.01, "2021-06-01").detail["degre"] == 4
    assert salaire_base(S, AUTRE, "1", 4.5, "2021-06-01").detail["degre"] == 4  # autre population : non concernée


def test_intervalle_absent_aucun_effet(installer):
    installer(grille())
    assert salaire_base(S, POP, "1", 4.5, "2021-06-01").montant == Decimal("530.000")


@pytest.mark.parametrize(
    "intervalles",
    [
        {POP: [dict(INTERVALLE, au_dela_de=5)]},
        {POP: [dict(INTERVALLE, jusqu_a_inclus=4.5)]},
        {POP: [dict(INTERVALLE, au_dela_de=-1)]},
        {POP: [dict(INTERVALLE, message_fr="sans ancienneté")]},
        {POP: [dict(INTERVALLE, source_article="")]},
        {POP: []},
        {"inconnue": [INTERVALLE]},
    ],
)
def test_intervalle_invalide(intervalles):
    invalide(grille(intervalles=intervalles))


# --- C. cases_refusees de l'écart cumulé ----------------------------------------------------------------


def test_case_refusee_au_dela_du_dernier_degre(installer):
    installer(grille(cases=[CASE_ECART]))
    e = refus(Refus.SOURCE_MANQUANTE, S, POP, "2", 9, "2021-06-01")
    assert (e.message_fr, e.message_ar) == ("Écart refusé à 9 ans", "الفارق مرفوض 9")


def test_case_refusee_dernier_degre_servi_tel_quel_et_borne_exacte(installer):
    installer(grille(cases=[CASE_ECART]))
    assert salaire_base(S, POP, "2", 7, "2021-06-01").montant == Decimal("640.000")  # n = 0
    refus(Refus.PARAM_INVALIDE, S, POP, "2", 8, "2021-06-01")  # 8 ans pile : palier de l'écart


def test_case_refusee_seulement_pour_sa_table_et_sa_categorie(installer):
    installer(grille(cases=[CASE_ECART]))
    assert salaire_base(S, POP, "1", 9, "2021-06-01").montant == Decimal("550.000")  # 540 + 1 × 10
    assert salaire_base(S, POP, "2", 9, "2023-06-01").montant == Decimal("750.000")  # autre table
    assert salaire_base(S, AUTRE, "2", 9, "2021-06-01").montant == Decimal("153.000")  # autre population


def test_case_refusee_absente_ecart_applique(installer):
    installer(grille())
    assert salaire_base(S, POP, "2", 9, "2021-06-01").montant == Decimal("650.000")


@pytest.mark.parametrize(
    "cases",
    [
        [dict(CASE_ECART, table_id="F_H_2021")],
        [dict(CASE_ECART, table_id="X")],
        [dict(CASE_ECART, categorie="9")],
        [dict(CASE_ECART, message_ar="")],
        [],
    ],
)
def test_case_refusee_invalide(cases):
    invalide(grille(cases=cases))


def test_case_refusee_hors_ecart_cumule_invalide():
    g = grille()
    g["au_dela_dernier_degre"][POP] = {
        "regle": "ouvert",
        "source_pdf_page": 7,
        "source_article": "14",
        "texte_source_ar": "نص",
        "cases_refusees": [CASE_ECART],
    }
    invalide(g)
