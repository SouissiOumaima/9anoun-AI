"""Split a legal text into articles ("الفصل N").

Decision (see DECISIONS.md): one chunk = one article. A chunk never crosses
an article boundary, so a retrieved chunk is always citable as-is.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from .normalize import normalize_digits

# Ordinal words used in some agreements ("الفصل الأول").
_ORDINALS: dict[str, int] = {
    "الأول": 1, "الاول": 1, "الثاني": 2, "الثالث": 3, "الرابع": 4,
    "الخامس": 5, "السادس": 6, "السابع": 7, "الثامن": 8, "التاسع": 9,
    "العاشر": 10,
}

# An article header at the start of a line:
#   "الفصل 14", "الفصل 14 (جديد)", "فصل 3 :", "الفصل الأول -", "Article 5"
# Tatweel ("ـ") and diacritics may appear between letters: "الفصــل", "الفَصْل".
_GAP = "[\u0640\u064B-\u065F\u0670]*"
_FASL = _GAP.join("فصل")  # ف<gap>ص<gap>ل
_AL = "ا" + _GAP + "ل" + _GAP  # optional "ال" prefix (also with gaps)

_HEADER = re.compile(
    r"^[ \t]*(?P<label>(?:" + _AL + r")?" + _FASL + r"|Article|Art\.)"
    + _GAP + r"[ \t]+"
    r"(?P<num>\d+|" + "|".join(_ORDINALS) + r")"
    # "14 مكرر" / "14 bis" is a DIFFERENT article from 14 (inserted later)
    r"(?:[ \t]*(?P<bis>مكرر|bis))?",
    re.MULTILINE,
)


@dataclass(frozen=True)
class RawArticle:
    """An article cut from the text, before metadata enrichment."""

    number: int | None  # parsed article number
    is_bis: bool  # "الفصل 7 مكرر" -> True (distinct from article 7)
    label: str  # header as written
    text: str  # full article text, header included
    start_offset: int  # character offset in the full text (-> page lookup)


def _parse_number(raw: str) -> int | None:
    """Turn "14" or "الأول" into an int; None if unknown."""
    if raw.isdigit():
        return int(raw)
    return _ORDINALS.get(raw)


def split_articles(text: str) -> tuple[str, list[RawArticle]]:
    """Return (preamble, articles).

    The preamble is the text before the first article (title, parties...).
    It is kept separately so nothing from the source is silently lost.
    """
    # Search on a digit-normalized copy ("الفصل ١٤" -> "الفصل 14"); the
    # translation is 1 char -> 1 char, so offsets stay valid and we can
    # slice the ORIGINAL text (citations must keep the original digits).
    matches = list(_HEADER.finditer(normalize_digits(text)))
    if not matches:  # no structure found: caller decides what to do
        return text.strip(), []

    preamble = text[: matches[0].start()].strip()
    articles: list[RawArticle] = []
    for i, m in enumerate(matches):
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        body = text[m.start():end].strip()
        articles.append(
            RawArticle(
                number=_parse_number(m.group("num")),
                is_bis=m.group("bis") is not None,
                label=text[m.start():m.end()].strip(),  # original spelling
                text=body,
                start_offset=m.start(),
            )
        )
    return preamble, articles
