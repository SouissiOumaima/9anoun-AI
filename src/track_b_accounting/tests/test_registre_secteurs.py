"""Registre des secteurs découvert dans data/processed/salary_grids/ (calc/loaders.py, decouvrir_grilles).
Lancer depuis la racine du dépôt : pytest src/track_b_accounting/tests/test_registre_secteurs.py
"""
import json
from decimal import Decimal

import pytest
from conftest import REPO_ROOT

from track_b_accounting.calc import Refus, salaire_base
from track_b_accounting.calc import loaders

BM_FILE = REPO_ROOT / "data/processed/salary_grids/metallurgie_batiment.json"


def _ecrire(dossier, nom, code, ref="D4"):
    """Copie de la grille métallurgie sous un autre code de secteur (et une autre référence)."""
    g = json.loads(BM_FILE.read_text(encoding="utf-8"))
    g["_meta"]["secteur_code"] = code
    if ref is None:
        g["_meta"].pop("decision_ref")
    else:
        g["_meta"]["decision_ref"] = ref
    (dossier / nom).write_text(json.dumps(g, ensure_ascii=False), encoding="utf-8")


@pytest.fixture
def registre_temporaire(monkeypatch):
    """Ajoute des secteurs au registre partagé le temps d'un test, caches vidés avant et après."""
    loaders._charger_grille.cache_clear()
    yield lambda code, chemin: monkeypatch.setitem(loaders.GRILLES, code, chemin)
    loaders._charger_grille.cache_clear()


def test_registre_actuel_identique():
    assert loaders.GRILLES == {
        "METALLURGIE_BATIMENT": "data/processed/salary_grids/metallurgie_batiment.json",
        "BATIMENT_TRAVAUX_PUBLICS": "data/processed/salary_grids/batiment_travaux_publics.json",
        "ASSOCIATIONS_PERSONNES_HANDICAPEES": "data/processed/salary_grids/associations_personnes_handicapees.json",
        "ASSURANCE": "data/processed/salary_grids/assurance.json",
    }
    assert list(loaders.GRILLES) == loaders.secteurs_disponibles()            # ordre D4, puis D9, D23, D29
    assert loaders.decouvrir_grilles() == loaders.GRILLES


def test_nouveau_fichier_valide_charge(tmp_path, registre_temporaire):
    _ecrire(tmp_path, "secteur_test.json", "SECTEUR_TEST", ref="D99")
    reg = loaders.decouvrir_grilles(tmp_path)
    assert list(reg) == ["SECTEUR_TEST"] and reg["SECTEUR_TEST"].endswith("/secteur_test.json")
    registre_temporaire("SECTEUR_TEST", reg["SECTEUR_TEST"])
    # Fichier hors de data/processed/ (dossier temporaire) : on ne passe pas par la fixture ok.
    r = salaire_base("SECTEUR_TEST", "admin_tech", "4", 15, "2022-06-01")
    assert r.montant == Decimal("593.873") and r.citations[0].decision_ref == "D99"
    assert r.citations[0].data_file == reg["SECTEUR_TEST"]


@pytest.mark.parametrize("ref", [None, "", "4", "D", "D-4", "d4", "D4a", 4])
def test_fichier_sans_decision_ref_valide_ignore(tmp_path, ref):
    _ecrire(tmp_path, "sans_ref.json", "SANS_REF", ref=ref)
    assert loaders.decouvrir_grilles(tmp_path) == {}


def test_fichier_ignore_refuse_comme_secteur_inconnu():
    """Un code absent du registre (fichier ignoré ou inexistant) : SOURCE_MANQUANTE, liste des secteurs disponibles."""
    with pytest.raises(Refus) as e:
        salaire_base("SANS_REF", "admin_tech", "4", 15, "2022-06-01")
    assert e.value.code == Refus.SOURCE_MANQUANTE
    assert e.value.message_fr == ("Aucune grille vérifiée pour le secteur 'SANS_REF' "
                                  "(disponibles : METALLURGIE_BATIMENT, BATIMENT_TRAVAUX_PUBLICS, ASSOCIATIONS_PERSONNES_HANDICAPEES, ASSURANCE).")


def test_fichiers_invalides_ou_ambigus_ignores(tmp_path):
    (tmp_path / "mal_forme.json").write_text("{", encoding="utf-8")
    (tmp_path / "liste.json").write_text("[]", encoding="utf-8")
    (tmp_path / "sans_code.json").write_text(json.dumps({"_meta": {"decision_ref": "D4"}}), encoding="utf-8")
    _ecrire(tmp_path, "a.json", "DOUBLON", ref="D4")
    _ecrire(tmp_path, "b.json", "DOUBLON", ref="D5")              # même code dans deux fichiers : ambigu
    _ecrire(tmp_path, "c.json", "UNIQUE", ref="D7")
    assert loaders.decouvrir_grilles(tmp_path) == {"UNIQUE": (tmp_path / "c.json").resolve().as_posix()}


def test_ordre_par_numero_de_decision(tmp_path):
    _ecrire(tmp_path, "a.json", "ZETA", ref="D2")
    _ecrire(tmp_path, "b.json", "ALPHA", ref="D10")
    _ecrire(tmp_path, "c.json", "BETA", ref="D10")
    assert list(loaders.decouvrir_grilles(tmp_path)) == ["ZETA", "ALPHA", "BETA"]
