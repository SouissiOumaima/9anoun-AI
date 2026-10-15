"""Count the worker-category terms REALLY used in the conventions (input of D21).

Prints counts only (term -> number of articles per source), never article text,
so the vocabulary for DS1 is built from the corpus, not invented.
    python -m src.legal_retrieval.tools.diagnose_vocabulary
"""

from __future__ import annotations

import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

from src.legal_retrieval.corpus.normalize import normalize_arabic

# Candidate patterns (normalized text: أ->ا, ة->ه). Two words after the head noun
# so "اعوان التنفيذ" and "اعوان التسيير" stay distinct.
_CORES = [
    r"(?:ال)?اعوان (?:ال)?\w+",
    r"(?:ال)?عمال (?:ال)?\w+",
    r"(?:ال)?اطارات|اطار (?:ال)?\w+",
    r"(?:ال)?صنف \d+",
    r"(?:ال)?سلم \w+",
    r"(?:ال)?رتبه (?:ال)?\w+",
    r"(?:ال)?(?:متربص|متعاقد|قار|وقتي|عرضي)\w*",
]
# Arabic clitics glued before the word: و / ف, then ب / ل / ك ("لأعوان", "والإطارات").
_TERM = re.compile(r"(?<!\S)(?:و|ف)?(?:ب|ل|ك)?(?P<term>" + "|".join(_CORES) + r")")


def main() -> None:
    corpus = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(
        "data/processed/legal_corpus/legal_articles.jsonl")
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
    counts: dict[str, Counter[str]] = defaultdict(Counter)  # term -> source -> nb articles
    for line in corpus.read_text(encoding="utf-8").splitlines():
        article = json.loads(line)
        text = article.get("text_normalized") or normalize_arabic(article["text"])
        found = {m.group("term") for m in _TERM.finditer(text)}
        for term in found:  # one count per article, not per occurrence
            counts[term][article["source_id"]] += 1
    ranked = sorted(counts.items(), key=lambda kv: -sum(kv[1].values()))
    print(f"{'terme':<28} {'articles':>8}  sources")
    for term, by_source in ranked[:60]:
        sources = ", ".join(f"{s.removeprefix('CCS-')}:{n}" for s, n in by_source.most_common())
        print(f"{term:<28} {sum(by_source.values()):>8}  {sources}")


if __name__ == "__main__":
    main()
