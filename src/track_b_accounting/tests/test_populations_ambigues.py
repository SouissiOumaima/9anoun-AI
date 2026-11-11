"""Populations aux catégories identiques, alias de catégories, degrés « 0-2 … 30-32 » et hypothèses de grille.
Données FICTIVES (montants inventés), sauf les sections qui lisent le fichier du secteur
ASSOCIATIONS_PERSONNES_HANDICAPEES (activé, D23).
Lancer depuis la racine du dépôt : pytest src/track_b_accounting/tests/test_populations_ambigues.py
"""

import copy
import io
import json
from pathlib import Path
from decimal import ROUND_HALF_UP, Decimal

import pytest
from conftest import lire_json

from track_b_accounting.calc import Refus, prime, salaire_base
from track_b_accounting.calc import loaders

S = "SECTEUR_FICTIF_APH"
SQUELETTE_FILE = "data/processed/salary_grids/associations_personnes_handicapees.json"
SQUELETTE = lire_json(SQUELETTE_FILE)
DEGRES = [{"degre": k, "anciennete_label": "0-2 ans" if k == 1 else f"{2 * k - 2}-{2 * k}"} for k in range(1, 17)]
HYP = {"fr": ["Hypothèse degrés FR", "Hypothèse unité FR"], "ar": ["فرضية الدرجات", "فرضية الوحدة"]}
AU_DELA = {
    "regle": "refus",
    "anciennete_max_couverte_annees": 32,
    "source_pdf_page": 7,
    "source_article": "12",
    "message_fr": "Plafond FR {a}",
    "message_ar": "سقف {a}",
}


def _ligne(base):
    """16 montants fictifs croissants."""
    return [Decimal(base + 10 * k) for k in range(16)]


def _table(tid, pop, cles, date, base, page=21, explicite=True):
    t = {
        "table_id": tid,
        "effective_date": date,
        "source_pdf_page": page,
        "unite": "TND/mois",
        "valeurs": {c: _ligne(base + 1000 * i) for i, c in enumerate(cles)},
    }
    if explicite:
        t["population"] = pop
    return t


def grille_fictive():
    """Deux populations avec les mêmes catégories {I, II, III}, une population « I, III+II »."""
    pops = {"alpha": ["I", "II", "III"], "beta": ["I", "II", "III"], "gamma": ["I", "III+II"]}
    g = {
        "_meta": {
            "source_file": "data/raw/pdf/fictif.pdf",
            "secteur_code": S,
            "decision_ref": "D99",
            "tables_transcrites": True,
        },
        "degres": {p: copy.deepcopy(DEGRES) for p in pops},
        "au_dela_dernier_degre": {p: copy.deepcopy(AU_DELA) for p in pops},
        "categories": pops,
        "alias_categories": {"alpha": {"1": "I", "2": "II", "3": "III"}, "gamma": {"1": "I"}},
        "hypotheses_grille": {p: copy.deepcopy(HYP) for p in pops},
        "grilles": [
            _table("A_2021", "alpha", pops["alpha"], "2021-12-01", 100),
            _table("B_2021", "beta", pops["beta"], "2021-12-01", 500),
            _table("G_2021", "gamma", pops["gamma"], "2021-12-01", 900),
            _table("A_2023", "alpha", pops["alpha"], "2023-01-01", 200),
        ],
        "primes": [
            {
                "code": "prime_transport",
                "source_article": "42 1",
                "source_pdf_page": 14,
                "unite": "TND/mois",
                "montants": [
                    {
                        "effective_date": "2021-12-01",
                        "au_titre_de": 2022,
                        "execution_et_maitrise": Decimal("1.000"),
                        "cadres": Decimal("2.000"),
                    }
                ],
            }
        ],
        "primes_non_couvertes": {
            "prime_production": {
                "source_pdf_page": 14,
                "source_article": "42 8",
                "message_fr": "Formule FR",
                "message_ar": "صيغة",
            }
        },
    }
    return loaders.valider_grille(g, "fictif.json")


@pytest.fixture
def fictif(monkeypatch):
    g = grille_fictive()
    for mod in ("salary", "primes"):
        monkeypatch.setattr(f"track_b_accounting.calc.{mod}.charger_grille", lambda s: g)
    monkeypatch.setitem(loaders.GRILLES, S, "data/processed/salary_grids/fictif.json")
    return g


def refus(code, f, *a, **k):
    with pytest.raises(Refus) as e:
        f(*a, **k)
    assert e.value.code == code and e.value.message_fr and e.value.message_ar
    return e.value


# --- population explicite des tables ---------------------------------------------------------------------


def test_tables_choisies_par_population_explicite(fictif):
    a = salaire_base(S, "alpha", "II", 5, "2022-06-01")
    b = salaire_base(S, "beta", "II", 5, "2022-06-01")
    assert (a.detail["table_id"], b.detail["table_id"]) == ("A_2021", "B_2021")
    assert a.montant == Decimal(100 + 1000 + 10 * 2) and b.montant == Decimal(500 + 1000 + 10 * 2)  # degré 3
    assert salaire_base(S, "alpha", "II", 5, "2024-01-01").detail["table_id"] == "A_2023"


def test_categories_ambigues_sans_population_refusees():
    g = grille_fictive()
    g["grilles"][0].pop("population")
    refus(Refus.SOURCE_MANQUANTE, loaders.valider_grille, g, "x.json")


@pytest.mark.parametrize(
    "mutation",
    [
        lambda g: g["grilles"][0].__setitem__("population", "inconnue"),
        lambda g: g["grilles"][0].__setitem__("population", "gamma"),  # catégories différentes
        lambda g: g["grilles"][2].__setitem__("population", 3),
    ],
)
def test_population_explicite_incoherente_refusee(mutation):
    g = grille_fictive()
    mutation(g)
    refus(Refus.SOURCE_MANQUANTE, loaders.valider_grille, g, "x.json")


def test_population_non_ambigue_sans_champ_acceptee():
    g = grille_fictive()
    g["grilles"][2].pop("population")  # gamma : catégories uniques
    assert loaders.population_de_table(loaders.valider_grille(g, "x.json"), g["grilles"][2]) == "gamma"


# --- alias de catégories -------------------------------------------------------------------------------------


@pytest.mark.parametrize("cat", ["2", 2])
def test_alias_arabe_vers_romain(fictif, cat):
    r = salaire_base(S, "alpha", cat, 5, "2022-06-01")
    assert r.detail["categorie"] == "II" and r.detail["categorie_demandee"] == "2"
    assert r.montant == salaire_base(S, "alpha", "II", 5, "2022-06-01").montant


def test_cle_romaine_sans_categorie_demandee(fictif):
    assert "categorie_demandee" not in salaire_base(S, "alpha", "II", 5, "2022-06-01").detail


def test_ligne_combinee_iii_ii(fictif):
    r = salaire_base(S, "gamma", "III+II", 5, "2022-06-01")
    assert r.detail["categorie"] == "III+II" and r.montant == Decimal(900 + 1000 + 20)


@pytest.mark.parametrize("cat", ["II", "III", "2", "3", "IV", "9"])
def test_categories_non_declarees_refusees(fictif, cat):
    e = refus(Refus.PARAM_INVALIDE, salaire_base, S, "gamma", cat, 5, "2022-06-01")
    assert "(attendu : I, III+II ; alias : 1)" in e.message_fr


def test_beta_sans_alias(fictif):
    e = refus(Refus.PARAM_INVALIDE, salaire_base, S, "beta", "1", 5, "2022-06-01")
    assert e.message_fr.endswith("(attendu : I, II, III).")


@pytest.mark.parametrize(
    "mutation",
    [
        lambda g: g["alias_categories"]["alpha"].__setitem__("II", "I"),  # alias = une vraie catégorie
        lambda g: g["alias_categories"]["alpha"].__setitem__("4", "IV"),  # cible inconnue
        lambda g: g["alias_categories"]["alpha"].__setitem__(" ", "I"),
        lambda g: g["alias_categories"].__setitem__("delta", {"1": "I"}),  # population inconnue
    ],
)
def test_alias_invalides_refuses(mutation):
    g = grille_fictive()
    mutation(g)
    refus(Refus.SOURCE_MANQUANTE, loaders.valider_grille, g, "x.json")


# --- degrés 0-2 … 30-32 et refus au-delà de 32 ans ------------------------------------------------------


@pytest.mark.parametrize(
    "annees,degre", [(0, 1), (Decimal("1.99"), 1), (3, 2), (Decimal("29.5"), 15), (Decimal("31.99"), 16)]
)
def test_degres(fictif, annees, degre):
    assert salaire_base(S, "alpha", "I", annees, "2022-06-01").detail["degre"] == degre


@pytest.mark.parametrize("borne", [2, 4, 16, 30])
def test_bornes_exactes_refusees(fictif, borne):
    refus(Refus.PARAM_INVALIDE, salaire_base, S, "alpha", "I", borne, "2022-06-01")


@pytest.mark.parametrize("annees", [32, Decimal("32.000"), 40])
def test_au_dela_de_32_ans(fictif, annees):
    e = refus(Refus.SOURCE_MANQUANTE, salaire_base, S, "alpha", "I", annees, "2022-06-01")
    assert e.message_fr == f"Plafond FR {Decimal(str(annees))}"


# --- hypothèses de grille dans detail ------------------------------------------------------------------------


def test_hypotheses_de_grille_dans_detail(fictif):
    r = salaire_base(S, "beta", "III", 5, "2022-06-01")
    assert r.detail["hypotheses"] == HYP["fr"] and r.detail["hypotheses_ar"] == HYP["ar"]
    assert "regle_art13" not in r.detail


@pytest.mark.parametrize(
    "mutation",
    [
        lambda g: g["hypotheses_grille"]["alpha"].__setitem__("ar", ["une seule"]),
        lambda g: g["hypotheses_grille"]["alpha"].__setitem__("fr", []),
        lambda g: g["hypotheses_grille"].__setitem__("delta", copy.deepcopy(HYP)),
    ],
)
def test_hypotheses_invalides_refusees(mutation):
    g = grille_fictive()
    mutation(g)
    refus(Refus.SOURCE_MANQUANTE, loaders.valider_grille, g, "x.json")


def test_metallurgie_sans_hypotheses_de_grille():
    assert "hypotheses" not in salaire_base("METALLURGIE_BATIMENT", "admin_tech", "4", 15, "2022-06-01").detail


# --- primes : groupes choisis par l'appelant, primes non couvertes ------------------------------------------------


def test_prime_transport_groupe_et_au_titre_de(fictif):
    r = prime(S, "prime_transport", "2022-06-01", groupe="cadres")
    assert r.montant == Decimal("2.000") and r.detail["au_titre_de"] == 2022


def test_prime_non_couverte(fictif):
    e = refus(Refus.SOURCE_MANQUANTE, prime, S, "prime_production", "2022-06-01")
    assert (e.message_fr, e.message_ar) == ("Formule FR", "صيغة")


# --- fichier du secteur : activé (D23), chargé par le registre --------------------------------------------


def test_secteur_valide_et_charge():
    loaders.valider_grille(copy.deepcopy(SQUELETTE), SQUELETTE_FILE)
    assert SQUELETTE["_meta"]["secteur_code"] == "ASSOCIATIONS_PERSONNES_HANDICAPEES"
    assert SQUELETTE["_meta"]["decision_ref"] == "D23" and SQUELETTE["_meta"]["tables_transcrites"] is True
    assert loaders.GRILLES["ASSOCIATIONS_PERSONNES_HANDICAPEES"] == SQUELETTE_FILE
    assert "ASSOCIATIONS_PERSONNES_HANDICAPEES" in loaders.secteurs_disponibles()


@pytest.mark.parametrize("ref", [None, "", "23", "D", "D23a", 23])
def test_sans_decision_ref_valide_fichier_ignore(tmp_path, monkeypatch, ref):
    """Sans _meta.decision_ref valide, le fichier est ignoré par le registre et le secteur répond SOURCE_MANQUANTE."""
    g = json.loads(Path(loaders.REPO_ROOT / SQUELETTE_FILE).read_text(encoding="utf-8"))
    if ref is None:
        del g["_meta"]["decision_ref"]
    else:
        g["_meta"]["decision_ref"] = ref
    (tmp_path / "associations_personnes_handicapees.json").write_text(
        json.dumps(g, ensure_ascii=False), encoding="utf-8"
    )
    assert loaders.decouvrir_grilles(tmp_path) == {}
    sauvegarde = dict(loaders.GRILLES)  # registre entier, ordre compris : restauré tel quel après le test
    del loaders.GRILLES["ASSOCIATIONS_PERSONNES_HANDICAPEES"]
    try:
        e = refus(
            Refus.SOURCE_MANQUANTE, salaire_base, "ASSOCIATIONS_PERSONNES_HANDICAPEES", "sport", "I", 5, "2022-06-01"
        )
        assert e.message_fr.startswith("Aucune grille vérifiée pour le secteur 'ASSOCIATIONS_PERSONNES_HANDICAPEES'")
        refus(Refus.SOURCE_MANQUANTE, prime, "ASSOCIATIONS_PERSONNES_HANDICAPEES", "prime_presence", "2022-06-01")
    finally:
        loaders.GRILLES.clear()
        loaders.GRILLES.update(sauvegarde)


# Tables dont les valeurs ont été transcrites (double lecture) et vérifiées par DS5 : lots B1 à B3 (2021, p.21 à 23),
# B4 à B6 (2023, p.24 à 26), B7 à B9 (2024, p.27 à 29). Les 15 tables sont transcrites.
TABLES_B1 = {"APH_EDUCATION_SPECIALISEE_2021-12-01", "APH_SPORT_2021-12-01"}
TABLES_B2 = {"APH_OUVRIERS_ADMINISTRATIFS_SURVEILLANTS_2021-12-01", "APH_TECHNICIENS_2021-12-01"}
TABLES_B3 = {"APH_FORMATEURS_PROFESSIONNELS_2021-12-01"}
TABLES_B4 = {"APH_EDUCATION_SPECIALISEE_2023-01-01", "APH_SPORT_2023-01-01"}
TABLES_B5 = {"APH_OUVRIERS_ADMINISTRATIFS_SURVEILLANTS_2023-01-01", "APH_TECHNICIENS_2023-01-01"}
TABLES_B6 = {"APH_FORMATEURS_PROFESSIONNELS_2023-01-01"}
TABLES_B7 = {"APH_EDUCATION_SPECIALISEE_2024-01-01", "APH_SPORT_2024-01-01"}
TABLES_B8 = {"APH_OUVRIERS_ADMINISTRATIFS_SURVEILLANTS_2024-01-01", "APH_TECHNICIENS_2024-01-01"}
TABLES_B9 = {"APH_FORMATEURS_PROFESSIONNELS_2024-01-01"}
TABLES_VALIDEES = (
    TABLES_B1 | TABLES_B2 | TABLES_B3 | TABLES_B4 | TABLES_B5 | TABLES_B6 | TABLES_B7 | TABLES_B8 | TABLES_B9
)
# Tables prévues (catégories imprimées, numéro, page), sans valeurs depuis l'activation (D23).
PREVUES = {t["table_id"]: t for t in SQUELETTE["tables_prevues"]}
# Primes datées de l'article 42 (جديد) (p.14) transcrites (double lecture) : seules autorisées à porter des montants.
PRIMES_VALIDEES = {"prime_transport", "prime_presence", "prime_specifique_handicap"}


def test_valeurs_seulement_dans_grilles_et_primes():
    assert {t["table_id"] for t in SQUELETTE["grilles"]} == TABLES_VALIDEES
    assert all(
        set(t)
        <= {"table_id", "population", "effective_date", "source_pdf_page", "unite", "valeurs", "anomalies_increment"}
        for t in SQUELETTE["grilles"]
    )
    assert all("valeurs" not in t and "anomalies_increment" not in t for t in SQUELETTE["tables_prevues"])
    assert "primes_prevues" not in SQUELETTE
    assert {p["code"] for p in SQUELETTE["primes"] if "montants" in p} == PRIMES_VALIDEES
    for bloc in SQUELETTE["primes_non_couvertes"].values():
        assert not any(c.isdigit() for c in bloc["message_fr"].split("page")[1].split(")")[1])  # aucun montant cité


def test_squelette_structure():
    pops = SQUELETTE["categories"]
    assert pops == {
        "education_specialisee": ["I", "II", "III"],
        "sport": ["I", "II", "III"],
        "ouvriers_administratifs_surveillants": ["I", "II", "III", "IV", "V", "VI"],
        "techniciens": ["I", "III+II"],
        "formateurs_professionnels": ["I", "II", "III", "IV"],
    }
    assert SQUELETTE["alias_categories"]["techniciens"] == {"1": "I"}  # 2 et 3 : non confirmés (annexe 4)
    assert all(len(d) == 16 and d[-1]["anciennete_label"] == "30-32" for d in SQUELETTE["degres"].values())
    assert len(SQUELETTE["tables_prevues"]) == 15
    assert {t["population"] for t in SQUELETTE["tables_prevues"]} == set(pops)
    assert sum(16 * len(t["categories"]) for t in SQUELETTE["tables_prevues"]) == 864


# --- hypothèses par ligne (hypotheses_categories) : lues dans le JSON -------------------------------------------

HYP_LIGNE = {"fr": ["Ligne combinée FR"], "ar": ["سطر مشترك"]}


@pytest.fixture
def fictif_lignes(monkeypatch):
    g = grille_fictive()
    g["hypotheses_categories"] = {"gamma": {"III+II": copy.deepcopy(HYP_LIGNE)}}
    g = loaders.valider_grille(g, "fictif.json")
    monkeypatch.setattr("track_b_accounting.calc.salary.charger_grille", lambda s: g)
    monkeypatch.setitem(loaders.GRILLES, S, "data/processed/salary_grids/fictif.json")
    return g


def test_hypothese_de_ligne_ajoutee_pour_sa_cle(fictif_lignes):
    r = salaire_base(S, "gamma", "III+II", 5, "2022-06-01")
    assert r.detail["hypotheses"] == HYP["fr"] + HYP_LIGNE["fr"]
    assert r.detail["hypotheses_ar"] == HYP["ar"] + HYP_LIGNE["ar"]


def test_hypothese_de_ligne_absente_pour_les_autres_cles(fictif_lignes):
    assert salaire_base(S, "gamma", "I", 5, "2022-06-01").detail["hypotheses"] == HYP["fr"]
    assert salaire_base(S, "alpha", "II", 5, "2022-06-01").detail["hypotheses"] == HYP["fr"]


def test_textes_d_hypotheses_lus_dans_le_json(fictif_lignes):
    fictif_lignes["hypotheses_categories"]["gamma"]["III+II"]["fr"] = ["TEXTE-MODIFIE"]
    fictif_lignes["hypotheses_grille"]["gamma"]["fr"] = ["GRILLE-MODIFIEE"]
    assert salaire_base(S, "gamma", "III+II", 5, "2022-06-01").detail["hypotheses"] == [
        "GRILLE-MODIFIEE",
        "TEXTE-MODIFIE",
    ]


@pytest.mark.parametrize(
    "mutation",
    [
        lambda g: g.__setitem__("hypotheses_categories", {"delta": {"I": copy.deepcopy(HYP_LIGNE)}}),
        lambda g: g.__setitem__("hypotheses_categories", {"gamma": {"II": copy.deepcopy(HYP_LIGNE)}}),
        lambda g: g.__setitem__("hypotheses_categories", {"gamma": {"III+II": {"fr": ["a"], "ar": []}}}),
    ],
)
def test_hypotheses_de_ligne_invalides_refusees(mutation):
    g = grille_fictive()
    mutation(g)
    refus(Refus.SOURCE_MANQUANTE, loaders.valider_grille, g, "x.json")


def test_squelette_correspondance_ligne_categorie():
    h = SQUELETTE["hypotheses_grille"]
    for pop in ("education_specialisee", "sport", "techniciens", "formateurs_professionnels"):
        assert "d'après l'ordre des lignes" in h[pop]["fr"][-1] and "n'est pas écrite explicitement" in h[pop]["fr"][-1]
        assert "ترتيب الأسطر" in h[pop]["ar"][-1]
    p3 = h["ouvriers_administratifs_surveillants"]
    assert "article 42-9 (page 15)" in p3["fr"][-1] and "déduite de l'ordre des lignes" in p3["fr"][-1]
    assert "الفصل 42-9" in p3["ar"][-1]
    ligne = SQUELETTE["hypotheses_categories"]["techniciens"]["III+II"]
    assert "d'après le seul libellé de la grille" in ligne["fr"][0] and "تسمية الجدول فقط" in ligne["ar"][0]
    assert list(SQUELETTE["hypotheses_categories"]) == ["techniciens"]
    assert all(len(x["fr"]) == len(x["ar"]) == 3 for x in h.values())  # degrés, unité, correspondance


# --- lot B1 (p.21, tables 1 et 2 de 2021) : contrôles de lecture --------------------------------------------------

LOT_B1 = {t["table_id"]: t for t in SQUELETTE["grilles"] if t["table_id"] in TABLES_B1}


@pytest.mark.parametrize("tid", sorted(TABLES_B1))
def test_b1_seize_valeurs_croissantes(tid):
    t = LOT_B1[tid]
    assert t["source_pdf_page"] == 21 and t["effective_date"] == "2021-12-01"
    assert list(t["valeurs"]) == PREVUES[tid]["categories"] == ["I", "II", "III"]
    for lig, v in t["valeurs"].items():
        assert len(v) == 16 and all(isinstance(x, Decimal) and x.as_tuple().exponent == -3 for x in v), (tid, lig)
        assert all(a < b for a, b in zip(v, v[1:])), (tid, lig)


@pytest.mark.parametrize("tid", sorted(TABLES_B1))
def test_b1_regularite_deux_pour_cent_controle_de_lecture(tid):
    """Régularité OBSERVÉE dans les grilles (aucun texte de la convention ne la fixe) : chaque degré est à ±0,001 de
    arrondi_millime(degré 1 × 1,02^(k−1)). Contrôle de lecture seulement : jamais utilisé pour calculer un montant.
    Ne contrôle pas le degré 1."""
    for lig, v in LOT_B1[tid]["valeurs"].items():
        for k in range(2, 17):
            prevu = (v[0] * Decimal("1.02") ** (k - 1)).quantize(Decimal("0.001"), rounding=ROUND_HALF_UP)
            assert abs(v[k - 1] - prevu) <= Decimal("0.001"), (tid, lig, k)


def test_b1_lignes_ii_iii_identiques_entre_tables_1_et_2():
    t1, t2 = LOT_B1["APH_EDUCATION_SPECIALISEE_2021-12-01"], LOT_B1["APH_SPORT_2021-12-01"]
    assert t1["valeurs"]["II"] == t2["valeurs"]["II"] and t1["valeurs"]["III"] == t2["valeurs"]["III"]
    assert t1["valeurs"]["I"] != t2["valeurs"]["I"]


def test_b1_cellules_de_base_verifiees():
    """Degré 1 de chaque ligne (base non contrôlée par la régularité) : valeurs vérifiées sur le PDF par DS5."""
    base = {tid: {lig: str(v[0]) for lig, v in LOT_B1[tid]["valeurs"].items()} for tid in LOT_B1}
    assert base == {
        "APH_EDUCATION_SPECIALISEE_2021-12-01": {"I": "814.351", "II": "950.077", "III": "1085.802"},
        "APH_SPORT_2021-12-01": {"I": "529.328", "II": "950.077", "III": "1085.802"},
    }


def test_b1_secteur_charge():
    assert loaders.decouvrir_grilles().keys() == {
        "METALLURGIE_BATIMENT",
        "BATIMENT_TRAVAUX_PUBLICS",
        "ASSOCIATIONS_PERSONNES_HANDICAPEES",
        "ASSURANCE",
        "ENSEIGNEMENT_PRIVE",
        "BANQUES",
        "GARDIENNAGE_SECURITE_TRANSPORT_FONDS",
        "TORREFACTION_CAFE",
        "AGENCES_VOYAGES",
        "HOTELS_TOURISTIQUES",
        "CONFISERIE_BISCUITERIE_CHOCOLATERIE",
        "PATES_ALIMENTAIRES_COUSCOUS",
        "COSMETIQUES_PARFUMS",
        "SAVONNERIE_RAFFINAGE_GRIGNONS",
        "COMMERCE_DISTRIBUTION_PETROLE",
        "PLASTURGIE",
        "MINOTERIES",
        "TEINTURERIES_PRESSINGS",
        "BOISSONS_GAZEUSES",
    }


# --- lot B2 (p.22, tables 3 et 4 de 2021) : contrôles de lecture --------------------------------------------------

LOT_B2 = {t["table_id"]: t for t in SQUELETTE["grilles"] if t["table_id"] in TABLES_B2}
LIGNES_B2 = {
    "APH_OUVRIERS_ADMINISTRATIFS_SURVEILLANTS_2021-12-01": ["I", "II", "III", "IV", "V", "VI"],
    "APH_TECHNICIENS_2021-12-01": ["I", "III+II"],
}


@pytest.mark.parametrize("tid", sorted(TABLES_B2))
def test_b2_seize_valeurs_croissantes(tid):
    t = LOT_B2[tid]
    assert t["source_pdf_page"] == 22 and t["effective_date"] == "2021-12-01"
    assert list(t["valeurs"]) == PREVUES[tid]["categories"] == LIGNES_B2[tid]
    for lig, v in t["valeurs"].items():
        assert len(v) == 16 and all(isinstance(x, Decimal) and x.as_tuple().exponent == -3 for x in v), (tid, lig)
        assert all(a < b for a, b in zip(v, v[1:])), (tid, lig)


@pytest.mark.parametrize("tid", sorted(TABLES_B2))
def test_b2_regularite_deux_pour_cent_controle_de_lecture(tid):
    """Régularité OBSERVÉE dans les grilles (aucun texte de la convention ne la fixe) : chaque degré est à ±0,001 de
    arrondi_millime(degré 1 × 1,02^(k−1)). Contrôle de lecture seulement : jamais utilisé pour calculer un montant.
    Ne contrôle pas le degré 1."""
    for lig, v in LOT_B2[tid]["valeurs"].items():
        for k in range(2, 17):
            prevu = (v[0] * Decimal("1.02") ** (k - 1)).quantize(Decimal("0.001"), rounding=ROUND_HALF_UP)
            assert abs(v[k - 1] - prevu) <= Decimal("0.001"), (tid, lig, k)


def test_b2_cellules_de_base_verifiees():
    """Degré 1 de chaque ligne (base non contrôlée par la régularité) : valeurs vérifiées sur le PDF par DS5."""
    base = {tid: {lig: str(v[0]) for lig, v in LOT_B2[tid]["valeurs"].items()} for tid in LOT_B2}
    assert base == {
        "APH_OUVRIERS_ADMINISTRATIFS_SURVEILLANTS_2021-12-01": {
            "I": "407.176",
            "II": "529.328",
            "III": "556.473",
            "IV": "590.405",
            "V": "678.626",
            "VI": "950.077",
        },
        "APH_TECHNICIENS_2021-12-01": {"I": "950.077", "III+II": "1072.229"},
    }


def test_identites_entre_tables_2021_controle_de_lecture():
    """Lignes identiques d'une table à l'autre, chacune lue séparément sur sa page : contrôle de lecture seulement
    (aucune valeur n'est recopiée d'une table à l'autre)."""
    v = {tid: t["valeurs"] for tid, t in {**LOT_B1, **LOT_B2, **LOT_B3}.items()}
    t1, t2 = v["APH_EDUCATION_SPECIALISEE_2021-12-01"], v["APH_SPORT_2021-12-01"]
    t3, t4 = v["APH_OUVRIERS_ADMINISTRATIFS_SURVEILLANTS_2021-12-01"], v["APH_TECHNICIENS_2021-12-01"]
    t5 = v["APH_FORMATEURS_PROFESSIONNELS_2021-12-01"]
    assert t3["II"] == t2["I"]
    assert t3["VI"] == t4["I"] == t1["II"] == t2["II"]
    assert t5["I"] == t2["I"] == t3["II"]


# --- lot B3 (p.23, table 5 de 2021) : contrôles de lecture -------------------------------------------------------

LOT_B3 = {t["table_id"]: t for t in SQUELETTE["grilles"] if t["table_id"] in TABLES_B3}


@pytest.mark.parametrize("tid", sorted(TABLES_B3))
def test_b3_seize_valeurs_croissantes(tid):
    t = LOT_B3[tid]
    assert t["source_pdf_page"] == 23 and t["effective_date"] == "2021-12-01"
    assert list(t["valeurs"]) == PREVUES[tid]["categories"] == ["I", "II", "III", "IV"]
    for lig, v in t["valeurs"].items():
        assert len(v) == 16 and all(isinstance(x, Decimal) and x.as_tuple().exponent == -3 for x in v), (tid, lig)
        assert all(a < b for a, b in zip(v, v[1:])), (tid, lig)


@pytest.mark.parametrize("tid", sorted(TABLES_B3))
def test_b3_regularite_deux_pour_cent_controle_de_lecture(tid):
    """Régularité OBSERVÉE dans les grilles (aucun texte de la convention ne la fixe) : chaque degré est à ±0,001 de
    arrondi_millime(degré 1 × 1,02^(k−1)). Contrôle de lecture seulement : jamais utilisé pour calculer un montant.
    Ne contrôle pas le degré 1."""
    for lig, v in LOT_B3[tid]["valeurs"].items():
        for k in range(2, 17):
            prevu = (v[0] * Decimal("1.02") ** (k - 1)).quantize(Decimal("0.001"), rounding=ROUND_HALF_UP)
            assert abs(v[k - 1] - prevu) <= Decimal("0.001"), (tid, lig, k)


def test_b3_cellules_de_base_verifiees():
    """Degré 1 de chaque ligne (base non contrôlée par la régularité) : valeurs vérifiées sur le PDF par DS5."""
    base = {tid: {lig: str(v[0]) for lig, v in LOT_B3[tid]["valeurs"].items()} for tid in LOT_B3}
    assert base == {
        "APH_FORMATEURS_PROFESSIONNELS_2021-12-01": {
            "I": "529.328",
            "II": "787.206",
            "III": "922.931",
            "IV": "1058.657",
        }
    }


# --- lot B4 (p.24, tables 6 et 7 de 2023) : contrôles de lecture -------------------------------------------------

LOT_B4 = {t["table_id"]: t for t in SQUELETTE["grilles"] if t["table_id"] in TABLES_B4}


@pytest.mark.parametrize("tid", sorted(TABLES_B4))
def test_b4_seize_valeurs_croissantes(tid):
    t = LOT_B4[tid]
    assert t["source_pdf_page"] == 24 and t["effective_date"] == "2023-01-01"
    assert list(t["valeurs"]) == PREVUES[tid]["categories"] == ["I", "II", "III"]
    for lig, v in t["valeurs"].items():
        assert len(v) == 16 and all(isinstance(x, Decimal) and x.as_tuple().exponent == -3 for x in v), (tid, lig)
        assert all(a < b for a, b in zip(v, v[1:])), (tid, lig)


@pytest.mark.parametrize("tid", sorted(TABLES_B4))
def test_b4_regularite_deux_pour_cent_controle_de_lecture(tid):
    """Régularité OBSERVÉE dans les grilles (aucun texte de la convention ne la fixe) : chaque degré est à ±0,001 de
    arrondi_millime(degré 1 × 1,02^(k−1)). Contrôle de lecture seulement : jamais utilisé pour calculer un montant.
    Ne contrôle pas le degré 1."""
    for lig, v in LOT_B4[tid]["valeurs"].items():
        for k in range(2, 17):
            prevu = (v[0] * Decimal("1.02") ** (k - 1)).quantize(Decimal("0.001"), rounding=ROUND_HALF_UP)
            assert abs(v[k - 1] - prevu) <= Decimal("0.001"), (tid, lig, k)


def test_b4_cellules_de_base_verifiees():
    """Degré 1 de chaque ligne (base non contrôlée par la régularité) : valeurs vérifiées sur le PDF par DS5."""
    base = {tid: {lig: str(v[0]) for lig, v in LOT_B4[tid]["valeurs"].items()} for tid in LOT_B4}
    assert base == {
        "APH_EDUCATION_SPECIALISEE_2023-01-01": {"I": "869.320", "II": "1014.207", "III": "1159.093"},
        "APH_SPORT_2023-01-01": {"I": "565.058", "II": "1014.207", "III": "1159.093"},
    }


def test_identites_entre_tables_2023_controle_de_lecture():
    """Lignes identiques d'une table à l'autre, chacune lue séparément sur sa page : contrôle de lecture seulement
    (aucune valeur n'est recopiée d'une table à l'autre)."""
    t6 = LOT_B4["APH_EDUCATION_SPECIALISEE_2023-01-01"]["valeurs"]
    t7 = LOT_B4["APH_SPORT_2023-01-01"]["valeurs"]
    t8 = LOT_B5["APH_OUVRIERS_ADMINISTRATIFS_SURVEILLANTS_2023-01-01"]["valeurs"]
    t9 = LOT_B5["APH_TECHNICIENS_2023-01-01"]["valeurs"]
    t10 = {t["table_id"]: t for t in SQUELETTE["grilles"]}["APH_FORMATEURS_PROFESSIONNELS_2023-01-01"]["valeurs"]
    assert t6["II"] == t7["II"] and t6["III"] == t7["III"]
    assert t6["I"] != t7["I"]
    assert t8["II"] == t7["I"]
    assert t8["VI"] == t9["I"] == t6["II"] == t7["II"]
    assert t10["I"] == t7["I"] == t8["II"]


# --- lot B5 (p.25, tables 8 et 9 de 2023) : contrôles de lecture -------------------------------------------------

LOT_B5 = {t["table_id"]: t for t in SQUELETTE["grilles"] if t["table_id"] in TABLES_B5}
LIGNES_B5 = {
    "APH_OUVRIERS_ADMINISTRATIFS_SURVEILLANTS_2023-01-01": ["I", "II", "III", "IV", "V", "VI"],
    "APH_TECHNICIENS_2023-01-01": ["I", "III+II"],
}


@pytest.mark.parametrize("tid", sorted(TABLES_B5))
def test_b5_seize_valeurs_croissantes(tid):
    t = LOT_B5[tid]
    assert t["source_pdf_page"] == 25 and t["effective_date"] == "2023-01-01"
    assert list(t["valeurs"]) == PREVUES[tid]["categories"] == LIGNES_B5[tid]
    for lig, v in t["valeurs"].items():
        assert len(v) == 16 and all(isinstance(x, Decimal) and x.as_tuple().exponent == -3 for x in v), (tid, lig)
        assert all(a < b for a, b in zip(v, v[1:])), (tid, lig)


@pytest.mark.parametrize("tid", sorted(TABLES_B5))
def test_b5_regularite_deux_pour_cent_controle_de_lecture(tid):
    """Régularité OBSERVÉE dans les grilles (aucun texte de la convention ne la fixe) : chaque degré est à ±0,001 de
    arrondi_millime(degré 1 × 1,02^(k−1)). Contrôle de lecture seulement : jamais utilisé pour calculer un montant.
    Ne contrôle pas le degré 1."""
    for lig, v in LOT_B5[tid]["valeurs"].items():
        for k in range(2, 17):
            prevu = (v[0] * Decimal("1.02") ** (k - 1)).quantize(Decimal("0.001"), rounding=ROUND_HALF_UP)
            assert abs(v[k - 1] - prevu) <= Decimal("0.001"), (tid, lig, k)


def test_b5_cellules_de_base_verifiees():
    """Degré 1 de chaque ligne (base non contrôlée par la régularité) : valeurs vérifiées sur le PDF par DS5."""
    base = {tid: {lig: str(v[0]) for lig, v in LOT_B5[tid]["valeurs"].items()} for tid in LOT_B5}
    assert base == {
        "APH_OUVRIERS_ADMINISTRATIFS_SURVEILLANTS_2023-01-01": {
            "I": "434.660",
            "II": "565.058",
            "III": "594.035",
            "IV": "630.257",
            "V": "724.433",
            "VI": "1014.207",
        },
        "APH_TECHNICIENS_2023-01-01": {"I": "1014.207", "III+II": "1144.605"},
    }


# --- lot B6 (p.26, table 10 de 2023) : contrôles de lecture -------------------------------------------------------

LOT_B6 = {t["table_id"]: t for t in SQUELETTE["grilles"] if t["table_id"] in TABLES_B6}

# Cellules imprimées qui s'écartent de la régularité observée : valeur imprimée conservée, aucune correction ;
# la régularité est une simple observation, pas une règle de la convention.
# (table, ligne, degré) : (valeur imprimée, valeur attendue par la régularité, écart)
EXCEPTIONS_REGULARITE = {
    ("APH_FORMATEURS_PROFESSIONNELS_2023-01-01", "III", 12): (
        Decimal("1225.010"),
        Decimal("1225.008"),
        Decimal("0.002"),
    ),
    ("APH_SPORT_2024-01-01", "I", 6): (Decimal("665.982"), Decimal("665.980"), Decimal("0.002")),
    ("APH_SPORT_2024-01-01", "I", 16): (Decimal("811.828"), Decimal("811.826"), Decimal("0.002")),
    ("APH_FORMATEURS_PROFESSIONNELS_2024-01-01", "I", 6): (Decimal("665.982"), Decimal("665.980"), Decimal("0.002")),
    ("APH_FORMATEURS_PROFESSIONNELS_2024-01-01", "I", 16): (Decimal("811.828"), Decimal("811.826"), Decimal("0.002")),
    ("APH_FORMATEURS_PROFESSIONNELS_2024-01-01", "III", 14): (
        Decimal("1360.529"),
        Decimal("1360.527"),
        Decimal("0.002"),
    ),
    ("APH_OUVRIERS_ADMINISTRATIFS_SURVEILLANTS_2024-01-01", "I", 4): (
        Decimal("492.399"),
        Decimal("492.401"),
        Decimal("-0.002"),
    ),
    ("APH_OUVRIERS_ADMINISTRATIFS_SURVEILLANTS_2024-01-01", "II", 6): (
        Decimal("665.982"),
        Decimal("665.980"),
        Decimal("0.002"),
    ),
    ("APH_OUVRIERS_ADMINISTRATIFS_SURVEILLANTS_2024-01-01", "II", 16): (
        Decimal("811.828"),
        Decimal("811.826"),
        Decimal("0.002"),
    ),
}
# Tables portant des anomalies imprimées consignées (anomalies_increment), comme au BTP.
TABLES_AVEC_ANOMALIES = {
    "APH_FORMATEURS_PROFESSIONNELS_2023-01-01",
    "APH_SPORT_2024-01-01",
    "APH_FORMATEURS_PROFESSIONNELS_2024-01-01",
    "APH_OUVRIERS_ADMINISTRATIFS_SURVEILLANTS_2024-01-01",
}


@pytest.mark.parametrize("tid", sorted(TABLES_B6))
def test_b6_seize_valeurs_croissantes(tid):
    t = LOT_B6[tid]
    assert t["source_pdf_page"] == 26 and t["effective_date"] == "2023-01-01"
    assert list(t["valeurs"]) == PREVUES[tid]["categories"] == ["I", "II", "III", "IV"]
    for lig, v in t["valeurs"].items():
        assert len(v) == 16 and all(isinstance(x, Decimal) and x.as_tuple().exponent == -3 for x in v), (tid, lig)
        assert all(a < b for a, b in zip(v, v[1:])), (tid, lig)


@pytest.mark.parametrize("tid", sorted(TABLES_B6))
def test_b6_regularite_deux_pour_cent_controle_de_lecture(tid):
    """Régularité OBSERVÉE dans les grilles (aucun texte de la convention ne la fixe) : chaque degré est à ±0,001 de
    arrondi_millime(degré 1 × 1,02^(k−1)). Contrôle de lecture seulement : jamais utilisé pour calculer un montant.
    Ne contrôle pas le degré 1. Les cellules de EXCEPTIONS_REGULARITE doivent garder exactement leur valeur imprimée
    et leur écart documenté ; toute autre cellule hors tolérance fait échouer le test."""
    for lig, v in LOT_B6[tid]["valeurs"].items():
        for k in range(2, 17):
            prevu = (v[0] * Decimal("1.02") ** (k - 1)).quantize(Decimal("0.001"), rounding=ROUND_HALF_UP)
            exc = EXCEPTIONS_REGULARITE.get((tid, lig, k))
            if exc is not None:
                imprimee, attendue, ecart = exc
                assert (v[k - 1], prevu, v[k - 1] - prevu) == (imprimee, attendue, ecart), (tid, lig, k)
            else:
                assert abs(v[k - 1] - prevu) <= Decimal("0.001"), (tid, lig, k)


def test_b6_anomalie_consignee_comme_au_btp():
    """L'anomalie est consignée dans le JSON (anomalies_increment, comme au BTP), valeur imprimée conservée."""
    t = LOT_B6["APH_FORMATEURS_PROFESSIONNELS_2023-01-01"]
    (a,) = t["anomalies_increment"]
    assert (a["categorie"], a["degre"], a["valeur_imprimee"]) == ("III", 12, Decimal("1225.010"))
    assert t["valeurs"]["III"][11] == a["valeur_imprimee"] and "aucune correction" in a["note"]
    assert all(
        "anomalies_increment" not in x for x in SQUELETTE["grilles"] if x["table_id"] not in TABLES_AVEC_ANOMALIES
    )


def test_b6_cellules_de_base_verifiees():
    """Degré 1 de chaque ligne (base non contrôlée par la régularité) : valeurs vérifiées sur le PDF par DS5."""
    base = {tid: {lig: str(v[0]) for lig, v in LOT_B6[tid]["valeurs"].items()} for tid in LOT_B6}
    assert base == {
        "APH_FORMATEURS_PROFESSIONNELS_2023-01-01": {
            "I": "565.058",
            "II": "840.343",
            "III": "985.229",
            "IV": "1130.116",
        }
    }


# --- lot B7 (p.27, tables 11 et 12 de 2024) : contrôles de lecture -------------------------------------------------

LOT_B7 = {t["table_id"]: t for t in SQUELETTE["grilles"] if t["table_id"] in TABLES_B7}


@pytest.mark.parametrize("tid", sorted(TABLES_B7))
def test_b7_seize_valeurs_croissantes(tid):
    t = LOT_B7[tid]
    assert t["source_pdf_page"] == 27 and t["effective_date"] == "2024-01-01"
    assert list(t["valeurs"]) == PREVUES[tid]["categories"] == ["I", "II", "III"]
    for lig, v in t["valeurs"].items():
        assert len(v) == 16 and all(isinstance(x, Decimal) and x.as_tuple().exponent == -3 for x in v), (tid, lig)
        assert all(a < b for a, b in zip(v, v[1:])), (tid, lig)


@pytest.mark.parametrize("tid", sorted(TABLES_B7))
def test_b7_regularite_deux_pour_cent_controle_de_lecture(tid):
    """Régularité OBSERVÉE dans les grilles (aucun texte de la convention ne la fixe) : chaque degré est à ±0,001 de
    arrondi_millime(degré 1 × 1,02^(k−1)). Contrôle de lecture seulement : jamais utilisé pour calculer un montant.
    Ne contrôle pas le degré 1. Les cellules de EXCEPTIONS_REGULARITE doivent garder exactement leur valeur imprimée
    et leur écart documenté ; toute autre cellule hors tolérance fait échouer le test."""
    for lig, v in LOT_B7[tid]["valeurs"].items():
        for k in range(2, 17):
            prevu = (v[0] * Decimal("1.02") ** (k - 1)).quantize(Decimal("0.001"), rounding=ROUND_HALF_UP)
            exc = EXCEPTIONS_REGULARITE.get((tid, lig, k))
            if exc is not None:
                imprimee, attendue, ecart = exc
                assert (v[k - 1], prevu, v[k - 1] - prevu) == (imprimee, attendue, ecart), (tid, lig, k)
            else:
                assert abs(v[k - 1] - prevu) <= Decimal("0.001"), (tid, lig, k)


def test_b7_anomalies_consignees_comme_au_btp():
    """Les deux anomalies sont consignées dans le JSON (anomalies_increment, comme au BTP), valeurs imprimées conservées."""
    t = LOT_B7["APH_SPORT_2024-01-01"]
    assert [(a["categorie"], a["degre"], a["valeur_imprimee"]) for a in t["anomalies_increment"]] == [
        ("I", 6, Decimal("665.982")),
        ("I", 16, Decimal("811.828")),
    ]
    for a in t["anomalies_increment"]:
        assert t["valeurs"]["I"][a["degre"] - 1] == a["valeur_imprimee"] and "aucune correction" in a["note"]
    assert "anomalies_increment" not in LOT_B7["APH_EDUCATION_SPECIALISEE_2024-01-01"]


def test_b7_cellules_de_base_verifiees():
    """Degré 1 de chaque ligne (base non contrôlée par la régularité) : valeurs vérifiées sur le PDF par DS5."""
    base = {tid: {lig: str(v[0]) for lig, v in LOT_B7[tid]["valeurs"].items()} for tid in LOT_B7}
    assert base == {
        "APH_EDUCATION_SPECIALISEE_2024-01-01": {"I": "927.999", "II": "1082.666", "III": "1237.332"},
        "APH_SPORT_2024-01-01": {"I": "603.199", "II": "1082.666", "III": "1237.332"},
    }


def test_identites_entre_tables_2024_controle_de_lecture():
    """Lignes identiques d'une table à l'autre, chacune lue séparément sur sa page : contrôle de lecture seulement
    (aucune valeur n'est recopiée d'une table à l'autre)."""
    t11 = LOT_B7["APH_EDUCATION_SPECIALISEE_2024-01-01"]["valeurs"]
    t12 = LOT_B7["APH_SPORT_2024-01-01"]["valeurs"]
    assert t11["II"] == t12["II"] and t11["III"] == t12["III"]
    assert t11["I"] != t12["I"]


# --- lot B9 (p.29, table 15 de 2024) : contrôles de lecture -------------------------------------------------------

LOT_B9 = {t["table_id"]: t for t in SQUELETTE["grilles"] if t["table_id"] in TABLES_B9}


@pytest.mark.parametrize("tid", sorted(TABLES_B9))
def test_b9_seize_valeurs_croissantes(tid):
    t = LOT_B9[tid]
    assert t["source_pdf_page"] == 29 and t["effective_date"] == "2024-01-01"
    assert list(t["valeurs"]) == PREVUES[tid]["categories"] == ["I", "II", "III", "IV"]
    for lig, v in t["valeurs"].items():
        assert len(v) == 16 and all(isinstance(x, Decimal) and x.as_tuple().exponent == -3 for x in v), (tid, lig)
        assert all(a < b for a, b in zip(v, v[1:])), (tid, lig)


@pytest.mark.parametrize("tid", sorted(TABLES_B9))
def test_b9_regularite_deux_pour_cent_controle_de_lecture(tid):
    """Régularité OBSERVÉE dans les grilles (aucun texte de la convention ne la fixe) : chaque degré est à ±0,001 de
    arrondi_millime(degré 1 × 1,02^(k−1)). Contrôle de lecture seulement : jamais utilisé pour calculer un montant.
    Ne contrôle pas le degré 1. Les cellules de EXCEPTIONS_REGULARITE doivent garder exactement leur valeur imprimée
    et leur écart documenté ; toute autre cellule hors tolérance fait échouer le test."""
    for lig, v in LOT_B9[tid]["valeurs"].items():
        for k in range(2, 17):
            prevu = (v[0] * Decimal("1.02") ** (k - 1)).quantize(Decimal("0.001"), rounding=ROUND_HALF_UP)
            exc = EXCEPTIONS_REGULARITE.get((tid, lig, k))
            if exc is not None:
                imprimee, attendue, ecart = exc
                assert (v[k - 1], prevu, v[k - 1] - prevu) == (imprimee, attendue, ecart), (tid, lig, k)
            else:
                assert abs(v[k - 1] - prevu) <= Decimal("0.001"), (tid, lig, k)


def test_b9_anomalies_consignees_comme_au_btp():
    """Les trois anomalies sont consignées dans le JSON (anomalies_increment, comme au BTP), valeurs imprimées conservées."""
    t = LOT_B9["APH_FORMATEURS_PROFESSIONNELS_2024-01-01"]
    assert [(a["categorie"], a["degre"], a["valeur_imprimee"]) for a in t["anomalies_increment"]] == [
        ("I", 6, Decimal("665.982")),
        ("I", 16, Decimal("811.828")),
        ("III", 14, Decimal("1360.529")),
    ]
    for a in t["anomalies_increment"]:
        assert t["valeurs"][a["categorie"]][a["degre"] - 1] == a["valeur_imprimee"] and "aucune correction" in a["note"]


def test_identites_b9_controle_de_lecture():
    """Ligne I de la table 15 identique à la ligne I de la table 12, chacune lue séparément sur sa page : contrôle de
    lecture seulement (aucune valeur n'est recopiée d'une table à l'autre)."""
    t15 = LOT_B9["APH_FORMATEURS_PROFESSIONNELS_2024-01-01"]["valeurs"]
    assert t15["I"] == LOT_B7["APH_SPORT_2024-01-01"]["valeurs"]["I"]


def test_b9_cellules_de_base_verifiees():
    """Degré 1 de chaque ligne (base non contrôlée par la régularité) : valeurs vérifiées sur le PDF par DS5."""
    base = {tid: {lig: str(v[0]) for lig, v in LOT_B9[tid]["valeurs"].items()} for tid in LOT_B9}
    assert base == {
        "APH_FORMATEURS_PROFESSIONNELS_2024-01-01": {
            "I": "603.199",
            "II": "897.066",
            "III": "1051.732",
            "IV": "1206.399",
        }
    }


# --- lot B8 (p.28, tables 13 et 14 de 2024) : contrôles de lecture -------------------------------------------------

LOT_B8 = {t["table_id"]: t for t in SQUELETTE["grilles"] if t["table_id"] in TABLES_B8}
LIGNES_B8 = {
    "APH_OUVRIERS_ADMINISTRATIFS_SURVEILLANTS_2024-01-01": ["I", "II", "III", "IV", "V", "VI"],
    "APH_TECHNICIENS_2024-01-01": ["I", "III+II"],
}


@pytest.mark.parametrize("tid", sorted(TABLES_B8))
def test_b8_seize_valeurs_croissantes(tid):
    t = LOT_B8[tid]
    assert t["source_pdf_page"] == 28 and t["effective_date"] == "2024-01-01"
    assert list(t["valeurs"]) == PREVUES[tid]["categories"] == LIGNES_B8[tid]
    for lig, v in t["valeurs"].items():
        assert len(v) == 16 and all(isinstance(x, Decimal) and x.as_tuple().exponent == -3 for x in v), (tid, lig)
        assert all(a < b for a, b in zip(v, v[1:])), (tid, lig)


@pytest.mark.parametrize("tid", sorted(TABLES_B8))
def test_b8_regularite_deux_pour_cent_controle_de_lecture(tid):
    """Régularité OBSERVÉE dans les grilles (aucun texte de la convention ne la fixe) : chaque degré est à ±0,001 de
    arrondi_millime(degré 1 × 1,02^(k−1)). Contrôle de lecture seulement : jamais utilisé pour calculer un montant.
    Ne contrôle pas le degré 1. Les cellules de EXCEPTIONS_REGULARITE doivent garder exactement leur valeur imprimée
    et leur écart documenté ; toute autre cellule hors tolérance fait échouer le test."""
    for lig, v in LOT_B8[tid]["valeurs"].items():
        for k in range(2, 17):
            prevu = (v[0] * Decimal("1.02") ** (k - 1)).quantize(Decimal("0.001"), rounding=ROUND_HALF_UP)
            exc = EXCEPTIONS_REGULARITE.get((tid, lig, k))
            if exc is not None:
                imprimee, attendue, ecart = exc
                assert (v[k - 1], prevu, v[k - 1] - prevu) == (imprimee, attendue, ecart), (tid, lig, k)
            else:
                assert abs(v[k - 1] - prevu) <= Decimal("0.001"), (tid, lig, k)


def test_b8_anomalies_consignees_comme_au_btp():
    """Les trois anomalies sont consignées dans le JSON (anomalies_increment, comme au BTP), valeurs imprimées conservées."""
    t = LOT_B8["APH_OUVRIERS_ADMINISTRATIFS_SURVEILLANTS_2024-01-01"]
    assert [(a["categorie"], a["degre"], a["valeur_imprimee"]) for a in t["anomalies_increment"]] == [
        ("I", 4, Decimal("492.399")),
        ("II", 6, Decimal("665.982")),
        ("II", 16, Decimal("811.828")),
    ]
    for a in t["anomalies_increment"]:
        assert t["valeurs"][a["categorie"]][a["degre"] - 1] == a["valeur_imprimee"] and "aucune correction" in a["note"]
    assert "anomalies_increment" not in LOT_B8["APH_TECHNICIENS_2024-01-01"]


def test_b8_cellules_de_base_verifiees():
    """Degré 1 de chaque ligne (base non contrôlée par la régularité) : valeurs vérifiées sur le PDF par DS5."""
    base = {tid: {lig: str(v[0]) for lig, v in LOT_B8[tid]["valeurs"].items()} for tid in LOT_B8}
    assert base == {
        "APH_OUVRIERS_ADMINISTRATIFS_SURVEILLANTS_2024-01-01": {
            "I": "464.000",
            "II": "603.199",
            "III": "634.133",
            "IV": "672.799",
            "V": "773.333",
            "VI": "1082.666",
        },
        "APH_TECHNICIENS_2024-01-01": {"I": "1082.666", "III+II": "1221.866"},
    }


def test_identites_b8_controle_de_lecture():
    """Lignes identiques d'une table à l'autre (2024), chacune lue séparément sur sa page : contrôle de lecture
    seulement (aucune valeur n'est recopiée d'une table à l'autre)."""
    t11 = LOT_B7["APH_EDUCATION_SPECIALISEE_2024-01-01"]["valeurs"]
    t12 = LOT_B7["APH_SPORT_2024-01-01"]["valeurs"]
    t13 = LOT_B8["APH_OUVRIERS_ADMINISTRATIFS_SURVEILLANTS_2024-01-01"]["valeurs"]
    t14 = LOT_B8["APH_TECHNICIENS_2024-01-01"]["valeurs"]
    t15 = LOT_B9["APH_FORMATEURS_PROFESSIONNELS_2024-01-01"]["valeurs"]
    assert t13["VI"] == t14["I"] == t11["II"] == t12["II"]
    assert t13["II"] == t12["I"] == t15["I"]


# --- primes datées de l'article 42 (جديد) (p.14) : valeurs transcrites, fichier toujours non chargé ----------------

PRIMES = {p["code"]: p for p in SQUELETTE["primes"]}
DATES_PRIMES = [("2021-12-01", 2022), ("2023-01-01", 2023), ("2024-01-01", 2024)]


def test_primes_montants_transcrits():
    """Les 12 montants lus sur la page 14 (double lecture), avec date « بداية من » et année « بعنوان سنة »."""
    lu = {
        code: [
            (
                ligne["effective_date"],
                ligne["au_titre_de"],
                {k: str(v) for k, v in ligne.items() if k not in ("effective_date", "au_titre_de")},
            )
            for ligne in p["montants"]
        ]
        for code, p in PRIMES.items()
    }
    assert lu == {
        "prime_transport": [
            (d, a, m)
            for (d, a), m in zip(
                DATES_PRIMES,
                (
                    {"execution_et_gestion": "30.199", "cadres": "36.239"},
                    {"execution_et_gestion": "32.238", "cadres": "38.685"},
                    {"execution_et_gestion": "34.414", "cadres": "41.296"},
                ),
            )
        ],
        "prime_presence": [(d, a, {"montant": m}) for (d, a), m in zip(DATES_PRIMES, ("6.281", "6.705", "7.158"))],
        "prime_specifique_handicap": [
            (d, a, {"montant": m}) for (d, a), m in zip(DATES_PRIMES, ("54.358", "58.027", "61.944"))
        ],
    }
    assert all(
        isinstance(v, Decimal)
        for p in PRIMES.values()
        for ligne in p["montants"]
        for k, v in ligne.items()
        if k not in ("effective_date", "au_titre_de")
    )


def test_primes_meme_structure_que_la_metallurgie():
    """Clés lues par calc/primes.py : montants datés, colonnes de groupe, au_titre_de ; pas de condition d'octroi."""
    for p in PRIMES.values():
        assert {"code", "label_ar", "source_article", "source_pdf_page", "unite", "montants"} <= set(p)
        assert p["source_pdf_page"] == 14 and p["unite"] == "TND/mois" and "condition" not in p
    assert (
        PRIMES["prime_presence"]["toutes_categories"]
        is PRIMES["prime_specifique_handicap"]["toutes_categories"]
        is True
    )


def test_primes_groupes_du_transport_fideles_au_texte():
    """« أعوان التنفيذ والتسيير » = agents d'exécution et de gestion ; « الإطارات » = cadres (art. 42 (جديد) 1, p.14)."""
    p = PRIMES["prime_transport"]
    assert all(
        set(ligne) == {"effective_date", "execution_et_gestion", "cadres", "au_titre_de"} for ligne in p["montants"]
    )
    assert p["libelles_groupes"] == {
        "execution_et_gestion": {"fr": "agents d'exécution et de gestion", "ar": "أعوان التنفيذ والتسيير"},
        "cadres": {"fr": "cadres", "ar": "الإطارات"},
    }
    assert "maîtrise" not in json.dumps(p, ensure_ascii=False, default=str)


def test_primes_toutes_categories_hypotheses_sans_ouvriers():
    for code, alinea in (("prime_presence", "2"), ("prime_specifique_handicap", "3")):
        h = PRIMES[code]["hypotheses"]
        assert len(h["fr"]) == len(h["ar"]) == 1
        assert "لكل الأصناف" in h["fr"][0] and f"42 (جديد) {alinea}" in h["fr"][0] and "لكل الأصناف" in h["ar"][0]
        assert "ouvrier" not in json.dumps(PRIMES[code], ensure_ascii=False, default=str).lower()


def test_primes_regle_date_effet_et_mention_des_decrets():
    regle = SQUELETTE["regle_date_effet_primes"]
    assert "بداية من" in regle["fr"] and "au_titre_de" in regle["fr"] and "au_titre_de" in regle["ar"]
    p = PRIMES["prime_transport"]
    assert "503" in p["note"] and "691" in p["note"] and "sans calcul" in p["note"]
    assert "503" in p["note_ar"] and "691" in p["note_ar"]


def test_primes_non_couvertes_motif_et_texte():
    nc = SQUELETTE["primes_non_couvertes"]
    assert {c: b["motif"] for c, b in nc.items()} == {
        "prime_frais_scolaires": "montant sans date d'effet dans la source",
        "prime_pedagogique": "montant sans date d'effet dans la source",
        "prime_sante": "montant sans date d'effet dans la source",
        "prime_fonctionnelle": "montant sans date d'effet dans la source",
        "prime_chauffeurs": "montant sans date d'effet dans la source",
        "prime_production": "formule, pas de montant",
    }
    assert all(b["texte_source_ar"].strip() for b in nc.values())
    assert set(nc).isdisjoint(PRIMES)


@pytest.fixture
def fictif_primes_aph(monkeypatch):
    """Grille fictive (salaires inventés) portant les primes réelles du secteur : test du rattachement aux dates."""
    g = grille_fictive()
    g["primes"] = copy.deepcopy(SQUELETTE["primes"])
    g["primes_non_couvertes"] = copy.deepcopy(SQUELETTE["primes_non_couvertes"])
    g = loaders.valider_grille(g, "fictif.json")
    for mod in ("salary", "primes"):
        monkeypatch.setattr(f"track_b_accounting.calc.{mod}.charger_grille", lambda s: g)
    monkeypatch.setitem(loaders.GRILLES, S, "data/processed/salary_grids/fictif.json")
    return g


@pytest.mark.parametrize(
    "jour, attendu, effet, titre",
    [
        ("2021-12-01", "36.239", "2021-12-01", 2022),
        ("2022-12-31", "36.239", "2021-12-01", 2022),
        ("2023-01-01", "38.685", "2023-01-01", 2023),
        ("2025-06-01", "41.296", "2024-01-01", 2024),
    ],
)
def test_primes_rattachement_date_bidaya_min(fictif_primes_aph, jour, attendu, effet, titre):
    r = prime(S, "prime_transport", jour, groupe="cadres")
    assert (str(r.montant), r.detail["effective_date"], r.detail["au_titre_de"]) == (attendu, effet, titre)


def test_primes_avant_premiere_date_refusees(fictif_primes_aph):
    refus(Refus.SOURCE_MANQUANTE, prime, S, "prime_presence", "2021-11-30")


def test_primes_non_couvertes_refusees_sans_montant(fictif_primes_aph):
    for code in SQUELETTE["primes_non_couvertes"]:
        e = refus(Refus.SOURCE_MANQUANTE, prime, S, code, "2024-06-01")
        assert e.message_fr == SQUELETTE["primes_non_couvertes"][code]["message_fr"]


@pytest.mark.parametrize(
    "population",
    [
        "education_specialisee",
        "sport",
        "ouvriers_administratifs_surveillants",
        "techniciens",
        "formateurs_professionnels",
    ],
)
@pytest.mark.parametrize(
    "code, montants",
    [("prime_presence", ("6.281", "6.705", "7.158")), ("prime_specifique_handicap", ("54.358", "58.027", "61.944"))],
)
def test_primes_toutes_categories_pour_les_5_populations(fictif_primes_aph, population, code, montants):
    """« لكل الأصناف » : la prime ne dépend pas de la population. primes.py ne prend aucun paramètre population ;
    le même montant est donc renvoyé pour un agent de chacune des 5 populations du secteur."""
    assert population in SQUELETTE["categories"]
    for (jour, _), attendu in zip(DATES_PRIMES, montants):
        assert str(prime(S, code, jour).montant) == attendu
    refus(Refus.PARAM_INVALIDE, prime, S, code, "2024-06-01", population=population)


def test_primes_transport_groupe_execution_et_gestion(fictif_primes_aph):
    r = prime(S, "prime_transport", "2024-06-01", groupe="execution_et_gestion")
    assert (str(r.montant), r.detail["groupe"]) == ("34.414", "execution_et_gestion")
    refus(Refus.PARAM_INVALIDE, prime, S, "prime_transport", "2024-06-01", groupe="execution_et_maitrise")


# --- textes affichés des primes (libellés de groupe, note_ar, hypothèses) : secteur réel, D23 ---------------------

APH = "ASSOCIATIONS_PERSONNES_HANDICAPEES"


@pytest.mark.parametrize("groupe", ["execution_et_gestion", "cadres"])
@pytest.mark.parametrize("jour", ["2022-06-01", "2023-06-01", "2024-06-01"])
def test_aph_transport_note_et_note_ar(jour, groupe):
    """Mention des décrets 503/1982 et 691/1986 reproduite sans calcul, FR et AR, pour une prime datée."""
    d = prime(APH, "prime_transport", jour, groupe=groupe).detail
    assert (d["note"], d["note_ar"]) == (PRIMES["prime_transport"]["note"], PRIMES["prime_transport"]["note_ar"])
    assert "503" in d["note_ar"] and "691" in d["note_ar"]


@pytest.mark.parametrize(
    "groupe, fr, ar",
    [
        ("execution_et_gestion", "agents d'exécution et de gestion", "أعوان التنفيذ والتسيير"),
        ("cadres", "cadres", "الإطارات"),
    ],
)
def test_aph_transport_groupe_libelle(groupe, fr, ar):
    d = prime(APH, "prime_transport", "2024-06-01", groupe=groupe).detail
    assert (d["groupe"], d["groupe_libelle"], d["groupe_libelle_ar"]) == (groupe, fr, ar)


@pytest.mark.parametrize("code", ["prime_presence", "prime_specifique_handicap"])
def test_aph_presence_et_specifique_hypotheses(code):
    d = prime(APH, code, "2024-06-01").detail
    assert (d["hypotheses"], d["hypotheses_ar"]) == (PRIMES[code]["hypotheses"]["fr"], PRIMES[code]["hypotheses"]["ar"])
    assert "لكل الأصناف" in d["hypotheses"][0] and "لكل الأصناف" in d["hypotheses_ar"][0]
    assert "ouvrier" not in json.dumps(d, ensure_ascii=False).lower()
    assert "note" not in d and "groupe_libelle" not in d


# Ensemble des clés de detail de chaque prime de la métallurgie, relevé avant la modification de calc/primes.py.
CLES_DETAIL_BM = {
    "prime_transport": {
        "secteur",
        "code",
        "label_fr",
        "label_ar",
        "date_calcul",
        "regles",
        "groupe",
        "effective_date",
        "au_titre_de",
    },
    "prime_presence": {"secteur", "code", "label_fr", "label_ar", "date_calcul", "regles", "effective_date"},
    "prime_logement": {
        "secteur",
        "code",
        "label_fr",
        "label_ar",
        "date_calcul",
        "regles",
        "variante",
        "effective_date",
    },
    "prime_panier_qefa": {
        "secteur",
        "code",
        "label_fr",
        "label_ar",
        "date_calcul",
        "regles",
        "effective_date",
        "note",
        "transport_assure",
    },
    "prime_deplacement_chantier": {
        "secteur",
        "code",
        "label_fr",
        "label_ar",
        "date_calcul",
        "regles",
        "condition",
        "effective_date",
    },
    "prime_travail_en_hauteur": {
        "secteur",
        "code",
        "label_fr",
        "label_ar",
        "date_calcul",
        "regles",
        "condition",
        "effective_date",
    },
}
PARAMS_BM = {
    "prime_transport": [{"groupe": "execution_et_maitrise"}, {"groupe": "cadres"}],
    "prime_logement": [{"variante": "base"}, {"variante": "complement_si_prime_superieure"}],
    "prime_panier_qefa": [{"transport_assure": True}, {"transport_assure": False}],
    "prime_deplacement_chantier": [{"condition_remplie": True}],
    "prime_travail_en_hauteur": [{"condition_remplie": True}],
}


@pytest.mark.parametrize("code", sorted(CLES_DETAIL_BM))
@pytest.mark.parametrize("jour", ["2021-12-01", "2022-06-01", "2023-01-01", "2024-06-01"])
def test_metallurgie_cles_de_detail_inchangees(code, jour):
    for params in PARAMS_BM.get(code, [{}]):
        d = prime("METALLURGIE_BATIMENT", code, jour, **params).detail
        assert set(d) == CLES_DETAIL_BM[code], (code, params)
        if code == "prime_panier_qefa":
            assert list(d).index("note") == list(d).index("effective_date") + 1  # ordre des clés conservé


@pytest.mark.parametrize(
    "mutation, message",
    [
        (lambda p: p.update(note_ar=" "), "note_ar non vide"),
        (lambda p: p.update(hypotheses={"fr": ["a", "b"], "ar": ["أ"]}), "hypotheses fr et ar"),
        (lambda p: p.update(hypotheses={"fr": [], "ar": []}), "hypotheses fr et ar"),
        (lambda p: p["libelles_groupes"].pop("cadres"), "libelles_groupes différents des colonnes"),
        (
            lambda p: p["libelles_groupes"].update(maitrise={"fr": "x", "ar": "س"}),
            "libelles_groupes différents des colonnes",
        ),
        (lambda p: p["libelles_groupes"]["cadres"].update(ar=""), "libelles_groupes fr et ar"),
    ],
)
def test_loaders_refuse_textes_de_prime_invalides(mutation, message):
    g = copy.deepcopy(SQUELETTE)
    mutation(next(x for x in g["primes"] if x["code"] == "prime_transport"))
    with pytest.raises(Refus) as e:
        loaders.valider_grille(g, SQUELETTE_FILE)
    assert e.value.code == Refus.SOURCE_MANQUANTE and message in e.value.message_fr


def test_demos_identiques_a_la_reference_a_l_octet():
    """Les 24 réponses de démo, telles qu'écrites par le CLI, identiques à la référence (avec D23, seule la liste des
    secteurs disponibles de demo-10 a changé parmi les 14 premières ; demo-15 à demo-18 portent sur le secteur ;
    avec D29, demo-10 gagne ASSURANCE et demo-19 à demo-24 portent sur l'assurance)."""
    from track_b_accounting.contract import cli

    sortie = io.StringIO()
    assert cli.main([str(loaders.REPO_ROOT / "data/mock_cards/track_b_requests_demo.json")], stdout=sortie) == 0
    reference = (Path(__file__).parent / "references" / "track_b_responses_demo.json").read_text(encoding="utf-8")
    assert sortie.getvalue() == reference
