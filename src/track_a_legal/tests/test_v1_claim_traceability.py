"""Regression tests for explicit DS4 claim traceability."""

from src.track_a_legal.v1_reference_validation import (
    validate_v1_references,
)


def test_unknown_claim_evidence_is_reported() -> None:
    """An unknown claim-evidence link must remain detectable."""

    # Use a fictitious case with one unsupported evidence reference.
    request = {
        "parties": [
            {
                "party_id": "P-001",
                "name": "Personne fictive",
                "role": "demandeur",
            }
        ],
        "events": [],
        "claims": [
            {
                "claim_id": "CL-001",
                "party_id": "P-001",
                "text": "Declaration fictive.",
                "evidence_ids": ["EVD-UNKNOWN"],
            }
        ],
        "evidence": [],
    }

    # Check cross-references without creating any evidence mapping.
    errors = validate_v1_references(request)

    # Preserve the exact invalid identifier and its source path.
    assert errors == [
        {
            "code": "UNKNOWN_REFERENCE",
            "path": "claims/0/evidence_ids/0",
            "reference_id": "EVD-UNKNOWN",
        }
    ]


def test_unknown_claim_event_is_reported() -> None:
    """An unknown event linked to a claim must be reported."""

    # Reference an event that does not exist.
    request = {
        "parties": [{"party_id": "P-001"}],
        "events": [],
        "claims": [{
            "claim_id": "CL-001",
            "party_id": "P-001",
            "text": "Declaration fictive.",
            "event_ids": ["EV-UNKNOWN"],
        }],
        "evidence": [],
    }

    # Verify the exact unknown reference.
    assert validate_v1_references(request) == [{
        "code": "UNKNOWN_REFERENCE",
        "path": "claims/0/event_ids/0",
        "reference_id": "EV-UNKNOWN",
    }]


def test_unknown_claim_legal_source_is_reported() -> None:
    """An unknown legal source linked to a claim must be reported."""

    # Reference a legal source that does not exist.
    request = {
        "parties": [{"party_id": "P-001"}],
        "events": [],
        "claims": [{
            "claim_id": "CL-001",
            "party_id": "P-001",
            "text": "Declaration fictive.",
            "legal_source_ids": ["SRC-UNKNOWN"],
        }],
        "evidence": [],
        "legal_sources": [],
    }

    # Verify the exact unknown legal-source reference.
    assert validate_v1_references(request) == [{
        "code": "UNKNOWN_REFERENCE",
        "path": "claims/0/legal_source_ids/0",
        "reference_id": "SRC-UNKNOWN",
    }]


def test_valid_claim_evidence_link_is_preserved() -> None:
    """Preserve explicit evidence links without verifying a claim."""

    # Import the future internal traceability component.
    from src.track_a_legal.v1_claim_traceability import (
        build_claim_traceability,
    )

    # Use a fictitious claim and an explicitly referenced document.
    request = {
        "parties": [{"party_id": "P-001"}],
        "events": [],
        "claims": [{
            "claim_id": "CL-001",
            "party_id": "P-001",
            "text": "Declaration fictive.",
            "evidence_ids": ["EVD-001"],
        }],
        "evidence": [{
            "evidence_id": "EVD-001",
            "type": "document",
            "description": "Document fictif.",
            "source": "document-test.pdf",
        }],
        "legal_sources": [],
    }

    # Build an internal traceability representation.
    result = build_claim_traceability(request)

    # Keep only the explicit, valid evidence relationship.
    assert result == [{
        "claim_id": "CL-001",
        "party_id": "P-001",
        "text": "Declaration fictive.",
        "status": "unverified",
        "event_ids": [],
        "evidence_ids": ["EVD-001"],
        "legal_source_ids": [],
    }]


def test_invalid_links_are_excluded_without_mutation() -> None:
    """Exclude unknown links without changing the original request."""

    from copy import deepcopy
    from src.track_a_legal.v1_claim_traceability import (
        build_claim_traceability,
    )

    # Include one valid and one unknown evidence identifier.
    request = {
        "parties": [{"party_id": "P-001"}],
        "events": [],
        "claims": [{
            "claim_id": "CL-001",
            "party_id": "P-001",
            "text": "Declaration fictive.",
            "evidence_ids": ["EVD-001", "EVD-UNKNOWN"],
        }],
        "evidence": [{
            "evidence_id": "EVD-001",
            "type": "document",
            "description": "Document fictif.",
            "source": "document-test.pdf",
        }],
        "legal_sources": [],
    }

    # Preserve a complete copy to detect accidental mutation.
    original_request = deepcopy(request)

    result = build_claim_traceability(request)

    # Only explicitly referenced, existing evidence is retained.
    assert result[0]["evidence_ids"] == ["EVD-001"]

    # Never promote a claim to verified status.
    assert result[0]["status"] == "unverified"

    # The source request must remain unchanged.
    assert request == original_request


def test_case_analysis_exposes_internal_claim_traceability() -> None:
    """Expose claim links internally without legal conclusions."""

    from src.track_a_legal.v1_case_analysis import analyze_case_v1

    # Construct a minimal schema-valid fictitious request.
    request = {
        "contract_version": "track_a.v1",
        "request_id": "REQ-S4-001",
        "case_id": "CASE-S4-001",
        "lang": "fr",
        "parties": [{
            "party_id": "P-001",
            "name": "Personne fictive",
            "role": "demandeur",
        }],
        "events": [],
        "claims": [{
            "claim_id": "CL-001",
            "party_id": "P-001",
            "text": "Declaration fictive.",
            "evidence_ids": ["EVD-001"],
        }],
        "evidence": [{
            "evidence_id": "EVD-001",
            "type": "document",
            "description": "Document fictif.",
            "source": "document-test.pdf",
        }],
    }

    # Execute the real v1 analysis pipeline.
    analysis = analyze_case_v1(request)

    # Verify the internal S4 traceability result.
    assert analysis["claim_traceability"] == [{
        "claim_id": "CL-001",
        "party_id": "P-001",
        "text": "Declaration fictive.",
        "status": "unverified",
        "event_ids": [],
        "evidence_ids": ["EVD-001"],
        "legal_source_ids": [],
    }]

    # Never infer a legal conclusion from a document link.
    assert analysis["legal_conclusion"] is None
