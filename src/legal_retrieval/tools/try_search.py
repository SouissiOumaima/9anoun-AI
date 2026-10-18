"""Try the real search on the ingested corpus (D26), confidentiality-safe output.

    python -m src.legal_retrieval.tools.try_search "منحة النقل" --sector btp
    python -m src.legal_retrieval.tools.try_search "الفصل 39" --sector btp --top-k 3

Prints per article: rank, version_group, score, status and a span of at most
60 characters. Never the full text (NDA: articles stay in the corpus files).
"""

from __future__ import annotations

import argparse
import sys

from src.legal_retrieval.contract.handler import CONTRACT_VERSION, handle

SPAN = 60  # max characters of article text shown


def main() -> None:
    parser = argparse.ArgumentParser(description="DS2 real search, short output")
    parser.add_argument("query")
    parser.add_argument("--sector", default=None, help="code D21, ex. banques, btp")
    parser.add_argument("--top-k", type=int, default=10)
    args = parser.parse_args()
    response = handle({"contract_version": CONTRACT_VERSION, "request_id": "try",
                       "query": args.query, "sector": args.sector, "top_k": args.top_k})
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]  # Windows console
    print(f"mode={response['mode']}  status={response['status']}  "
          f"computed_by={response['computed_by']}")
    if response["status"] != "ok":
        print("refus :", (response.get("refus") or response.get("erreur") or {}).get("message_fr"))
        return
    seen: list[str] = []
    for r in response["results"]:
        first = r["version_group"] not in seen
        seen.append(r["version_group"])
        rank = f"{len(set(seen)):>2}." if first else "   "  # other versions of the same article
        span = " ".join(r["text"].split())[:SPAN]
        print(f"{rank} {r['article_id']:<40} {r['score']:.3f}  {r['status']:<10} {span}")


if __name__ == "__main__":
    main()
