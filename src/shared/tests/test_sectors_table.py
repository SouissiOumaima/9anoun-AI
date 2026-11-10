"""Table de correspondance des secteurs DS2 ↔ DS5 (D30) : schéma, registre DS5, registre DS2, vocabulaire D21.
Lancer depuis la racine du dépôt : pytest src/shared/tests/test_sectors_table.py
"""
import copy
import json
import sys
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

# src/shared/tests/test_sectors_table.py -> tests -> shared -> src -> <racine>
REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "src"))

from legal_retrieval.corpus.registry import REGISTRY, match_source  # noqa: E402
from track_b_accounting.calc import loaders  # noqa: E402

TABLE_PATH = REPO_ROOT / "src" / "shared" / "sectors" / "sectors.v0.json"
SCHEMA_PATH = REPO_ROOT / "src" / "shared" / "schemas" / "common_sectors.v0.schema.json"
VOCABULARY_PATH = REPO_ROOT / "data" / "mock_cards" / "legal_retrieval_vocabulary.v0.json"
TABLE = json.loads(TABLE_PATH.read_text(encoding="utf-8"))
SCHEMA = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
VALIDATEUR = Draft202012Validator(SCHEMA)
ACTIFS = [s for s in TABLE["sectors"] if s["ds5_status"] == "actif"]
# Secteurs sectoriels du registre DS2 (la convention cadre et le SMIG n'ont pas de secteur).
REGISTRE_DS2 = {e.source_id: e for e in REGISTRY if e.sector is not None}


def erreurs(instance) -> list[str]:
    return [f"{'/'.join(map(str, e.absolute_path))}: {e.message}" for e in VALIDATEUR.iter_errors(instance)]


# --- (1) schéma et en-tête ------------------------------------------------------------------------------------

def test_schema_valide_et_table_conforme():
    Draft202012Validator.check_schema(SCHEMA)
    assert SCHEMA["$id"] == "common_sectors.v0.schema.json" and SCHEMA_PATH.name.endswith(".v0.schema.json")
    assert "v0 : proposition, à valider par l'équipe" in SCHEMA["description"]
    assert erreurs(TABLE) == []
    assert (TABLE["table_version"], TABLE["decision_ref"], TABLE["vocabulary_ref"]) == ("common.sectors.v0", "D30", "D21")


def test_codes_uniques():
    for champ in ("ds2_code", "source_id"):
        valeurs = [s[champ] for s in TABLE["sectors"]]
        assert len(valeurs) == len(set(valeurs)), champ
    codes_ds5 = [s["ds5_code"] for s in ACTIFS]
    assert len(codes_ds5) == len(set(codes_ds5))


@pytest.mark.parametrize("statut", ["actif", "en_preparation", "aucun"])
def test_schema_lie_statut_et_champs_ds5(statut):
    """actif ⇒ ds5_code, ds5_decision_ref et evidence renseignés ; en_preparation / aucun ⇒ les trois à null."""
    actif = copy.deepcopy(ACTIFS[0])
    vide = {**actif, "ds5_status": "aucun", "ds5_code": None, "ds5_decision_ref": None, "evidence": None}
    assert erreurs({**TABLE, "sectors": [vide]}) == []
    for champ in ("ds5_code", "ds5_decision_ref", "evidence"):
        if statut == "actif":
            entree = {**actif, champ: None}
        else:
            entree = {**vide, "ds5_status": statut, champ: actif[champ]}
        assert erreurs({**TABLE, "sectors": [entree]}), (statut, champ)


# --- (2) et (3) registre DS5 ----------------------------------------------------------------------------------

def test_codes_ds5_dans_le_registre_et_meta_identique():
    disponibles = loaders.secteurs_disponibles()
    for s in TABLE["sectors"]:
        if s["ds5_code"] is None:
            continue
        assert s["ds5_code"] in loaders.GRILLES and s["ds5_code"] in disponibles, s["ds5_code"]
        meta = loaders.charger_grille(s["ds5_code"])["_meta"]
        assert s["ds5_decision_ref"] == meta["decision_ref"]
        assert s["evidence"]["source_file"] == meta["source_file"]
        assert s["evidence"]["convention_ar"] == meta["convention_ar"]


# Seule exemption : grilles de la vague 1 (D49 à D54), activées dans le registre DS5 sans entrée dans la table, en
# attente de validation DS2 (noms, codes et alias). Vider cette liste quand l'équipe les inscrit dans la table.
EN_ATTENTE_DS2 = ["TORREFACTION_CAFE", "AGENCES_VOYAGES", "HOTELS_TOURISTIQUES", "CONFISERIE_BISCUITERIE_CHOCOLATERIE",
                  "PATES_ALIMENTAIRES_COUSCOUS", "COSMETIQUES_PARFUMS"]


def test_chaque_secteur_ds5_disponible_figure_une_fois():
    """Une nouvelle grille ajoutée au registre DS5 doit être inscrite dans la table (sauf EN_ATTENTE_DS2)."""
    codes = [s["ds5_code"] for s in ACTIFS]
    disponibles = loaders.secteurs_disponibles()
    for code in disponibles:
        if code in EN_ATTENTE_DS2:
            continue
        assert codes.count(code) == 1, code
    # Les secteurs exemptés sont bien disponibles et absents de la table : à leur ajout, ce test échoue jusqu'à ce
    # que la liste d'exemption soit vidée.
    tous_codes = [s["ds5_code"] for s in TABLE["sectors"]]
    for code in EN_ATTENTE_DS2:
        assert code in disponibles, code
        assert code not in tous_codes, code


# --- (4) preuve exécutable : même fichier source côté DS2 -----------------------------------------------------

@pytest.mark.parametrize("secteur", ACTIFS, ids=[s["ds2_code"] for s in ACTIFS])
def test_preuve_meme_source_file(secteur):
    chemin = REPO_ROOT / secteur["evidence"]["source_file"]
    assert chemin.is_file(), chemin
    entree = match_source(chemin.name)
    assert entree is not None
    assert (entree.source_id, entree.sector) == (secteur["source_id"], secteur["ds2_code"])


def test_registre_ds2_correspond_aux_sept_secteurs():
    assert len(TABLE["sectors"]) == 7
    assert {s["source_id"]: s["ds2_code"] for s in TABLE["sectors"]} == {
        sid: e.sector for sid, e in REGISTRE_DS2.items()}


def test_ambiguites_sans_resolution():
    codes = {s["ds2_code"] for s in TABLE["sectors"]}
    for a in TABLE["sector_ambiguities"]:
        assert set(a["codes"]) <= codes
    # « bâtiment » seul et « البناء » seul ne mènent jamais à METALLURGIE_BATIMENT.
    for s in TABLE["sectors"]:
        if s["ds5_code"] == "METALLURGIE_BATIMENT":
            assert not {"bâtiment", "البناء"} & {x.strip().lower() for x in s["aliases"]}


# --- (5) copie fidèle du vocabulaire D21 ----------------------------------------------------------------------

def test_copie_fidele_du_vocabulaire_d21():
    if not VOCABULARY_PATH.is_file():
        pytest.skip("data/mock_cards/legal_retrieval_vocabulary.v0.json absent de cette branche (vocabulaire D21 "
                    "pas encore fusionné dans main) : comparaison exécutée dès que le fichier est présent.")
    vocab = json.loads(VOCABULARY_PATH.read_text(encoding="utf-8"))
    attendu = [{"ds2_code": v["code"], **{k: v[k] for k in ("source_id", "label_fr", "label_ar", "aliases")}}
               for v in vocab["sectors"]]
    copie = [{k: s[k] for k in ("ds2_code", "source_id", "label_fr", "label_ar", "aliases")} for s in TABLE["sectors"]]
    assert copie == attendu
    assert TABLE["sector_ambiguities"] == vocab["sector_ambiguities"]
    assert TABLE["vocabulary_ref"] == vocab["decision_ref"]
