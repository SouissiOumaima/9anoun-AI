"""Describe the metadata of the Tradrly OCR JSON files (data/raw/txt/*.json).

Each file holds `sections` already split by Tradrly (one per article + preamble).
This tool prints METADATA ONLY — section types, article numbers, headings
(the short header line, never the article body), page ranges — so we can
decide how the loader should read them.
    python -m src.legal_retrieval.tools.diagnose_ocr_json
"""

from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any


def describe(path: Path) -> dict[str, Any]:
    """Metadata summary of one OCR JSON file."""
    data = json.loads(path.read_text(encoding="utf-8"))
    sections: list[dict[str, Any]] = data.get("sections", [])
    articles = [s.get("source_article") for s in sections]
    joined = [s for s in sections  # does `content` equal the joined paragraphs?
              if isinstance(s.get("paragraphs"), list)
              and "".join(map(str, s["paragraphs"])).replace("\n", "")
              == str(s.get("content", "")).replace("\n", "")]
    return {
        "file": path.name,
        "top_level_keys": sorted(data),
        "structure": data.get("structure"),          # short description (~100 chars)
        "quality": data.get("quality"),
        "sections": len(sections),
        "content_types": Counter(str(s.get("content_type")) for s in sections).most_common(),
        "source_article_null": sum(a is None for a in articles),
        "source_article_types": Counter(type(a).__name__ for a in articles).most_common(),
        "source_article_samples": [a for a in articles if a is not None][:12],
        "headings_first_8": [s.get("source_heading") for s in sections[:8]],
        "headings_plural_or_dual": [s.get("source_heading") for s in sections
                                    if any(w in str(s.get("source_heading", ""))
                                           for w in ("الفصول", "الفصلان", "ألغي"))],
        "headings_with_jadid": sum("جديد" in str(s.get("source_heading", "")) for s in sections),
        "pdf_pages_samples": [s.get("source_pdf_pages") for s in sections[:5]],
        "titles_first_5": [s.get("title") for s in sections[:5]],
        "content_equals_paragraphs": f"{len(joined)}/{len(sections)}",
    }


def main() -> None:
    """Print a summary per file and save the full report as UTF-8 JSON."""
    folder = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("data/raw/txt")
    report = [describe(p) for p in sorted(folder.glob("*.json"))]
    out = Path("data/processed/legal_corpus/ocr_json_diagnosis.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
    for r in report:
        print(f"\n== {str(r['file'])[:50]}")
        for key in ("sections", "content_types", "source_article_null", "source_article_types",
                    "source_article_samples", "headings_with_jadid", "headings_plural_or_dual",
                    "pdf_pages_samples", "titles_first_5", "content_equals_paragraphs",
                    "structure"):
            print(f"   {key:<26}: {r[key]}")
    print(f"\nRapport complet : {out}")


if __name__ == "__main__":
    main()
