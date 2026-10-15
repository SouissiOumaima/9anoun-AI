"""Arabic text normalization used for matching and keyword search.

IMPORTANT: normalized text is NEVER shown to users nor used in citations;
citations always use the original text.
"""

from __future__ import annotations

import re
import unicodedata

# Arabic diacritics (harakat), shadda, sukun, superscript alef.
_DIACRITICS = re.compile(r"[ؐ-ًؚ-ٰٟۖ-ۭ]")
_TATWEEL = "ـ"  # "ـ" stretching character, e.g. "التأمـين"
_ALEF_VARIANTS = re.compile(r"[آأإٱ]")  # آ أ إ ٱ -> ا
_SPACES = re.compile(r"\s+")

# Eastern Arabic (٠-٩) and Persian (۰-۹) digits -> ASCII digits.
_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹", "01234567890123456789")


def normalize_digits(text: str) -> str:
    """Convert Eastern Arabic digits to ASCII (keeps the rest untouched)."""
    return text.translate(_DIGITS)


def normalize_arabic(text: str) -> str:
    """Return a normalized version of `text` for search/matching.

    Steps: unicode NFKC, remove diacritics and tatweel, unify alef variants,
    ى->ي, ة->ه, ASCII digits, lowercase (for French), collapse spaces.
    """
    text = unicodedata.normalize("NFKC", text)  # unify presentation forms
    text = _DIACRITICS.sub("", text)  # drop harakat / shadda
    text = text.replace(_TATWEEL, "")  # drop stretching character
    text = _ALEF_VARIANTS.sub("ا", text)  # all alef forms -> ا
    text = text.replace("ى", "ي")  # ى -> ي
    text = text.replace("ة", "ه")  # ة -> ه
    text = normalize_digits(text)  # ٣ -> 3
    text = text.lower()  # French part of bilingual texts
    return _SPACES.sub(" ", text).strip()  # collapse whitespace
