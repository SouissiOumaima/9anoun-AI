"""Unit tests for conservative documentary verification."""

import pytest

from src.track_a_legal.tools.documentary_verification import (
    verify_documentary_citation,
)


def make_source(page=1, excerpt="Article fictif."):
    """Build a synthetic legal citation."""
    return {
        "source_id": "SRC-TEST-001",
        "citation": {
            "document": "document_fictif.pdf",
            "page": page,
            "exact_excerpt": excerpt,
        },
    }


def test_exact_documentary_match():
    """Accept an exact match without certifying authenticity."""
    result = verify_documentary_citation(
        make_source(),
        ["Article fictif."],
    )

    assert result["status"] == "text_matched"
    assert result["official_authenticity_confirmed"] is False
    assert result["legal_applicability_confirmed"] is False


def test_whitespace_normalization():
    """Accept formatting differences only."""
    result = verify_documentary_citation(
        make_source(),
        ["Article\n   fictif."],
    )

    assert result["status"] == "text_matched"


def test_documentary_mismatch():
    """Reject a non-matching excerpt."""
    result = verify_documentary_citation(
        make_source(),
        ["Autre disposition."],
    )

    assert result["status"] == "not_matched"


@pytest.mark.parametrize("page", [None, 0, -1, True, "1"])
def test_invalid_page(page):
    """Never invent or coerce a citation page."""
    result = verify_documentary_citation(
        make_source(page=page),
        ["Article fictif."],
    )

    assert result["status"] == "not_verifiable"
    assert result["reason"] == "MISSING_CITATION_PAGE"


def test_document_unavailable():
    """Handle missing original documents."""
    result = verify_documentary_citation(make_source(), None)

    assert result["status"] == "not_verifiable"
    assert result["reason"] == "DOCUMENT_UNAVAILABLE"


def test_page_out_of_range():
    """Reject pages outside the document."""
    result = verify_documentary_citation(
        make_source(page=2),
        ["Article fictif."],
    )

    assert result["reason"] == "PAGE_OUT_OF_RANGE"


def test_empty_page():
    """Do not classify an unreadable page as false evidence."""
    result = verify_documentary_citation(make_source(), [""])

    assert result["status"] == "not_verifiable"
    assert result["reason"] == "PAGE_TEXT_UNAVAILABLE"


def test_missing_citation():
    """Handle missing citation metadata."""
    result = verify_documentary_citation(
        {"source_id": "SRC-TEST-002"},
        ["Article fictif."],
    )

    assert result["reason"] == "MISSING_CITATION"


def test_missing_excerpt():
    """Reject empty citation excerpts."""
    result = verify_documentary_citation(
        make_source(excerpt=""),
        ["Article fictif."],
    )

    assert result["reason"] == "MISSING_CITATION_EXCERPT"


def test_numeric_difference():
    """Preserve legally significant numerical differences."""
    result = verify_documentary_citation(
        make_source(excerpt="Salaire: 500 TND"),
        ["Salaire: 600 TND"],
    )

    assert result["status"] == "not_matched"


def test_match_on_wrong_page():
    """Never silently replace the declared citation page."""
    result = verify_documentary_citation(
        make_source(page=1),
        ["Autre article.", "Article fictif."],
    )

    assert result["status"] == "not_matched"
