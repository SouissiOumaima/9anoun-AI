"""Secure local PDF resolution for DS4 documentary verification."""

from pathlib import Path
from hashlib import sha256
from typing import Any
import io

from src.track_a_legal.tools.documentary_verification import (
    verify_documentary_citation,
)


def verify_local_pdf(
    source: dict[str, Any],
    pdf_root: Path,
) -> dict[str, Any]:
    """Verify a citation against its associated local PDF."""

    # Preserve preliminary validation and conservative defaults.
    result = verify_documentary_citation(source, None)
    result["pdf_sha256"] = None
    result["resolved_document"] = None

    if result["reason"] != "DOCUMENT_UNAVAILABLE":
        return result

    document = source["citation"]["document"]

    # Reject absolute paths and directory traversal.
    if (
        "/" in document
        or "\\" in document
        or ":" in document
        or document in {".", ".."}
    ):
        result["reason"] = "UNSAFE_DOCUMENT_IDENTIFIER"
        return result

    # Resolve only known PDF or JSON document extensions.
    name = Path(document)

    if name.suffix.lower() not in {".pdf", ".json"}:
        result["reason"] = "UNSUPPORTED_DOCUMENT_FORMAT"
        return result

    root = Path(pdf_root).resolve()
    candidate = (root / name.with_suffix(".pdf")).resolve()

    # Prevent access outside the authorized PDF directory.
    if candidate.parent != root:
        result["reason"] = "UNSAFE_DOCUMENT_PATH"
        return result

    if not candidate.is_file():
        result["reason"] = "DOCUMENT_UNAVAILABLE"
        return result

    # Read and hash the same bytes used for extraction.
    try:
        import pymupdf

        content = candidate.read_bytes()
        fingerprint = sha256(content).hexdigest()

        with pymupdf.open(
            stream=content,
            filetype="pdf",
        ) as pdf:
            pages = [page.get_text() for page in pdf]

    except ImportError:
        result["reason"] = "PDF_READER_UNAVAILABLE"
        return result

    except Exception:
        result["reason"] = "PDF_EXTRACTION_FAILED"
        return result

    # Compare the declared citation against the resolved PDF.
    result = verify_documentary_citation(source, pages)
    result["pdf_sha256"] = fingerprint
    result["resolved_document"] = candidate.name

    return result
