"""Diagnose HOW article headers look in the PDF text layer (Sprint 1).

Prints statistics and the most frequent FIRST WORDS of lines (header shapes),
never whole paragraphs. Output also saved as UTF-8 JSON (readable in VS Code):
    python -m src.legal_retrieval.tools.diagnose_text_layer
"""

from __future__ import annotations

import json
import re
import sys
import unicodedata
from collections import Counter
from pathlib import Path

from src.legal_retrieval.corpus.loaders import load_pdf_pages
from src.legal_retrieval.corpus.normalize import normalize_arabic

_WORD = re.compile(r"\S+")


def _char_profile(text: str) -> dict[str, int]:
    """Count character families that break Arabic matching."""
    return {
        "arabic_letters": sum("ء" <= c <= "ي" for c in text),
        "presentation_forms": sum("ﭐ" <= c <= "﻿" for c in text),
        "private_use": sum(unicodedata.category(c) == "Co" for c in text),
        "latin_letters": sum(c.isascii() and c.isalpha() for c in text),
        "tatweel": text.count("ـ"),
        "diacritics": sum("ً" <= c <= "ٟ" for c in text),
        "replacement_char": text.count("�"),  # unreadable glyphs
    }


def _line_starts(text: str, top: int = 20) -> list[tuple[str, int]]:
    """Most frequent first 1-2 words of lines (digits -> '#')."""
    starts: Counter[str] = Counter()
    for line in text.splitlines():
        words = _WORD.findall(line)
        if words:
            head = " ".join(words[:2])[:30]
            starts[re.sub(r"[0-9٠-٩]+", "#", head)] += 1
    return starts.most_common(top)


def diagnose(path: Path) -> dict[str, object]:
    """Statistics + header-shape hints for one PDF."""
    text = "\n".join(p.text for p in load_pdf_pages(path))
    norm = normalize_arabic(text)
    return {
        "file": path.name,
        "chars": len(text),
        "profile": _char_profile(text),
        "keyword_counts_normalized": {
            k: norm.count(k) for k in ("فصل", "لصف", "البند", "الماده", "الباب",
                                         "العنوان", "اولا", "ثانيا", "article")
        },
        "line_starts_top20": _line_starts(text),
    }


def main() -> None:
    """Run on data/raw/pdf (or the folder given) and save a JSON report."""
    folder = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("data/raw/pdf")
    report = [diagnose(p) for p in sorted(folder.glob("*.pdf"))]
    out = Path("data/processed/legal_corpus/text_layer_diagnosis.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
    for r in report:
        print(str(r["file"])[:35], r["profile"], r["keyword_counts_normalized"])
    print(f"\nRapport complet : {out}")


if __name__ == "__main__":
    main()
