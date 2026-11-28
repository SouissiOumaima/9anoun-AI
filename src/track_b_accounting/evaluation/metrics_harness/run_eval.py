"""Évaluation du Track B contre le jeu de référence lu dans les PDF (golden_sets/track_b_golden.v0.json).

Depuis la racine du dépôt :
    python src/track_b_accounting/evaluation/metrics_harness/run_eval.py --date 2026-10-09
    python src/track_b_accounting/evaluation/metrics_harness/run_eval.py --date 2026-10-09 --baseline

Appelle le handler en Python direct (track_b_accounting.contract.handle), comme l'orchestrateur.
Écrit results/eval_<date>.json et .md (ou results/baseline.json et .md avec --baseline).
Sortie déterministe : même commit + même --date ⇒ fichiers identiques à l'octet près.

Sans --baseline, les métriques de l'ensemble sont comparées automatiquement à results/baseline.json :
écart par métrique affiché et écrit dans results/eval_<date>_comparaison.json.

Tranche hors périmètre (D110) : golden_sets/track_b_hors_perimetre.v0.json, évaluée à part (les cas du jeu
principal ne changent pas). Métrique taux_refus_hors_perimetre = refus corrects (même code, motif attendu présent dans
message_fr) / cas hors périmètre ; seuil 85 % (cahier des charges §8.4) ; comparée à la baseline comme les autres.

Jeu du livrable (rapport de conformité, D108) : golden_sets/track_b_livrable.v0.json, évalué à part (bloc « livrable »
du rapport) ; ses métriques sont comparées à celles du bloc « livrable » de la baseline, quand il existe.

Code de sortie :
    1 s'il y a au moins un faux montant ou une exception inattendue (jeu principal, hors périmètre ou livrable) ;
    2 sinon, si au moins deux métriques baissent par rapport à la baseline (règle de régression) ;
    3 sinon, si taux_refus_hors_perimetre est sous le seuil de 85 % ;
    0 sinon.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import re
import sys
from pathlib import Path

# metrics_harness -> evaluation -> track_b_accounting -> src -> <racine>
REPO_ROOT = Path(__file__).resolve().parents[4]
EVAL_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from jsonschema import Draft202012Validator  # noqa: E402

from track_b_accounting.contract import handle  # noqa: E402

GOLDEN = EVAL_DIR / "golden_sets" / "track_b_golden.v0.json"
GOLDEN_HORS_PERIMETRE = EVAL_DIR / "golden_sets" / "track_b_hors_perimetre.v0.json"
SCHEMA_TB = REPO_ROOT / "data" / "mock_cards" / "schemas" / "track_b_response.v0.schema.json"
# Cas dont la requête porte contract_version = track_b.v1 (D75) : réponse validée avec le schéma v1.
SCHEMA_TB_V1 = REPO_ROOT / "data" / "mock_cards" / "schemas" / "track_b_response.v1.schema.json"
SCHEMA_COMMUN = REPO_ROOT / "src" / "shared" / "schemas" / "common.v0.schema.json"
DECISIONS = REPO_ROOT / "docs" / "DECISIONS.md"
# Livrable : rapport de conformité d'une fiche de paie (opération rapport_conformite du contrat v1, D108, D109).
GOLDEN_LIVRABLE = EVAL_DIR / "golden_sets" / "track_b_livrable.v0.json"
SCHEMA_RAPPORT = REPO_ROOT / "data" / "mock_cards" / "schemas" / "track_b_rapport_response.v1.schema.json"

# Verdicts d'un cas. Les deux premiers sont critiques (« Citation ou Silence »).
CORRECT = "correct"
FAUX_MONTANT = "faux_montant"  # ok attendu, montant ou unité différents
MONTANT_AU_LIEU_DE_REFUS = "montant_au_lieu_de_refus"  # refus attendu, ok renvoyé
SILENCE_EXCESSIF = "silence_excessif"  # ok attendu, refus renvoyé
CODE_INCORRECT = "code_refus_incorrect"  # refus attendu, autre code
MESSAGE_INCORRECT = "message_refus_incorrect"  # bon code, mais message FR ou AR différent de celui attendu
ERREUR = "statut_erreur"  # réponse status = erreur
EXCEPTION = "exception_inattendue"  # le handler a levé une exception
CRITIQUES = (FAUX_MONTANT, MONTANT_AU_LIEU_DE_REFUS)
# Verdicts propres au livrable. Un faux montant y est une ligne dont le montant de convention, l'unité ou la
# différence diffère de l'attendu (y compris un montant donné là où l'attendu n'en a pas).
LIGNES_DIFFERENTES = "lignes_differentes"  # lignes manquantes, en trop ou dans un autre ordre
STATUT_LIGNE_INCORRECT = "statut_ligne_incorrect"  # bon montant, mais statut ou motif différent
DOCUMENTS_INCORRECTS = "documents_incorrects"  # documents manquants ou drapeau aucune_ligne_verifiee différents
CHAMPS_MONTANT = ("montant_convention", "unite", "difference")

RESULTS_DIR = EVAL_DIR / "results"
BASELINE = RESULTS_DIR / "baseline.json"

# Sens de chaque métrique comparée à la baseline : +1 = plus haut est meilleur, -1 = plus bas est meilleur.
# faux_montants_total n'est pas comparé : il additionne faux_montants et montants_au_lieu_de_refus.
SENS_METRIQUES = {
    "exactitude_montants": 1,
    "refus_corrects": 1,
    "citations_valides": 1,
    "conformite_schema_track_b": 1,
    "conformite_schema_commun": 1,
    "faux_montants": -1,
    "montants_au_lieu_de_refus": -1,
    "silence_excessif": -1,
    "codes_refus_incorrects": -1,
    "messages_refus_incorrects": -1,
    "statut_erreur": -1,
    "exceptions_inattendues": -1,
    "taux_refus_hors_perimetre": 1,
}
SEUIL_BAISSES = 2  # nombre de métriques en baisse qui bloque le changement
SEUIL_HORS_PERIMETRE = 0.85  # taux de refus corrects exigé sur la tranche hors périmètre (cahier des charges §8.4)
SENS_LIVRABLE = {
    "cas_corrects": 1,
    "lignes_correctes": 1,
    "refus_corrects": 1,
    "citations_valides": 1,
    "conformite_schema_rapport": 1,
    "faux_montants": -1,
    "statuts_incorrects": -1,
    "statut_erreur": -1,
    "exceptions_inattendues": -1,
}
STABLE, AMELIORATION, BAISSE, NON_COMPARABLE = "stable", "amélioration", "baisse", "non comparable"
CODE_CRITIQUE, CODE_REGRESSION, CODE_SEUIL_HORS_PERIMETRE = 1, 2, 3


def _sha256(p: Path) -> str:
    """Empreinte du fichier, fins de ligne normalisées (CRLF → LF) : identique sous Windows, Linux et macOS."""
    return hashlib.sha256(p.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def _validateur(chemin: Path) -> Draft202012Validator:
    return Draft202012Validator(json.loads(chemin.read_text(encoding="utf-8")))


def _requete(c: dict) -> dict:
    return {"contract_version": "track_b.v0", "request_id": c["id"], **c["requete"]}


def _verdict(attendu: dict, rep: dict) -> str:
    if rep["status"] == "erreur":
        return ERREUR
    if attendu["status"] == "ok":
        if rep["status"] == "refus":
            return SILENCE_EXCESSIF
        r = rep["result"]
        return CORRECT if (r["montant"], r["unite"]) == (attendu["montant"], attendu["unite"]) else FAUX_MONTANT
    if rep["status"] == "ok":
        return MONTANT_AU_LIEU_DE_REFUS
    if rep["refus"]["code"] != attendu["code"]:
        return CODE_INCORRECT
    # Messages comparés seulement quand le cas les fixe (message_fr, message_ar).
    if any(k in attendu and rep["refus"][k] != attendu[k] for k in ("message_fr", "message_ar")):
        return MESSAGE_INCORRECT
    # Tranche hors périmètre (D110) : le motif attendu doit figurer dans le message FR.
    if "message_fr_contient" in attendu and attendu["message_fr_contient"] not in rep["refus"]["message_fr"]:
        return MESSAGE_INCORRECT
    return CORRECT


def _citations_valides(attendu: dict, rep: dict, refs: set[str]) -> list[str]:
    """Écarts entre les citations renvoyées et celles attendues (PDF et page lus dans le golden set)."""
    problemes = []
    obtenues = rep["citations"]
    if len(obtenues) != len(attendu["citations"]):
        problemes.append(f"{len(obtenues)} citation(s) au lieu de {len(attendu['citations'])}")
    for att, c in zip(attendu["citations"], obtenues):
        if Path(c["source_file"]).name != att["pdf"]:
            problemes.append(f"PDF cité {Path(c['source_file']).name!r} ≠ {att['pdf']!r}")
        if c["page"] != att["page"]:
            problemes.append(f"page citée {c['page']} ≠ {att['page']}")
        if not (REPO_ROOT / c["source_file"]).is_file():
            problemes.append(f"source_file introuvable : {c['source_file']}")
        if not (REPO_ROOT / c["data_file"]).is_file():
            problemes.append(f"data_file introuvable : {c['data_file']}")
        if c["decision_ref"] not in refs:
            problemes.append(f"decision_ref {c['decision_ref']} absente de docs/DECISIONS.md")
    return problemes


def evaluer_cas(c: dict, refs: set[str], v_tb, v_commun, v_tb_v1=None) -> dict:
    """v_tb : schéma de réponse Track B v0 ; v_tb_v1 : schéma v1, pour une réponse en track_b.v1."""
    out = {
        "id": c["id"],
        "categorie": c["categorie"],
        "certitude": c["certitude"],
        "decision": c["decision"],
        "verification_humaine": c["verification_humaine"],
        "attendu": c["attendu"],
    }
    try:
        rep = json.loads(json.dumps(handle(_requete(c)), ensure_ascii=False))  # telle qu'elle circule en JSON
    except Exception as exc:  # noqa: BLE001
        # Erreur inattendue : enregistrée comme échec, l'évaluation continue.
        out.update(
            verdict=EXCEPTION,
            obtenu={"exception": type(exc).__name__, "message": str(exc)[:300]},
            citations_ok=None,
            problemes_citations=[],
            conforme_schema_track_b=None,
            conforme_schema_commun=None,
        )
        return out
    obtenu = {"status": rep["status"]}
    if rep["status"] == "ok":
        obtenu.update(
            montant=rep["result"]["montant"],
            unite=rep["result"]["unite"],
            citations=[
                {"pdf": Path(x["source_file"]).name, "page": x["page"], "decision_ref": x["decision_ref"]}
                for x in rep["citations"]
            ],
        )
    elif rep["status"] == "refus":
        obtenu.update(code=rep["refus"]["code"], message_fr=rep["refus"]["message_fr"])
        if "message_ar" in c["attendu"]:
            obtenu["message_ar"] = rep["refus"]["message_ar"]
    else:
        obtenu.update(erreur=rep["erreur"]["type"])
    verdict = _verdict(c["attendu"], rep)
    problemes = (
        _citations_valides(c["attendu"], rep, refs) if rep["status"] == "ok" and c["attendu"]["status"] == "ok" else []
    )
    out.update(
        verdict=verdict,
        obtenu=obtenu,
        citations_ok=(not problemes) if rep["status"] == "ok" and c["attendu"]["status"] == "ok" else None,
        problemes_citations=problemes,
        conforme_schema_track_b=(
            v_tb_v1 if v_tb_v1 is not None and rep.get("contract_version") == "track_b.v1" else v_tb
        ).is_valid(rep),
        conforme_schema_commun=v_commun.is_valid(rep),
    )
    return out


def _ligne_comparee(ligne: dict) -> dict:
    """Projection d'une ligne de rapport sur les champs du jeu du livrable."""
    return {
        "rubrique": ligne["rubrique"],
        "code": ligne["code"],
        "statut": ligne["statut"],
        "montant_convention": ligne["montant_convention"],
        "unite": ligne["unite"],
        "difference": ligne["difference"],
        "motif": ligne["motif"]["code"] if ligne["motif"] else None,
        "citations": [{"pdf": Path(c["source_file"]).name, "page": c["page"]} for c in ligne["citations"]],
    }


def evaluer_cas_livrable(c: dict, refs: set[str], v_rapport) -> dict:
    """Un cas du jeu du livrable : requête rapport_conformite en track_b.v1, lignes comparées une à une."""
    out: dict = {
        "id": c["id"],
        "categorie": c["categorie"],
        "certitude": c["certitude"],
        "decision": c["decision"],
        "verification_humaine": c["verification_humaine"],
        "attendu": c["attendu"],
        "lignes": 0,
        "lignes_correctes": 0,
        "faux_montants": 0,
        "statuts_incorrects": 0,
        "problemes_citations": [],
        "citations_ok": None,
    }
    requete = {"contract_version": "track_b.v1", "request_id": c["id"], **c["requete"]}
    try:
        rep = json.loads(json.dumps(handle(requete), ensure_ascii=False))
    except Exception as exc:  # noqa: BLE001
        out.update(
            verdict=EXCEPTION,
            obtenu={"exception": type(exc).__name__, "message": str(exc)[:300]},
            conforme_schema=None,
        )
        return out
    att = c["attendu"]
    out["conforme_schema"] = v_rapport.is_valid(rep)
    out["obtenu"] = {"status": rep["status"]}
    if rep["status"] == "erreur":
        out.update(verdict=ERREUR, obtenu={"status": "erreur", "erreur": rep["erreur"]["type"]})
        return out
    if att["status"] == "refus":
        if rep["status"] == "ok":
            out["verdict"] = MONTANT_AU_LIEU_DE_REFUS
        else:
            out["obtenu"]["code"] = rep["refus"]["code"]
            out["verdict"] = CORRECT if rep["refus"]["code"] == att["code"] else CODE_INCORRECT
        return out
    if rep["status"] == "refus":
        out.update(verdict=SILENCE_EXCESSIF, obtenu={"status": "refus", "code": rep["refus"]["code"]})
        return out
    r = rep["rapport"]
    obtenues = [_ligne_comparee(x) for x in r["lignes"]]
    documents = [d["document"] for d in r["documents_manquants"]]
    out["obtenu"].update(
        lignes=obtenues, documents_manquants=documents, aucune_ligne_verifiee=r["aucune_ligne_verifiee"]
    )
    attendues = att["lignes"]
    structure = [(x["rubrique"], x["code"]) for x in attendues] != [(x["rubrique"], x["code"]) for x in obtenues]
    out["lignes"] = len(attendues)
    for a, o in zip(attendues, obtenues):
        if any(a[k] != o[k] for k in CHAMPS_MONTANT):
            out["faux_montants"] += 1
        elif (a["statut"], a["motif"]) != (o["statut"], o["motif"]):
            out["statuts_incorrects"] += 1
        else:
            out["lignes_correctes"] += 1
        if a["citations"] != o["citations"]:
            out["problemes_citations"].append(f"{a['rubrique']} {a['code']} : citations {o['citations']}")
    for x in r["lignes"]:
        for cit in x["citations"]:
            if not (REPO_ROOT / cit["source_file"]).is_file() or not (REPO_ROOT / cit["data_file"]).is_file():
                out["problemes_citations"].append(f"fichier cité introuvable : {cit['source_file']}")
            if cit["decision_ref"] not in refs:
                out["problemes_citations"].append(f"decision_ref {cit['decision_ref']} absente de docs/DECISIONS.md")
    out["citations_ok"] = not out["problemes_citations"]
    if out["faux_montants"]:
        out["verdict"] = FAUX_MONTANT
    elif structure:
        out["verdict"] = LIGNES_DIFFERENTES
    elif out["statuts_incorrects"]:
        out["verdict"] = STATUT_LIGNE_INCORRECT
    elif documents != att["documents_manquants"] or r["aucune_ligne_verifiee"] != att["aucune_ligne_verifiee"]:
        out["verdict"] = DOCUMENTS_INCORRECTS
    else:
        out["verdict"] = CORRECT
    return out


def metriques_livrable(res: list[dict]) -> dict:
    refus_att = [r for r in res if r["attendu"]["status"] == "refus"]
    avec_cit = [r for r in res if r["citations_ok"] is not None]
    evalues = [r for r in res if r["conforme_schema"] is not None]
    return {
        "cas": len(res),
        "cas_corrects": _taux(sum(r["verdict"] == CORRECT for r in res), len(res)),
        "lignes_correctes": _taux(sum(r["lignes_correctes"] for r in res), sum(r["lignes"] for r in res)),
        "faux_montants": sum(r["faux_montants"] for r in res)
        + sum(r["verdict"] == MONTANT_AU_LIEU_DE_REFUS for r in res),
        "statuts_incorrects": sum(r["statuts_incorrects"] for r in res),
        "refus_corrects": _taux(sum(r["verdict"] == CORRECT for r in refus_att), len(refus_att)),
        "citations_valides": _taux(sum(bool(r["citations_ok"]) for r in avec_cit), len(avec_cit)),
        "conformite_schema_rapport": _taux(sum(bool(r["conforme_schema"]) for r in evalues), len(evalues)),
        "statut_erreur": sum(r["verdict"] == ERREUR for r in res),
        "exceptions_inattendues": sum(r["verdict"] == EXCEPTION for r in res),
    }


def bloc_livrable(golden: dict, res: list[dict]) -> dict:
    return {
        "golden_set": {
            "fichier": GOLDEN_LIVRABLE.relative_to(REPO_ROOT).as_posix(),
            "version": golden["version"],
            "sha256": _sha256(GOLDEN_LIVRABLE),
            "cas": len(res),
            "cas_verifies_par_ds5": sum(bool(r["verification_humaine"]) for r in res),
        },
        "metriques": metriques_livrable(res),
        "echecs": [
            r["id"]
            for r in res
            if r["verdict"] != CORRECT or r["citations_ok"] is False or r["conforme_schema"] is False
        ],
        "cas": res,
    }


def _taux(n: int, d: int) -> dict:
    return {"n": n, "sur": d, "taux": None if d == 0 else round(n / d, 4)}


def metriques(res: list[dict]) -> dict:
    ok_att = [r for r in res if r["attendu"]["status"] == "ok"]
    refus_att = [r for r in res if r["attendu"]["status"] == "refus"]
    avec_cit = [r for r in res if r["citations_ok"] is not None]
    evalues = [r for r in res if r["conforme_schema_track_b"] is not None]
    m = {
        "cas": len(res),
        "faux_montants": _taux(sum(r["verdict"] == FAUX_MONTANT for r in ok_att), len(ok_att)),
        "montants_au_lieu_de_refus": _taux(
            sum(r["verdict"] == MONTANT_AU_LIEU_DE_REFUS for r in refus_att), len(refus_att)
        ),
        "exactitude_montants": _taux(sum(r["verdict"] == CORRECT for r in ok_att), len(ok_att)),
        "silence_excessif": _taux(sum(r["verdict"] == SILENCE_EXCESSIF for r in ok_att), len(ok_att)),
        "refus_corrects": _taux(sum(r["verdict"] == CORRECT for r in refus_att), len(refus_att)),
        "codes_refus_incorrects": _taux(sum(r["verdict"] == CODE_INCORRECT for r in refus_att), len(refus_att)),
        "messages_refus_incorrects": _taux(sum(r["verdict"] == MESSAGE_INCORRECT for r in refus_att), len(refus_att)),
        "citations_valides": _taux(sum(bool(r["citations_ok"]) for r in avec_cit), len(avec_cit)),
        "conformite_schema_track_b": _taux(sum(bool(r["conforme_schema_track_b"]) for r in evalues), len(evalues)),
        "conformite_schema_commun": _taux(sum(bool(r["conforme_schema_commun"]) for r in evalues), len(evalues)),
        "statut_erreur": sum(r["verdict"] == ERREUR for r in res),
        "exceptions_inattendues": sum(r["verdict"] == EXCEPTION for r in res),
    }
    m["faux_montants_total"] = m["faux_montants"]["n"] + m["montants_au_lieu_de_refus"]["n"]
    return m


def _echec(r: dict) -> bool:
    return (
        r["verdict"] != CORRECT
        or r["citations_ok"] is False
        or r["conforme_schema_track_b"] is False
        or r["conforme_schema_commun"] is False
    )


def taux_refus_hors_perimetre(res_hp: list[dict]) -> dict:
    """Refus corrects (code et motif attendus) sur les cas hors périmètre."""
    return _taux(sum(r["verdict"] == CORRECT for r in res_hp), len(res_hp))


def rapport(
    golden: dict,
    res: list[dict],
    date: str,
    golden_hp: dict | None = None,
    res_hp: list[dict] | None = None,
    livrable: dict | None = None,
) -> dict:
    lecture = [r for r in res if r["certitude"] in ("L", "C")]
    verifies = [r for r in res if r["verification_humaine"]]
    ensemble = metriques(res)
    extra: dict = {}
    if golden_hp is not None and res_hp is not None:
        ensemble["taux_refus_hors_perimetre"] = taux_refus_hors_perimetre(res_hp)
        extra = {
            "hors_perimetre": {
                "fichier": GOLDEN_HORS_PERIMETRE.relative_to(REPO_ROOT).as_posix(),
                "version": golden_hp["version"],
                "sha256": _sha256(GOLDEN_HORS_PERIMETRE),
                "cas": len(res_hp),
                "seuil": SEUIL_HORS_PERIMETRE,
                "taux_refus_hors_perimetre": ensemble["taux_refus_hors_perimetre"],
                "seuil_atteint": _seuil_atteint(ensemble["taux_refus_hors_perimetre"]),
                "metriques": metriques(res_hp),
                "echecs": [r["id"] for r in res_hp if _echec(r)],
                "cas_detail": res_hp,
            }
        }
    rap = {
        "evaluation": "track_b",
        "date": date,
        "golden_set": {
            "fichier": GOLDEN.relative_to(REPO_ROOT).as_posix(),
            "version": golden["version"],
            "sha256": _sha256(GOLDEN),
            "cas": len(res),
            "cas_verifies_par_ds5": len(verifies),
        },
        "metriques": {
            "ensemble": ensemble,
            "cas_verifies": metriques(verifies),
            "par_certitude": {k: metriques([r for r in res if r["certitude"] == k]) for k in ("L", "C", "I")},
            "par_categorie": {
                k: metriques([r for r in res if r["categorie"] == k]) for k in ("ok", "art13", "refus", "piege")
            },
        },
        # Un échec sur un cas L ou C = erreur de lecture (du golden set ou du code) ; sur un cas I = désaccord d'interprétation.
        "erreurs_de_lecture": [r["id"] for r in lecture if _echec(r)],
        "desaccords_interpretation": [r["id"] for r in res if r["certitude"] == "I" and _echec(r)],
        "cas": res,
        **extra,
    }
    if livrable is not None:
        rap["livrable"] = livrable
    return rap


def _seuil_atteint(t: dict) -> bool:
    return t["taux"] is not None and t["taux"] >= SEUIL_HORS_PERIMETRE


def _ligne_taux(nom: str, t: dict) -> str:
    pct = "—" if t["taux"] is None else f"{100 * t['taux']:.1f} %"
    return f"| {nom} | {t['n']} / {t['sur']} | {pct} |"


def markdown(rap: dict) -> str:
    g, m = rap["golden_set"], rap["metriques"]
    lignes = [
        f"# Évaluation Track B — {rap['date']}",
        "",
        f"Jeu de référence : `{g['fichier']}` ({g['version']}, {g['cas']} cas, sha256 `{g['sha256'][:12]}…`).",
        f"Cas vérifiés sur les PDF par DS5 : **{g['cas_verifies_par_ds5']} / {g['cas']}**.",
        "",
        f"**Faux montants : {m['ensemble']['faux_montants_total']}** "
        "(montant faux pour un ok attendu, ou montant renvoyé alors qu'un refus était attendu).",
        "",
    ]
    for titre, cle in (("Ensemble des cas", "ensemble"), ("Cas vérifiés par DS5", "cas_verifies")):
        mm = m[cle]
        lignes += [
            f"## {titre} ({mm['cas']} cas)",
            "",
            "| Métrique | Nombre | Taux |",
            "|---|---|---|",
            _ligne_taux("Faux montants (ok attendu)", mm["faux_montants"]),
            _ligne_taux("Montant au lieu d'un refus", mm["montants_au_lieu_de_refus"]),
            _ligne_taux("Exactitude des montants", mm["exactitude_montants"]),
            _ligne_taux("Silence excessif", mm["silence_excessif"]),
            _ligne_taux("Refus corrects (même code ; même message s'il est fixé)", mm["refus_corrects"]),
            _ligne_taux("Messages de refus différents de l'attendu", mm["messages_refus_incorrects"]),
            _ligne_taux("Citations valides", mm["citations_valides"]),
            _ligne_taux("Conformité schéma Track B", mm["conformite_schema_track_b"]),
            _ligne_taux("Conformité schéma commun", mm["conformite_schema_commun"]),
            f"| Statut erreur / exceptions | {mm['statut_erreur']} / {mm['exceptions_inattendues']} | |",
            "",
        ]
    hp = rap.get("hors_perimetre")
    if hp is not None:
        t = hp["taux_refus_hors_perimetre"]
        lignes += [
            f"## Hors périmètre ({hp['cas']} cas, D110)",
            "",
            f"Jeu : `{hp['fichier']}` ({hp['version']}, sha256 `{hp['sha256'][:12]}…`).",
            "",
            "| Métrique | Nombre | Taux |",
            "|---|---|---|",
            _ligne_taux("Taux de refus hors périmètre (code et motif attendus)", t),
            _ligne_taux("Montant au lieu d'un refus", hp["metriques"]["montants_au_lieu_de_refus"]),
            _ligne_taux("Conformité schéma Track B", hp["metriques"]["conformite_schema_track_b"]),
            "",
            f"Seuil : {100 * hp['seuil']:.0f} % ; **{'atteint' if hp['seuil_atteint'] else 'non atteint'}**. "
            f"Échecs : {', '.join(hp['echecs']) or 'aucun'}.",
            "",
            "| Cas | Thème | Attendu | Obtenu | Verdict |",
            "|---|---|---|---|---|",
        ]
        for r in hp["cas_detail"]:
            o = r["obtenu"]
            obt = o.get("code") or o.get("status") or o.get("exception")
            lignes.append(f"| {r['id']} | {r['theme']} | {r['attendu']['code']} | {obt} | {r['verdict']} |")
        lignes.append("")
    lignes += [
        "## Par certitude",
        "",
        "| Certitude | Cas | Exactitude montants | Refus corrects | Faux montants |",
        "|---|---|---|---|---|",
    ]
    for k, mm in m["par_certitude"].items():
        ex, rc = mm["exactitude_montants"], mm["refus_corrects"]
        lignes.append(
            f"| {k} | {mm['cas']} | {ex['n']} / {ex['sur']} | {rc['n']} / {rc['sur']} | {mm['faux_montants_total']} |"
        )
    lignes += [
        "",
        "L = lu dans le PDF, C = calculé à la main, I = interprétation (Dn). Un échec sur un cas I est un "
        "désaccord d'interprétation, pas une erreur de lecture.",
        "",
        f"- Erreurs de lecture (cas L ou C en échec) : {', '.join(rap['erreurs_de_lecture']) or 'aucune'}",
        f"- Désaccords d'interprétation (cas I en échec) : {', '.join(rap['desaccords_interpretation']) or 'aucun'}",
        "",
        "## Détail des cas",
        "",
        "| Cas | Cat. | Cert. | Vérifié | Attendu | Obtenu | Verdict |",
        "|---|---|---|---|---|---|---|",
    ]
    for r in rap["cas"]:
        a, o = r["attendu"], r["obtenu"]
        att = f"{a['montant']} {a['unite']}" if a["status"] == "ok" else a["code"]
        obt = (
            f"{o['montant']} {o['unite']}"
            if o.get("status") == "ok"
            else o.get("code") or o.get("erreur") or o.get("exception")
        )
        v = r["verdict"] + (
            "" if r["citations_ok"] is not False else " ; citations : " + " ; ".join(r["problemes_citations"])
        )
        lignes.append(
            f"| {r['id']} | {r['categorie']} | {r['certitude']}{' ' + r['decision'] if r['decision'] else ''} "
            f"| {'oui' if r['verification_humaine'] else 'non'} | {att} | {obt} | {v} |"
        )
    if "livrable" in rap:
        lignes += markdown_livrable(rap["livrable"])
    return "\n".join(lignes) + "\n"


def markdown_livrable(liv: dict) -> list[str]:
    g, m = liv["golden_set"], liv["metriques"]
    lignes = [
        "",
        f"## Livrable : rapport de conformité ({g['cas']} cas, D108, D109)",
        "",
        f"Jeu de référence : `{g['fichier']}` ({g['version']}, sha256 `{g['sha256'][:12]}…`). "
        f"Cas vérifiés par DS5 : **{g['cas_verifies_par_ds5']} / {g['cas']}**.",
        "",
        f"**Faux montants (lignes) : {m['faux_montants']}**",
        "",
        "| Métrique | Nombre | Taux |",
        "|---|---|---|",
        _ligne_taux("Cas corrects", m["cas_corrects"]),
        _ligne_taux("Lignes correctes (montant, différence, statut, motif)", m["lignes_correctes"]),
        _ligne_taux("Refus corrects", m["refus_corrects"]),
        _ligne_taux("Citations valides", m["citations_valides"]),
        _ligne_taux("Conformité schéma du rapport", m["conformite_schema_rapport"]),
        f"| Statuts incorrects | {m['statuts_incorrects']} | |",
        f"| Statut erreur / exceptions | {m['statut_erreur']} / {m['exceptions_inattendues']} | |",
        "",
        "| Cas | Vérifié | Attendu | Verdict |",
        "|---|---|---|---|",
    ]
    for r in liv["cas"]:
        a = r["attendu"]
        att = a["code"] if a["status"] == "refus" else f"{len(a['lignes'])} lignes"
        lignes.append(f"| {r['id']} | {'oui' if r['verification_humaine'] else 'non'} | {att} | {r['verdict']} |")
    return lignes


def _valeur(m: object) -> float | int | None:
    """Valeur comparée d'une métrique : le taux pour un ratio, le nombre pour un compteur."""
    if isinstance(m, dict):
        return m.get("taux")
    return m if isinstance(m, (int, float)) and not isinstance(m, bool) else None


def comparer(baseline: dict, actuel: dict, sens_metriques: dict[str, int] | None = None) -> list[dict]:
    """Écart, métrique par métrique, entre les métriques « ensemble » de la baseline et celles de la relance
    (ou celles du livrable, avec sens_metriques=SENS_LIVRABLE)."""
    ecarts = []
    for nom, sens in (SENS_METRIQUES if sens_metriques is None else sens_metriques).items():
        b, a = _valeur(baseline.get(nom)), _valeur(actuel.get(nom))
        if b is None or a is None:
            statut, ecart = NON_COMPARABLE, None
        else:
            ecart = round(a - b, 4)
            statut = STABLE if ecart == 0 else AMELIORATION if ecart * sens > 0 else BAISSE
        ecarts.append({"metrique": nom, "baseline": b, "actuel": a, "ecart": ecart, "statut": statut})
    return ecarts


def baisses(ecarts: list[dict]) -> list[str]:
    return [e["metrique"] for e in ecarts if e["statut"] == BAISSE]


def code_sortie(m: dict, ecarts: list[dict] | None, m_hp: dict | None = None, m_livrable: dict | None = None) -> int:
    """1 : faux montant ou exception (m, m_hp pour la tranche hors périmètre, m_livrable pour le livrable) ;
    2 : au moins SEUIL_BAISSES métriques en baisse ; 3 : taux_refus_hors_perimetre sous SEUIL_HORS_PERIMETRE ;
    0 sinon."""
    if any(x is not None and (x["faux_montants_total"] or x["exceptions_inattendues"]) for x in (m, m_hp)):
        return CODE_CRITIQUE
    if m_livrable is not None and (m_livrable["faux_montants"] or m_livrable["exceptions_inattendues"]):
        return CODE_CRITIQUE
    if ecarts is not None and len(baisses(ecarts)) >= SEUIL_BAISSES:
        return CODE_REGRESSION
    t = m.get("taux_refus_hors_perimetre")
    if isinstance(t, dict) and not _seuil_atteint(t):
        return CODE_SEUIL_HORS_PERIMETRE
    return 0


def texte_comparaison(ecarts: list[dict], cas_baseline: object, cas_actuel: object) -> str:
    def fmt(v: object) -> str:
        return "—" if v is None else str(v)

    lignes = [f"Comparaison à la baseline ({cas_baseline} cas -> {cas_actuel} cas) :"]
    for e in ecarts:
        lignes.append(
            f"  {e['metrique']:28s} {fmt(e['baseline']):>8s} -> {fmt(e['actuel']):<8s} "
            f"écart {fmt(e['ecart']):>8s}  {e['statut']}"
        )
    b = baisses(ecarts)
    lignes.append(
        f"Métriques en baisse : {len(b)} ({', '.join(b) or 'aucune'}) ; "
        f"le changement est bloqué à partir de {SEUIL_BAISSES}."
    )
    return "\n".join(lignes)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--date", required=True, help="date du rapport (AAAA-MM-JJ), écrite telle quelle : aucune horloge")
    ap.add_argument("--baseline", action="store_true", help="écrit results/baseline.json et .md")
    args = ap.parse_args(argv)
    dt.date.fromisoformat(args.date)
    golden = json.loads(GOLDEN.read_text(encoding="utf-8"))
    refs = set(re.findall(r"^### (D[0-9]+)\b", DECISIONS.read_text(encoding="utf-8"), flags=re.M))
    v_tb, v_commun, v_tb_v1 = _validateur(SCHEMA_TB), _validateur(SCHEMA_COMMUN), _validateur(SCHEMA_TB_V1)
    res = [evaluer_cas(c, refs, v_tb, v_commun, v_tb_v1) for c in golden["cases"]]
    golden_hp = json.loads(GOLDEN_HORS_PERIMETRE.read_text(encoding="utf-8"))
    res_hp = [dict(evaluer_cas(c, refs, v_tb, v_commun, v_tb_v1), theme=c["theme"]) for c in golden_hp["cases"]]
    golden_l = json.loads(GOLDEN_LIVRABLE.read_text(encoding="utf-8"))
    v_rapport = _validateur(SCHEMA_RAPPORT)
    livrable = bloc_livrable(golden_l, [evaluer_cas_livrable(c, refs, v_rapport) for c in golden_l["cases"]])
    rap = rapport(golden, res, args.date, golden_hp, res_hp, livrable)
    nom = "baseline" if args.baseline else f"eval_{args.date}"
    sortie = RESULTS_DIR
    sortie.mkdir(exist_ok=True)
    (sortie / f"{nom}.json").write_text(
        json.dumps(rap, ensure_ascii=False, indent=1, sort_keys=True) + "\n", encoding="utf-8", newline="\n"
    )
    (sortie / f"{nom}.md").write_text(markdown(rap), encoding="utf-8", newline="\n")
    m = rap["metriques"]["ensemble"]
    print(
        f"{m['cas']} cas, faux montants : {m['faux_montants_total']}, exceptions : {m['exceptions_inattendues']}, "
        f"erreurs de lecture : {rap['erreurs_de_lecture'] or 'aucune'}, "
        f"désaccords d'interprétation : {rap['desaccords_interpretation'] or 'aucun'} -> results/{nom}.json, .md"
    )
    hp = rap["hors_perimetre"]
    t = hp["taux_refus_hors_perimetre"]
    print(
        f"Hors périmètre : {t['n']} / {t['sur']} refus corrects, taux_refus_hors_perimetre = {100 * t['taux']:.1f} % "
        f"(seuil {100 * SEUIL_HORS_PERIMETRE:.0f} % : {'atteint' if hp['seuil_atteint'] else 'NON ATTEINT'}), "
        f"faux montants : {hp['metriques']['faux_montants_total']}, échecs : {hp['echecs'] or 'aucun'}"
    )
    ml = livrable["metriques"]
    print(
        f"Livrable : {ml['cas']} cas, {ml['cas_corrects']['n']} corrects, faux montants : {ml['faux_montants']}, "
        f"exceptions : {ml['exceptions_inattendues']}, échecs : {livrable['echecs'] or 'aucun'}"
    )
    ecarts = None
    ecarts_l: list[dict] = []
    if not args.baseline:
        if BASELINE.is_file():
            base_complete = json.loads(BASELINE.read_text(encoding="utf-8"))
            base = base_complete["metriques"]["ensemble"]
            ecarts = comparer(base, m)
            base_l = base_complete.get("livrable", {}).get("metriques")
            if base_l is not None:
                ecarts_l = comparer(base_l, ml, SENS_LIVRABLE)
            (sortie / f"{nom}_comparaison.json").write_text(
                json.dumps(
                    {
                        "baseline": BASELINE.name,
                        "cas_baseline": base.get("cas"),
                        "cas": m["cas"],
                        "ecarts": ecarts,
                        "baisses": baisses(ecarts),
                        "ecarts_livrable": ecarts_l,
                        "baisses_livrable": baisses(ecarts_l),
                        "seuil_baisses": SEUIL_BAISSES,
                    },
                    ensure_ascii=False,
                    indent=1,
                    sort_keys=True,
                )
                + "\n",
                encoding="utf-8",
                newline="\n",
            )
            print(texte_comparaison(ecarts, base.get("cas"), m["cas"]))
            if base_l is not None:
                print("Livrable : " + texte_comparaison(ecarts_l, base_l.get("cas"), ml["cas"]))
        else:
            print(f"Aucune baseline ({BASELINE.name}) : comparaison impossible.")
    code = code_sortie(m, ecarts, hp["metriques"], ml)
    if code == 0 and len(baisses(ecarts or [])) + len(baisses(ecarts_l)) >= SEUIL_BAISSES:
        code = CODE_REGRESSION
    return code


if __name__ == "__main__":
    sys.exit(main())
