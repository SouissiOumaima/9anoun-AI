"""Recall@k on a hand-computed example (no corpus needed).

Five in-scope questions; the rank of the first expected article is:
    q1 -> 1, q2 -> 2, q3 -> 3, q4 -> 4, q5 -> not found (None)

Hand computation (a question counts for Recall@k when rank <= k):
    Recall@1  : only q1                 -> 1/5 = 0.2
    Recall@3  : q1, q2, q3              -> 3/5 = 0.6
    Recall@5  : q1, q2, q3, q4          -> 4/5 = 0.8
    Recall@10 : q1, q2, q3, q4          -> 4/5 = 0.8
"""

from __future__ import annotations

import pytest

from src.legal_retrieval.evaluation.metrics import _recall


def _rows(ranks: list[int | None]) -> list[dict]:
    # Only the keys that _recall reads are needed: "rank".
    return [{"id": f"Q{i}", "rank": r} for i, r in enumerate(ranks, start=1)]


@pytest.mark.parametrize(
    ("k", "expected"),
    [(1, 1 / 5), (3, 3 / 5), (5, 4 / 5), (10, 4 / 5)],
)
def test_recall_at_k_matches_hand_computation(k: int, expected: float) -> None:
    rows = _rows([1, 2, 3, 4, None])
    assert _recall(rows, k) == pytest.approx(expected)


def test_recall_at_k_is_none_for_empty_scope() -> None:
    # No question in scope: the metric is undefined, not 0.
    assert _recall([], 3) is None
