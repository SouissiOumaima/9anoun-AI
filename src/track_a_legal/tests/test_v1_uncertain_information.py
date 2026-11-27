"""Regression tests for Track A v1 uncertainty diagnostics."""

from copy import deepcopy

from src.track_a_legal.v1_uncertain_information import (
    build_uncertain_information,
)


def test_empty_diagnostics():
    assert build_uncertain_information(
        {}, {"reference_errors": []}
    ) == []


def test_preserve_reference_error():
    analysis = {
        "reference_errors": [{
            "reference_id": "EVD-UNKNOWN",
            "code": "UNKNOWN_REFERENCE",
            "path": "events/0/evidence_ids/0",
        }]
    }

    assert build_uncertain_information({}, analysis) == [{
        "reference_id": "EVD-UNKNOWN",
        "reason": "UNKNOWN_REFERENCE at events/0/evidence_ids/0",
    }]


def test_documentary_fact_reasons():
    analysis = {
        "reference_errors": [],
        "document_fact_assessments": [{
            "fact_id": "FACT-001",
            "reasons": [
                "USER_NOT_CONFIRMED",
                "LOW_OR_MISSING_CONFIDENCE",
            ],
        }],
    }

    result = build_uncertain_information({}, analysis)

    assert result == [
        {
            "reference_id": "FACT-001",
            "reason": "USER_NOT_CONFIRMED",
        },
        {
            "reference_id": "FACT-001",
            "reason": "LOW_OR_MISSING_CONFIDENCE",
        },
    ]


def test_deduplicate_legal_and_pdf_reasons():
    analysis = {
        "reference_errors": [],
        "legal_source_assessments": [{
            "source_id": "SRC-001",
            "reasons": ["MISSING_CITATION_PAGE"],
        }],
        "legal_temporal_assessments": [{
            "source_id": "SRC-001",
            "reasons": [
                "MISSING_CITATION_PAGE",
                "EFFECTIVE_DATE_UNKNOWN",
            ],
        }],
        "documentary_assessments": [{
            "source_id": "SRC-001",
            "status": "not_verifiable",
            "reason": "MISSING_CITATION_PAGE",
        }],
    }

    result = build_uncertain_information({}, analysis)

    assert len(result) == 2
    assert result[0]["reason"] == "MISSING_CITATION_PAGE"
    assert result[1]["reason"] == "EFFECTIVE_DATE_UNKNOWN"


def test_declared_missing_information_and_contradictions():
    request = {
        "missing_information": [{
            "missing_id": "M1",
            "field_name": "sector",
            "reason": "Sector unknown.",
        }],
        "contradictions": [{
            "contradiction_id": "C1",
            "description": "Conflicting salary amounts.",
        }],
    }

    result = build_uncertain_information(
        request, {"reference_errors": []}
    )

    assert result == [
        {
            "reference_id": "M1",
            "reason": "MISSING_INFORMATION: sector: Sector unknown.",
        },
        {
            "reference_id": "C1",
            "reason": "DECLARED_CONTRADICTION: Conflicting salary amounts.",
        },
    ]


def test_pdf_match_does_not_generate_uncertainty():
    analysis = {
        "reference_errors": [],
        "documentary_assessments": [{
            "source_id": "SRC-001",
            "status": "text_matched",
            "reason": "EXCERPT_FOUND_ON_DECLARED_PAGE",
        }],
    }

    assert build_uncertain_information({}, analysis) == []


def test_pdf_failure_is_traceable():
    analysis = {
        "reference_errors": [],
        "documentary_assessments": [{
            "source_id": "SRC-001",
            "status": "not_matched",
            "reason": "EXCERPT_NOT_FOUND_ON_DECLARED_PAGE",
        }],
    }

    assert build_uncertain_information({}, analysis) == [{
        "reference_id": "SRC-001",
        "reason": "EXCERPT_NOT_FOUND_ON_DECLARED_PAGE",
    }]


def test_temporal_consistency_findings():
    analysis = {
        "reference_errors": [],
        "temporal_consistency_findings": [{
            "source_id": "SRC-001",
            "findings": [{
                "code": "EFFECTIVE_DATE_DIVERGENCE",
                "path": "effective_date",
            }],
        }],
    }

    assert build_uncertain_information({}, analysis) == [{
        "reference_id": "SRC-001",
        "reason": "EFFECTIVE_DATE_DIVERGENCE at effective_date",
    }]


def test_determinism_and_input_preservation():
    request = {"reference_date": None}
    analysis = {
        "reference_errors": [],
        "legal_version_errors": [{
            "code": "REFERENCE_DATE_MISSING",
            "path": "reference_date",
        }],
    }

    original_request = deepcopy(request)
    original_analysis = deepcopy(analysis)

    first = build_uncertain_information(request, analysis)
    second = build_uncertain_information(request, analysis)

    assert first == second == [{
        "reference_id": "reference_date",
        "reason": "REFERENCE_DATE_MISSING",
    }]
    assert request == original_request
    assert analysis == original_analysis


def test_historical_version_is_informational():
    request = {
        "reference_date": "2026-03-01",
        "legal_sources": [
            {
                "source_id": "SRC-V1",
                "version_group": "GROUP-001",
                "effective_from": "2020-01-01",
                "effective_to": "2025-12-31",
                "applicable_at_reference_date": False,
            },
            {
                "source_id": "SRC-V2",
                "version_group": "GROUP-001",
                "effective_from": "2026-01-01",
                "effective_to": None,
                "applicable_at_reference_date": True,
            },
        ],
    }

    analysis = {
        "reference_errors": [],
        "legal_version_errors": [{
            "code": "NO_LONGER_EFFECTIVE",
            "path": "legal_sources[0]",
        }],
    }

    # Une version historique coherente ne constitue pas un blocage.
    assert build_uncertain_information(request, analysis) == []


def test_inconsistent_applicable_version_remains_blocking():
    request = {
        "reference_date": "2026-03-01",
        "legal_sources": [{
            "source_id": "SRC-V1",
            "version_group": "GROUP-001",
            "effective_from": "2027-01-01",
            "effective_to": None,
            "applicable_at_reference_date": True,
        }],
    }

    analysis = {
        "reference_errors": [],
        "legal_version_errors": [
            {
                "code": "NOT_YET_EFFECTIVE",
                "path": "legal_sources[0]",
            },
            {
                "code": "APPLICABILITY_DATE_CONTRADICTION",
                "path": "legal_sources[0].applicable_at_reference_date",
            },
        ],
    }

    # Une version future declaree applicable reste bloquante.
    result = build_uncertain_information(request, analysis)

    assert result == [
        {
            "reference_id": "legal_sources[0]",
            "reason": "NOT_YET_EFFECTIVE",
        },
        {
            "reference_id": "legal_sources[0].applicable_at_reference_date",
            "reason": "APPLICABILITY_DATE_CONTRADICTION",
        },
    ]
