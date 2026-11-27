from collections import Counter

# Les sept cas fictifs et les six critères soumis à revue humaine.
EXPECTED_PAIRS = {
    (f"CASE-A-{i:03d}", criterion)
    for i in range(1, 8)
    for criterion in (
        "S6-C02", "S6-C03", "S6-C04",
        "S6-C05", "S6-C06", "S6-C08"
    )
}


def validate_review_pairs(reviews, require_complete=False):
    """Contrôler les couples de revue sans produire de décision juridique."""

    if not isinstance(reviews, list):
        raise ValueError("reviews must be a list")

    for review in reviews:
        if not isinstance(review, dict) or any(
            not isinstance(review.get(key), str) or not review[key].strip()
            for key in ("case_id", "criterion_id")
        ):
            raise ValueError("Each review must contain case_id and criterion_id strings")

    pairs = [
        (review["case_id"], review["criterion_id"])
        for review in reviews
    ]

    counts = Counter(pairs)

    duplicates = [
        pair for pair, count in counts.items()
        if count > 1
    ]

    unknown = set(pairs) - EXPECTED_PAIRS
    missing = EXPECTED_PAIRS - set(pairs)

    if duplicates:
        raise ValueError(f"Duplicate review pairs: {duplicates}")

    if unknown:
        raise ValueError(f"Unknown review pairs: {sorted(unknown)}")

    if require_complete and missing:
        raise ValueError(f"Missing review pairs: {sorted(missing)}")

    return {
        "valid": True,
        "review_count": len(pairs),
        "missing_count": len(missing),
        "complete": len(missing) == 0
    }
