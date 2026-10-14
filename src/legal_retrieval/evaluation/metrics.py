"""Measure the real DS2 search on the golden set (D27): Recall@k, MRR, abstention.

    python -m src.legal_retrieval.evaluation.metrics            # print + save results/<date>.json
    python -m src.legal_retrieval.evaluation.metrics --no-save

- Recall@k : share of in-scope questions with AT LEAST ONE expected article in
  the first k articles (target Recall@10 >= 88 %, spec §8.4).
- MRR      : mean of 1 / rank of the first expected article (0 if absent).
- Abstention : share of out-of-scope questions answered by a refusal (target >= 85 %).
- Threshold study : the first result always has a normalized score of 1.0, so only
  the RAW BM25 score can say "nothing relevant". For each candidate threshold t
  (questions without article number and raw < t would be refused) we show the
  Recall@10 kept and the abstention reached -> the value to fix in bm25.py.
Only ids, ranks and scores are printed: no article text (NDA).
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ..contract.handler import CONTRACT_VERSION, handle
from ..corpus.store import CorpusStore, load_store
from ..search.bm25 import top_signals

HERE = Path(__file__).resolve().parent
GOLDEN = HERE / "golden_set_retrieval.v0.json"
RESULTS = HERE / "results"
CORE_KINDS = ("sujet", "numero")  # headline scope of the v0 (dialect / French reported apart)
OUT_OF_SCOPE = "hors_perimetre"


def load_golden(path: Path = GOLDEN) -> dict[str, Any]:
    data: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    return data


def run_question(item: dict[str, Any], store: CorpusStore) -> dict[str, Any]:
    """One question through the REAL handler; rank of the first expected article."""
    request = {"contract_version": CONTRACT_VERSION, "request_id": f"golden-{item['id']}",
               "query": item["question"], "sector": item.get("sector"), "top_k": 10}
    response = handle(request)
    groups: list[str] = []  # article order (each article may come with several versions)
    for result in response["results"]:
        if result["version_group"] not in groups:
            groups.append(result["version_group"])
    ranks = [groups.index(g) + 1 for g in item["expected"] if g in groups]
    signals = top_signals(request, store)
    return {"id": item["id"], "kind": item["kind"], "mode": response["mode"],
            "status": response["status"], "rank": min(ranks) if ranks else None,
            "top1": groups[0] if groups else None, "raw_top": round(signals["raw"], 3),
            "coverage": round(signals["coverage"], 3),
            "article_number_asked": signals["number_asked"], "expected": item["expected"]}


def _recall(rows: list[dict[str, Any]], k: int) -> float | None:
    return sum(1 for r in rows if r["rank"] and r["rank"] <= k) / len(rows) if rows else None


def summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Headline metrics, per kind, and the abstention threshold study."""
    in_scope = [r for r in rows if r["kind"] != OUT_OF_SCOPE]
    core = [r for r in in_scope if r["kind"] in CORE_KINDS]
    outside = [r for r in rows if r["kind"] == OUT_OF_SCOPE]
    kinds = sorted({r["kind"] for r in in_scope})
    summary: dict[str, Any] = {
        "n_questions": len(rows),
        "core": {"n": len(core), **{f"recall@{k}": _recall(core, k) for k in (1, 5, 10)},
                 "mrr": (sum(1 / r["rank"] for r in core if r["rank"]) / len(core)) if core else None},
        "per_kind_recall@10": {k: _recall([r for r in in_scope if r["kind"] == k], 10)
                               for k in kinds},
        "abstention": (sum(r["status"] == "refus" for r in outside) / len(outside)
                       if outside else None),
        "false_refusals": [r["id"] for r in in_scope if r["status"] == "refus"],
        "missed@10": [r["id"] for r in core if not (r["rank"] and r["rank"] <= 10)],
    }
    summary["threshold_study"] = threshold_study(core, outside, "raw_top")
    summary["coverage_study"] = threshold_study(core, outside, "coverage")
    return summary


def threshold_study(core: list[dict[str, Any]], outside: list[dict[str, Any]],
                    signal: str = "raw_top") -> list[dict[str, Any]]:
    """Recall@10 / abstention if questions without number and <signal> < t were refused.

    signal = "raw_top" (raw BM25 score) or "coverage" (share of the question found).
    """
    def refused(r: dict[str, Any], t: float) -> bool:
        return r["status"] == "refus" or (not r["article_number_asked"] and r[signal] < t)

    # candidates: just above each out-of-scope value (refuses that question) + 0
    candidates = sorted({0.0, *(round(r[signal] + 0.001, 3) for r in outside)})
    study = []
    for t in candidates:
        kept = [r for r in core if not refused(r, t)]
        study.append({
            "threshold": t,
            "recall@10": (sum(1 for r in kept if r["rank"] and r["rank"] <= 10) / len(core)
                          if core else None),
            "abstention": (sum(refused(r, t) for r in outside) / len(outside)) if outside else None,
            "core_refused": [r["id"] for r in core if refused(r, t)],
        })
    return study


def evaluate(golden: dict[str, Any], store: CorpusStore) -> dict[str, Any]:
    complete = [q for q in golden["questions"] if q["status"] == "complet"]
    rows = [run_question(q, store) for q in complete]
    if any(r["mode"] != "live" for r in rows):
        raise SystemExit("La mesure doit tourner en mode live (corpus ingéré).")
    return {"golden_set_version": golden["golden_set_version"],
            "date": datetime.now(timezone.utc).date().isoformat(),
            "skipped_a_completer": [q["id"] for q in golden["questions"]
                                    if q["status"] != "complet"],
            "targets": golden.get("targets"), "summary": summarize(rows), "rows": rows}


def _pct(x: float | None) -> str:
    return "  -  " if x is None else f"{100 * x:5.1f} %"


def main() -> None:
    parser = argparse.ArgumentParser(description="DS2 golden set metrics")
    parser.add_argument("--no-save", action="store_true")
    args = parser.parse_args()
    store = load_store()
    if store is None:
        raise SystemExit("Corpus absent : lancer python -m src.legal_retrieval.corpus.ingest_sections")
    report = evaluate(load_golden(), store)
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]  # Windows console
    for r in report["rows"]:
        rank = r["rank"] if r["rank"] else "-"
        print(f"{r['id']:<4} {r['kind']:<15} {r['status']:<6} rang={rank!s:<3} "
              f"raw={r['raw_top']:<7} cov={r['coverage']:<5} n°={'oui' if r['article_number_asked'] else 'non'}  top1={r['top1']}")
    s = report["summary"]
    print(f"\nquestions mesurées : {s['n_questions']}  (ignorées, a_completer : "
          f"{len(report['skipped_a_completer'])})")
    c = s["core"]
    print(f"sujet+numero (n={c['n']}) : R@1 {_pct(c['recall@1'])}  R@5 {_pct(c['recall@5'])}  "
          f"R@10 {_pct(c['recall@10'])}  (cible 88 %)  MRR {c['mrr'] if c['mrr'] is None else round(c['mrr'], 3)}")
    print("R@10 par type :", {k: _pct(v) for k, v in s["per_kind_recall@10"].items()})
    print(f"abstention hors périmètre : {_pct(s['abstention'])}  (cible 85 %)")
    print("refus à tort :", s["false_refusals"], " | ratées à 10 :", s["missed@10"])
    for title, key in (("seuil brut", "threshold_study"), ("seuil couverture", "coverage_study")):
        print(f"\n{title:<16} R@10     abstention  questions du périmètre refusées")
        for t in s[key]:
            print(f"{t['threshold']:<16} {_pct(t['recall@10'])}  {_pct(t['abstention'])}    "
                  f"{t['core_refused']}")
    if not args.no_save:
        RESULTS.mkdir(exist_ok=True)
        out = RESULTS / f"{report['date']}.json"
        out.write_text(json.dumps(report, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        print(f"\n-> {out}")


if __name__ == "__main__":
    main()
