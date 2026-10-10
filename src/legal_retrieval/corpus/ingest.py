"""Sprint 1 ingestion (hybrid): OCR JSON for the text, PDF for the numbers.

- Arabic TEXT comes from data/raw/txt/*.json (Tradrly OCR): the PDF text layer
  stores Arabic as private-use glyphs (U+F2xx), unusable (DECISIONS D-DS2-6).
- NUMBERS of each article are checked against the PDF text layer
  (data/raw/pdf), whose digits are reliable (DECISIONS D1, DS5).

Run from the repo root:
    python -m src.legal_retrieval.corpus.ingest
"""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from pathlib import Path

from .loaders import Page, load_pages, load_pdf_pages, reversed_text_ratio
from .models import LegalArticle, LegalSource
from .normalize import normalize_arabic, normalize_digits
from .registry import match_source
from .splitter import split_articles


def _join_pages(pages: list[Page]) -> tuple[str, list[tuple[int, int | None]]]:
    """Concatenate pages; return text + (start_offset, page_number) index."""
    parts: list[str] = []
    index: list[tuple[int, int | None]] = []
    offset = 0
    for page in pages:
        index.append((offset, page.number))  # page starts at this offset
        parts.append(page.text)
        offset += len(page.text) + 1  # +1 for the "\n" separator
    return "\n".join(parts), index


def _page_at(offset: int, index: list[tuple[int, int | None]]) -> int | None:
    """Page number containing character `offset`."""
    current: int | None = None
    for start, number in index:
        if start > offset:
            break
        current = number
    return current


# 1500 / 1.500 / 459.264 / 2,5 -> one token each
_NUMBER = re.compile(r"\d+(?:[.,]\d+)*")


def extract_numbers(text: str) -> list[str]:
    """All numeric tokens of a text (Eastern Arabic digits converted)."""
    return _NUMBER.findall(normalize_digits(text))


def _canonical(number: str) -> str:
    """Digits only: "1.500", "1,500" and "1500" compare equal."""
    return re.sub(r"[.,]", "", number)


def pdf_number_index(pdf_text: str) -> set[str]:
    """Canonical numbers of the PDF, also in reversed digit order.

    RTL extraction can return "1500" as "0051"; accepting both keeps the
    check about OCR errors, not about the PDF reading direction.
    """
    index: set[str] = set()
    for number in extract_numbers(pdf_text):
        digits = _canonical(number)
        index.update({digits, digits[::-1]})
    return index


def ingest_file(
    path: Path, pdf_dir: Path | None = None
) -> tuple[LegalSource, list[LegalArticle], dict[str, object]]:
    """Ingest one file; return source, its articles and a quality report.

    If `pdf_dir` holds a PDF with the same name, every number of every article
    is looked up in that PDF's text layer (reliable digits).
    """
    entry = match_source(path.stem)
    if entry is None:  # unknown file: fail loudly, never guess metadata
        raise ValueError(f"No registry entry matches file: {path.name}")

    source = LegalSource(
        source_id=entry.source_id,
        title_ar=path.stem,
        source_type=entry.source_type,
        sector=entry.sector,
        file_name=path.name,
    )
    pages = load_pdf_pages(path) if path.suffix.lower() == ".pdf" else load_pages(path)
    text, page_index = _join_pages(pages)
    preamble, raw_articles = split_articles(text)

    # Reliable numbers of the original PDF (None if no PDF to compare with)
    pdf_path = pdf_dir / f"{path.stem}.pdf" if pdf_dir else None
    pdf_numbers: set[str] | None = None
    if pdf_path is not None and pdf_path.exists() and path.suffix.lower() != ".pdf":
        pdf_text = "\n".join(p.text for p in load_pdf_pages(pdf_path))
        pdf_numbers = pdf_number_index(pdf_text)

    articles: list[LegalArticle] = []
    seen: Counter[str] = Counter()  # duplicate numbers (annexes restart at 1)
    for raw in raw_articles:
        number = raw.number if raw.number is not None else "X"
        base = f"{entry.source_id}-ART-{number}{'BIS' if raw.is_bis else ''}"
        seen[base] += 1
        # 2nd "الفصل 1" (e.g. in an annex) gets a suffix to keep ids unique
        article_id = base if seen[base] == 1 else f"{base}-DUP{seen[base]}"
        articles.append(
            LegalArticle(
                article_id=f"{article_id}-v1",
                source_id=entry.source_id,
                article_number=raw.number,
                article_label=raw.label,
                text=raw.text,
                text_normalized=normalize_arabic(raw.text),
                hierarchy_path=f"{entry.hierarchy_label} > {path.stem} > {raw.label}",
                page_start=_page_at(raw.start_offset, page_index),
                sector=entry.sector,
                text_source="pdf_text_layer" if path.suffix.lower() == ".pdf"
                else "ocr_json",
                numbers_unverified=None if pdf_numbers is None else
                [n for n in extract_numbers(raw.text)
                 if _canonical(n) not in pdf_numbers],
            )
        )

    numbers = [a.article_number for a in articles if a.article_number is not None]
    report: dict[str, object] = {
        "file": path.name,
        "source_id": entry.source_id,
        "pages": len(page_index),
        "chars": len(text),
        "preamble_chars": len(preamble),
        "articles": len(articles),
        "unparsed_numbers": sum(a.article_number is None for a in articles),
        "duplicate_ids": sum(c - 1 for c in seen.values() if c > 1),
        # gaps like 1,2,4 often mean a header was not detected (OCR noise)
        "missing_numbers": sorted(set(range(1, max(numbers) + 1)) - set(numbers))
        if numbers else [],
        "empty_articles": sum(len(a.text) < 30 for a in articles),
        "empty_pages": sum(not p.text.strip() for p in pages),  # scanned pages?
        "reversed_text_ratio": round(reversed_text_ratio(text), 2),  # RTL bug?
        # many "فصل" mentions but few detected headers -> header layout issue
        "fasl_mentions": normalize_arabic(text).count("فصل"),  # tatweel-proof
        "numbers_checked_against_pdf": pdf_numbers is not None,
        # ~0 means the PDF digits are private-use glyphs too: check impossible
        "pdf_distinct_numbers": len(pdf_numbers) if pdf_numbers is not None else 0,
        "numbers_total": sum(len(extract_numbers(a.text)) for a in articles),
        "numbers_unverified": sum(len(a.numbers_unverified or []) for a in articles),
    }
    return source, articles, report


def run(input_dir: Path, output_dir: Path,
        pdf_dir: Path | None = None) -> list[dict[str, object]]:
    """Ingest every *.json (or *.pdf) of input_dir and write the outputs."""
    output_dir.mkdir(parents=True, exist_ok=True)
    sources: list[LegalSource] = []
    reports: list[dict[str, object]] = []
    with (output_dir / "legal_articles.jsonl").open("w", encoding="utf-8") as out:
        files = sorted(input_dir.glob("*.json")) or sorted(input_dir.glob("*.pdf"))
        for path in files:
            source, articles, report = ingest_file(path, pdf_dir)
            sources.append(source)
            reports.append(report)
            for article in articles:  # one JSON object per line
                out.write(article.model_dump_json() + "\n")
    (output_dir / "legal_sources.json").write_text(
        json.dumps([s.model_dump(mode="json") for s in sources],
                   ensure_ascii=False, indent=2), encoding="utf-8")
    (output_dir / "ingestion_report.json").write_text(
        json.dumps(reports, ensure_ascii=False, indent=2), encoding="utf-8")
    return reports


def main() -> None:
    """CLI entry point."""
    parser = argparse.ArgumentParser(description="DS2 corpus ingestion")
    parser.add_argument("--input", type=Path, default=Path("data/raw/txt"))
    parser.add_argument("--pdf-dir", type=Path, default=Path("data/raw/pdf"))
    parser.add_argument("--output", type=Path,
                        default=Path("data/processed/legal_corpus"))
    args = parser.parse_args()
    for r in run(args.input, args.output, args.pdf_dir):  # console summary
        print(f"{r['source_id']:<28} articles={r['articles']:<4}"
              f" fasl={r['fasl_mentions']:<4} dup={r['duplicate_ids']:<3}"
              f" nums={r['numbers_unverified']}/{r['numbers_total']} unverified"
              f" pdf_nums={r['pdf_distinct_numbers']}"
              f" reversed={r['reversed_text_ratio']} missing={r['missing_numbers']}")


if __name__ == "__main__":
    main()
