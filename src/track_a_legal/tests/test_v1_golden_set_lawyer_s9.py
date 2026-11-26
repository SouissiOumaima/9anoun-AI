"""Regression tests for the S9 lawyer-review preparation dataset."""

import json
from copy import deepcopy
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator


ROOT = Path("data/mock_cards")


def load_json(filename):
    """Load a UTF-8 JSON fixture."""
    return json.loads(
        (ROOT / filename).read_text(encoding="utf-8-sig")
    )


def get_validator():
    """Create the official S9 preparation validator."""
    schema = load_json(
        "schemas/track_a_golden_set_lawyer_s9.v1.schema.json"
    )
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema)


def test_s9_dataset_matches_schema():
    """Validate the complete S9 preparation dataset."""
    dataset = load_json("track_a_golden_set_lawyer_s9.v1.json")
    get_validator().validate(dataset)


def test_s9_preserves_s6_criteria_and_cases():
    """Verify S9 coverage against the original S6 baseline."""
    s6 = load_json("track_a_business_validation_s6.v1.json")
    s9 = load_json("track_a_golden_set_lawyer_s9.v1.json")

    assert s9["criteria"] == s6["criteria"]

    expected_ids = [case["case_id"] for case in s6["cases"]]
    actual_ids = [case["case_id"] for case in s9["cases"]]

    assert actual_ids == expected_ids
    assert len(actual_ids) == len(set(actual_ids))

    review_ids = {
        criterion["id"]
        for criterion in s6["criteria"]
        if criterion["verification"] != "automated"
    }

    for case in s9["cases"]:
        ids = [
            review["criterion_id"]
            for review in case["lawyer_reviews"]
        ]
        assert set(ids) == review_ids
        assert len(ids) == len(set(ids))


def test_s9_contains_no_invented_lawyer_decisions():
    """Keep all legal assessments pending until human review."""
    dataset = load_json("track_a_golden_set_lawyer_s9.v1.json")

    assert dataset["lawyer_validated"] is False

    for case in dataset["cases"]:
        assert case["lawyer_status"] == "pending"

        for review in case["lawyer_reviews"]:
            assert review["decision"] is None
            assert review["comments"] is None
            assert review["supporting_references"] == []


@pytest.mark.parametrize(
    "field,value",
    [
        ("decision", "approved"),
        ("comments", "Automatically validated"),
        ("supporting_references", ["FAKE-REFERENCE"]),
    ],
)
def test_s9_rejects_prefilled_lawyer_reviews(field, value):
    """Reject unauthorized lawyer annotations in preparation mode."""
    dataset = load_json("track_a_golden_set_lawyer_s9.v1.json")
    modified = deepcopy(dataset)

    modified["cases"][0]["lawyer_reviews"][0][field] = value

    assert not get_validator().is_valid(modified)


def test_s9_rejects_automatic_lawyer_validation():
    """Prevent automatic promotion to lawyer-validated status."""
    dataset = load_json("track_a_golden_set_lawyer_s9.v1.json")
    modified = deepcopy(dataset)

    modified["lawyer_validated"] = True

    assert not get_validator().is_valid(modified)
