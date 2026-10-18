"""Count the references REALLY present in the corpus (input of the Sprint 3 graph).

Prints counts and the short reference expressions only (<= 60 characters,
never an article body): kinds, targets, and whether each target exists.
    python -m src.legal_retrieval.tools.diagnose_references
"""

from __future__ import annotations

import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from src.legal_retrieval.corpus.store import corpus_dir, version_group
from src.legal_retrieval.graph.references import find_references

_SKIP_ORIGINS = {"abrogation_line", "manual_check"}  # the repeal note itself, not a citation


def _exists(groups: set[str], source_id: str, number: str) -> bool:
    """Is there an article <source>[-P<n>]-ART-<number> in the corpus?"""
    pattern = re.compile(rf"^{re.escape(source_id)}(-P\d+)?-ART-{re.escape(number)}$")
    return any(pattern.match(g) for g in groups)


def diagnose(folder: Path) -> dict[str, Any]:
    articles = [json.loads(line) for line in
                (folder / "legal_articles.jsonl").read_text(encoding="utf-8").splitlines() if line]
    groups = {version_group(a["article_id"]) for a in articles}
    avenants_file = folder / "avenants.json"
    avenants = {h["source_id"]: {a["number"] for a in h["avenants"]}
                for h in json.loads(avenants_file.read_text(encoding="utf-8"))} \
        if avenants_file.exists() else {}

    kinds: Counter[str] = Counter()
    per_source: dict[str, Counter[str]] = defaultdict(Counter)
    resolution: Counter[str] = Counter()
    unresolved: Counter[str] = Counter()
    spans: Counter[str] = Counter()
    externals: Counter[str] = Counter()
    articles_with_refs = 0
    for article in articles:
        if article.get("origin") in _SKIP_ORIGINS:
            continue
        refs = find_references(article["text"])
        articles_with_refs += bool(refs)
        source = article["source_id"]
        for ref in refs:
            key = f"{ref.kind}:{ref.target}"
            kinds[key] += 1
            per_source[source][key] += 1
            if ref.kind == "external":
                externals[ref.span] += 1
                continue
            spans[ref.span] += 1
            if ref.kind == "avenant":
                ok = int(ref.numbers[0]) in avenants.get(source, set())
                resolution["avenant_ok" if ok else "avenant_unknown"] += 1
                if not ok:
                    unresolved[f"{source} avenant {ref.numbers[0]}"] += 1
                continue
            target_source = {"same_source": source, "CC-CADRE": "CC-CADRE"}.get(ref.target)
            if target_source is None:  # Code du travail / decree: not in the corpus
                resolution[f"hors_corpus:{ref.target}"] += 1
                continue
            for number in ref.numbers:
                own = version_group(article["article_id"]).endswith(f"-ART-{number}")
                if own:
                    resolution["self"] += 1
                elif _exists(groups, target_source, number):
                    resolution["article_ok"] += 1
                else:
                    resolution["article_missing"] += 1
                    cited_by = article["article_id"]
                    unresolved[f"{target_source} art. {number} (cité par {cited_by})"] += 1
    return {
        "articles": len(articles),
        "articles_with_references": articles_with_refs,
        "by_kind_target": dict(kinds.most_common()),
        "resolution": dict(resolution.most_common()),
        "per_source": {s: dict(c.most_common()) for s, c in sorted(per_source.items())},
        "top_spans": spans.most_common(30),
        "top_external": externals.most_common(20),
        "unresolved": unresolved.most_common(40),
    }


def main() -> None:
    folder = Path(sys.argv[1]) if len(sys.argv) > 1 else corpus_dir()
    report = diagnose(folder)
    (folder / "references_diagnosis.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
    print(f"articles={report['articles']}  avec_renvois={report['articles_with_references']}")
    for title in ("by_kind_target", "resolution"):
        print(f"\n== {title}")
        for key, value in report[title].items():
            print(f"   {key:<32} {value}")
    print("\n== par source")
    for source, counts in report["per_source"].items():
        print(f"   {source:<28} {counts}")
    for title in ("top_spans", "top_external", "unresolved"):
        print(f"\n== {title}")
        for key, value in report[title]:
            print(f"   {value:>4}  {key}")
    print(f"\nRapport complet : {folder / 'references_diagnosis.json'}")


if __name__ == "__main__":
    main()
