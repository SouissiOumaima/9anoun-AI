"""Conservative documentary verification for DS4."""

from typing import Any
import unicodedata


def normalize_documentary_text(text: str) -> str:
    """Normalize Unicode and whitespace without changing legal content."""
    return " ".join(
        unicodedata.normalize("NFC", text).split()
    )


def verify_documentary_citation(
    source: dict[str, Any],
    document_pages: list[str] | None,
) -> dict[str, Any]:
    """Compare a citation with independently extracted document pages."""

    result = {
        "source_id": source.get("source_id"),
        "status": "not_verifiable",
        "reason": None,
        "official_authenticity_confirmed": False,
        "legal_applicability_confirmed": False,
    }

    citation = source.get("citation")

    # Never invent missing citation metadata.
    if not isinstance(citation, dict):
        result["reason"] = "MISSING_CITATION"
        return result

    document = citation.get("document")
    page = citation.get("page")
    excerpt = citation.get("exact_excerpt")

    if not isinstance(document, str) or not document.strip():
        result["reason"] = "MISSING_DOCUMENT_IDENTIFIER"
        return result

    if type(page) is not int or page < 1:
        result["reason"] = "MISSING_CITATION_PAGE"
        return result

    if not isinstance(excerpt, str) or not excerpt.strip():
        result["reason"] = "MISSING_CITATION_EXCERPT"
        return result

    # Require independently supplied document content.
    if document_pages is None:
        result["reason"] = "DOCUMENT_UNAVAILABLE"
        return result

    if page > len(document_pages):
        result["reason"] = "PAGE_OUT_OF_RANGE"
        return result

    page_text = document_pages[page - 1]

    if not isinstance(page_text, str) or not page_text.strip():
        result["reason"] = "PAGE_TEXT_UNAVAILABLE"
        return result

    # Compare without fuzzy matching or invented evidence.
    if normalize_documentary_text(excerpt) in normalize_documentary_text(page_text):
        result["status"] = "text_matched"
        result["reason"] = "EXCERPT_FOUND_ON_DECLARED_PAGE"
    else:
        result["status"] = "not_matched"
        result["reason"] = "EXCERPT_NOT_FOUND_ON_DECLARED_PAGE"

    return result
