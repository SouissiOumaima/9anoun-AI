"""Recall@k on a hand-computed example (no corpus needed).

Five in-scope questions; the rank of the first expected article is:
    q1 -> 1, q2 -> 2, q3 -> 3, q4 -> 4, q5 -> not found (None)

Hand computation (a question counts for Recall@k when rank <= k):
    Recall@1  : only q1                 -> 1/5 = 0.2
    Recall@3  : q1, q2, q3              -> 3/5 = 0.6
    Recall@5  : q1, q2, q3, q4          -> 4/5 = 0.8
    Recall@10 : q1, q2, q3, q4          -> 4/5 = 0.8

`_recall` is a private helper: proving it right proves the arithmetic, not that
the published report carries the figure. The last two tests check the public
surface, `summarize`, on the same five questions.
"""

from __future__ import annotations

import pytest

from src.legal_retrieval.evaluation.metrics import _recall, summarize

RANKS: list[int | None] = [1, 2, 3, 4, None]


def _rows(ranks: list[int | None]) -> list[dict]:
    # Only the keys that _recall reads are needed: "rank".
    return [{"id": f"Q{i}", "rank": r} for i, r in enumerate(ranks, start=1)]


def _report_rows(ranks: list[int | None]) -> list[dict]:
    """Same five questions, with every key `summarize` reads.

    kind is in CORE_KINDS so the questions land in the "core" block; raw_top is
    above any plausible threshold and status is "ok", so the threshold study
    refuses none of them and the headline figures stay the hand-computed ones.
    """
    return [{"id": f"Q{i}", "kind": "sujet", "mode": "live", "status": "ok",
             "rank": r, "top1": None, "raw_top": 12.0, "coverage": 0.9,
             "cosine": None, "article_number_asked": False, "expected": []}
            for i, r in enumerate(ranks, start=1)]


@pytest.mark.parametrize(
    ("k", "expected"),
    [(1, 1 / 5), (3, 3 / 5), (5, 4 / 5), (10, 4 / 5)],
)
def test_recall_at_k_matches_hand_computation(k: int, expected: float) -> None:
    rows = _rows(RANKS)
    assert _recall(rows, k) == pytest.approx(expected)


def test_recall_at_k_is_none_for_empty_scope() -> None:
    # No question in scope: the metric is undefined, not 0.
    assert _recall([], 3) is None


def test_summarize_reports_recall_at_3() -> None:
    """The figure must reach the report, not just the helper."""
    core = summarize(_report_rows(RANKS))["core"]
    assert core["n"] == 5
    assert core["recall@3"] == pytest.approx(0.6)


def test_summarize_keeps_recall_at_3_between_1_and_5() -> None:
    """R@1 <= R@3 <= R@5 always holds: a wider window never finds less.

    This is the invariant a wrong k would break, and it would survive a copy
    and paste error that an equality check on one value would not.
    """
    core = summarize(_report_rows(RANKS))["core"]
    assert core["recall@1"] <= core["recall@3"] <= core["recall@5"]
