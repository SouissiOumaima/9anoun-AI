import pytest

from src.track_a_legal.lawyer_review_validator_s9 import (
    EXPECTED_PAIRS,
    validate_review_pairs,
)


def make_review(case_id, criterion_id):
    """Construire une entrée minimale pour tester les couples."""
    return {
        "case_id": case_id,
        "criterion_id": criterion_id,
    }


def test_partial_review_accepted():
    """Une revue partielle doit rester autorisée."""
    reviews = [make_review("CASE-A-001", "S6-C02")]

    result = validate_review_pairs(reviews)

    assert result["valid"] is True
    assert result["complete"] is False
    assert result["missing_count"] == 41


def test_duplicate_rejected():
    """Un même couple ne doit pas apparaître deux fois."""
    review = make_review("CASE-A-001", "S6-C02")

    with pytest.raises(ValueError, match="Duplicate"):
        validate_review_pairs([review, review])


def test_unknown_pair_rejected():
    """Un cas ou critère inconnu doit être refusé."""
    reviews = [make_review("CASE-A-999", "S6-C02")]

    with pytest.raises(ValueError, match="Unknown"):
        validate_review_pairs(reviews)


def test_incomplete_review_rejected():
    """Le mode complet exige les 42 couples attendus."""
    reviews = [make_review("CASE-A-001", "S6-C02")]

    with pytest.raises(ValueError, match="Missing"):
        validate_review_pairs(reviews, require_complete=True)


def test_complete_review_accepted():
    """Les 42 couples uniques doivent être acceptés."""
    reviews = [
        make_review(case_id, criterion_id)
        for case_id, criterion_id in sorted(EXPECTED_PAIRS)
    ]

    result = validate_review_pairs(
        reviews,
        require_complete=True,
    )

    assert result["valid"] is True
    assert result["review_count"] == 42
    assert result["missing_count"] == 0
    assert result["complete"] is True


def test_invalid_type_rejected():
    """Une valeur non-list doit être refusée."""
    with pytest.raises(ValueError, match="must be a list"):
        validate_review_pairs("invalid")
