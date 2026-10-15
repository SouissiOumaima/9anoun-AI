"""Show the sections whose number is repeated or out of order (to decide by eye).

Prints, for each such section, its position, the number given by Tradrly, the
heading and the first characters of its text (never the whole article), next
to its neighbours' numbers. Run from the repo root:
    python -m src.legal_retrieval.tools.inspect_sections
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from src.legal_retrieval.corpus.registry import match_source
from src.legal_retrieval.corpus.sections import read_sections, split_trailing_annexes


def _short(text: str, size: int) -> str:
    """One line, at most `size` characters."""
    return " / ".join(text.split("\n"))[:size]


def main() -> None:
    folder = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("data/raw/txt")
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
    for path in sorted(folder.glob("*.json")):
        _, articles, _ = read_sections(json.loads(path.read_text(encoding="utf-8")))
        entry = match_source(path.stem)
        annexes = split_trailing_annexes(articles)  # same order as the ingestion
        keys = [(a.part, a.key) for a in articles]
        flagged = [i for i, k in enumerate(keys)
                   if keys.count(k) > 1  # repeated article
                   or (i and articles[i].part == articles[i - 1].part
                       and articles[i].order <= articles[i - 1].order)  # goes back
                   or articles[i].corrected_from is not None  # R9 correction
                   or articles[i].merged_positions]  # R10: sections glued to it
        if not flagged and not annexes:
            continue
        print(f"\n== {entry.source_id if entry else path.name}")
        for k, annex in enumerate(annexes, start=1):
            print(f"  ANNEXE-{k} (pos {annex.positions}, renvoie à l'art. {annex.refers_to})"
                  f"  [après le dernier article: {articles[-1].label}]")
            print(f"     début : {_short(annex.text, 70)}")
        for i in flagged:
            a = articles[i]
            before = articles[i - 1].label if i else "-"
            after = articles[i + 1].label if i + 1 < len(articles) else "-"
            fixed = f" (R9: écrit {a.corrected_from})" if a.corrected_from is not None else ""
            print(f"  pos={a.position:<3} P{a.part} {a.label}{fixed}"
                  f"  [avant: {before} | après: {after}]")
            if a.merged_positions:
                print(f"     R10   : sections collées à cet article : pos {a.merged_positions}")
            print(f"     titre : {_short(a.heading or a.title, 70)}")
            print(f"     début : {_short(a.text, 70)}")


if __name__ == "__main__":
    main()
