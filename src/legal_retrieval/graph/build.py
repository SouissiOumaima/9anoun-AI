"""Build the DS2 legal graph from the ingested corpus (Sprint 3 CORE, D24).

Nodes : SECTOR, SOURCE, ARTICLE (one per version_group), AVENANT, EXTERNAL
        (Code du travail articles, decrees, laws: cited but NOT in the corpus).
Edges : APPARTIENT_A          article -> source
        S_APPLIQUE_AU_SECTEUR source  -> sector (convention cadre / SMIG -> every sector)
        AVENANT_DE            avenant -> source
        ABROGE                avenant -> article (status abroge + amended_by, D18/D20)
        MENTIONNE_AVENANT     article -> avenant (text "الملحق التعديلي عدد N")
        CITE                  article -> article | external (text "بالفصل 51", "الفصل 166
                              من مجلة الشغل"...)
Every edge keeps its evidence (the reference as written, <= 60 characters).
Nothing is guessed silently: an avenant cited but absent from the history becomes
a node with known=false; a citation resolved by inference carries inferred=true.

    python -m src.legal_retrieval.graph.build
"""

from __future__ import annotations

import json
import re
import sys
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ..contract.vocabulary import load_vocabulary
from ..corpus.normalize import normalize_arabic
from ..corpus.registry import REGISTRY
from ..corpus.sections import find_dates
from ..corpus.store import corpus_dir, version_group
from .references import find_references

GRAPH_FILE = "legal_graph.json"
_SKIP_ORIGINS = {"abrogation_line", "manual_check"}  # the repeal note is not a citation
_CODE_MENTION = re.compile(r"مجل[هي]?\s*الشغل")
_EXTERNAL_KIND = {"امر": "DECRET", "قانون": "LOI", "مرسوم": "DECRET-LOI"}


@dataclass
class Graph:
    """Nodes by id, edges as dicts (JSON-ready)."""

    nodes: dict[str, dict[str, Any]] = field(default_factory=dict)
    edges: list[dict[str, Any]] = field(default_factory=list)

    def node(self, node_id: str, node_type: str, **attrs: Any) -> str:
        """Create a node once (later calls keep the first attributes)."""
        self.nodes.setdefault(node_id, {"id": node_id, "type": node_type, **attrs})
        return node_id

    def edge(self, src: str, dst: str, edge_type: str, **attrs: Any) -> None:
        self.edges.append({"from": src, "to": dst, "type": edge_type, **attrs})

    def to_json(self) -> dict[str, Any]:
        return {"graph_version": "legal_graph.v0", "decision_ref": "D24",
                "nodes": sorted(self.nodes.values(), key=lambda n: n["id"]),
                "edges": self.edges}


def external_text_id(span: str) -> str:
    """Stable id of a cited text that is not in the corpus.

    "الامر عدد 501 لسنه 1982" -> "DECRET-501-1982" ; "القانون عدد 27" -> "LOI-27" ;
    "الامر المؤرخ في 8 جانفي 1948" -> "DECRET-1948-01-08" (no number: its date) ;
    "مجله الشغل" -> "CODE-TRAVAIL".
    """
    if _CODE_MENTION.search(span):
        return "CODE-TRAVAIL"
    kind = re.search(r"(امر|قانون|مرسوم)", span)
    if not kind:
        return "TEXTE-EXTERNE"
    prefix = _EXTERNAL_KIND[kind.group(1)]
    numbered = re.search(r"عدد\s*(\d+)(?:\s*لسنه\s*(\d{4}))?", span)
    if numbered:
        number, year = numbered.groups()
        return f"{prefix}-{number}" + (f"-{year}" if year else "")
    dates = find_dates(span)  # never the day of the month taken for a number
    return f"{prefix}-{dates[0].isoformat()}" if dates else prefix


def _resolve(groups: set[str], source_id: str, number: str) -> str | None:
    """version_group of article <number> of <source_id> (any part), or None."""
    pattern = re.compile(rf"^{re.escape(source_id)}(-P\d+)?-ART-{re.escape(number)}$")
    return next((g for g in sorted(groups) if pattern.match(g)), None)


def build_graph(folder: Path) -> tuple[Graph, dict[str, Any]]:
    """Graph + build report from an ingested corpus folder."""
    articles = [json.loads(line) for line in
                (folder / "legal_articles.jsonl").read_text(encoding="utf-8").splitlines() if line]
    histories = json.loads((folder / "avenants.json").read_text(encoding="utf-8")) \
        if (folder / "avenants.json").exists() else []
    graph = Graph()
    report: Counter[str] = Counter()
    unresolved: list[str] = []  # listed for a human check, never silently dropped

    # sectors and sources (vocabulary D21 + registry)
    sectors = {s["code"]: s for s in load_vocabulary()["sectors"]}
    for code, sector in sectors.items():
        graph.node(f"SECTOR:{code}", "SECTOR", label_fr=sector["label_fr"],
                   label_ar=sector["label_ar"])
    for entry in REGISTRY:
        source = graph.node(f"SOURCE:{entry.source_id}", "SOURCE",
                            source_type=entry.source_type.value, sector=entry.sector)
        targets = [entry.sector] if entry.sector else list(sectors)  # cadre / SMIG: all
        for code in targets:
            graph.edge(source, f"SECTOR:{code}", "S_APPLIQUE_AU_SECTEUR",
                       scope="secteur" if entry.sector else "tous_secteurs")

    # avenants of the history (dated)
    known_avenants: dict[str, set[int]] = {}
    for history in histories:
        known_avenants[history["source_id"]] = {a["number"] for a in history["avenants"]}
        for av in history["avenants"]:
            node_id = f"AVENANT:{av['avenant_id']}"
            if node_id in graph.nodes:  # same number listed twice in the history
                first = graph.nodes[node_id]
                same = (first["signed_on"], first["approved_on"]) == (av["signed_on"],
                                                                      av["approved_on"])
                key = "avenant_doublon_meme_dates" if same else "avenant_doublon_dates_differentes"
                report[key] += 1
                if not same:  # keep the first, record the conflict for a human check
                    first.setdefault("conflicting_dates", []).append(
                        {"signed_on": av["signed_on"], "approved_on": av["approved_on"]})
                continue
            graph.node(node_id, "AVENANT", known=True, number=av["number"],
                       signed_on=av["signed_on"], approved_on=av["approved_on"])
            graph.edge(node_id, f"SOURCE:{history['source_id']}", "AVENANT_DE")

    def avenant_node(source_id: str, number: int) -> str:
        """Avenant node; created with known=false when cited but not in the history."""
        node_id = f"AVENANT:{source_id}-AVENANT-{number}"
        if node_id not in graph.nodes:
            graph.node(node_id, "AVENANT", known=False, number=number,
                       signed_on=None, approved_on=None)
            graph.edge(node_id, f"SOURCE:{source_id}", "AVENANT_DE")
            report["avenants_cites_hors_historique"] += 1
        return node_id

    # articles, repeals
    groups = {version_group(a["article_id"]) for a in articles}
    for article in articles:
        group = version_group(article["article_id"])
        node = graph.node(f"ARTICLE:{group}", "ARTICLE", source_id=article["source_id"],
                          label=article["article_label"], status=article["status"],
                          modified=bool(article.get("modified")), origin=article.get("origin"))
        graph.edge(node, f"SOURCE:{article['source_id']}", "APPARTIENT_A")
        amended_by = article.get("amended_by")
        if article["status"] == "abroge" and amended_by:
            avenant_number = int(amended_by.rsplit("-", 1)[1])
            graph.edge(avenant_node(article["source_id"], avenant_number), node, "ABROGE")
            report["ABROGE"] += 1

    # citations found in the texts
    for article in articles:
        if article.get("origin") in _SKIP_ORIGINS:
            continue
        source_id = article["source_id"]
        node = f"ARTICLE:{version_group(article['article_id'])}"
        mentions_code = bool(_CODE_MENTION.search(normalize_arabic(article["text"])))
        for ref in find_references(article["text"]):
            if ref.kind == "avenant":
                graph.edge(node, avenant_node(source_id, int(ref.numbers[0])),
                           "MENTIONNE_AVENANT", evidence=ref.span)
                report["MENTIONNE_AVENANT"] += 1
                continue
            if ref.kind == "external":
                ext = graph.node(f"EXTERNAL:{external_text_id(ref.span)}", "EXTERNAL",
                                 in_corpus=False, label=ref.span)
                graph.edge(node, ext, "CITE", evidence=ref.span, inferred=False)
                report["CITE_texte_externe"] += 1
                continue
            for cited in ref.numbers:
                target, inferred = None, False
                if ref.target in ("same_source", "CC-CADRE"):
                    wanted = source_id if ref.target == "same_source" else "CC-CADRE"
                    found = _resolve(groups, wanted, cited)
                    if found == version_group(article["article_id"]):
                        report["auto_reference_ignoree"] += 1
                        continue
                    if found:
                        target = f"ARTICLE:{found}"
                    elif ref.target == "same_source" and mentions_code:
                        # "أحكام الفصل 138 المقصودة": no such article here, Code cited in
                        # the same article -> Code du travail, flagged as inferred
                        target, inferred = "code_travail", True
                if ref.target == "code_travail" or target == "code_travail":
                    target = graph.node(f"EXTERNAL:CODE-TRAVAIL-ART-{cited}", "EXTERNAL",
                                        in_corpus=False, label=f"مجلة الشغل، الفصل {cited}")
                elif ref.target == "external_text":  # "بالفصل 5 من الامر المؤرخ في ..."
                    text_id = external_text_id(ref.after)
                    target = graph.node(f"EXTERNAL:{text_id}-ART-{cited}", "EXTERNAL",
                                        in_corpus=False, label=f"{ref.after} — الفصل {cited}")
                if target is None:
                    report["citation_non_resolue"] += 1
                    unresolved.append(f"{article['article_id']} -> {ref.span}")
                    continue
                graph.edge(node, target, "CITE", evidence=ref.span, inferred=inferred)
                key = "CITE_code_travail" if "CODE-TRAVAIL" in target else (
                    "CITE_texte_externe" if target.startswith("EXTERNAL") else "CITE_article")
                report[key] += 1
    report["noeuds"] = len(graph.nodes)
    report["aretes"] = len(graph.edges)
    return graph, {**report, "citations_non_resolues": unresolved}


def main() -> None:
    folder = Path(sys.argv[1]) if len(sys.argv) > 1 else corpus_dir()
    graph, report = build_graph(folder)
    (folder / GRAPH_FILE).write_text(
        json.dumps(graph.to_json(), ensure_ascii=False, indent=1), encoding="utf-8")
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
    types = Counter(n["type"] for n in graph.nodes.values())
    edges = Counter(e["type"] for e in graph.edges)
    print("noeuds  :", dict(types.most_common()))
    print("aretes  :", dict(edges.most_common()))
    print("rapport :", report)
    print(f"-> {folder / GRAPH_FILE}")


if __name__ == "__main__":
    main()
