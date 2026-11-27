"""Tests for secure documentary PDF verification."""

from hashlib import sha256

import pytest

from src.track_a_legal.tools.documentary_pdf_adapter import (
    verify_local_pdf,
)

pymupdf = pytest.importorskip("pymupdf")


def make_source(document="test.pdf", page=1):
    """Build a synthetic citation."""
    return {
        "source_id": "SRC-TEST",
        "citation": {
            "document": document,
            "page": page,
            "exact_excerpt": "Article fictif.",
        },
    }


@pytest.fixture
def pdf_file(tmp_path):
    """Create an independent temporary PDF."""
    path = tmp_path / "test.pdf"

    with pymupdf.open() as pdf:
        page = pdf.new_page()
        page.insert_text((72, 72), "Article fictif.")
        pdf.save(path)

    return path


def test_pdf_match(pdf_file):
    """Verify actual PDF extraction and fingerprint."""
    result = verify_local_pdf(
        make_source(), pdf_file.parent
    )

    assert result["status"] == "text_matched"
    assert result["resolved_document"] == "test.pdf"
    assert result["pdf_sha256"] == sha256(
        pdf_file.read_bytes()
    ).hexdigest()

    assert result["official_authenticity_confirmed"] is False
    assert result["legal_applicability_confirmed"] is False


def test_json_to_pdf_resolution(pdf_file):
    """Resolve a JSON source to its corresponding PDF."""
    result = verify_local_pdf(
        make_source(document="test.json"),
        pdf_file.parent,
    )

    assert result["status"] == "text_matched"
    assert result["resolved_document"] == "test.pdf"


@pytest.mark.parametrize("document", [
    "../test.pdf",
    "..\\test.pdf",
    "/test.pdf",
    "C:\\test.pdf",
    "folder/test.pdf",
])
def test_unsafe_document_identifier(tmp_path, document):
    """Prevent access outside the authorized directory."""
    result = verify_local_pdf(
        make_source(document=document), tmp_path
    )

    assert result["status"] == "not_verifiable"
    assert result["reason"] == "UNSAFE_DOCUMENT_IDENTIFIER"
    assert result["pdf_sha256"] is None


def test_missing_pdf(tmp_path):
    """Handle unavailable original documents."""
    result = verify_local_pdf(make_source(), tmp_path)

    assert result["reason"] == "DOCUMENT_UNAVAILABLE"


def test_unsupported_extension(tmp_path):
    """Reject unsupported document formats."""
    result = verify_local_pdf(
        make_source(document="test.exe"), tmp_path
    )

    assert result["reason"] == "UNSUPPORTED_DOCUMENT_FORMAT"


def test_corrupted_pdf(tmp_path):
    """Handle invalid PDF content without crashing."""
    (tmp_path / "test.pdf").write_bytes(b"Invalid PDF")

    result = verify_local_pdf(make_source(), tmp_path)

    assert result["status"] == "not_verifiable"
    assert result["reason"] == "PDF_EXTRACTION_FAILED"


def test_missing_page(pdf_file):
    """Never infer an undeclared citation page."""
    result = verify_local_pdf(
        make_source(page=None), pdf_file.parent
    )

    assert result["reason"] == "MISSING_CITATION_PAGE"
    assert result["pdf_sha256"] is None


def test_page_out_of_range(pdf_file):
    """Reject nonexistent PDF pages."""
    result = verify_local_pdf(
        make_source(page=2), pdf_file.parent
    )

    assert result["reason"] == "PAGE_OUT_OF_RANGE"


def test_pdf_content_mismatch(pdf_file):
    """Detect a citation absent from the declared page."""
    source = make_source()
    source["citation"]["exact_excerpt"] = "Autre article."

    result = verify_local_pdf(source, pdf_file.parent)

    assert result["status"] == "not_matched"
    assert result["reason"] == "EXCERPT_NOT_FOUND_ON_DECLARED_PAGE"
