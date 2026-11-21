"""Schéma commun v0 des réponses : le schéma est valide, et Track B s'y conforme déjà sans modification.
Lancer depuis la racine du dépôt : pytest src/shared/tests/test_common_schema.py
"""
import copy
import json
import sys
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

# src/shared/tests/test_common_schema.py -> tests -> shared -> src -> <racine>
REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "src"))

from track_b_accounting.contract import handle  # noqa: E402
from track_b_accounting.contract.handler import reponse_erreur  # noqa: E402

COMMON_PATH = REPO_ROOT / "src" / "shared" / "schemas" / "common.v0.schema.json"
COMMON = json.loads(COMMON_PATH.read_text(encoding="utf-8"))
DEMO = json.loads((REPO_ROOT / "data" / "mock_cards" / "track_b_requests_demo.json").read_text(encoding="utf-8"))


def validateur(definition: str | None = None) -> Draft202012Validator:
    """Valide contre l'enveloppe (racine du schéma) ou contre une définition de $defs, références comprises."""
    schema = copy.deepcopy(COMMON)
    if definition is not None:
        schema["$ref"] = f"#/$defs/{definition}"
    return Draft202012Validator(schema)


ENVELOPPE, CITATION, REFUS = validateur(), validateur("citation"), validateur("refus")


def erreurs(v: Draft202012Validator, instance) -> list[str]:
    return [f"{'/'.join(map(str, e.absolute_path))}: {e.message}" for e in v.iter_errors(instance)]


# --- (a) le schéma commun lui-même ---------------------------------------------------------------------------

def test_schema_commun_valide():
    Draft202012Validator.check_schema(COMMON)
    assert COMMON["$schema"] == "https://json-schema.org/draft/2020-12/schema"
    assert COMMON["$id"] == "common.v0.schema.json" and COMMON_PATH.name.endswith(".v0.schema.json")
    assert "v0 : proposition, à valider par l'équipe" in COMMON["description"]
    attendues = {"contract_version", "request_id", "response_request_id", "case_id", "lang", "status", "montant",
                 "date", "citation", "refus_code", "refus", "erreur", "response_envelope"}
    assert attendues <= set(COMMON["$defs"])


def test_definitions_identiques_a_track_b():
    """Reprises à l'identique : aucun nom ni champ changé par rapport au schéma de réponse Track B."""
    tb = json.loads((REPO_ROOT / "data/mock_cards/schemas/track_b_response.v0.schema.json").read_text(encoding="utf-8"))
    req = json.loads((REPO_ROOT / "data/mock_cards/schemas/track_b_request.v0.schema.json").read_text(encoding="utf-8"))
    d = COMMON["$defs"]
    assert {k: v for k, v in d["citation"].items() if k != "description"} == tb["$defs"]["citation"]
    refus_tb = tb["properties"]["refus"]["oneOf"][1]
    assert d["refus"]["required"] == refus_tb["required"] and set(d["refus"]["properties"]) == set(refus_tb["properties"])
    assert d["refus_code"]["enum"] == refus_tb["properties"]["code"]["enum"]
    sans_desc = lambda s: {k: v for k, v in s.items() if k != "description"}   # noqa: E731
    assert sans_desc(d["erreur"]) == sans_desc(tb["properties"]["erreur"])
    assert d["status"]["enum"] == tb["properties"]["status"]["enum"]
    assert d["montant"]["pattern"] == tb["properties"]["result"]["oneOf"][1]["properties"]["montant"]["pattern"]
    assert d["response_request_id"]["type"] == tb["properties"]["request_id"]["type"]
    assert d["lang"]["enum"] == req["properties"]["lang"]["enum"]
    assert d["date"]["pattern"] == req["$defs"]["date"]["pattern"]
    assert {k: d["request_id"][k] for k in ("type", "minLength", "maxLength")} == \
        {k: req["properties"]["request_id"][k] for k in ("type", "minLength", "maxLength")}


# --- (b) toutes les réponses Track B sont conformes à l'enveloppe commune ----------------------------------------

def _reponses_track_b():
    reps = [(r["request_id"], handle(r)) for r in DEMO]
    # Hors démo, pour couvrir aussi le refus de contrat et le statut erreur.
    reps.append(("refus-contrat", handle({**DEMO[0], "operation": "calcul_irpp"})))
    reps.append(("erreur-json", reponse_erreur(None, json.JSONDecodeError("x", "{", 0))))
    return reps


REPONSES = _reponses_track_b()


def test_deux_cent_cinquante_cinq_requetes_de_demo():
    assert len(DEMO) == 255
    assert {rep["status"] for _, rep in REPONSES} == {"ok", "refus", "erreur"}


@pytest.mark.parametrize("rid,rep", REPONSES, ids=[r for r, _ in REPONSES])
def test_reponse_track_b_conforme_au_schema_commun(rid, rep):
    rep = json.loads(json.dumps(rep, ensure_ascii=False))       # telle qu'elle circule en JSON
    assert erreurs(ENVELOPPE, rep) == []
    for c in rep["citations"]:
        assert erreurs(CITATION, c) == []
    if rep["refus"] is not None:
        assert erreurs(REFUS, rep["refus"]) == []


def test_reponses_ok_avec_deux_citations_couvertes():
    """Les réponses de l'article 13 (D10) portent deux citations : toutes deux conformes."""
    assert any(len(rep["citations"]) == 2 for _, rep in REPONSES)


# --- l'enveloppe rejette ce qu'elle doit rejeter -------------------------------------------------------------------

def _ok():
    return copy.deepcopy(next(rep for _, rep in REPONSES if rep["status"] == "ok"))


def _refus():
    return copy.deepcopy(next(rep for _, rep in REPONSES if rep["status"] == "refus"))


@pytest.mark.parametrize("mutation", [
    lambda r: r.__setitem__("status", "succes"),
    lambda r: r.__setitem__("citations", []),                                   # ok sans citation
    lambda r: r["citations"][0].__setitem__("decision_ref", "D-4"),
    lambda r: r["citations"][0].__setitem__("data_file", "data/raw/x.json"),
    lambda r: r["citations"][0].__setitem__("page", 0),
    lambda r: r["citations"][0].__setitem__("extra", 1),
    lambda r: r.__setitem__("contract_version", "trackB-0"),
    lambda r: r.__setitem__("case_id", ""),
    lambda r: r.pop("refus"),
])
def test_enveloppe_rejette_ok_invalide(mutation):
    r = _ok()
    mutation(r)
    assert erreurs(ENVELOPPE, r)


@pytest.mark.parametrize("mutation", [
    lambda r: r["refus"].__setitem__("code", "INTERDIT"),
    lambda r: r["refus"].__setitem__("message_ar", ""),
    lambda r: r["refus"].pop("message_fr"),
    lambda r: r.__setitem__("refus", None),                                     # refus sans motif
    lambda r: r.__setitem__("citations", [_ok()["citations"][0]]),              # refus avec citation
])
def test_enveloppe_rejette_refus_invalide(mutation):
    r = _refus()
    mutation(r)
    assert erreurs(ENVELOPPE, r)


def test_case_id_optionnel_accepte():
    r = _ok()
    r["case_id"] = "dossier-42"
    assert erreurs(ENVELOPPE, r) == []


def test_extension_par_un_track():
    """Un track étend l'enveloppe (allOf + unevaluatedProperties) : champ propre accepté, champ inconnu rejeté."""
    ext = {"$schema": COMMON["$schema"], "$defs": COMMON["$defs"],
           "allOf": [{"$ref": "#/$defs/response_envelope"}],
           "properties": {"result": {"type": ["object", "null"]}},
           "unevaluatedProperties": False}
    v = Draft202012Validator(ext)
    assert not list(v.iter_errors(_ok()))
    r = _ok()
    r["inconnu"] = 1
    assert list(v.iter_errors(r))
