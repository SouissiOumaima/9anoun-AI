"""Vocabulary of the legal_retrieval.v0 request fields (D21), for DS1.

    from src.legal_retrieval.contract.vocabulary import sector_codes, worker_category_codes

The JSON file (data/mock_cards/legal_retrieval_vocabulary.v0.json) is the
reference; these helpers only read it, so DS1 never copies the lists by hand.
"""

from __future__ import annotations

import json
from functools import cache
from pathlib import Path
from typing import Any

# vocabulary.py -> contract -> legal_retrieval -> src -> <repo root>
VOCABULARY_PATH = (Path(__file__).resolve().parents[3]
                   / "data" / "mock_cards" / "legal_retrieval_vocabulary.v0.json")


@cache
def load_vocabulary() -> dict[str, Any]:
    """The whole vocabulary file (read once)."""
    data: dict[str, Any] = json.loads(VOCABULARY_PATH.read_text(encoding="utf-8"))
    return data


def sector_codes() -> list[str]:
    """Values DS1 may send in `sector` (null = no sector given)."""
    return [s["code"] for s in load_vocabulary()["sectors"]]


def worker_category_codes() -> list[str]:
    """Values DS1 may send in `worker_category` (null = not given)."""
    return [c["code"] for c in load_vocabulary()["worker_categories"]]
