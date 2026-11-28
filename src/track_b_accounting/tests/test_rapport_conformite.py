"""Rapport de conformité d'une fiche de paie : opération rapport_conformite du contrat v1 (D108, D109).

Le rapport assemble des réponses de calc/ : chaque montant de convention doit être celui que calc/ renvoie pour les
mêmes paramètres, et la seule opération faite ici est la différence « imprimé − convention », arrondie au millime.
Lancer depuis la racine du dépôt.
"""

import copy
import io
import json
from decimal import Decimal as D

import pytest
from conftest import REPO_ROOT
from jsonschema import Draft202012Validator

from track_b_accounting import demo_rapport
from track_b_accounting.calc import Refus, prime_v1, salaire_base, smig
from track_b_accounting.calc.models import arrondi_millime
from track_b_accounting.contract import cli, handle
from track_b_accounting.contract import handler as H
from track_b_accounting.rapport import conformite as C
from track_b_accounting.rapport import documents as DOCS

SCHEMAS = REPO_ROOT / "data" / "mock_cards" / "schemas"
REQ = json.loads((SCHEMAS / "track_b_rapport_request.v1.schema.json").read_text(encoding="utf-8"))
REP = json.loads((SCHEMAS / "track_b_rapport_response.v1.schema.json").read_text(encoding="utf-8"))
REQ_V, REP_V = Draft202012Validator(REQ), Draft202012Validator(REP)
DEMO_FILE = REPO_ROOT / "data" / "mock_cards" / "track_b_rapport_demo.v1.json"
REF_FILE = REPO_ROOT / "src" / "track_b_accounting" / "tests" / "references" / "track_b_rapport_demo.v1.json"
DEMOS = json.loads(DEMO_FILE.read_text(encoding="utf-8"))
PAR_ID = {d["request_id"]: d for d in DEMOS}
BM_PDF = "data/raw/pdf/الاتفاقية المشتركة القطاعية  للبناء المعدني.pdf"

FICHE_01 = {
    "secteur": "METALLURGIE_BATIMENT",
    "population": "admin_tech",
    "categorie": "3",
    "anciennete_annees": 6.49589,
    "date": "2026-03-01",
    "regime_heures": 48,
    "mode_paie": "mensuel",
    "salaire_base_imprime": "424.100",
    "primes_imprimees": [
        {"code": "prime_transport", "montant": "56.000"},
        {"code": "prime_presence", "montant": "36.000"},
    ],
    "documents_fournis": ["fiche_de_paie"],
}


def req(params: dict, lang: str = "fr", rid: str = "t-rapport") -> dict:
    return {
        "contract_version": "track_b.v1",
        "request_id": rid,
        "operation": "rapport_conformite",
        "params": params,
        "lang": lang,
    }


def valide(rep: dict) -> dict:
    erreurs = sorted(REP_V.iter_errors(rep), key=str)
    assert not erreurs, [e.message for e in erreurs]
    return rep


def rapport(params: dict) -> dict:
    rep = valide(handle(req(params)))
    assert rep["status"] == "ok", rep
    return rep


def ligne(rep: dict, rubrique: str, code: str | None = None) -> dict:
    (out,) = [x for x in rep["rapport"]["lignes"] if x["rubrique"] == rubrique and x["code"] == code]
    return out


# --- schémas et aiguillage -----------------------------------------------------------------------------------------


def test_schemas_bien_formes():
    for s in (REQ, REP):
        Draft202012Validator.check_schema(s)
        assert "v1 — proposition Track B, à valider avec l'équipe" in s["description"]
        assert "D108" in s["description"]


def test_schemas_v0_et_v1_existants_ne_connaissent_pas_l_operation():
    for v in ("v0", "v1"):
        s = json.loads((SCHEMAS / f"track_b_request.{v}.schema.json").read_text(encoding="utf-8"))
        assert "rapport_conformite" not in s["properties"]["operation"]["enum"]


def test_requete_v0_de_l_operation_reste_un_refus_de_contrat_v0():
    rep = handle(dict(req(FICHE_01), contract_version="track_b.v0"))
    assert rep["contract_version"] == "track_b.v0" and rep["status"] == "refus"
    assert rep["refus"]["code"] == "PARAM_INVALIDE"
    assert rep["refus"]["message_fr"].startswith("Requête non conforme au contrat track_b.v0")


@pytest.mark.parametrize(
    "alteration,chemin",
    [
        (lambda p: p.update(secteur=""), "params/secteur"),
        (lambda p: p.update(salaire_base_imprime=424.1), "params/salaire_base_imprime"),
        (lambda p: p.update(salaire_base_imprime="424,100"), "params/salaire_base_imprime"),
        (lambda p: p["primes_imprimees"][0].update(condition_remplie=True), "params/primes_imprimees/0"),
        (lambda p: p.update(inconnu=1), "params"),
        (lambda p: p.update(mode_paie="annuel"), "params/mode_paie"),
        (lambda p: p.update(documents_fournis=["releve_bancaire"]), "params/documents_fournis/0"),
        (lambda p: p.update(origines={"secteur": "devine"}), "params/origines/secteur"),
    ],
)
def test_requete_non_conforme_refus_de_contrat(alteration, chemin):
    p = copy.deepcopy(FICHE_01)
    alteration(p)
    rep = valide(handle(req(p)))
    assert rep["status"] == "refus" and rep["refus"]["code"] == "PARAM_INVALIDE"
    assert rep["computed_by"] == H.COMPUTED_BY_CONTRACT
    assert rep["refus"]["message_fr"].startswith(f"Requête non conforme au contrat track_b.v1 ({chemin})")
    assert rep["rapport"] is None and rep["texte_fr"] is None and rep["citations"] == []


def test_condition_remplie_jamais_acceptee_par_le_schema():
    """Une fiche de paie ne prouve pas une condition d'octroi : le paramètre n'existe pas dans le schéma."""
    props = REQ["properties"]["params"]["properties"]["primes_imprimees"]["items"]["properties"]
    assert "condition_remplie" not in props


@pytest.mark.parametrize("secteur", ["SECTEUR_FICTIF_NON_SUPPORTE", "metallurgie_batiment"])
def test_secteur_inconnu_refuse_le_rapport_entier(secteur):
    rep = valide(handle(req({"secteur": secteur, "categorie": "3"})))
    assert rep["status"] == "refus" and rep["refus"]["code"] == "SOURCE_MANQUANTE"
    assert rep["computed_by"] == H.COMPUTED_BY_RAPPORT
    assert rep["refus"]["message_fr"].startswith(f"Aucune grille vérifiée pour le secteur {secteur!r}")


def test_secteur_sans_table_transcrite_refuse(monkeypatch):
    vraie = C.charger_grille

    def sans_table(s):
        g = copy.deepcopy(vraie(s))
        g["_meta"]["tables_transcrites"] = False
        return g

    monkeypatch.setattr(C, "charger_grille", sans_table)
    rep = valide(handle(req(FICHE_01)))
    assert rep["status"] == "refus" and rep["refus"]["code"] == "SOURCE_MANQUANTE"


def test_erreur_interne_reponse_erreur_conforme(monkeypatch):
    def boom(**_):
        raise RuntimeError("panne")

    monkeypatch.setattr(C.calc, "salaire_base", boom)
    rep = valide(handle(req(FICHE_01)))
    assert rep["status"] == "erreur" and rep["rapport"] is None and "panne" not in json.dumps(rep)
    assert rep["contract_version"] == "track_b.v1"


def test_reponse_non_conforme_remplacee_par_erreur(monkeypatch):
    monkeypatch.setattr(H.rapport, "texte_fr", lambda r: "")
    rep = valide(handle(req(FICHE_01)))
    assert rep["status"] == "erreur" and rep["erreur"]["type"] == "ValueError"


# --- fiche 01 (ARRÊT 3, réponses a à e) ----------------------------------------------------------------------------


def test_fiche_01_salaire_non_verifiable_regime_different():
    rep = rapport(FICHE_01)
    s = ligne(rep, "salaire_base")
    assert (s["statut"], s["montant_convention"], s["montant_imprime"], s["difference"]) == (
        "non_verifiable",
        "641.013",
        "424.100",
        "-216.913",
    )
    assert s["motif"]["code"] == "REGIME_DIFFERENT"
    assert s["motif"]["message_fr"] == (
        "La grille est établie pour 42 h, la fiche indique 48 h ; aucune conversion n'est faite (D6)."
    )
    assert s["citations"] == [
        {
            "source_file": BM_PDF,
            "page": 34,
            "article": None,
            "data_file": "data/processed/salary_grids/metallurgie_batiment.json",
            "decision_ref": "D4",
        }
    ]


def test_fiche_01_primes_et_smig():
    rep = rapport(FICHE_01)
    t = ligne(rep, "prime", "prime_transport")
    assert t["statut"] == "non_verifiable" and t["motif"]["code"] == "GROUPE_NON_LU"
    assert t["montant_convention"] is None and t["citations"][0]["page"] == 16
    assert "92,800 TND/mois (execution_et_maitrise)" in t["motif"]["message_fr"]
    assert "100,533 TND/mois (cadres)" in t["motif"]["message_fr"]
    assert t["documents"] == ["attestation_classification"]
    p = ligne(rep, "prime", "prime_presence")
    assert (p["statut"], p["montant_convention"], p["difference"]) == ("conforme", "7.856", "28.144")
    lg = ligne(rep, "prime_absente", "prime_logement")
    assert (lg["statut"], lg["montant_convention"], lg["montant_imprime"]) == ("absente_de_la_fiche", "26.293", None)
    sm = ligne(rep, "smig")
    assert (sm["statut"], sm["montant_convention"], sm["difference"]) == ("ecart", "459.264", "-35.164")
    assert sm["hypotheses_fr"][-1] == "Comparaison faite avec le salaire de base imprimé seul, sans les primes."
    r = rep["rapport"]
    assert r["bilan"] == {"conforme": 1, "ecart": 1, "non_verifiable": 2, "absente_de_la_fiche": 1}
    assert r["aucune_ligne_verifiee"] is False
    assert [d["document"] for d in r["documents_manquants"]] == ["attestation_classification"]


def test_degre_et_anciennete_observation_jamais_un_ecart():
    sans = rapport(FICHE_01)
    avec = rapport(dict(FICHE_01, degre=2))
    s0, s1 = ligne(sans, "salaire_base"), ligne(avec, "salaire_base")
    assert {k: v for k, v in s1.items() if k != "observation"} == {k: v for k, v in s0.items() if k != "observation"}
    obs = s1["observation"]
    assert (obs["degre_imprime"], obs["degre_deduit"]) == ("2", "4")
    assert "L'échelon de la fiche peut ne pas correspondre au degré de la grille." in obs["message_fr"]
    assert avec["rapport"]["bilan"] == sans["rapport"]["bilan"]
    assert "Observation : Degré imprimé sur la fiche : 2" in avec["texte_fr"]


def test_comparaison_quand_les_regimes_sont_egaux():
    rep = rapport(dict(FICHE_01, regime_heures=42, salaire_base_imprime="700.000"))
    s = ligne(rep, "salaire_base")
    assert (s["statut"], s["difference"], s["motif"]) == ("conforme", "58.987", None)
    assert ligne(rep, "smig")["motif"]["code"] == "SOURCE_MANQUANTE"  # 42 h absent du barème : refus repris


def test_regime_de_la_fiche_non_lu_hypothese_et_comparaison():
    rep = rapport(dict(FICHE_01, regime_heures=None))
    s = ligne(rep, "salaire_base")
    assert s["statut"] == "ecart" and s["difference"] == "-216.913"
    assert "Régime horaire de la fiche non lu : la grille est établie pour 42 h." in s["hypotheses_fr"]
    assert "contrat_de_travail" in [d["document"] for d in rep["rapport"]["documents_manquants"]]


# --- fiche 02 (pièges) ---------------------------------------------------------------------------------------------


def test_fiche_02_refus_du_moteur_repris_et_origines():
    d = PAR_ID["demo-rapport-02-fiche02-pieges-refus-du-moteur"]
    rep = valide(handle(d))
    s = ligne(rep, "salaire_base")
    with pytest.raises(Refus) as e:
        salaire_base(secteur="METALLURGIE_BATIMENT", population="execution", categorie="2B", degre=7, date="2024-02-01")
    assert s["motif"] == {"code": e.value.code, "message_fr": e.value.message_fr, "message_ar": e.value.message_ar}
    assert s["statut"] == "non_verifiable" and s["montant_convention"] is None
    sm = ligne(rep, "smig")
    assert sm["motif"]["code"] == "CHAMP_ABSENT" and "« 195 h », aucune conversion fixe" in sm["motif"]["message_fr"]
    r = rep["rapport"]
    assert r["aucune_ligne_verifiee"] is True
    assert r["origines"] == {"secteur": "carte", "population": "utilisateur"}
    assert "Secteur : METALLURGIE_BATIMENT (pris dans la carte du dossier)" in rep["texte_fr"]
    assert "Population : execution (déclarée par l'utilisateur)" in rep["texte_fr"]
    assert "الفئة: execution (مصرح به من المستعمل)" in rep["texte_ar"]
    assert [x["document"] for x in r["documents_manquants"]] == ["contrat_de_travail", "attestation_classification"]


# --- règles de ligne -----------------------------------------------------------------------------------------------


def test_aucune_ligne_verifiee_phrase_en_tete():
    rep = valide(handle(PAR_ID["demo-rapport-07-aucune-ligne-verifiee"]))
    assert rep["rapport"]["aucune_ligne_verifiee"] is True and rep["citations"] == []
    fr = rep["texte_fr"].split("\n")
    assert "Aucune ligne n'a pu être vérifiée : ce rapport indique seulement ce qui manque pour conclure." in fr[:5]
    assert "لم يتسنّ التحقق من أي سطر: يبيّن هذا التقرير فقط ما ينقص للحسم." in rep["texte_ar"].split("\n")[:5]


def test_condition_non_verifiable_sans_montant():
    rep = valide(handle(PAR_ID["demo-rapport-05-condition-non-verifiable"]))
    x = ligne(rep, "prime", "prime_risque")
    assert x["statut"] == "non_verifiable" and x["motif"]["code"] == "CONDITION_NON_VERIFIABLE"
    assert x["montant_convention"] is None and x["difference"] is None
    assert "agent de maintenance ou de nettoyage du dépôt" in x["motif"]["message_fr"]
    assert x["citations"][0]["page"] == 16 and x["documents"] == ["attestation_employeur_prime"]


def test_unite_differente_grille_horaire():
    rep = rapport(
        dict(
            FICHE_01,
            population="execution",
            categorie="7",
            anciennete_annees=0.5,
            date="2024-06-01",
            primes_imprimees=[],
        )
    )
    s = ligne(rep, "salaire_base")
    assert (s["statut"], s["montant_convention"], s["unite"], s["difference"]) == (
        "non_verifiable",
        "4.449",
        "TND/heure",
        None,
    )
    assert s["motif"]["code"] == "UNITE_DIFFERENTE"


def test_prime_journaliere_unite_differente_et_transport_non_lu():
    p = dict(FICHE_01, primes_imprimees=[{"code": "prime_panier_qefa", "montant": "12.320"}])
    x = ligne(rapport(p), "prime", "prime_panier_qefa")
    assert x["motif"]["code"] == "TRANSPORT_NON_LU" and x["documents"] == ["attestation_employeur_prime"]
    p["primes_imprimees"][0]["transport_assure"] = False
    x = ligne(rapport(p), "prime", "prime_panier_qefa")
    assert (x["motif"]["code"], x["montant_convention"], x["unite"]) == ("UNITE_DIFFERENTE", "0.560", "TND/jour")


def test_prime_inconnue_refus_source_manquante_repris():
    p = dict(FICHE_01, primes_imprimees=[{"code": "prime_fictive", "montant": "10.000"}])
    x = ligne(rapport(p), "prime", "prime_fictive")
    with pytest.raises(Refus) as e:
        prime_v1("METALLURGIE_BATIMENT", "prime_fictive", "2026-03-01")
    assert x["motif"]["code"] == "SOURCE_MANQUANTE" and x["motif"]["message_fr"] == e.value.message_fr


def test_prime_avec_groupe_comparee():
    p = dict(
        FICHE_01, primes_imprimees=[{"code": "prime_transport", "montant": "92.800", "groupe": "execution_et_maitrise"}]
    )
    x = ligne(rapport(p), "prime", "prime_transport")
    assert (x["statut"], x["montant_convention"], x["difference"]) == ("conforme", "92.800", "0.000")
    p["primes_imprimees"][0]["montant"] = "56.000"
    x = ligne(rapport(p), "prime", "prime_transport")
    assert (x["statut"], x["difference"]) == ("ecart", "-36.800")


def test_primes_absentes_seulement_mensuelles_sans_condition_ni_groupe():
    rep = rapport(dict(FICHE_01, primes_imprimees=[]))
    assert [x["code"] for x in rep["rapport"]["lignes"] if x["rubrique"] == "prime_absente"] == [
        "prime_presence",
        "prime_logement",
    ]


def test_sans_date_aucune_prime_absente_et_champ_absent():
    rep = rapport(dict(FICHE_01, date=None))
    r = rep["rapport"]
    assert all(x["rubrique"] != "prime_absente" for x in r["lignes"])
    assert all(x["statut"] == "non_verifiable" for x in r["lignes"]) and r["aucune_ligne_verifiee"] is True
    assert {"champ": "date", "etat": "absent", "raison": None} in r["champs_manquants"]


def test_documents_fournis_retires_de_la_liste():
    rep = rapport(dict(FICHE_01, documents_fournis=["fiche_de_paie", "attestation_classification"]))
    assert rep["rapport"]["documents_manquants"] == []
    assert ligne(rep, "prime", "prime_transport")["documents"] == ["attestation_classification"]


def test_chaque_champ_a_un_document_connu():
    assert set(DOCS.CHAMPS) == set(
        REQ["properties"]["params"]["properties"]["champs_illisibles"]["propertyNames"]["enum"]
    )
    for _, _, d in DOCS.CHAMPS.values():
        assert d in DOCS.DOCUMENTS
    assert set(DOCS.DOCUMENTS) == set(REQ["properties"]["params"]["properties"]["documents_fournis"]["items"]["enum"])
    assert set(DOCS.CHAMPS_ATTENDUS) <= set(DOCS.CHAMPS)


# --- aucun montant hors du moteur ----------------------------------------------------------------------------------


def _montant_moteur(params: dict, x: dict) -> str:
    """Montant que calc/ renvoie pour la ligne x d'un rapport construit sur params."""
    if x["rubrique"] == "salaire_base":
        args = {
            k: params[k] for k in ("population", "categorie", "sous_categorie", "date") if params.get(k) is not None
        }
        if params.get("anciennete_annees") is not None:
            args["anciennete_annees"] = params["anciennete_annees"]
        elif params.get("degre") is not None:
            args["degre"] = params["degre"]
        return str(salaire_base(secteur=params["secteur"], **args).montant)
    if x["rubrique"] == "smig":
        return str(smig(mode=params["mode_paie"], regime_heures=params["regime_heures"], date=params["date"]).montant)
    imprimee: dict = next((p for p in params.get("primes_imprimees") or [] if p["code"] == x["code"]), {})
    extra = {k: v for k, v in imprimee.items() if k not in ("code", "montant")}
    return str(prime_v1(params["secteur"], x["code"], params["date"], **extra).montant)


@pytest.mark.parametrize("demo", DEMOS, ids=[d["request_id"] for d in DEMOS])
def test_montants_de_convention_venus_du_moteur_et_difference_au_millime(demo):
    rep = valide(handle(demo))
    if rep["status"] != "ok":
        return
    for x in rep["rapport"]["lignes"]:
        if x["montant_convention"] is not None:
            assert x["montant_convention"] == _montant_moteur(demo["params"], x)
            assert x["citations"], x
        if x["difference"] is not None:
            attendu = arrondi_millime(D(x["montant_imprime"]) - D(x["montant_convention"]))
            assert x["difference"] == str(attendu)
        if x["statut"] in ("conforme", "ecart"):
            assert (x["statut"] == "conforme") == (D(x["montant_imprime"]) >= D(x["montant_convention"]))
        if x["statut"] == "non_verifiable":
            assert x["motif"] is not None
    assert rep["citations"] == C.citations(rep["rapport"])


# --- démos et rendu ------------------------------------------------------------------------------------------------


def test_demos_conformes_et_au_moins_six_rapports():
    assert len(DEMOS) == len(PAR_ID) == 9
    for d in DEMOS:
        assert REQ_V.is_valid(d), d["request_id"]
        assert d["params"].get("anciennete_annees") is None or not isinstance(d["params"]["anciennete_annees"], bool)
    statuts = [valide(handle(d))["status"] for d in DEMOS]
    assert statuts.count("ok") >= 6 and statuts.count("refus") == 1 and "erreur" not in statuts


def test_demos_identiques_a_la_reference_a_l_octet():
    sortie = io.StringIO()
    assert cli.main([str(DEMO_FILE)], stdout=sortie) == 0
    assert sortie.getvalue() == REF_FILE.read_text(encoding="utf-8")


def test_demo_rapport_affiche_chaque_rendu_et_le_bilan():
    out = io.StringIO()
    assert demo_rapport.main(out=out) == 0
    texte = out.getvalue()
    assert texte.count("=== Rapport ") == 9
    assert texte.rstrip().endswith("Bilan rapports : 8 ok, 1 refus, 0 erreur(s).")
    assert "تقرير مطابقة كشف الأجر" in texte  # démos en arabe rendues en arabe


def test_rendu_deterministe_et_fixe():
    a, b = rapport(FICHE_01), rapport(FICHE_01)
    assert a["texte_fr"] == b["texte_fr"] and a["texte_ar"] == b["texte_ar"]
    fr = a["texte_fr"]
    assert fr.startswith("RAPPORT DE CONFORMITÉ D'UNE FICHE DE PAIE\n")
    assert "1. Salaire de base : non vérifiable" in fr
    assert "   Différence (imprimé − convention) : -216,913" in fr
    assert "4. Prime de logement : absente de la fiche" in fr
    assert "Signalée seulement : la fiche ne permet pas de dire si cette prime est due." in fr
    assert "Bilan : 1 conforme(s), 1 écart(s), 2 non vérifiable(s), 1 absente(s) de la fiche." in fr
    assert "page 2, décret gouvernemental n°769 du 2022-10-19 ; décision D2" in fr
    assert "الفارق (المطبوع − الاتفاقية): -216.913" in a["texte_ar"]


def test_decisions_d108_d109_presentes():
    texte = (REPO_ROOT / "docs" / "DECISIONS.md").read_text(encoding="utf-8")
    assert "### D108 — " in texte and "### D109 — " in texte
