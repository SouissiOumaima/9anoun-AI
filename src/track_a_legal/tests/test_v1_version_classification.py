"""Tests for legal version diagnostic classification."""

from src.track_a_legal.v1_legal_version_validation import (
    classify_version_diagnostics,
)


def make_source(version, start, end, applicable):
    """Build a fictitious legal version."""
    return {
        "source_id": f"SRC-{version}",
        "version_group": "GROUP-1",
        "version": version,
        "effective_from": start,
        "effective_to": end,
        "applicable_at_reference_date": applicable,
    }


def test_coherent_version_history():
    """Historical and future versions remain informational."""
    sources = [
        make_source(1, "2020-01-01", "2024-12-31", False),
        make_source(2, "2025-01-01", "2027-12-31", True),
        make_source(3, "2028-01-01", None, False),
    ]

    result = classify_version_diagnostics(sources, "2026-03-01")

    assert result["blocking"] == []
    assert {
        item["code"] for item in result["informational"]
    } == {"NO_LONGER_EFFECTIVE", "NOT_YET_EFFECTIVE"}


def test_isolated_future_version_remains_blocking():
    """A future version without replacement remains blocking."""
    sources = [
        make_source(1, "2028-01-01", None, False),
    ]

    result = classify_version_diagnostics(sources, "2026-03-01")

    assert result["informational"] == []
    assert result["blocking"][0]["code"] == "NOT_YET_EFFECTIVE"


def test_expired_applicable_version_remains_blocking():
    """An expired version declared applicable is contradictory."""
    sources = [
        make_source(1, "2020-01-01", "2024-12-31", True),
    ]

    result = classify_version_diagnostics(sources, "2026-03-01")

    assert result["informational"] == []
    assert {
        item["code"] for item in result["blocking"]
    } == {
        "NO_LONGER_EFFECTIVE",
        "APPLICABILITY_DATE_CONTRADICTION",
    }


def test_multiple_applicable_versions_remain_blocking():
    """Conflicting applicable versions cannot be accepted."""
    sources = [
        make_source(1, "2020-01-01", None, True),
        make_source(2, "2025-01-01", None, True),
    ]

    result = classify_version_diagnostics(sources, "2026-03-01")

    assert result["informational"] == []
    assert any(
        item["code"] == "MULTIPLE_APPLICABLE_VERSIONS"
        for item in result["blocking"]
    )


def test_different_version_group_cannot_replace_future_source():
    """A different legal group cannot justify a future version."""
    future = make_source(1, "2028-01-01", None, False)
    current = make_source(2, "2025-01-01", None, True)
    current["version_group"] = "GROUP-2"

    result = classify_version_diagnostics(
        [future, current], "2026-03-01"
    )

    assert result["informational"] == []
    assert result["blocking"][0]["code"] == "NOT_YET_EFFECTIVE"


def test_unknown_start_cannot_justify_historical_version():
    """An unknown effective start cannot establish coherence."""
    sources = [
        make_source(1, "2020-01-01", "2024-12-31", False),
        make_source(2, None, None, True),
    ]

    result = classify_version_diagnostics(sources, "2026-03-01")

    assert result["informational"] == []
    assert result["blocking"][0]["code"] == "NO_LONGER_EFFECTIVE"


def test_reuse_precomputed_diagnostics(monkeypatch):
    """Reuse existing diagnostics without rerunning validation."""
    from src.track_a_legal import v1_legal_version_validation as module

    sources = [
        make_source(1, "2028-01-01", None, False),
    ]

    diagnostics = module.validate_legal_versions(
        sources, "2026-03-01"
    )

    def forbidden_call(*args, **kwargs):
        raise AssertionError("Unexpected duplicate validation")

    monkeypatch.setattr(
        module, "validate_legal_versions", forbidden_call
    )

    result = module.classify_version_diagnostics(
        sources,
        "2026-03-01",
        diagnostics=diagnostics,
    )

    assert result["blocking"] == diagnostics
    assert result["informational"] == []
