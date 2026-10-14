"""Find the references an article makes to other legal texts (future CITE edges).

Works on the NORMALIZED text (أ->ا, ة->ه, ى->ي, digits ASCII). Kinds:
  article    "بالفصل 51 فقرة (ب)", "الفصلين الاول و2 من هذا الامر"  -> article(s) N
  avenant    "الملحق التعديلي عدد 3"                              -> avenant N
  external   "مجله الشغل", "الامر عدد 1112 لسنه 1975", "القانون عدد 27"
The target of an article reference is read in the words that follow:
  "من مجله الشغل" (OCR: "مجل الشغل"), or "... مجله الشغل وخاصه الفصل 143 منها"
      -> code_travail ;
  "من الاتفاقيه (المشتركه) الاطاريه" -> CC-CADRE ;
  "من الامر / القانون / المرسوم" -> external_text ; otherwise -> same_source.
Never a reference: an article header ("الفصل 51 (جديد):") or a repeal list ("(الغيت").
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from ..corpus.normalize import normalize_arabic

_ORDINALS = {"الاول": 1, "الثاني": 2, "الثالث": 3, "الرابع": 4, "الخامس": 5,
             "السادس": 6, "السابع": 7, "الثامن": 8, "التاسع": 9, "العاشر": 10}
_NUM = r"(?:\d+(?:\s*مكرر)?|" + "|".join(_ORDINALS) + r")"
# clitics glued before the word: و/ف then ب/ل/ك, then ال or ل ("بالفصل", "للفصل" = ل+الفصل)
_ARTICLE_REF = re.compile(
    r"(?<!\S)(?:و|ف)?(?:ب|ل|ك)?(?:ال|ل)?(?:فصل|فصلين|فصلان|فصول)\s*"
    r"(?P<nums>" + _NUM + r"(?:\s*(?:و|،|,|-|–|الي)\s*" + _NUM + r")*)"
    r"(?=(?P<after>[^\n]{0,60}))")  # lookahead: the next reference stays findable
_AVENANT_REF = re.compile(r"(?:ال)?ملحق\s*(?:ال)?تعديلي\S*\s*عدد\s*(?P<n>\d+)")
_CODE = r"مجل[هي]?\s*الشغل"  # "مجلة الشغل"; the OCR often drops/changes the final ة
_EXTERNAL = re.compile(
    _CODE +
    r"|(?:ال)?(?:امر|قانون|مرسوم)(?:\s*الحكومي)?\s*عدد\s*\d+(?:\s*لسنه\s*\d{4})?")
_HEADER_AFTER = re.compile(r"^\s*(?:\(\s*جديد\s*\))?\s*[:：]")  # "الفصل 51 (جديد):"


@dataclass(frozen=True)
class Reference:
    """One reference found in an article text."""

    kind: str  # "article" | "avenant" | "external"
    target: str  # same_source | code_travail | CC-CADRE | external_text | avenant | text
    numbers: tuple[str, ...]  # "51", "7BIS" ; ("3",) for an avenant ; () for external
    span: str  # the reference itself, at most 60 characters (never the article body)
    after: str = ""  # the words that name the target ("من الامر عدد 501 لسنه 1982")


def _numbers(raw: str) -> tuple[str, ...]:
    """"الاول و2 مكرر" -> ("1", "2BIS")."""
    found = []
    for token, bis in re.findall(r"(\d+|" + "|".join(_ORDINALS) + r")(\s*مكرر)?", raw):
        number = str(_ORDINALS.get(token, token))
        found.append(number + ("BIS" if bis.strip() else ""))
    return tuple(found)


def _target(after: str, before: str) -> str:
    """Which text an article reference points to.

    Read in the words that follow it; "منها" (of it) points BACK to the text named
    just before: "مقتضيات مجلة الشغل وخاصة الفصل 143 منها" -> Code du travail.
    """
    # stop at the next reference or sentence end: "الفصل 99 والملحق ... والفصل 5 من
    # الاتفاقيه الاطاريه" -> the Cadre target belongs to article 5, not to 99
    head = re.split(r"فصل|ملحق|[.؛;]", after, maxsplit=1)[0][:45]
    if re.search(_CODE, head) or (re.match(r"\s*منه[اا]?\b", head)
                                   and re.search(_CODE, before)):
        return "code_travail"
    if re.search(r"الاتفاقيه\s*(?:المشتركه\s*)?الاطاريه", head):
        return "CC-CADRE"
    if re.search(r"(?:من|ب)\s*(?:ال)?(?:امر|قانون|مرسوم)", head):
        return "external_text"
    return "same_source"


def find_references(text: str) -> list[Reference]:
    """All references of an article text (normalized internally)."""
    norm = normalize_arabic(text)
    refs: list[Reference] = []
    for m in _ARTICLE_REF.finditer(norm):
        after = m.group("after")
        if _HEADER_AFTER.match(after) or re.match(r"\s*:?\s*\(?\s*(?:تم\s*)?(?:الغي|ملغ)", after):
            continue  # a header (R1/R4) or a repeal list (R2): not a citation
        before = norm[max(0, m.start() - 50): m.start()]
        refs.append(Reference("article", _target(after, before), _numbers(m.group("nums")),
                              norm[m.start(): m.end("nums")][:60], after.strip()[:45]))
    for m in _AVENANT_REF.finditer(norm):
        refs.append(Reference("avenant", "avenant", (m.group("n"),), m.group(0)[:60]))
    for m in _EXTERNAL.finditer(norm):
        refs.append(Reference("external", "text", (), m.group(0)[:60]))
    return refs
