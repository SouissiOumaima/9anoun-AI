"""Contrat JSON Track B v0 (D7) : schémas, handler, CLI, démo.
Lancer depuis la racine du dépôt : pytest src/track_b_accounting/tests/test_contract.py
"""
import copy
import io
import json
import re

import pytest
from conftest import REPO_ROOT
from jsonschema import Draft202012Validator
from mocks import DEMO_FILE, MockOrchestrator, MockTrackA

from track_b_accounting.contract import handle
from track_b_accounting.contract import handler as H
from track_b_accounting.contract.cli import main as cli_main

SCHEMAS = REPO_ROOT / "data" / "mock_cards" / "schemas"
REQ_SCHEMA = json.loads((SCHEMAS / "track_b_request.v0.schema.json").read_text(encoding="utf-8"))
REP_SCHEMA = json.loads((SCHEMAS / "track_b_response.v0.schema.json").read_text(encoding="utf-8"))
REQ_V = Draft202012Validator(REQ_SCHEMA)
REP_V = Draft202012Validator(REP_SCHEMA)
DEMO = json.loads(DEMO_FILE.read_text(encoding="utf-8"))
REQ_OK = DEMO[0]


def valide(rep: dict) -> dict:
    erreurs = sorted(REP_V.iter_errors(rep), key=str)
    assert not erreurs, [e.message for e in erreurs]
    return rep


# --- schémas ------------------------------------------------------------------------------------

def test_schemas_bien_formes_et_marques_v0():
    for s in (REQ_SCHEMA, REP_SCHEMA):
        Draft202012Validator.check_schema(s)
        assert s["$schema"] == "https://json-schema.org/draft/2020-12/schema"
        assert "v0 — proposition Track B, à valider avec l'équipe" in s["description"]


@pytest.mark.parametrize("req", DEMO, ids=lambda r: r["request_id"])
def test_requetes_demo_toutes_conformes_au_schema(req):
    assert REQ_V.is_valid(req)


# --- refus métier (schéma valide) vs refus de contrat (schéma invalide) ------------------------------

def test_cnss_valide_au_schema_puis_refus_metier_hors_scope():
    req = next(r for r in DEMO if r["operation"] == "cotisation_cnss")
    assert REQ_V.is_valid(req)                                  # la requête n'est pas un bug appelant
    rep = valide(handle(req))
    assert rep["status"] == "refus" and rep["refus"]["code"] == "HORS_SCOPE"
    assert rep["refus"]["message_fr"].startswith("Opération 'cotisation_cnss' hors du périmètre Track B v0")
    assert rep["refus"]["message_ar"] and rep["result"] is None and rep["citations"] == []


def test_cnss_mal_formee_refusee_par_le_contrat_avant_le_perimetre():
    """La validation du schéma passe en premier : une requête CNSS mal formée reste un refus de contrat."""
    req = copy.deepcopy(next(r for r in DEMO if r["operation"] == "cotisation_cnss"))
    req.pop("lang")
    rep = valide(handle(req))
    assert rep["refus"]["code"] == "PARAM_INVALIDE" and "non conforme" in rep["refus"]["message_fr"]


@pytest.mark.parametrize("operation", ["calcul_irpp", "salaire_net", ""])
def test_operation_inconnue_refus_de_contrat_param_invalide(operation):
    req = dict(copy.deepcopy(REQ_OK), operation=operation)
    assert not REQ_V.is_valid(req)
    rep = valide(handle(req))
    assert rep["status"] == "refus" and rep["refus"]["code"] == "PARAM_INVALIDE"
    assert "non conforme" in rep["refus"]["message_fr"] and rep["computed_by"] == "track_b_accounting.contract"


def test_schema_reponse_impose_citation_si_ok():
    rep = handle(REQ_OK)
    assert REP_V.is_valid(rep)
    sans_citation = dict(rep, citations=[])
    assert not REP_V.is_valid(sans_citation)


@pytest.mark.parametrize("alteration", [
    lambda r: r["result"].__setitem__("montant", 593.873),          # nombre JSON interdit
    lambda r: r["result"].__setitem__("montant", "593.87"),         # 3 décimales exigées
    lambda r: r["result"]["detail"].__setitem__("x", 1.5),          # float dans detail
    lambda r: r.__setitem__("refus", {"code": "HORS_SCOPE", "message_fr": "x", "message_ar": "x"}),
    lambda r: r.__setitem__("status", "refus"),                     # refus avec montant
    lambda r: r.__setitem__("status", "erreur"),
    lambda r: r["citations"][0].__setitem__("data_file", "data/raw/pdf/x.pdf"),
    lambda r: r.__setitem__("contract_version", "track_b.v1"),
])
def test_schema_reponse_rejette(alteration):
    rep = copy.deepcopy(handle(REQ_OK))
    alteration(rep)
    assert not REP_V.is_valid(rep)


# --- les 10 échanges de démo -----------------------------------------------------------------------

@pytest.mark.parametrize("req", DEMO, ids=lambda r: r["request_id"])
def test_chaque_requete_demo_donne_une_reponse_valide(req):
    rep = valide(handle(req))
    assert rep["request_id"] == req["request_id"] and rep["contract_version"] == "track_b.v0"
    if rep["status"] == "ok":
        assert rep["citations"], "ok ⇒ au moins une citation"
        for c in rep["citations"]:
            assert c["source_file"].endswith(".pdf") and isinstance(c["page"], int)
        assert re.fullmatch(r"\d+\.\d{3}", rep["result"]["montant"])
        assert rep["refus"] is None
    else:
        assert rep["status"] == "refus" and rep["result"] is None and rep["citations"] == []
        assert rep["refus"]["message_fr"] and rep["refus"]["message_ar"]


def test_bilan_demo_6_ok_4_refus():
    statuts = {req["request_id"]: handle(req)["status"] for req in DEMO}
    assert list(statuts.values()).count("ok") == 6 and list(statuts.values()).count("refus") == 4
    codes = {r["request_id"]: handle(r)["refus"]["code"] for r in DEMO[6:]}
    assert codes == {
        "demo-07-refus-cnss": "HORS_SCOPE",
        "demo-08-refus-date-anterieure": "SOURCE_MANQUANTE",
        "demo-09-refus-categorie-inconnue": "PARAM_INVALIDE",
        "demo-10-refus-secteur-non-couvert": "SOURCE_MANQUANTE",
    }


def test_montants_demo_identiques_a_calc():
    """Le handler ne calcule rien : il recopie le Result de calc/ (ici des cellules vérifiées D4/D2)."""
    attendus = ["593.873", "4.620", "100.533", "0.160", "459.264", "2.254"]
    assert [handle(r)["result"]["montant"] for r in DEMO[:6]] == attendus


@pytest.mark.parametrize("req", DEMO, ids=lambda r: r["request_id"])
def test_round_trip_json(req):
    rep = handle(req)
    texte = json.dumps(rep, ensure_ascii=False)
    assert json.loads(texte) == rep
    assert valide(json.loads(texte))


def test_deterministe():
    assert [handle(r) for r in DEMO] == [handle(r) for r in DEMO]


# --- requêtes invalides ---------------------------------------------------------------------------

def _alterer(f):
    r = copy.deepcopy(REQ_OK)
    f(r)
    return r


@pytest.mark.parametrize("req,rid", [
    (None, None),
    ([REQ_OK], None),
    ("texte", None),
    ({}, None),
    (_alterer(lambda r: r.pop("request_id")), None),
    (_alterer(lambda r: r.__setitem__("request_id", 42)), None),
    (_alterer(lambda r: r.__setitem__("contract_version", "track_b.v1")), "demo-01-salaire-admin-2022"),
    (_alterer(lambda r: r.__setitem__("lang", "en")), "demo-01-salaire-admin-2022"),
    (_alterer(lambda r: r.__setitem__("extra", 1)), "demo-01-salaire-admin-2022"),
    (_alterer(lambda r: r["params"].pop("date")), "demo-01-salaire-admin-2022"),
    (_alterer(lambda r: r["params"].__setitem__("date", "01/06/2022")), "demo-01-salaire-admin-2022"),
    (_alterer(lambda r: r["params"].__setitem__("anciennete_annees", "15")), "demo-01-salaire-admin-2022"),
    (_alterer(lambda r: r["params"].__setitem__("brut", True)), "demo-01-salaire-admin-2022"),
    (_alterer(lambda r: r.__setitem__("params", [])), "demo-01-salaire-admin-2022"),
    (_alterer(lambda r: r.__setitem__("operation", 3)), "demo-01-salaire-admin-2022"),
])
def test_requete_invalide_donne_refus_valide(req, rid):
    rep = valide(handle(req))
    assert rep["status"] == "refus" and rep["refus"]["code"] == "PARAM_INVALIDE"
    assert rep["request_id"] == rid and rep["result"] is None and rep["citations"] == []
    assert rep["computed_by"] == "track_b_accounting.contract"


def test_refus_metier_attribue_a_calc():
    rep = valide(handle(_alterer(lambda r: r["params"].__setitem__("anciennete_annees", 4))))
    assert rep["refus"]["code"] == "PARAM_INVALIDE" and rep["computed_by"] == "track_b_accounting.calc.salaire_base"


def test_parametre_prime_inconnu_refuse_par_calc():
    req = copy.deepcopy(DEMO[2])
    req["params"]["bonus"] = "x"
    rep = valide(handle(req))
    assert rep["status"] == "refus" and rep["computed_by"] == "track_b_accounting.calc.prime"


def test_exception_inattendue_donne_erreur_sans_montant(monkeypatch):
    def boom(**_):
        raise RuntimeError("panne")
    monkeypatch.setitem(H.OPERATIONS, "smig", boom)
    rep = valide(handle(DEMO[4]))
    assert rep["status"] == "erreur" and rep["result"] is None and rep["citations"] == []
    assert rep["erreur"]["type"] == "RuntimeError" and "panne" not in json.dumps(rep)
    assert rep["request_id"] == DEMO[4]["request_id"]


def test_reponse_non_conforme_remplacee_par_erreur(monkeypatch):
    monkeypatch.setattr(H, "reponse_ok", lambda rid, r, qui: {"status": "ok", "montant": 1.5})
    rep = valide(handle(REQ_OK))
    assert rep["status"] == "erreur" and rep["erreur"]["type"] == "ValueError"


# --- CLI -----------------------------------------------------------------------------------------

def test_cli_fichier_liste():
    out = io.StringIO()
    assert cli_main([str(DEMO_FILE)], stdout=out) == 0
    reps = json.loads(out.getvalue())
    assert len(reps) == 10 and all(REP_V.is_valid(r) for r in reps)
    assert "لا يوجد" in out.getvalue() and "\\u06" not in out.getvalue()     # ensure_ascii=False


def test_cli_stdin_objet():
    out = io.StringIO()
    assert cli_main([], stdin=io.StringIO(json.dumps(REQ_OK)), stdout=out) == 0
    assert valide(json.loads(out.getvalue()))["result"]["montant"] == "593.873"


@pytest.mark.parametrize("argv,stdin", [(["introuvable.json"], None), ([], "{pas du json")])
def test_cli_entree_illisible(argv, stdin):
    out = io.StringIO()
    assert cli_main(argv, stdin=io.StringIO(stdin or ""), stdout=out) == 1
    assert valide(json.loads(out.getvalue()))["status"] == "erreur"


# --- mocks et démo ---------------------------------------------------------------------------------

def test_mock_track_a_recopie_sans_calculer():
    a = MockTrackA()
    for req, rep in MockOrchestrator(handle).run():
        phrase = a.formuler(req, rep)
        if rep["status"] == "ok":
            assert rep["result"]["montant"] in phrase and f"{rep['citations'][0]['page']}" in phrase
            assert ("المصدر" in phrase) if req["lang"] == "ar" else ("source :" in phrase)
        else:
            msg = rep["refus"]["message_ar"] if req["lang"] == "ar" else rep["refus"]["message_fr"]
            assert msg in phrase


def test_mock_track_a_erreur(monkeypatch):
    monkeypatch.setitem(H.OPERATIONS, "smig", lambda **_: 1 / 0)
    for lang in ("fr", "ar"):
        req = dict(DEMO[4], lang=lang)
        rep = handle(req)
        assert MockTrackA().formuler(req, rep) == rep["erreur"][f"message_{lang}"]


def test_demo_affiche_10_echanges():
    from track_b_accounting.demo import main
    out = io.StringIO()
    assert main(out=out) == 0
    texte = out.getvalue()
    assert texte.count("=== Échange ") == 10 and "Bilan : 6 ok, 4 refus, 0 erreur(s)." in texte
