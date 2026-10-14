"""Help fill the golden set: which articles contain a word? (independent of BM25)

    python -m src.legal_retrieval.evaluation.find_candidates "عطلة"
    python -m src.legal_retrieval.evaluation.find_candidates "تجربة" --source CC-CADRE
    python -m src.legal_retrieval.evaluation.find_candidates "ولادة" --sector banques

Plain substring search on the normalized text (same normalization as the
corpus): it does NOT use the search engine, so the expected articles of the
golden set are not chosen by the system being measured.
Prints version_group, status and the 60 characters around the first match
(NDA: never a full article).
"""

from __future__ import annotations

import argparse
import sys

from ..corpus.normalize import normalize_arabic
from ..corpus.store import load_store

SPAN = 60  # max characters shown


def main() -> None:
    parser = argparse.ArgumentParser(description="articles containing a word")
    parser.add_argument("word", help="mot ou expression (arabe), ex. عطلة")
    parser.add_argument("--source", help="ex. CCS-BANQUES, CC-CADRE")
    parser.add_argument("--sector", help="code D21 : garde ce secteur + les textes tous secteurs")
    args = parser.parse_args()
    store = load_store()
    if store is None:
        raise SystemExit("Corpus absent : lancer python -m src.legal_retrieval.corpus.ingest_sections")
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]  # Windows console
    needle = normalize_arabic(args.word)
    hits = 0
    for group in sorted(store.groups):
        article = store.find_group(group)[0]  # newest version
        if args.source and article["source_id"] != args.source:
            continue
        if args.sector and article.get("sector") not in (None, args.sector):
            continue
        text = article.get("text_normalized") or normalize_arabic(article["text"])
        at = text.find(needle)
        if at < 0:
            continue
        hits += 1
        start = max(0, at - SPAN // 3)
        print(f"{group:<38} {article['status']:<10} …{text[start:start + SPAN]}…")
    print(f"{hits} article(s) contiennent « {args.word} »")


if __name__ == "__main__":
    main()
