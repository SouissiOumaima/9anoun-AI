"""Text -> search terms, and article references found in a question (D26).

The SAME function cuts the corpus and the question: a light, predictable
stemming applied on both sides matters more than linguistic perfection.

    terms("الإجازات السنوية للعامل")   -> ["اجاز", "سنوي", "عامل"]
    article_refs("ما ينص عليه الفصل 42 مكرر") -> [("42", "BIS")]
"""

from __future__ import annotations

import re

from ..corpus.normalize import normalize_arabic

# after normalize_arabic: one alef, ة->ه, ى->ي, ASCII digits, lowercase French
_TOKEN = re.compile(r"[ء-ي]+|[a-zà-ÿ]+|\d+")

# Function words (normalized form). "فصل" is not a topic word: an article
# number in the question is handled by article_refs, not by BM25.
_STOPWORDS_RAW = """
في من على الي الى عن ان او و ثم قد لا لم لن ما ماذا متي كيف هل اي التي الذي الذين اللذين
هذا هذه ذلك تلك هو هي هم هن كل بعض بين عند مع غير كان يكون تكون كانت ليس اذا حيث حتي
لدي به بها له لها فيه فيها منه منها عليه عليها اليه عنه الا اما بعد قبل
فصل فصول الفصل الفصول
le la les de des du un une et en au aux pour par sur dans est que qui quel quelle
quels quelles ce cette ces se sa son ses il elle ils a l d
"""
# normalized like the text they are compared with ("على" -> "علي")
STOPWORDS = frozenset(normalize_arabic(w) for w in _STOPWORDS_RAW.split())

# conjunction / preposition glued to the article "ال", longest first
_PREFIXES = ("وبال", "وال", "بال", "كال", "فال", "لل", "ال")
# plural / feminine / pronoun endings, removed only from long words
_SUFFIXES = (("ات", 5), ("ون", 5), ("ين", 5), ("ها", 5), ("ه", 4))


def stem(token: str) -> str:
    """Light Arabic stemming: drop "ال"-type prefixes and common endings."""
    if not ("ء" <= token[0] <= "ي"):
        return token  # digits and French words unchanged
    for prefix in _PREFIXES:
        if token.startswith(prefix) and len(token) - len(prefix) >= 2:
            token = token[len(prefix):]
            break
    else:  # "و" conjunction alone: only on long words ("وعطله", never "وزير" short ones)
        if token.startswith("و") and len(token) > 4:
            token = token[1:]
    for suffix, min_len in _SUFFIXES:
        if token.endswith(suffix) and len(token) >= min_len:
            return token[: -len(suffix)]
    return token


def terms(text: str) -> list[str]:
    """Search terms of a text (normalized, without function words, stemmed)."""
    words = _TOKEN.findall(normalize_arabic(text))
    return [stem(w) for w in words if w not in STOPWORDS]


# "الفصل 42" / "بالفصل 42 مكرر" / "الفصل 46 - 3" / "article 14 bis"
_SUFFIX_CODE = {"مكرر": "BIS", "مثلث": "TER", "مربع": "QUATER",
                "bis": "BIS", "ter": "TER", "quater": "QUATER"}
_REF = re.compile(
    r"(?:\b[وبلك]{0,2}ال)?فصل\s*(\d+)(?:\s*-\s*(\d+))?\s*(مكرر|مثلث|مربع)?"
    r"|\bart(?:icle|\.)?\s*(\d+)(?:\s*-\s*(\d+))?\s*(bis|ter|quater)?")


def article_refs(question: str) -> list[tuple[str, str]]:
    """Article numbers asked in the question: [(number, suffix)] e.g. ("46-3", "")."""
    refs: list[tuple[str, str]] = []
    for m in _REF.finditer(normalize_arabic(question)):
        number, sub, suffix = (m.group(1), m.group(2), m.group(3)) if m.group(1) \
            else (m.group(4), m.group(5), m.group(6))
        ref = (f"{number}-{sub}" if sub else number, _SUFFIX_CODE.get(suffix or "", ""))
        if ref not in refs:
            refs.append(ref)
    return refs


def without_refs(question: str) -> str:
    """The question minus its article references (their digits are not topic words)."""
    return _REF.sub(" ", normalize_arabic(question))
