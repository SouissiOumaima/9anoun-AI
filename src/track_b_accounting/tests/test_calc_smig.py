"""SMIG non agricole (décret n°769/2022, effet 2022-10-01) — D2, D3.
Lancer depuis la racine du dépôt : pytest src/track_b_accounting/tests/test_calc_smig.py
"""

import copy
from decimal import Decimal

import pytest
from conftest import lire_json

from track_b_accounting.calc import Refus, smig
from track_b_accounting.calc import loaders, smig_calc

SMIG = lire_json("data/processed/smig_smag/smig_smag.json")
BAREME = SMIG["smig_non_agricole"]["bareme"]


def refus(code, *a):
    with pytest.raises(Refus) as e:
        smig(*a)
    assert e.value.code == code and e.value.message_fr and e.value.message_ar
    return e.value


@pytest.mark.parametrize(
    "ligne", BAREME, ids=lambda ligne: f"{ligne['mode_remuneration']}-{ligne['regime_hebdomadaire_heures']}h"
)
def test_quatre_lignes_egales_au_json(ligne, ok):
    r = ok(smig(ligne["mode_remuneration"], ligne["regime_hebdomadaire_heures"], "2023-01-01"))
    assert r.montant == ligne["montant"]
    c = r.citations[0]
    assert c.page == SMIG["smig_non_agricole"]["source_pdf_page"] == 2  # page lue en D2
    assert c.decision_ref == "D2" and "769" in c.article


@pytest.mark.parametrize(
    "mode,regime,montant,unite",
    [
        ("mensuel", 48, "459.264", "TND/mois"),
        ("mensuel", 40, "390.692", "TND/mois"),
        ("horaire", 48, "2.208", "TND/heure"),
        ("horaire", 40, "2.254", "TND/heure"),
    ],
)
def test_valeurs_codees_en_dur_d2(mode, regime, montant, unite, ok):
    r = ok(smig(mode, regime, "2022-10-01"))
    assert r.montant == Decimal(montant) and r.unite == unite


def test_pages_sources_du_json():
    """Pages relevées dans la couche texte du PDF SMIG (D6) : SMIG p.2, SMAG p.3, prime de transport p.4."""
    assert [SMIG[k]["source_pdf_page"] for k in ("smig_non_agricole", "smag_agricole", "prime_transport")] == [2, 3, 4]


@pytest.mark.parametrize("valeur", ["absent", None, "2", True])
def test_page_source_absente_refusee(valeur, monkeypatch):
    d = copy.deepcopy(SMIG)
    if valeur == "absent":
        d["smig_non_agricole"].pop("source_pdf_page")
    else:
        d["smig_non_agricole"]["source_pdf_page"] = valeur
    monkeypatch.setattr(smig_calc, "charger_smig", lambda: d)
    e = refus(Refus.SOURCE_MANQUANTE, "mensuel", 48, "2023-01-01")
    assert "source_pdf_page" in e.message_fr


def test_regime_42h_refuse():
    e = refus(Refus.SOURCE_MANQUANTE, "mensuel", 42, "2023-01-01")
    assert "42" in e.message_fr and e.message_ar


def test_avant_decret_refuse():
    refus(Refus.SOURCE_MANQUANTE, "mensuel", 48, "2022-09-30")


@pytest.mark.parametrize("mode", ["journalier", "net", "", None])
def test_mode_inconnu(mode):
    refus(Refus.PARAM_INVALIDE, mode, 48, "2023-01-01")


@pytest.mark.parametrize("regime", ["48", 48.0, True, None])
def test_regime_invalide(regime):
    refus(Refus.PARAM_INVALIDE, "mensuel", regime, "2023-01-01")


def test_date_invalide():
    refus(Refus.PARAM_INVALIDE, "mensuel", 48, "1er octobre 2022")


@pytest.mark.parametrize(
    "mutation",
    [
        lambda d: d["_meta"].pop("source_file"),
        lambda d: d["smig_non_agricole"]["decree"].pop("effective_date"),
        lambda d: d["smig_non_agricole"].__setitem__("bareme", []),
        lambda d: d["smig_non_agricole"]["bareme"][0].pop("regime_hebdomadaire_heures"),
        lambda d: d["smig_non_agricole"]["bareme"][0].__setitem__("montant", 459.264),
        lambda d: d.pop("smig_non_agricole"),
    ],
)
def test_valider_smig_rejette(mutation):
    d = copy.deepcopy(SMIG)
    mutation(d)
    with pytest.raises(Refus) as e:
        loaders.valider_smig(d, "x.json")
    assert e.value.code == Refus.SOURCE_MANQUANTE


# --- référence de vérification (smig_non_agricole.decision_ref) --------------------------------------


def test_decision_ref_lue_dans_le_json(ok):
    r = ok(smig("mensuel", 48, "2023-01-01"))
    assert r.citations[0].decision_ref == SMIG["smig_non_agricole"]["decision_ref"] == "D2"
    assert SMIG["_meta"]["decision_log"] == "docs/DECISIONS.md (D1, D2)"  # champ libre conservé


def test_decision_ref_pas_en_dur(monkeypatch, ok):
    d = copy.deepcopy(SMIG)
    d["smig_non_agricole"]["decision_ref"] = "D99"
    monkeypatch.setattr(smig_calc, "charger_smig", lambda: d)
    assert ok(smig("mensuel", 48, "2023-01-01")).citations[0].decision_ref == "D99"


@pytest.mark.parametrize("valeur", ["absent", None, "", "2", "D1, D2", True])
def test_decision_ref_absente_refusee(valeur, monkeypatch):
    d = copy.deepcopy(SMIG)
    if valeur == "absent":
        d["smig_non_agricole"].pop("decision_ref")
    else:
        d["smig_non_agricole"]["decision_ref"] = valeur
    monkeypatch.setattr(smig_calc, "charger_smig", lambda: d)
    e = refus(Refus.SOURCE_MANQUANTE, "mensuel", 48, "2023-01-01")
    assert "decision_ref" in e.message_fr
