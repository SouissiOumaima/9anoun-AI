"""Évaluation du Track B contre le jeu de référence lu dans les PDF (golden_sets/track_b_golden.v0.json).

Depuis la racine du dépôt :
    python src/track_b_accounting/evaluation/metrics_harness/run_eval.py --date 2026-10-09
    python src/track_b_accounting/evaluation/metrics_harness/run_eval.py --date 2026-10-09 --baseline

Appelle le handler en Python direct (track_b_accounting.contract.handle), comme l'orchestrateur.
Écrit results/eval_<date>.json et .md (ou results/baseline.json et .md avec --baseline).
Sortie déterministe : même commit + même --date ⇒ fichiers identiques à l'octet près.
Code de sortie : 1 s'il y a au moins un faux montant ou une exception inattendue, sinon 0.
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
SCHEMA_TB = REPO_ROOT / "data" / "mock_cards" / "schemas" / "track_b_response.v0.schema.json"
SCHEMA_COMMUN = REPO_ROOT / "src" / "shared" / "schemas" / "common.v0.schema.json"
DECISIONS = REPO_ROOT / "docs" / "DECISIONS.md"

# Verdicts d'un cas. Les deux premiers sont critiques (« Citation ou Silence »).
CORRECT = "correct"
FAUX_MONTANT = "faux_montant"                   # ok attendu, montant ou unité différents
MONTANT_AU_LIEU_DE_REFUS = "montant_au_lieu_de_refus"   # refus attendu, ok renvoyé
SILENCE_EXCESSIF = "silence_excessif"           # ok attendu, refus renvoyé
CODE_INCORRECT = "code_refus_incorrect"         # refus attendu, autre code
ERREUR = "statut_erreur"                        # réponse status = erreur
EXCEPTION = "exception_inattendue"              # le handler a levé une exception
CRITIQUES = (FAUX_MONTANT, MONTANT_AU_LIEU_DE_REFUS)


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
    return CORRECT if rep["refus"]["code"] == attendu["code"] else CODE_INCORRECT


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


def evaluer_cas(c: dict, refs: set[str], v_tb, v_commun) -> dict:
    out = {"id": c["id"], "categorie": c["categorie"], "certitude": c["certitude"], "decision": c["decision"],
           "verification_humaine": c["verification_humaine"], "attendu": c["attendu"]}
    try:
        rep = json.loads(json.dumps(handle(_requete(c)), ensure_ascii=False))     # telle qu'elle circule en JSON
    except Exception as exc:                                                       # noqa: BLE001
        # Erreur inattendue : enregistrée comme échec, l'évaluation continue.
        out.update(verdict=EXCEPTION, obtenu={"exception": type(exc).__name__, "message": str(exc)[:300]},
                   citations_ok=None, problemes_citations=[], conforme_schema_track_b=None, conforme_schema_commun=None)
        return out
    obtenu = {"status": rep["status"]}
    if rep["status"] == "ok":
        obtenu.update(montant=rep["result"]["montant"], unite=rep["result"]["unite"],
                      citations=[{"pdf": Path(x["source_file"]).name, "page": x["page"], "decision_ref": x["decision_ref"]}
                                 for x in rep["citations"]])
    elif rep["status"] == "refus":
        obtenu.update(code=rep["refus"]["code"], message_fr=rep["refus"]["message_fr"])
    else:
        obtenu.update(erreur=rep["erreur"]["type"])
    verdict = _verdict(c["attendu"], rep)
    problemes = (_citations_valides(c["attendu"], rep, refs)
                 if rep["status"] == "ok" and c["attendu"]["status"] == "ok" else [])
    out.update(verdict=verdict, obtenu=obtenu,
               citations_ok=(not problemes) if rep["status"] == "ok" and c["attendu"]["status"] == "ok" else None,
               problemes_citations=problemes,
               conforme_schema_track_b=v_tb.is_valid(rep), conforme_schema_commun=v_commun.is_valid(rep))
    return out


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
        "montants_au_lieu_de_refus": _taux(sum(r["verdict"] == MONTANT_AU_LIEU_DE_REFUS for r in refus_att), len(refus_att)),
        "exactitude_montants": _taux(sum(r["verdict"] == CORRECT for r in ok_att), len(ok_att)),
        "silence_excessif": _taux(sum(r["verdict"] == SILENCE_EXCESSIF for r in ok_att), len(ok_att)),
        "refus_corrects": _taux(sum(r["verdict"] == CORRECT for r in refus_att), len(refus_att)),
        "codes_refus_incorrects": _taux(sum(r["verdict"] == CODE_INCORRECT for r in refus_att), len(refus_att)),
        "citations_valides": _taux(sum(bool(r["citations_ok"]) for r in avec_cit), len(avec_cit)),
        "conformite_schema_track_b": _taux(sum(bool(r["conforme_schema_track_b"]) for r in evalues), len(evalues)),
        "conformite_schema_commun": _taux(sum(bool(r["conforme_schema_commun"]) for r in evalues), len(evalues)),
        "statut_erreur": sum(r["verdict"] == ERREUR for r in res),
        "exceptions_inattendues": sum(r["verdict"] == EXCEPTION for r in res),
    }
    m["faux_montants_total"] = m["faux_montants"]["n"] + m["montants_au_lieu_de_refus"]["n"]
    return m


def _echec(r: dict) -> bool:
    return r["verdict"] != CORRECT or r["citations_ok"] is False or r["conforme_schema_track_b"] is False \
        or r["conforme_schema_commun"] is False


def rapport(golden: dict, res: list[dict], date: str) -> dict:
    lecture = [r for r in res if r["certitude"] in ("L", "C")]
    verifies = [r for r in res if r["verification_humaine"]]
    return {
        "evaluation": "track_b",
        "date": date,
        "golden_set": {"fichier": GOLDEN.relative_to(REPO_ROOT).as_posix(), "version": golden["version"],
                       "sha256": _sha256(GOLDEN), "cas": len(res), "cas_verifies_par_ds5": len(verifies)},
        "metriques": {
            "ensemble": metriques(res),
            "cas_verifies": metriques(verifies),
            "par_certitude": {k: metriques([r for r in res if r["certitude"] == k]) for k in ("L", "C", "I")},
            "par_categorie": {k: metriques([r for r in res if r["categorie"] == k])
                              for k in ("ok", "art13", "refus", "piege")},
        },
        # Un échec sur un cas L ou C = erreur de lecture (du golden set ou du code) ; sur un cas I = désaccord d'interprétation.
        "erreurs_de_lecture": [r["id"] for r in lecture if _echec(r)],
        "desaccords_interpretation": [r["id"] for r in res if r["certitude"] == "I" and _echec(r)],
        "cas": res,
    }


def _ligne_taux(nom: str, t: dict) -> str:
    pct = "—" if t["taux"] is None else f"{100 * t['taux']:.1f} %"
    return f"| {nom} | {t['n']} / {t['sur']} | {pct} |"


def markdown(rap: dict) -> str:
    g, m = rap["golden_set"], rap["metriques"]
    lignes = [f"# Évaluation Track B — {rap['date']}", "",
              f"Jeu de référence : `{g['fichier']}` ({g['version']}, {g['cas']} cas, sha256 `{g['sha256'][:12]}…`).",
              f"Cas vérifiés sur les PDF par DS5 : **{g['cas_verifies_par_ds5']} / {g['cas']}**.", "",
              f"**Faux montants : {m['ensemble']['faux_montants_total']}** "
              "(montant faux pour un ok attendu, ou montant renvoyé alors qu'un refus était attendu).", ""]
    for titre, cle in (("Ensemble des cas", "ensemble"), ("Cas vérifiés par DS5", "cas_verifies")):
        mm = m[cle]
        lignes += [f"## {titre} ({mm['cas']} cas)", "", "| Métrique | Nombre | Taux |", "|---|---|---|",
                   _ligne_taux("Faux montants (ok attendu)", mm["faux_montants"]),
                   _ligne_taux("Montant au lieu d'un refus", mm["montants_au_lieu_de_refus"]),
                   _ligne_taux("Exactitude des montants", mm["exactitude_montants"]),
                   _ligne_taux("Silence excessif", mm["silence_excessif"]),
                   _ligne_taux("Refus corrects (même code)", mm["refus_corrects"]),
                   _ligne_taux("Citations valides", mm["citations_valides"]),
                   _ligne_taux("Conformité schéma Track B", mm["conformite_schema_track_b"]),
                   _ligne_taux("Conformité schéma commun", mm["conformite_schema_commun"]),
                   f"| Statut erreur / exceptions | {mm['statut_erreur']} / {mm['exceptions_inattendues']} | |", ""]
    lignes += ["## Par certitude", "", "| Certitude | Cas | Exactitude montants | Refus corrects | Faux montants |",
               "|---|---|---|---|---|"]
    for k, mm in m["par_certitude"].items():
        ex, rc = mm["exactitude_montants"], mm["refus_corrects"]
        lignes.append(f"| {k} | {mm['cas']} | {ex['n']} / {ex['sur']} | {rc['n']} / {rc['sur']} | {mm['faux_montants_total']} |")
    lignes += ["", "L = lu dans le PDF, C = calculé à la main, I = interprétation (Dn). Un échec sur un cas I est un "
               "désaccord d'interprétation, pas une erreur de lecture.", "",
               f"- Erreurs de lecture (cas L ou C en échec) : {', '.join(rap['erreurs_de_lecture']) or 'aucune'}",
               f"- Désaccords d'interprétation (cas I en échec) : {', '.join(rap['desaccords_interpretation']) or 'aucun'}",
               "", "## Détail des cas", "", "| Cas | Cat. | Cert. | Vérifié | Attendu | Obtenu | Verdict |",
               "|---|---|---|---|---|---|---|"]
    for r in rap["cas"]:
        a, o = r["attendu"], r["obtenu"]
        att = f"{a['montant']} {a['unite']}" if a["status"] == "ok" else a["code"]
        obt = (f"{o['montant']} {o['unite']}" if o.get("status") == "ok" else o.get("code") or o.get("erreur")
               or o.get("exception"))
        v = r["verdict"] + ("" if r["citations_ok"] is not False else " ; citations : " + " ; ".join(r["problemes_citations"]))
        lignes.append(f"| {r['id']} | {r['categorie']} | {r['certitude']}{' ' + r['decision'] if r['decision'] else ''} "
                      f"| {'oui' if r['verification_humaine'] else 'non'} | {att} | {obt} | {v} |")
    return "\n".join(lignes) + "\n"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--date", required=True, help="date du rapport (AAAA-MM-JJ), écrite telle quelle : aucune horloge")
    ap.add_argument("--baseline", action="store_true", help="écrit results/baseline.json et .md")
    args = ap.parse_args(argv)
    dt.date.fromisoformat(args.date)
    golden = json.loads(GOLDEN.read_text(encoding="utf-8"))
    refs = set(re.findall(r"^### (D[0-9]+)\b", DECISIONS.read_text(encoding="utf-8"), flags=re.M))
    v_tb, v_commun = _validateur(SCHEMA_TB), _validateur(SCHEMA_COMMUN)
    res = [evaluer_cas(c, refs, v_tb, v_commun) for c in golden["cases"]]
    rap = rapport(golden, res, args.date)
    nom = "baseline" if args.baseline else f"eval_{args.date}"
    sortie = EVAL_DIR / "results"
    sortie.mkdir(exist_ok=True)
    (sortie / f"{nom}.json").write_text(json.dumps(rap, ensure_ascii=False, indent=1, sort_keys=True) + "\n",
                                        encoding="utf-8", newline="\n")
    (sortie / f"{nom}.md").write_text(markdown(rap), encoding="utf-8", newline="\n")
    m = rap["metriques"]["ensemble"]
    print(f"{m['cas']} cas, faux montants : {m['faux_montants_total']}, exceptions : {m['exceptions_inattendues']}, "
          f"erreurs de lecture : {rap['erreurs_de_lecture'] or 'aucune'}, "
          f"désaccords d'interprétation : {rap['desaccords_interpretation'] or 'aucun'} -> results/{nom}.json, .md")
    return 1 if m["faux_montants_total"] or m["exceptions_inattendues"] else 0


if __name__ == "__main__":
    sys.exit(main())
