"""Questions asked to the legal graph (Sprint 3 demo, D24).

    python -m src.legal_retrieval.graph.query --sector banques
    python -m src.legal_retrieval.graph.query --article CCS-BTP-ART-39

`texts_for_sector` answers the Sprint 3 deliverable: "all the texts that apply
to the banking sector" = its sectoral convention + the texts for every sector.
`related` gives the neighbours of an article (future `related` field of search).
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any

from ..corpus.store import corpus_dir
from .build import GRAPH_FILE


def load_graph(folder: Path | None = None) -> dict[str, Any]:
    folder = folder or corpus_dir()
    data: dict[str, Any] = json.loads((folder / GRAPH_FILE).read_text(encoding="utf-8"))
    return data


def texts_for_sector(graph: dict[str, Any], sector: str) -> list[dict[str, Any]]:
    """Sources applying to `sector`, sectoral first, with their article counts."""
    target = f"SECTOR:{sector}"
    applying = {e["from"]: e["scope"] for e in graph["edges"]
                if e["type"] == "S_APPLIQUE_AU_SECTEUR" and e["to"] == target}
    status: dict[str, Counter[str]] = {s: Counter() for s in applying}
    for node in graph["nodes"]:
        source = f"SOURCE:{node.get('source_id')}"
        if node["type"] == "ARTICLE" and source in status:
            status[source][node["status"]] += 1
    rows = [{"source": s.removeprefix("SOURCE:"), "scope": scope,
             "articles": dict(status[s])} for s, scope in applying.items()]
    return sorted(rows, key=lambda r: (r["scope"] != "secteur", r["source"]))


def related(graph: dict[str, Any], article: str) -> dict[str, list[dict[str, Any]]]:
    """Neighbours of an article: what it cites, who cites it, its avenants."""
    node = f"ARTICLE:{article}"
    out = [e for e in graph["edges"] if e["from"] == node and e["type"] != "APPARTIENT_A"]
    inc = [e for e in graph["edges"] if e["to"] == node]
    return {
        "cite": [{"to": e["to"], "evidence": e.get("evidence"), "inferred": e.get("inferred")}
                 for e in out if e["type"] == "CITE"],
        "avenants_mentionnes": [{"to": e["to"], "evidence": e.get("evidence")}
                                for e in out if e["type"] == "MENTIONNE_AVENANT"],
        "cite_par": [{"from": e["from"], "evidence": e.get("evidence")}
                     for e in inc if e["type"] == "CITE"],
        "abroge_par": [{"from": e["from"]} for e in inc if e["type"] == "ABROGE"],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="DS2 legal graph queries")
    parser.add_argument("--sector", help="code D21, ex. banques")
    parser.add_argument("--article", help="version_group, ex. CCS-BTP-ART-39")
    args = parser.parse_args()
    graph = load_graph()
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
    if args.sector:
        for row in texts_for_sector(graph, args.sector):
            print(f"{row['source']:<28} {row['scope']:<14} {row['articles']}")
    if args.article:
        print(json.dumps(related(graph, args.article), ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
