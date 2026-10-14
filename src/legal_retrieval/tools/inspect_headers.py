"""Show WHY some articles are missing or duplicated, for one source (local use).

Prints OCR lines that mention "فصل" + a missing number, and the header lines
of duplicated articles. Shows corpus text: read it locally, share only the
header shapes.
    python -m src.legal_retrieval.tools.inspect_headers CCS-BTP
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

from src.legal_retrieval.corpus.loaders import load_pages
from src.legal_retrieval.corpus.normalize import normalize_arabic
from src.legal_retrieval.corpus.registry import match_source

_OUT = Path("data/processed/legal_corpus")


def main() -> None:
    """Print diagnostics for the source id given as argument."""
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
    source_id = sys.argv[1] if len(sys.argv) > 1 else "CCS-BTP"
    report = next(r for r in json.loads((_OUT / "ingestion_report.json")
                                        .read_text("utf-8"))
                  if r["source_id"] == source_id)
    path = next(p for p in Path("data/raw/txt").glob("*.json")
                if (e := match_source(p.stem)) and e.source_id == source_id)
    lines = "\n".join(p.text for p in load_pages(path)).splitlines()

    print(f"== {source_id} — articles manquants : {report['missing_numbers']}")
    for number in report["missing_numbers"]:
        pattern = re.compile(rf"فصل\D{{0,15}}\b{number}\b")  # "فصل" then the number
        hits: list[tuple[int, str, re.Match[str]]] = []
        for i, raw_line in enumerate(lines, 1):
            line = normalize_arabic(raw_line)
            match = pattern.search(line)
            if match:
                hits.append((i, line, match))
        print(f"\n-- {number} : {len(hits)} ligne(s)")
        for i, line, m in hits[:3]:
            where = "DEBUT de ligne" if m.start() < 5 else f"position {m.start()}"
            # 25 chars before / 40 after the match: shows if it is a header
            # ("الفصل 51 :") or a reference ("طبقا للفصل 51")
            print(f"   l.{i} ({where}): …{line[max(0, m.start() - 25):m.end() + 40]}…")

    print("\n== doublons (même numéro détecté plusieurs fois)")
    for row in (_OUT / "legal_articles.jsonl").read_text("utf-8").splitlines():
        article = json.loads(row)
        if article["source_id"] == source_id and "-DUP" in article["article_id"]:
            print(f"   {article['article_id']:<34} p.{article['page_start']}: "
                  f"{article['text'].splitlines()[0][:60]}")


if __name__ == "__main__":
    main()
