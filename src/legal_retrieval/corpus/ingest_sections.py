"""Sprint 2 ingestion: read the Tradrly sections instead of re-splitting the text.

Replaces Sprint 1's text splitting for the OCR JSON files (D20):
  - 1 section = 1 article, text from `content` only (no double reading);
  - history section -> convention and avenant dates (avenants.json);
  - articles hidden inside another section are cut out (R1/R4, Cadre art. 5);
  - abrogation lists become `abroge` entries linked to their avenant (R2/R3/R7);
  - "(جديد)" -> modified, previous version not in the corpus (R6, D17);
  - numbering restarts -> new part (Assurance), never a "duplicate";
  - gaps verified by hand (manual_checks.json, R8) are not alerts.
Numbers are still checked against the PDF text layer when the PDF exists (D11).

Run from the repo root:
    python -m src.legal_retrieval.corpus.ingest_sections
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any

from .ingest import _canonical, extract_numbers, pdf_number_index
from .loaders import load_pdf_pages
from .models import ArticleStatus, LegalArticle, LegalSource
from .normalize import normalize_arabic
from .registry import match_source
from .sections import (
    ConventionHistory,
    SectionArticle,
    abrogation_like_lines,
    find_abrogations,
    find_dates,
    find_embedded_headers,
    parse_history,
    read_sections,
    self_abrogation,
    split_merged,
    split_trailing_annexes,
)

_MANUAL_CHECKS = Path(__file__).with_name("manual_checks.json")


def _key(number: int, is_bis: bool) -> str:
    """"38" / "10BIS": the article key used in reports and ids."""
    return f"{number}{'BIS' if is_bis else ''}"


def load_manual_checks(path: Path = _MANUAL_CHECKS) -> list[dict[str, Any]]:
    """Checks made by hand in the original PDF (R8), see manual_checks.json."""
    if not path.exists():
        return []
    checks: list[dict[str, Any]] = json.loads(path.read_text(encoding="utf-8"))["checks"]
    return checks


def _checked_keys(checks: list[dict[str, Any]], source_id: str) -> set[tuple[int, str]]:
    """(part, article) of `source_id` explained by a manual check (any verdict)."""
    return {(int(c["part"]), str(a)) for c in checks if c["source_id"] == source_id
            for a in c["articles"]}


def _missing(present: set[tuple[int, bool]]) -> set[tuple[int, bool]]:
    """Plain numbers 1..max absent from `present` (bis articles are never 'expected')."""
    numbers = [n for n, _ in present]
    return {(n, False) for n in range(1, max(numbers) + 1)} - present if numbers else set()


def ingest_json(path: Path, pdf_dir: Path | None = None,
                manual: list[dict[str, Any]] | None = None,
                ) -> tuple[LegalSource, list[LegalArticle], ConventionHistory, dict[str, Any]]:
    """Ingest one Tradrly digest; return source, articles, history and report."""
    entry = match_source(path.stem)
    if entry is None:  # unknown file: fail loudly, never guess metadata
        raise ValueError(f"No registry entry matches file: {path.name}")
    manual = manual or []
    data = json.loads(path.read_text(encoding="utf-8"))
    history_text, sections, preamble = read_sections(data)
    history = parse_history(history_text, entry.source_id)
    annexes = split_trailing_annexes(sections)  # text after the last article
    known_avenants = {a.number for a in history.avenants}

    # 1) cut articles hidden inside another section (only MISSING numbers)
    parts = sorted({s.part for s in sections})
    present = {p: {(s.number, s.is_bis) for s in sections if s.part == p and s.number}
               for p in parts}
    articles_raw: list[tuple[SectionArticle, str]] = []
    split_labels: list[str] = []
    for section in sections:
        pieces = split_merged(section, _missing(present[section.part]))
        for i, piece in enumerate(pieces):
            origin = "section" if i == 0 else "split_from_section"
            if i and piece.number is not None:
                present[piece.part].add((piece.number, piece.is_bis))
                split_labels.append(f"P{piece.part}:{piece.key}")
            articles_raw.append((piece, origin))

    # 2) abrogation lists written inside the texts (R2/R3)
    # (part, key) -> (avenant, citable line, origin)
    abrogated: dict[tuple[int, str], tuple[int | None, str, str]] = {}
    foreign_lines: dict[int, list[str]] = {}  # piece index -> lines about OTHER articles
    for index, (piece, _) in enumerate(articles_raw):
        own_note = self_abrogation(piece.heading, piece.text)
        if own_note is not False and piece.number is not None:  # "الفصل55: (ألغي ...)"
            abrogated[(piece.part, piece.key)] = (
                own_note if isinstance(own_note, int) else None, piece.text, "section")
        for abrogation in find_abrogations(piece.text):
            for key in abrogation.numbers:
                abrogated.setdefault((piece.part, key), (abrogation.avenant_number,
                                                          abrogation.line, "abrogation_line"))
            # e.g. "الفصول 38-41 (ألغيت)" glued to article 37: moved out of its text
            if piece.number is not None and piece.key not in abrogation.numbers:
                foreign_lines.setdefault(index, []).append(abrogation.line)

    # R8: repeals read by eye in the PDF when the OCR broke the line
    # ("38 -39- ()I4 41", "عدد؟"): complete the avenant, add what the OCR lost.
    from_manual: list[str] = []
    for check in manual:
        if check["source_id"] != entry.source_id or check["verdict"] != "abroge":
            continue
        for article in map(str, check["articles"]):
            slot = (int(check["part"]), article)
            if slot in abrogated and abrogated[slot][0] is None:  # OCR lost "عدد 5"
                abrogated[slot] = (int(check["avenant"]), abrogated[slot][1], abrogated[slot][2])
            elif slot not in abrogated:  # OCR line unreadable: text read in the PDF
                abrogated[slot] = (int(check["avenant"]), check["pdf_text"], "manual_check")
            from_manual.append(f"P{slot[0]}:{article}")

    def avenant_id(number: int | None) -> str | None:
        return f"{entry.source_id}-AVENANT-{number}" if number is not None else None

    # 3) build the LegalArticle list
    pdf_numbers: set[str] | None = None
    pdf_path = pdf_dir / f"{path.stem}.pdf" if pdf_dir else None
    if pdf_path is not None and pdf_path.exists():
        pdf_numbers = pdf_number_index("\n".join(p.text for p in load_pdf_pages(pdf_path)))

    seen: Counter[str] = Counter()
    articles: list[LegalArticle] = []

    def add(number: int | None, key: str, label: str, text: str, part: int, *,
            status: ArticleStatus, modified: bool, amended_by: str | None,
            previous: bool, origin: str) -> None:
        base = f"{entry.source_id}{f'-P{part}' if part > 1 else ''}-ART-" + (
            key if number is not None else "X")
        seen[base] += 1
        article_id = base if seen[base] == 1 else f"{base}-DUP{seen[base]}"
        articles.append(LegalArticle(
            article_id=f"{article_id}-v1",
            source_id=entry.source_id,
            article_number=number,
            article_label=label,
            text=text,
            text_normalized=normalize_arabic(text),
            hierarchy_path=f"{entry.hierarchy_label} > {path.stem}"
                           + (f" > جزء {part}" if part > 1 else "") + f" > {label}",
            status=status,
            sector=entry.sector,
            text_source="ocr_json_sections",
            numbers_unverified=None if pdf_numbers is None else
            [n for n in extract_numbers(text) if _canonical(n) not in pdf_numbers],
            part=part, modified=modified, amended_by=amended_by,
            previous_version_available=previous, origin=origin,
        ))

    for index, (piece, origin) in enumerate(articles_raw):
        if index in foreign_lines:  # the abrogation line belongs to its own entry
            text = "\n".join(line for line in piece.text.splitlines()
                              if line.strip() not in foreign_lines[index]).strip()
            piece = SectionArticle(**{**piece.__dict__, "text": text})
        assert piece.number is not None  # read_sections drops sections without number
        own = abrogated.get((piece.part, piece.key))
        if own is not None:  # the section itself only says "(ألغي ...)"
            add(piece.number, piece.key, piece.label, piece.text, piece.part,
                status=ArticleStatus.ABROGE, modified=False,
                amended_by=avenant_id(own[0]), previous=False, origin=origin)
        else:  # consolidated digest: the text given is the current one
            add(piece.number, piece.key, piece.label, piece.text, piece.part,
                status=ArticleStatus.EN_VIGUEUR, modified=piece.modified,
                amended_by=None,  # which avenant changed it: not in the digest (open)
                previous=not piece.modified, origin=origin)

    created_abrogated: list[str] = []
    for (part, key), (avenant, line, origin) in sorted(abrogated.items()):
        number, is_bis = int(key.removesuffix("BIS")), key.endswith("BIS")
        if (number, is_bis) in present.get(part, set()):
            continue  # already an article (handled above)
        add(number, key, f"الفصل {number}{' مكرر' if is_bis else ''}", line, part,
            status=ArticleStatus.ABROGE, modified=False, amended_by=avenant_id(avenant),
            previous=False, origin=origin)
        present.setdefault(part, set()).add((number, is_bis))
        created_abrogated.append(f"P{part}:{key}")

    for k, annex in enumerate(annexes, start=1):  # annexes: own id, never an article
        refs = "، ".join(map(str, annex.refers_to))
        label = f"نص ملحق بالاتفاقية (يحيل إلى الفصل {refs})"
        articles.append(LegalArticle(
            article_id=f"{entry.source_id}-ANNEXE-{k}-v1", source_id=entry.source_id,
            article_number=None, article_label=label, text=annex.text,
            text_normalized=normalize_arabic(annex.text),
            hierarchy_path=f"{entry.hierarchy_label} > {path.stem} > ملاحق > {label}",
            status=ArticleStatus.INCONNU, sector=entry.sector,
            text_source="ocr_json_sections", origin="annex",
            numbers_unverified=None if pdf_numbers is None else
            [n for n in extract_numbers(annex.text) if _canonical(n) not in pdf_numbers],
        ))

    # 4) quality report: every gap must be explained
    missing_raw = {p: sorted(n for n, _ in _missing(
        {(s.number, s.is_bis) for s in sections if s.part == p and s.number})) for p in parts}
    unexplained = {p: [n for n, _ in sorted(_missing(present[p]))
                       if (p, str(n)) not in _checked_keys(manual, entry.source_id)]
                   for p in parts}
    own_numbers = {(s.part, s.number, s.is_bis) for s in sections}
    headers_in_text = sorted({  # headers of EXISTING articles found inside another text
        f"P{s.part}:{_key(h.number, h.is_bis)} in {s.key}"
        for s in sections for h in find_embedded_headers(s.text)
        if (s.part, h.number, h.is_bis) in own_numbers and h.number != s.number})
    # numbering as Tradrly gives it (numbers only, no text) + where it goes back
    sequence: dict[int, list[str]] = {}
    out_of_order: list[str] = []
    for before, s in zip([None, *sections], sections, strict=False):
        if before is not None and before.part == s.part and s.order <= before.order:
            out_of_order.append(f"P{s.part}:{before.key}->{s.key}")
        sequence.setdefault(s.part, []).append(s.key)
    continuations = [f"P{s.part}:{s.key} <- pos {s.merged_positions}"
                     for s in sections if s.merged_positions]
    report: dict[str, Any] = {
        "file": path.name,
        "source_id": entry.source_id,
        "sections_total": len(data.get("sections") or []),
        "history_found": bool(history_text),
        "convention_signed_on": str(history.signed_on) if history.signed_on else None,
        "convention_approved_on": str(history.approved_on) if history.approved_on else None,
        "avenants": len(history.avenants),
        "history_lines_to_check": history.unparsed_lines,
        "preamble_sections": len(preamble),
        "parts": len(parts),
        "articles": sum(a.origin != "annex" for a in articles),
        "from_sections": sum(a.origin == "section" for a in articles),
        "split_from_sections": split_labels,
        "abrogated_entries_created": created_abrogated,
        "completed_by_manual_checks": from_manual,
        "numbers_corrected_r9": [f"P{s.part}:{s.corrected_from}->{s.number}"
                                 for s in sections if s.corrected_from is not None],
        "known_gaps": sorted(f"P{c['part']}:{a} {c['verdict']}" for c in manual
                             if c["source_id"] == entry.source_id and c["verdict"] != "abroge"
                             for a in c["articles"]),
        "abroge_total": sum(a.status == ArticleStatus.ABROGE for a in articles),
        "abrogation_avenant_unknown": sorted(
            f"P{p}:{k}" for (p, k), (av, _, _) in abrogated.items() if av is None),
        "abrogation_avenant_not_in_history": sorted(
            f"P{p}:{k}" for (p, k), (av, _, _) in abrogated.items()
            if av is not None and av not in known_avenants),
        "abrogation_lines_moved_out": sum(len(v) for v in foreign_lines.values()),
        "modified_jadid": sum(a.modified for a in articles),
        "duplicate_ids": sum(c - 1 for c in seen.values() if c > 1),
        "missing_before_rules": {str(p): v for p, v in missing_raw.items() if v},
        "missing_unexplained": {str(p): v for p, v in unexplained.items() if v},
        "headers_of_existing_articles_in_text": headers_in_text,
        "numbering_out_of_order": out_of_order,
        "continuations_r10": continuations,
        "annexes": [f"ANNEXE-{k} -> art. {a.refers_to} (pos {a.positions})"
                    for k, a in enumerate(annexes, start=1)],
        "number_sequence": {f"P{p}": " ".join(v) for p, v in sequence.items()},
        "abrogation_lines_unparsed": [line for s in sections
                                      for line in abrogation_like_lines(s.heading + "\n" + s.text)],
        "history_dated_lines": sum(bool(find_dates(normalize_arabic(line)))
                                   for line in history_text.splitlines()),
        "numbers_checked_against_pdf": pdf_numbers is not None,
        "numbers_total": sum(len(extract_numbers(a.text)) for a in articles),
        "numbers_unverified": sum(len(a.numbers_unverified or []) for a in articles),
    }
    source = LegalSource(source_id=entry.source_id, title_ar=path.stem,
                         source_type=entry.source_type, sector=entry.sector,
                         file_name=path.name)
    return source, articles, history, report


def _history_json(source_id: str, history: ConventionHistory) -> dict[str, Any]:
    """Serializable dates (ISO) of one convention and its avenants."""
    return {
        "source_id": source_id,
        "signed_on": history.signed_on.isoformat() if history.signed_on else None,
        "approved_on": history.approved_on.isoformat() if history.approved_on else None,
        "avenants": [
            {"avenant_id": a.avenant_id, "number": a.number,
             "signed_on": a.signed_on.isoformat() if a.signed_on else None,
             "approved_on": a.approved_on.isoformat() if a.approved_on else None}
            for a in history.avenants
        ],
    }


def run(input_dir: Path, output_dir: Path, pdf_dir: Path | None = None) -> list[dict[str, Any]]:
    """Ingest every *.json of input_dir; write articles, sources, avenants, report."""
    output_dir.mkdir(parents=True, exist_ok=True)
    manual = load_manual_checks()
    sources, histories, reports = [], [], []
    with (output_dir / "legal_articles.jsonl").open("w", encoding="utf-8") as out:
        for path in sorted(input_dir.glob("*.json")):
            source, articles, history, report = ingest_json(path, pdf_dir, manual)
            sources.append(source.model_dump(mode="json"))
            histories.append(_history_json(source.source_id, history))
            reports.append(report)
            for article in articles:  # one JSON object per line
                out.write(article.model_dump_json() + "\n")
    for name, payload in (("legal_sources.json", sources), ("avenants.json", histories),
                          ("ingestion_report.json", reports)):
        (output_dir / name).write_text(json.dumps(payload, ensure_ascii=False, indent=2),
                                       encoding="utf-8")
    return reports


def main() -> None:
    """CLI entry point: one summary line per file."""
    parser = argparse.ArgumentParser(description="DS2 ingestion of the Tradrly sections")
    parser.add_argument("--input", type=Path, default=Path("data/raw/txt"))
    parser.add_argument("--pdf-dir", type=Path, default=Path("data/raw/pdf"))
    parser.add_argument("--output", type=Path, default=Path("data/processed/legal_corpus"))
    args = parser.parse_args()
    reports = run(args.input, args.output, args.pdf_dir)
    for r in reports:
        print(f"{r['source_id']:<28} sections={r['sections_total']:<3} art={r['articles']:<3}"
              f" parts={r['parts']} avenants={r['avenants']:<2} abroge={r['abroge_total']:<2}"
              f" jadid={r['modified_jadid']:<2} split={r['split_from_sections']}"
              f" r9={r['numbers_corrected_r9']} r10={len(r['continuations_r10'])}"
              f" annexes={len(r['annexes'])}"
              f" dup={r['duplicate_ids']}"
              f" desordre={len(r['numbering_out_of_order'])}"
              f" abrog_non_lues={len(r['abrogation_lines_unparsed'])}"
              f" unexplained={r['missing_unexplained']}")
    print(f"TOTAL articles={sum(r['articles'] for r in reports)}"
          f" annexes={sum(len(r['annexes']) for r in reports)}"
          f" avenants={sum(r['avenants'] for r in reports)}"
          f" -> {args.output}/ingestion_report.json")


if __name__ == "__main__":
    main()
