"""Évalue l'extracteur DS3 (avec le vrai Gemini) sur le jeu de référence des documents fictifs.

Lancer depuis la racine du dépôt (la clé GEMINI_API_KEY doit être dans le fichier .env) :
    python -m src.document_intelligence.evaluation.run_gemini_eval
    python -m src.document_intelligence.evaluation.run_gemini_eval --cases DS3-01 DS3-04

Seuls des documents FICTIFS sont envoyés à Gemini. Ne jamais lancer ce script sur des documents
Tradrly réels sans l'accord de l'encadrant (NDA).

Pour chaque champ, le résultat est classé ainsi :
- correct   : la valeur obtenue est la valeur attendue (ou null attendu et null obtenu) ;
- faux      : une valeur est obtenue, mais pas la bonne ;
- silence   : null obtenu alors qu'une valeur était attendue (prudent, mais à améliorer) ;
- invention : une valeur obtenue alors que null était attendu (le plus grave : « citation ou silence »).
Les réponses complètes sont enregistrées dans evaluation/results/ (ignoré par Git).
"""

from __future__ import annotations

import argparse
import json
import time
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

from src.document_intelligence.contract.v2.models import DS3Request
from src.document_intelligence.evaluation.fictive_documents import DOCS_DIR, GOLDEN_FILE
from src.document_intelligence.extraction.assemble import PAYSLIP_FIELDS

Outcome = Literal["correct", "faux", "silence", "invention"]
RESULTS_DIR = Path(__file__).resolve().parent / "results"
NEEDS_OCR = {"DS3-03"}  # page scannée : attend l'OCR de la partie A


@dataclass
class CaseScore:
    case_id: str
    status_ok: bool  # le statut (ok / refus) et, pour un refus, le code sont ceux attendus
    fields: dict[str, tuple[Outcome, str | None, str | None]] = field(default_factory=dict)

    def count(self) -> Counter[str]:
        return Counter(outcome for outcome, _, _ in self.fields.values())


def score_case(case: dict[str, Any], response: dict[str, Any]) -> CaseScore:
    """Compare une réponse ds3.v2 aux valeurs attendues d'un cas du jeu de référence."""
    attendu = case["attendu"]
    if attendu["issue"] == "refus":
        status_ok = response["status"] == "refus" and (response.get("refus") or {}).get("code") == attendu["code_v2"]
    else:
        status_ok = response["status"] == "ok"
    expected_fields: dict[str, str | None] = attendu.get("fields", {})
    got_fields = (response.get("result") or {}).get("fields", {})
    score = CaseScore(case["id"], status_ok)
    for name in PAYSLIP_FIELDS:
        expected = expected_fields.get(name)
        got = (got_fields.get(name) or {}).get("value")
        outcome: Outcome
        if got == expected:
            outcome = "correct"
        elif got is None:
            outcome = "silence"
        elif expected is None:
            outcome = "invention"
        else:
            outcome = "faux"
        score.fields[name] = (outcome, expected, got)
    return score


def request_for(case: dict[str, Any]) -> DS3Request:
    return DS3Request.model_validate({
        "contract_version": "ds3.v2", "request_id": f"eval-{case['id']}", "lang": case["requete"]["lang"],
        "operation": "analyze_document",
        "context": {"organization_id": "org_eval", "user_id": "eval", "role": "accountant",
                    "card_id": "company_eval", "card_type": "company"},
        "document": {"document_id": case["doc_id"], "card_id": "company_eval",
                     "file_name": case["requete"]["file_name"], "mime_type": "application/pdf",
                     "storage_ref": "local://golden_sets/documents"},
        "options": {"expected_type": case["requete"]["expected_type"]},
    })


def _print_case(score: CaseScore, response: dict[str, Any]) -> None:
    marks = {"correct": "OK ", "faux": "FAUX", "silence": "null", "invention": "INVENTION"}
    print(f"\n=== {score.case_id} : statut {response['status']} ({'attendu' if score.status_ok else 'NON ATTENDU'})")
    for name, (outcome, expected, got) in score.fields.items():
        if outcome != "correct" or expected is not None:
            print(f"  {marks[outcome]:9} {name:24} attendu={expected!r:20} obtenu={got!r}")
    for warning in response.get("warnings", []):
        print(f"  ⚠ {warning}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Évalue l'extracteur DS3 avec Gemini.")
    parser.add_argument("--cases", nargs="*", help="Cas à lancer (par défaut : tous sauf ceux qui attendent l'OCR).")
    parser.add_argument("--model", help="Modèle Gemini (par défaut : GEMINI_MODEL du .env).")
    args = parser.parse_args(argv)

    try:
        from dotenv import load_dotenv

        load_dotenv()
    except ImportError:
        print("python-dotenv absent : la clé doit être dans les variables d'environnement.")

    from src.document_intelligence.extraction.pipeline import analyze_payslip_pdf

    golden = json.loads(GOLDEN_FILE.read_text(encoding="utf-8"))
    cases = [c for c in golden["cases"] if (c["id"] in args.cases if args.cases else c["id"] not in NEEDS_OCR)]
    totals: Counter[str] = Counter()
    statuses = 0
    saved: list[dict[str, Any]] = []
    for case in cases:
        response = analyze_payslip_pdf(DOCS_DIR / case["requete"]["file_name"], request_for(case), model=args.model)
        score = score_case(case, response)
        _print_case(score, response)
        totals += score.count()
        statuses += score.status_ok
        saved.append({"case": case["id"], "response": response})
        time.sleep(1)  # reste sous le quota gratuit de l'API

    n = sum(totals.values())
    print(f"\n=== Bilan sur {len(cases)} cas, {n} champs")
    print(f"  statuts attendus : {statuses}/{len(cases)}")
    for outcome in ("correct", "faux", "silence", "invention"):
        print(f"  {outcome:10} {totals[outcome]:3}  ({100 * totals[outcome] / max(n, 1):.0f} %)")
    RESULTS_DIR.mkdir(exist_ok=True)
    out = RESULTS_DIR / f"gemini_{time.strftime('%Y%m%d_%H%M%S')}.json"
    out.write_text(json.dumps(saved, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nRéponses complètes : {out}")
    return 0 if totals["invention"] == 0 and statuses == len(cases) else 1


if __name__ == "__main__":
    raise SystemExit(main())
