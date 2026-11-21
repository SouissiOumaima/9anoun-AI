"""Regression tests for DS4 S6 business-readiness evaluation."""

import copy
import json
from pathlib import Path

import pytest

from src.track_a_legal.v1_business_validation_s6 import evaluate_case_s6


# Load the seven existing fictitious cases.
CASES_PATH = Path("data/mock_cards/track_a_case_cards_v1.json")
CASES = json.loads(CASES_PATH.read_text(encoding="utf-8-sig"))


@pytest.mark.parametrize("case", CASES, ids=lambda c: c["case_id"])
def test_s6_existing_cases(case):
    """Preserve expected outcomes without asserting legal correctness."""

    report = evaluate_case_s6(case)

    # The current contract limits explanations for cases 003 and 004.
    expected_status = (
        "issues_found"
        if case["case_id"] in {"CASE-A-003", "CASE-A-004"}
        else "passed"
    )

    assert report["automated_status"] == expected_status
    assert report["lawyer_status"] == "pending"

    # No automated evaluation can substitute for lawyer review.
    assert report["checks"]["S6-C06"]["passed"] is None
    assert report["checks"]["S6-C08"]["passed"] is None
    assert report["checks"]["S6-C07"]["passed"] is True

    # The reference regression must match the technical baseline.
    assert report["checks"]["S6-C04"]["passed"] is True


def test_s6_unknown_case_is_not_accepted():
    """Reject automatic acceptance of a case absent from the baseline."""

    unknown = copy.deepcopy(CASES[0])
    unknown["case_id"] = "CASE-A-S6-UNKNOWN"
    unknown["request_id"] = "REQ-A-S6-UNKNOWN"

    report = evaluate_case_s6(unknown)

    assert report["checks"]["S6-C04"]["passed"] is False
    assert report["automated_status"] != "passed"
    assert report["lawyer_status"] == "pending"
