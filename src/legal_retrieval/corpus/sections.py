"""Reader of the Tradrly OCR JSON digest (data/raw/txt/*.json), Sprint 2.

The JSON is already split by Tradrly: `sections[]`, one per article, plus ONE
history section (content_type "legal_history_reconstructed_from_page_images")
holding the dates of the convention and of its avenants.

Three parts:
  1. parse_history     -> signature / approval dates of the convention and avenants
  2. read_sections     -> 1 section = 1 article ; text from `content` ONLY
                          (`paragraphs` repeats it: cause of the 492 vs ~451 count)
  3. scan_text         -> rules R1-R5 of the manual verification (D18) INSIDE the
                          article texts: merged headers, abrogation lists, references

Nothing here guesses legal meaning: every date and number comes from the text.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date
from typing import Any

from .normalize import normalize_arabic, normalize_digits

HISTORY_TYPE_MARK = "history"  # content_type "legal_history_reconstructed_from_page_images"

# --- dates ---------------------------------------------------------------
# Tunisian month names, written AFTER normalize_arabic (أ->ا, ة->ه, ى->ي).
_MONTHS: dict[str, int] = {
    "جانفي": 1, "فيفري": 2, "مارس": 3, "افريل": 4, "ماي": 5, "جوان": 6,
    "جويليه": 7, "جويلية": 7, "اوت": 8, "سبتمبر": 9, "اكتوبر": 10,
    "نوفمبر": 11, "ديسمبر": 12,
}
# "16 جانفي 1975" (also "1er"-like "1" and OCR without space before the year)
_DATE = re.compile(r"(\d{1,2})\s*(" + "|".join(_MONTHS) + r")\s*(\d{4})")


def find_dates(normalized: str) -> list[date]:
    """All valid dates of a normalized line, in reading order."""
    found: list[date] = []
    for day, month, year in _DATE.findall(normalized):
        try:  # an OCR error like "31 فيفري" is skipped, never "fixed"
            found.append(date(int(year), _MONTHS[month], int(day)))
        except ValueError:
            continue
    return found


@dataclass
class Avenant:
    """One amending agreement (ملحق تعديلي). Numbering is PER convention (R7)."""

    avenant_id: str  # "CCS-BTP-AVENANT-5"
    number: int
    signed_on: date | None  # الممضى بتاريخ
    approved_on: date | None  # المصادق عليه بقرار ... المؤرخ في


@dataclass
class ConventionHistory:
    """Dates read from the history section of one file."""

    signed_on: date | None = None
    approved_on: date | None = None
    avenants: list[Avenant] = field(default_factory=list)
    unparsed_lines: list[int] = field(default_factory=list)  # line indexes to inspect


_AVENANT_LINE = re.compile(r"ملحق\s*(?:ال)?تعديلي?\S*\s*عدد\s*(\d+)")


def parse_history(text: str, source_id: str) -> ConventionHistory:
    """Read the convention dates and the avenant list from the history text.

    Line form (BTP, verified on the real file):
      "- الملحق التعديلي عدد 5 الممضى بتاريخ 24 سبتمبر 1996 والمصادق عليه ...
         المؤرخ في 16 أكتوبر 1996."
    First date = signature, second = ministerial approval. Which one starts
    the effect of the avenant is a LEGAL question still open (see D20).
    """
    history = ConventionHistory()
    for index, line in enumerate(text.splitlines()):
        norm = normalize_arabic(line)
        dates = find_dates(norm)
        avenant = _AVENANT_LINE.search(norm)
        if avenant:
            number = int(avenant.group(1))
            if len(dates) < 2:  # keep the avenant, flag the line for a human
                history.unparsed_lines.append(index)
            history.avenants.append(Avenant(
                avenant_id=f"{source_id}-AVENANT-{number}",
                number=number,
                signed_on=dates[0] if dates else None,
                approved_on=dates[1] if len(dates) > 1 else None,
            ))
        elif dates and history.signed_on is None:
            # first dated line = the convention itself:
            # "أمضيت بتاريخ ... وتمت المصادقة عليها ... المؤرخ في ..." (BTP, real form)
            history.signed_on = dates[0]
            history.approved_on = dates[1] if len(dates) > 1 else None
    return history


# --- rules inside the article texts (R1-R5) -------------------------------
_GAP = "[ـً-ٰٟ]*"  # tatweel / diacritics between letters
# first letter: any alef form — the OCR wrote BTP art. 51 as "إلفصل 51 (جديد):" (real run)
_FASL = "[اأإآ]" + _GAP + _GAP.join("لفصل")

# R1 + R4: an article header INSIDE a text. Space before the number optional
# (R1 "الفصل56:"), accepted mid-line ONLY when followed by ":" (R4).
# Preceded by start/space/punctuation: "بالفصل 51" (reference, R5) never matches.
_EMBEDDED_HEADER = re.compile(
    r"(?:^|(?<=[\s.:؛،)]))" + _FASL + r"[ \t]*(?P<num>\d+)"
    r"(?:[ \t]*(?P<bis>مكرر))?"
    r"(?:[ \t]*\(\s*(?P<new>جديد)\s*\))?"
    r"[ \t]*[:：]",
    re.MULTILINE,
)

# R2 + R3: list of repealed articles, on NORMALIZED text:
#   "الفصول 38-39-40-41 : (الغيت بمقتضي الملحق التعديلي عدد 5)"
#   "الفصلان 52 و53 : (الغيا ...)"   "الفصول 31-32-33 (الغيت ...)"  (no ":")
#   "الفصول 6 و7 و8 و9 و10 و10 مكرر: ..."   "الفصل55: (الغي ... عدد؟)"
#   "الفصول 31—32—33 (الغيت ...)"  (EM DASH, real run 2026-10-10: Gardiennage, Construction)
_NUM = r"\d+(?:\s*مكرر)?"
_ABROGATION = re.compile(
    r"(?:^|(?<=[\s.:؛،(]))(?:ال)?(?:فصول|فصلان|فصلين|فصل)\s*"
    r"(?P<nums>" + _NUM + r"(?:\s*(?:[-–—−،,]|و)\s*" + _NUM + r")*)"
    r"\s*:?\s*\(?\s*(?:تم\s*)?(?:الغيت|الغيا|الغي|ملغي)"
    r"(?P<rest>[^)\n]{0,120})"
)
_AVENANT_NUM = re.compile(r"عدد\s*(\d+)")


@dataclass(frozen=True)
class EmbeddedHeader:
    """An article header found inside the text of another section."""

    number: int
    is_bis: bool
    modified: bool  # "(جديد)"
    start: int  # offset in the ORIGINAL text (used to cut it)


@dataclass(frozen=True)
class Abrogation:
    """Articles repealed by an avenant, as written in the text."""

    numbers: tuple[str, ...]  # "38", "10BIS"
    avenant_number: int | None  # None when the OCR lost it ("عدد؟")
    line: str  # ORIGINAL line (used as citable text of the repealed entry)


def find_embedded_headers(text: str) -> list[EmbeddedHeader]:
    """R1/R4 headers of `text` (digits normalized, same length -> same offsets)."""
    return [
        EmbeddedHeader(int(m.group("num")), bool(m.group("bis")), bool(m.group("new")),
                       m.start())
        for m in _EMBEDDED_HEADER.finditer(normalize_digits(text))
    ]


def find_abrogations(text: str) -> list[Abrogation]:
    """R2/R3 abrogation lists of `text`, line by line (original line kept)."""
    found: list[Abrogation] = []
    for line in text.splitlines():
        for m in _ABROGATION.finditer(normalize_arabic(line)):
            numbers = tuple(
                num + ("BIS" if bis.strip() else "")
                for num, bis in re.findall(r"(\d+)(\s*مكرر)?", m.group("nums"))
            )
            avenant = _AVENANT_NUM.search(m.group("rest"))
            found.append(Abrogation(numbers, int(avenant.group(1)) if avenant else None,
                                    line.strip()))
    return found


# "الغي" but NOT "الغيابات" (absences), "الغير" (others), "الغيار" (spare parts):
# false positives seen in the real run of 2026-10-10.
_REPEAL_STEM = r"(?:الغي(?!اب|ار|ر)|ملغ[ايه]|الغاء)"
_SELF_ABROGATION = re.compile(r"^\W*(?:تم\s*)?" + _REPEAL_STEM)


def self_abrogation(heading: str, text: str) -> int | None | bool:
    """Is a section only the note that it was repealed? ("(ألغي بمقتضى ... عدد 5)")

    The header "الفصل55:" is often in `source_heading`, the note in `content`.
    Returns the avenant number, None if the OCR lost it, False if not repealed.
    """
    norm = normalize_arabic(text)
    if not _SELF_ABROGATION.match(norm) and not _SELF_ABROGATION.match(
            normalize_arabic(heading).split(":", 1)[-1]):
        return False
    avenant = _AVENANT_NUM.search(norm) or _AVENANT_NUM.search(normalize_arabic(heading))
    return int(avenant.group(1)) if avenant else None


# "ألغي/ألغيت/ألغيا", "ملغى/ملغاة", "إلغاء" (normalized) as a whole word:
# "المبالغ" (amounts) must NOT match, hence the word start.
_REPEAL_WORD = re.compile(r"(?:^|(?<=[\s(:،-]))" + _REPEAL_STEM)


def abrogation_like_lines(text: str) -> list[str]:
    """Lines speaking of a repeal ("ألغي", "ملغى") that R2/R3 did NOT parse.

    Used by the report only: shows the real form to write the next rule,
    instead of guessing it (first 120 characters of each line).
    """
    lines: list[str] = []
    for line in text.splitlines():
        norm = normalize_arabic(line)
        if _REPEAL_WORD.search(norm) and not _ABROGATION.search(norm) \
                and not _SELF_ABROGATION.match(norm):
            lines.append(line.strip()[:120])
    return lines


# --- sections ---------------------------------------------------------------
_SOURCE_ARTICLE = re.compile(r"^\s*(\d+)\s*(مكرر|bis)?", re.IGNORECASE)


@dataclass
class SectionArticle:
    """One article read from one section."""

    number: int | None
    is_bis: bool
    label: str  # "الفصل 7 مكرر" (rebuilt from source_article)
    heading: str  # source_heading as given by Tradrly
    title: str
    text: str  # `content` only
    modified: bool  # "(جديد)": consolidated new version (R6)
    part: int  # 1, 2, ... : numbering restarted (several texts in one file)
    position: int  # index of the section in the file
    corrected_from: int | None = None  # R9: number as written by the OCR, if corrected
    # "TER" (مثلث / ثالثا), "QUATER" (رابعا), "-3" (sub-article "الفصل 46 - 3:"),
    # read in source_heading: Tradrly gives "54" for "الفصل 54 مثلث" (real run).
    suffix: str = ""
    merged_positions: list[int] = field(default_factory=list)  # R10 continuations
    # R10 blocks glued to this article: (position, number written by Tradrly, text)
    merged_blocks: list[tuple[int, int, str]] = field(default_factory=list)
    own_text: str | None = None  # text before any R10 block was glued

    @property
    def key(self) -> str:
        """"38", "10BIS", "54TER", "46-3": article key used in ids and reports."""
        return f"{self.number}{'BIS' if self.is_bis else ''}{self.suffix}"

    @property
    def order(self) -> tuple[int, int]:
        """Reading order: 46 < 46 مكرر < 46 ثالثا < 46-3 < 47."""
        rank = {"": 0, "TER": 2, "QUATER": 3}.get(self.suffix)
        if rank is None:  # "-3"
            rank = 10 + int(self.suffix[1:])
        return (self.number or 0, 1 if self.is_bis else rank)


def parse_source_article(value: Any) -> tuple[int | None, bool]:
    """"7 مكرر" -> (7, True) ; 12 -> (12, False) ; None/"" -> (None, False)."""
    if value is None:
        return None, False
    match = _SOURCE_ARTICLE.match(normalize_digits(str(value)))
    if not match:
        return None, False
    return int(match.group(1)), bool(match.group(2))


def section_text(section: dict[str, Any]) -> str:
    """Text of a section WITHOUT double reading: `content`, else the paragraphs."""
    content = section.get("content")
    if isinstance(content, str) and content.strip():
        return content.strip()
    paragraphs = section.get("paragraphs") or []
    return "\n".join(str(p) for p in paragraphs).strip()


def is_history(section: dict[str, Any]) -> bool:
    """True for the history section (dates of the convention and its avenants)."""
    return HISTORY_TYPE_MARK in str(section.get("content_type", ""))


_SUFFIX_WORDS = {"مثلث": "TER", "ثالثا": "TER", "رابعا": "QUATER", "مربع": "QUATER"}
_SUFFIX_LABEL = {"TER": " ثالثا", "QUATER": " رابعا"}


def heading_suffix(heading: str, number: int) -> str:
    """Suffix written in the heading after the number, "" when none.

    "الفصل 54 مثلث (جديد):" -> "TER" ; "الفصل 51 ثالثا ( جديد):" -> "TER" ;
    "الفصل 46 - 3: منحة الحضور" -> "-3" ; "الفصل 54 —5: منحة" -> "-5" ;
    "الفصل 2 - المدة" -> "" (no digit after the dash: just a separator).
    """
    norm = normalize_arabic(heading)
    match = re.match(r"\W*الفصل\s*" + str(number) + r"(?!\d)\s*"
                     r"(?:(?P<word>" + "|".join(_SUFFIX_WORDS) + r")"
                     r"|[-–—]\s*(?P<sub>\d{1,2})\s*[:：])", norm)
    if not match:
        return ""
    if match.group("word"):
        return _SUFFIX_WORDS[match.group("word")]
    return f"-{match.group('sub')}"


def is_continuation(heading: str, number: int) -> bool:
    """R10: Tradrly cut a section on a REFERENCE, not on a header (real run).

    "وينص الفصل 46 من هذه الاتفاقية ..." / "الفصل 36 من هذه الاتفاقية." /
    "بالفصل 5 من الأمر المؤرخ في 8 جانفي 1948" / "مقتضيات الفصل 25 من ..." :
    the number is not this section's article, the text continues the previous one.
    A heading with no "فصل N" at all is trusted (title-only headings).
    """
    norm = normalize_arabic(heading)
    match = re.search(r"(\S*)فصل\s*" + str(number) + r"(?!\d)(?P<after>.{0,12})", norm)
    if not match:
        return False
    word = match.group(1)
    before = norm[: match.start()]
    preceded = word not in ("ال", "(ال") or bool(re.search(r"[^\W\d_]", before))
    return preceded or match.group("after").strip().startswith("من ")


def read_sections(data: dict[str, Any]) -> tuple[str, list[SectionArticle], list[str]]:
    """Split the digest into (history text, articles, preamble texts).

    A new `part` starts ONLY when the numbering restarts at 1 (Assurance holds
    several texts). A repeated number (46 then 46: one article in two sections,
    or two versions) or a number out of order stays in the same part: it is
    kept (DUP id, never dropped, D17) and listed in the report for inspection.
    Real run 2026-10-10: the rule "any lower number = new part" made up to 7
    fake parts (Enseignement).
    """
    history: list[str] = []
    preamble: list[str] = []
    articles: list[SectionArticle] = []
    part, previous = 1, (0, False)
    for position, section in enumerate(data.get("sections") or []):
        if not isinstance(section, dict):
            continue
        text = section_text(section)
        if is_history(section):
            history.append(text)
            continue
        number, is_bis = parse_source_article(section.get("source_article"))
        if number is None:  # title page, preamble, signatures...
            preamble.append(text)
            continue
        if (number == 1 and not is_bis and previous != (0, False)
                and not is_continuation(str(section.get("source_heading") or ""), 1)):
            part += 1  # a new text starts
        heading = str(section.get("source_heading") or "")
        title = str(section.get("title") or "")
        if articles and is_continuation(heading, number):  # R10: glue to previous article
            last = articles[-1]
            block = "\n".join(t for t in (heading.strip(), text) if t)
            if last.own_text is None:
                last.own_text = last.text
            last.text = "\n".join(t for t in (last.text, block) if t)
            last.merged_positions.append(position)
            last.merged_blocks.append((position, number, block))
            continue
        previous = (number, is_bis)
        suffix = "" if is_bis else heading_suffix(heading, number)
        articles.append(SectionArticle(
            number=number,
            is_bis=is_bis,
            suffix=suffix,
            label=f"الفصل {number}{' مكرر' if is_bis else ''}"
                  f"{_SUFFIX_LABEL.get(suffix, suffix)}",
            heading=heading,
            title=title,
            text=text,
            modified="جديد" in normalize_arabic(heading + " " + title),
            part=part,
            position=position,
        ))
    fix_dropped_digits(articles)
    return "\n".join(history), articles, preamble


@dataclass
class Annex:
    """Text placed AFTER the last article (Construction, Enseignement: real run).

    The last articles are "تاريخ التطبيق" (date of application); what Tradrly
    put after them (sanctions list, recruitment conditions) is an annex that
    refers to an article, not a continuation of the last one.
    """

    refers_to: list[int]  # article numbers the annex heading refers to
    positions: list[int]
    text: str


def split_trailing_annexes(articles: list[SectionArticle]) -> list[Annex]:
    """Take the R10 blocks glued to the LAST article out as one annex."""
    if not articles or not articles[-1].merged_blocks:
        return []
    last = articles[-1]
    annex = Annex(refers_to=sorted({n for _, n, _ in last.merged_blocks}),
                  positions=[p for p, _, _ in last.merged_blocks],
                  text="\n".join(b for _, _, b in last.merged_blocks))
    last.text = last.own_text or ""
    last.merged_blocks, last.merged_positions, last.own_text = [], [], None
    return [annex]


def fix_dropped_digits(articles: list[SectionArticle]) -> None:
    """R9: "50, 5, 52" -> the 5 is article 51 whose last digit the OCR dropped.

    Corrected ONLY when both neighbours (same part, not bis) prove it:
    next == previous + 2, and the written number is the start of previous + 1.
    The written number is kept in `corrected_from` and reported. Case seen:
    Runs AFTER R10: the first real run "corrected" BTP "بالفصل 5 من الأمر" (a
    reference, R10) into 51 — a false fix caught by tools/inspect_sections.py.
    """
    for before, current, after in zip(articles, articles[1:], articles[2:], strict=False):
        if (current.number is None or before.number is None or after.number is None
                or current.is_bis or before.is_bis or after.is_bis
                or current.suffix or before.suffix or after.suffix
                or not before.part == current.part == after.part):
            continue
        expected = before.number + 1
        if (after.number == before.number + 2 and current.number < before.number
                and str(expected).startswith(str(current.number))):
            current.corrected_from = current.number
            current.number = expected
            current.label = f"الفصل {expected}"


def split_merged(article: SectionArticle,
                 missing: set[tuple[int, bool]]) -> list[SectionArticle]:
    """Cut an article whose text contains the header of a MISSING article.

    Case found: Cadre article 5 ("الفصل5 (جديد): ...") is inside the section of
    article 4. Only numbers absent from the file's own sections (`missing`) and
    greater than the section's number are cut: an existing article is never
    duplicated, a header repeating the section's own number is its title.
    """
    cuts = [h for h in find_embedded_headers(article.text)
            if article.number is not None
            and (h.number, h.is_bis) in missing
            and (h.number, h.is_bis) > (article.number, article.is_bis)]
    if not cuts:
        return [article]
    pieces = [article.text[: cuts[0].start].strip()]
    pieces += [article.text[c.start: n.start].strip() if n else article.text[c.start:].strip()
               for c, n in zip(cuts, [*cuts[1:], None], strict=True)]
    result = [SectionArticle(**{**article.__dict__, "text": pieces[0]})]
    for cut, piece in zip(cuts, pieces[1:], strict=True):
        result.append(SectionArticle(
            number=cut.number, is_bis=cut.is_bis,
            label=f"الفصل {cut.number}{' مكرر' if cut.is_bis else ''}",
            heading=piece.splitlines()[0][:120] if piece else "", title="",
            text=piece, modified=cut.modified, part=article.part,
            position=article.position,
        ))
    return result
