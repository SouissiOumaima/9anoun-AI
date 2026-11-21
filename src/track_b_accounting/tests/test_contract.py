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
    assert REQ_V.is_valid(req)  # la requête n'est pas un bug appelant
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


@pytest.mark.parametrize(
    "alteration",
    [
        lambda r: r["result"].__setitem__("montant", 593.873),  # nombre JSON interdit
        lambda r: r["result"].__setitem__("montant", "593.87"),  # 3 décimales exigées
        lambda r: r["result"]["detail"].__setitem__("x", 1.5),  # float dans detail
        lambda r: r.__setitem__("refus", {"code": "HORS_SCOPE", "message_fr": "x", "message_ar": "x"}),
        lambda r: r.__setitem__("status", "refus"),  # refus avec montant
        lambda r: r.__setitem__("status", "erreur"),
        lambda r: r["citations"][0].__setitem__("data_file", "data/raw/pdf/x.pdf"),
        lambda r: r.__setitem__("contract_version", "track_b.v1"),
    ],
)
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


def test_bilan_demo_109_ok_102_refus():
    statuts = {req["request_id"]: handle(req)["status"] for req in DEMO}
    assert list(statuts.values()).count("ok") == 109 and list(statuts.values()).count("refus") == 102
    codes = {r["request_id"]: handle(r)["refus"]["code"] for r in DEMO if statuts[r["request_id"]] == "refus"}
    assert codes == {
        "demo-07-refus-cnss": "HORS_SCOPE",
        "demo-08-refus-date-anterieure": "SOURCE_MANQUANTE",
        "demo-09-refus-categorie-inconnue": "PARAM_INVALIDE",
        "demo-10-refus-secteur-non-couvert": "SOURCE_MANQUANTE",
        "demo-13-refus-btp-anciennete-27-ans": "SOURCE_MANQUANTE",
        "demo-17-refus-associations-anciennete-33-ans": "SOURCE_MANQUANTE",
        "demo-23-refus-assurance-avant-2020-10-01": "SOURCE_MANQUANTE",
        "demo-24-refus-assurance-borne-exacte": "PARAM_INVALIDE",
        "demo-32-refus-enseignement-borne-exacte": "PARAM_INVALIDE",
        "demo-33-refus-enseignement-au-dela-36-ans": "SOURCE_MANQUANTE",
        "demo-36-refus-banques-prime-transport-sans-date": "SOURCE_MANQUANTE",
        "demo-37-refus-banques-borne-exacte": "PARAM_INVALIDE",
        "demo-38-refus-banques-avant-2020-09-01": "SOURCE_MANQUANTE",
        "demo-39-refus-banques-anciennete-33-ans": "SOURCE_MANQUANTE",
        "demo-43-refus-gardiennage-borne-exacte": "PARAM_INVALIDE",
        "demo-44-refus-gardiennage-avant-2010-05-01": "SOURCE_MANQUANTE",
        "demo-45-refus-gardiennage-prime-risque-sans-date": "SOURCE_MANQUANTE",
        "demo-46-refus-gardiennage-grille-revisee-avenant-7": "SOURCE_MANQUANTE",
        "demo-49-refus-cafe-borne-exacte": "PARAM_INVALIDE",
        "demo-50-refus-cafe-avant-2021-12-01": "SOURCE_MANQUANTE",
        "demo-51-refus-cafe-prime-production": "SOURCE_MANQUANTE",
        "demo-52-refus-cafe-employes-mensuels": "SOURCE_MANQUANTE",
        "demo-55-refus-voyages-borne-exacte": "PARAM_INVALIDE",
        "demo-56-refus-voyages-avant-2022-05-01": "SOURCE_MANQUANTE",
        "demo-57-refus-voyages-prime-repas-periode": "SOURCE_MANQUANTE",
        "demo-60-refus-hotels-5-etoiles": "SOURCE_MANQUANTE",
        "demo-61-refus-hotels-anciennete-30-ans": "SOURCE_MANQUANTE",
        "demo-62-refus-hotels-avant-2022-05-01": "SOURCE_MANQUANTE",
        "demo-66-refus-confiserie-population-omise": "PARAM_INVALIDE",
        "demo-67-refus-confiserie-art-53-4-a-5-ans": "SOURCE_MANQUANTE",
        "demo-68-refus-confiserie-cellule-illisible": "SOURCE_MANQUANTE",
        "demo-69-refus-confiserie-ecart-negatif": "SOURCE_MANQUANTE",
        "demo-73-refus-pates-sous-categorie-manquante": "PARAM_INVALIDE",
        "demo-74-refus-pates-palier-art-14": "PARAM_INVALIDE",
        "demo-76-refus-pates-transport-niveau-smig": "SOURCE_MANQUANTE",
        "demo-79-refus-cosmetiques-categorie-1-apres-un-an": "SOURCE_MANQUANTE",
        "demo-80-refus-cosmetiques-cellule-illisible": "SOURCE_MANQUANTE",
        "demo-81-refus-cosmetiques-transport-cadres": "SOURCE_MANQUANTE",
        "demo-83-refus-cosmetiques-avant-2021-12-01": "SOURCE_MANQUANTE",
        "demo-87-refus-savonnerie-borne-exacte": "PARAM_INVALIDE",
        "demo-88-refus-savonnerie-21-ans": "SOURCE_MANQUANTE",
        "demo-89-refus-savonnerie-prime-panier": "SOURCE_MANQUANTE",
        "demo-90-refus-savonnerie-population-omise": "PARAM_INVALIDE",
        "demo-94-refus-petrole-32-ans": "SOURCE_MANQUANTE",
        "demo-95-refus-petrole-prime-responsabilite": "SOURCE_MANQUANTE",
        "demo-96-refus-petrole-sous-categorie-manquante": "PARAM_INVALIDE",
        "demo-97-refus-petrole-avant-2021-12-01": "SOURCE_MANQUANTE",
        "demo-101-refus-plasturgie-32-ans": "SOURCE_MANQUANTE",
        "demo-102-refus-plasturgie-population-omise": "PARAM_INVALIDE",
        "demo-103-refus-plasturgie-prime-production": "SOURCE_MANQUANTE",
        "demo-106-refus-minoteries-promotion-non-calculee": "SOURCE_MANQUANTE",
        "demo-107-refus-minoteries-palier-27": "PARAM_INVALIDE",
        "demo-109-refus-minoteries-prime-caisse": "SOURCE_MANQUANTE",
        "demo-113-refus-teintureries-borne-exacte": "PARAM_INVALIDE",
        "demo-114-refus-teintureries-avant-2021-12-01": "SOURCE_MANQUANTE",
        "demo-115-refus-teintureries-prime-lait-salete": "SOURCE_MANQUANTE",
        "demo-118-refus-boissons-cellule-illisible": "SOURCE_MANQUANTE",
        "demo-119-refus-boissons-30-ans": "SOURCE_MANQUANTE",
        "demo-120-refus-boissons-prime-panier-periode": "SOURCE_MANQUANTE",
        "demo-122-refus-boissons-population-omise": "PARAM_INVALIDE",
        "demo-127-refus-mecanique-30-ans": "SOURCE_MANQUANTE",
        "demo-128-refus-mecanique-borne-exacte": "PARAM_INVALIDE",
        "demo-129-refus-mecanique-avant-2021-12-01": "SOURCE_MANQUANTE",
        "demo-133-refus-alcool-34-ans": "SOURCE_MANQUANTE",
        "demo-134-refus-alcool-prime-panier": "SOURCE_MANQUANTE",
        "demo-135-refus-alcool-transport-niveau-smig": "SOURCE_MANQUANTE",
        "demo-136-refus-alcool-population-omise": "PARAM_INVALIDE",
        "demo-140-refus-bois-palier-27": "PARAM_INVALIDE",
        "demo-141-refus-bois-au-dela-27-ans": "SOURCE_MANQUANTE",
        "demo-142-refus-bois-aide-deces": "SOURCE_MANQUANTE",
        "demo-143-refus-bois-avant-2021-12-01": "SOURCE_MANQUANTE",
        "demo-148-refus-dechets-cellule-illisible": "SOURCE_MANQUANTE",
        "demo-149-refus-dechets-palier-26": "PARAM_INVALIDE",
        "demo-150-refus-dechets-prime-lait": "SOURCE_MANQUANTE",
        "demo-151-refus-dechets-avant-2020-05-01": "SOURCE_MANQUANTE",
        "demo-155-refus-habillement-33-ans": "SOURCE_MANQUANTE",
        "demo-156-refus-habillement-prime-assiduite": "SOURCE_MANQUANTE",
        "demo-157-refus-habillement-avant-2021-09-01": "SOURCE_MANQUANTE",
        "demo-162-refus-commerce-promotion-non-calculee": "SOURCE_MANQUANTE",
        "demo-163-refus-commerce-palier-26": "PARAM_INVALIDE",
        "demo-164-refus-commerce-population-omise": "PARAM_INVALIDE",
        "demo-165-refus-commerce-prime-fin-annee": "SOURCE_MANQUANTE",
        "demo-170-refus-imprimerie-31-ans": "SOURCE_MANQUANTE",
        "demo-171-refus-imprimerie-borne-exacte": "PARAM_INVALIDE",
        "demo-172-refus-imprimerie-avant-2021-12-01": "SOURCE_MANQUANTE",
        "demo-173-refus-imprimerie-prime-fin-annee": "SOURCE_MANQUANTE",
        "demo-174-refus-verre-salaire-horaires": "SOURCE_MANQUANTE",
        "demo-175-refus-verre-salaire-mensuels": "SOURCE_MANQUANTE",
        "demo-180-refus-verre-prime-globale": "SOURCE_MANQUANTE",
        "demo-184-refus-agricole-cellule-illisible": "SOURCE_MANQUANTE",
        "demo-187-refus-agricole-prime-transport": "SOURCE_MANQUANTE",
        "demo-188-refus-agricole-40-ans": "SOURCE_MANQUANTE",
        "demo-192-refus-boulangerie-cellule-illisible": "SOURCE_MANQUANTE",
        "demo-194-refus-boulangerie-24-ans": "SOURCE_MANQUANTE",
        "demo-195-refus-boulangerie-population-omise": "PARAM_INVALIDE",
        "demo-199-refus-textile-colonne-stage": "SOURCE_MANQUANTE",
        "demo-200-refus-textile-35-ans": "SOURCE_MANQUANTE",
        "demo-202-refus-textile-prime-assiduite": "SOURCE_MANQUANTE",
        "demo-206-refus-fonderie-cellule-illisible": "SOURCE_MANQUANTE",
        "demo-209-refus-fonderie-prime-panier": "SOURCE_MANQUANTE",
        "demo-210-refus-fonderie-borne-exacte": "PARAM_INVALIDE",
        "demo-211-refus-fonderie-35-ans-et-plus": "SOURCE_MANQUANTE",
    }
    # demo-13 (BTP, catégorie 19, 28 ans) : refus de la case « 950 dinars » de l'article 13 (D10).
    rep13 = handle(next(r for r in DEMO if r["request_id"] == "demo-13-refus-btp-anciennete-27-ans"))
    assert rep13["refus"]["message_fr"].startswith("Catégorie 19, après 3 ans au degré 11")


def test_demo_10_secteur_fictif():
    """Depuis D9, BATIMENT_TRAVAUX_PUBLICS est couvert : demo-10 garde un refus « secteur inconnu » avec un code fictif."""
    rep = handle(next(r for r in DEMO if r["request_id"] == "demo-10-refus-secteur-non-couvert"))
    assert rep["refus"]["message_fr"] == (
        "Aucune grille vérifiée pour le secteur 'SECTEUR_FICTIF_NON_SUPPORTE' "
        "(disponibles : METALLURGIE_BATIMENT, BATIMENT_TRAVAUX_PUBLICS, ASSOCIATIONS_PERSONNES_HANDICAPEES, ASSURANCE, ENSEIGNEMENT_PRIVE, BANQUES, GARDIENNAGE_SECURITE_TRANSPORT_FONDS, "
        "TORREFACTION_CAFE, AGENCES_VOYAGES, HOTELS_TOURISTIQUES, CONFISERIE_BISCUITERIE_CHOCOLATERIE, PATES_ALIMENTAIRES_COUSCOUS, COSMETIQUES_PARFUMS, "
        "SAVONNERIE_RAFFINAGE_GRIGNONS, COMMERCE_DISTRIBUTION_PETROLE, PLASTURGIE, MINOTERIES, TEINTURERIES_PRESSINGS, BOISSONS_GAZEUSES, "
        "MECANIQUE_STATIONS_SERVICE, BOISSONS_ALCOOLISEES, BOIS_AMEUBLEMENT_LIEGE, GESTION_DECHETS, HABILLEMENT, COMMERCE_GROS_DETAIL, "
        "IMPRIMERIE_EDITION_CARTONNAGE, VERRE_MIROIRS, CONCESSIONNAIRES_MATERIEL_AGRICOLE, BOULANGERIES, TEXTILE, FONDERIE_METALLURGIE_MECANIQUE)."
    )


def test_montants_demo_identiques_a_calc():
    """Le handler ne calcule rien : il recopie le Result de calc/ (ici des cellules vérifiées D4/D2)."""
    attendus = ["593.873", "4.620", "100.533", "0.160", "459.264", "2.254"]
    assert [handle(r)["result"]["montant"] for r in DEMO[:6]] == attendus
    # BTP (D9) : tableau 6 p.25, cat. 4 degré 7 ; tableau 3 p.24, chef d'équipe 2e degré.
    assert [handle(r)["result"]["montant"] for r in DEMO[10:12]] == ["699.751", "4.276"]
    # Article 13 (D10) : métallurgie admin_tech cat. 4, 25 ans, 2024 : 680.334 + 2 × 2.148.
    rep14 = handle(DEMO[13])
    assert rep14["result"]["montant"] == "684.630" and len(rep14["citations"]) == 2


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


@pytest.mark.parametrize(
    "req,rid",
    [
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
    ],
)
def test_requete_invalide_donne_refus_valide(req, rid):
    rep = valide(handle(req))
    assert rep["status"] == "refus" and rep["refus"]["code"] == "PARAM_INVALIDE"
    assert rep["request_id"] == rid and rep["result"] is None and rep["citations"] == []
    assert rep["computed_by"] == "track_b_accounting.contract"


def test_refus_metier_attribue_a_calc():
    rep = valide(handle(_alterer(lambda r: r["params"].__setitem__("anciennete_annees", 4))))
    assert rep["refus"]["code"] == "PARAM_INVALIDE" and rep["computed_by"] == "track_b_accounting.calc.salaire_base"


def test_anciennete_25_ans_article_13_deux_citations_et_hypotheses():
    """Au-delà du dernier degré (art. 13, p.9, D10) : montant, deux citations et hypothèses à afficher."""
    rep = valide(handle(_alterer(lambda r: r["params"].__setitem__("anciennete_annees", 25))))
    assert rep["status"] == "ok" and rep["result"]["detail"]["regle_art13"] == "ecart_cumule_biennal"
    assert [(c["page"], c["article"], c["decision_ref"]) for c in rep["citations"]] == [
        (30, None, "D4"),
        (9, "13 (جديد) ب", "D10"),
    ]
    assert (
        isinstance(rep["result"]["detail"]["hypotheses"], list) and len(rep["result"]["detail"]["hypotheses_ar"]) == 4
    )
    assert re.fullmatch(r"\d+\.\d{3}", rep["result"]["detail"]["ecart"])  # Decimal → chaîne, jamais float


def test_schema_reponse_rejette_hypotheses_mal_formees():
    rep = handle(_alterer(lambda r: r["params"].__setitem__("anciennete_annees", 25)))
    rep["result"]["detail"]["hypotheses"] = [1, 2]
    assert not REP_V.is_valid(rep)
    rep["result"]["detail"]["hypotheses"] = [""]
    assert not REP_V.is_valid(rep)


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
    assert len(reps) == len(DEMO) == 211 and all(REP_V.is_valid(r) for r in reps)
    assert "لا يوجد" in out.getvalue() and "\\u06" not in out.getvalue()  # ensure_ascii=False


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


def test_demo_affiche_211_echanges():
    from track_b_accounting.demo import main

    out = io.StringIO()
    assert main(out=out) == 0
    texte = out.getvalue()
    assert texte.count("=== Échange ") == 211 and "Bilan : 109 ok, 102 refus, 0 erreur(s)." in texte
