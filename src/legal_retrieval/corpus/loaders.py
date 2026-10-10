"""Load the raw corpus into page texts.

TEXT source  = data/raw/txt/*.json (Tradrly OCR): Arabic words are readable.
NUMBER check = data/raw/pdf/*.pdf (pymupdf): digits reliable, but Arabic is
stored as private-use glyphs U+F2xx (see DECISIONS D16 and D1 of DS5).

The JSON loader accepts these shapes:
  1. [{"page": 1, "text": "..."}, ...]
  2. {"pages": [{"page_number": 1, "content": "..."}, ...], ...}
  3. {"text": "..."}  /  {"content": "..."}
  4. anything else -> all strings collected recursively (no page numbers)
"""

from __future__ import annotations

import json
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pymupdf

_TEXT_KEYS = ("text", "content", "page_content", "body")
_PAGE_KEYS = ("page", "page_number", "page_num", "num")
_PAGES_KEYS = ("pages", "data", "items")


@dataclass(frozen=True)
class Page:
    """Text of one page; number is None when the file has no paging."""

    number: int | None
    text: str


def _page_from_dict(d: dict[str, Any], fallback_number: int) -> Page | None:
    """Build a Page from a dict that has a text-like key."""
    text = next((d[k] for k in _TEXT_KEYS if isinstance(d.get(k), str)), None)
    if text is None:
        return None
    raw_num = next((d[k] for k in _PAGE_KEYS if k in d), fallback_number)
    number = int(raw_num) if str(raw_num).isdigit() else fallback_number
    return Page(number=number, text=text)


def _collect_strings(obj: Any, out: list[str]) -> None:
    """Depth-first collection of every string value (last-resort shape)."""
    if isinstance(obj, str):
        out.append(obj)
    elif isinstance(obj, dict):
        for value in obj.values():
            _collect_strings(value, out)
    elif isinstance(obj, list):
        for value in obj:
            _collect_strings(value, out)


def parse_pages(data: Any) -> list[Page]:
    """Turn decoded JSON into an ordered list of pages."""
    items: Any = data
    if isinstance(data, dict):
        # shape 2: a container key holding a list of pages
        items = next((data[k] for k in _PAGES_KEYS
                      if isinstance(data.get(k), list)), data)
    if isinstance(items, list) and items and all(isinstance(i, dict) for i in items):
        pages = [_page_from_dict(d, n) for n, d in enumerate(items, start=1)]
        if all(p is not None for p in pages):
            return [p for p in pages if p is not None]  # shapes 1 and 2
    if isinstance(items, dict):
        single = _page_from_dict(items, 1)
        if single is not None:
            return [Page(number=None, text=single.text)]  # shape 3
    strings: list[str] = []
    _collect_strings(data, strings)
    return [Page(number=None, text="\n".join(strings))]  # shape 4


def load_pages(path: Path) -> list[Page]:
    """Read one corpus file from disk."""
    with path.open(encoding="utf-8") as fh:  # files are UTF-8 Arabic
        return parse_pages(json.load(fh))


def load_pdf_pages(path: Path) -> list[Page]:
    """Read the native text layer of a PDF, one Page per PDF page (1-based)."""
    pages: list[Page] = []
    with pymupdf.open(path) as doc:  # closes the file even on error
        for index, page in enumerate(doc, start=1):
            # sort=True orders blocks top->bottom, which keeps article order
            raw = page.get_text("text", sort=True)
            # NFKC turns Arabic presentation forms ("ﺍﻟﻔﺼﻞ") back into
            # normal letters ("الفصل"); without it no header is detected.
            pages.append(Page(number=index, text=unicodedata.normalize("NFKC", raw)))
    return pages


def reversed_text_ratio(text: str) -> float:
    """Share of "فصل" written backwards ("لصف") among all occurrences.

    Some RTL extractions return Arabic words in reversed character order.
    A ratio close to 1.0 means the file must be fixed before splitting.
    """
    forward = text.count("فصل")  # normal reading order
    backward = text.count("لصف")  # reversed reading order
    total = forward + backward
    return backward / total if total else 0.0
