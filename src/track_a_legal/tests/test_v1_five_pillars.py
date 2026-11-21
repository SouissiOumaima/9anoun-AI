"""Tests for the internal DS4 five-pillar drafting preparation."""

import pytest

from src.track_a_legal.v1_five_pillars import (
    build_five_pillars,
)


def test_five_pillars_preserve_unverified_claims() -> None:
    """Organize claims without inventing legal conclusions."""

    # Simulate an already validated DS4 internal analysis.
    analysis = {
        "case_id": "CASE-S5-001",
        "claim_traceability": [{
            "claim_id": "CL-001",
            "party_id": "P-001",
            "text": "Declaration fictive.",
            "status": "unverified",
            "event_ids": [],
            "evidence_ids": ["EVD-001"],
            "legal_source_ids": [],
        }],
        "document_fact_assessments": [],
        "legal_source_assessments": [],
        "legal_temporal_assessments": [],
        "legal_conclusion": None,
    }

    # Build the five pillars from internal analysis only.
    result = build_five_pillars(analysis)

    # All five conceptual pillars must be present.
    assert set(result["pillars"]) == {
        "faits",
        "declarations",
        "regles",
        "interpretation",
        "strategie",
    }

    # Preserve the claim and its explicit evidence link.
    declarations = result["pillars"]["declarations"]
    assert declarations[0]["claim_id"] == "CL-001"
    assert declarations[0]["evidence_ids"] == ["EVD-001"]
    assert declarations[0]["status"] == "unverified"

    # No legal conclusion or strategy may be invented.
    assert result["legal_conclusion"] is None
    assert result["pillars"]["regles"] == []
    # No legal sources: interpretation must explicitly abstain.
    assert result["pillars"]["interpretation"] == [{
        "status": "blocked",
        "reason": "insufficient_legal_sources",
        "legal_conclusion": None,
        "citation_ids": [],
    }]
    # Without verified interpretation, legal strategy is blocked.
    assert result["pillars"]["strategie"] == [{
        "status": "blocked",
        "reason": "verified_interpretation_unavailable",
        "recommendations": [],
        "legal_conclusion": None,
    }]


def test_document_fact_requires_authenticity_verification() -> None:
    """A preliminary DS3 qualification must not certify a fact."""

    from src.track_a_legal.v1_five_pillars import (
        build_five_pillars,
    )

    # Simulate an assessment that passed preliminary DS3 checks.
    analysis = {
        "case_id": "CASE-S5-FACT-001",
        "claim_traceability": [],
        "document_fact_assessments": [{
            "fact_id": "FACT-001",
            "eligible_for_established_fact": True,
            "reasons": [],
        }],
        "legal_conclusion": None,
    }

    result = build_five_pillars(analysis)

    # Preserve the qualification without certifying authenticity.
    assert result["pillars"]["faits"] == [{
        "fact_id": "FACT-001",
        "eligible_for_established_fact": True,
        "reasons": [],
        "status": "pending_authenticity_verification",
    }]

    # No legal conclusion can follow from preliminary checks.
    assert result["legal_conclusion"] is None


def test_insufficient_document_fact_is_not_established() -> None:
    """Preserve DS3 rejection reasons without establishing a fact."""

    from src.track_a_legal.v1_five_pillars import (
        build_five_pillars,
    )

    # Simulate a document assessment that failed DS3 checks.
    analysis = {
        "case_id": "CASE-S5-FACT-002",
        "claim_traceability": [],
        "document_fact_assessments": [{
            "fact_id": "FACT-002",
            "eligible_for_established_fact": False,
            "reasons": [
                "USER_NOT_CONFIRMED",
                "MISSING_CITATION",
            ],
        }],
        "legal_conclusion": None,
    }

    result = build_five_pillars(analysis)

    # Keep the original reasons and mark support as insufficient.
    assert result["pillars"]["faits"] == [{
        "fact_id": "FACT-002",
        "eligible_for_established_fact": False,
        "reasons": [
            "USER_NOT_CONFIRMED",
            "MISSING_CITATION",
        ],
        "status": "insufficient_documentary_support",
    }]

    # No legal conclusion can be inferred from this assessment.
    assert result["legal_conclusion"] is None


def test_legal_rule_requires_applicability_verification() -> None:
    """Keep legal sources unconfirmed until applicability is verified."""

    from src.track_a_legal.v1_five_pillars import build_five_pillars

    analysis = {
        "case_id": "CASE-S5-RULE-001",
        "claim_traceability": [],
        "legal_source_assessments": [{
            "source_id": "SOURCE-001",
            "eligible_for_legal_support": True,
            "reasons": [],
        }],
        "legal_temporal_assessments": [{
            "source_id": "SOURCE-001",
            "temporal_eligibility": "not_confirmed",
            "eligible_for_legal_conclusion": False,
            "validity_status_reported": "unknown",
            "reasons": ["VALIDITY_STATUS_REQUIRES_REVIEW"],
        }],
        "legal_conclusion": None,
    }

    result = build_five_pillars(analysis)

    # Preserve the source and both assessment results.
    rules = result["pillars"]["regles"]

    assert len(rules) == 1
    assert rules[0]["source_id"] == "SOURCE-001"
    assert rules[0]["eligible_for_legal_support"] is True
    assert rules[0]["temporal_eligibility"] == "not_confirmed"
    assert rules[0]["eligible_for_legal_conclusion"] is False
    assert rules[0]["status"] == "pending_applicability_verification"

    # A preliminary legal rule cannot generate a conclusion.
    assert result["legal_conclusion"] is None

def test_legal_rule_without_temporal_assessment() -> None:
    """Never confirm applicability when temporal checks are missing."""

    from src.track_a_legal.v1_five_pillars import build_five_pillars

    analysis = {
        "case_id": "CASE-S5-RULE-002",
        "claim_traceability": [],
        "legal_source_assessments": [{
            "source_id": "SOURCE-002",
            "eligible_for_legal_support": True,
            "reasons": [],
        }],
        "legal_temporal_assessments": [],
        "legal_conclusion": None,
    }

    result = build_five_pillars(analysis)

    # Preserve the source but explicitly identify missing checks.
    rules = result["pillars"]["regles"]

    assert len(rules) == 1
    assert rules[0]["source_id"] == "SOURCE-002"
    assert rules[0]["temporal_eligibility"] == "not_assessed"
    assert rules[0]["eligible_for_legal_conclusion"] is False
    assert rules[0]["status"] == "temporal_verification_missing"

    # Missing temporal checks must never produce legal conclusions.
    assert result["legal_conclusion"] is None

def test_interpretation_blocked_without_legal_sources() -> None:
    """Block legal interpretation when legal support is unavailable."""

    from src.track_a_legal.v1_five_pillars import build_five_pillars

    analysis = {
        "case_id": "CASE-S5-INTERP-001",
        "claim_traceability": [{
            "claim_id": "CLAIM-001",
            "party_id": "PARTY-001",
            "text": "Fictitious unverified claim",
            "status": "unverified",
            "event_ids": [],
            "evidence_ids": [],
            "legal_source_ids": [],
        }],
        "legal_source_assessments": [],
        "legal_temporal_assessments": [],
        "legal_conclusion": None,
    }

    result = build_five_pillars(analysis)

    # No legal source means no substantive interpretation.
    interpretation = result["pillars"]["interpretation"]

    assert interpretation == [{
        "status": "blocked",
        "reason": "insufficient_legal_sources",
        "legal_conclusion": None,
        "citation_ids": [],
    }]

    # Preserve the global no-conclusion guarantee.
    assert result["legal_conclusion"] is None

def test_interpretation_pending_with_unverified_legal_source() -> None:
    """Do not infer legal conclusions from preliminary legal sources."""

    from src.track_a_legal.v1_five_pillars import build_five_pillars

    analysis = {
        "case_id": "CASE-S5-INTERP-002",
        "claim_traceability": [],
        "legal_source_assessments": [{
            "source_id": "SOURCE-INTERP-001",
            "eligible_for_legal_support": True,
            "reasons": [],
        }],
        "legal_temporal_assessments": [{
            "source_id": "SOURCE-INTERP-001",
            "temporal_eligibility": "not_confirmed",
            "eligible_for_legal_conclusion": False,
            "validity_status_reported": "unknown",
            "reasons": ["VALIDITY_STATUS_REQUIRES_REVIEW"],
        }],
        "legal_conclusion": None,
    }

    result = build_five_pillars(analysis)

    # A source can be present without being legally applicable.
    assert result["pillars"]["interpretation"] == [{
        "status": "pending_verification",
        "reason": "additional_legal_verification_required",
        "legal_conclusion": None,
        "citation_ids": [],
    }]

    # Never generate legal conclusions automatically.
    assert result["legal_conclusion"] is None

def test_strategy_blocked_without_verified_interpretation() -> None:
    """Never propose legal strategy without verified interpretation."""

    from src.track_a_legal.v1_five_pillars import build_five_pillars

    analysis = {
        "case_id": "CASE-S5-STRATEGY-001",
        "claim_traceability": [{
            "claim_id": "CLAIM-STRATEGY-001",
            "party_id": "PARTY-001",
            "text": "Fictitious unverified claim",
            "status": "unverified",
            "event_ids": [],
            "evidence_ids": [],
            "legal_source_ids": [],
        }],
        "legal_source_assessments": [],
        "legal_temporal_assessments": [],
        "legal_conclusion": None,
    }

    result = build_five_pillars(analysis)

    # No verified interpretation means no legal strategy.
    assert result["pillars"]["strategie"] == [{
        "status": "blocked",
        "reason": "verified_interpretation_unavailable",
        "recommendations": [],
        "legal_conclusion": None,
    }]

    # Preserve the global no-conclusion guarantee.
    assert result["legal_conclusion"] is None


def test_orphan_temporal_assessment_is_rejected() -> None:
    """Reject temporal assessments without a matching legal source."""

    import pytest

    from src.track_a_legal.v1_five_pillars import build_five_pillars

    # Internal analysis contains no legal source assessments.
    # The temporal assessment refers to a nonexistent source.
    analysis = {
        "case_id": "CASE-S5-ORPHAN-001",
        "claim_traceability": [],
        "legal_source_assessments": [],
        "legal_temporal_assessments": [
            {
                "source_id": "SRC-999",
                "temporal_eligibility": "not_confirmed",
                "reasons": [],
            }
        ],
    }

    # Fail closed instead of silently ignoring the orphan assessment.
    with pytest.raises(
        ValueError,
        match="Orphan legal temporal source_id",
    ):
        build_five_pillars(analysis)


def test_duplicate_document_fact_id_is_rejected() -> None:
    """Reject ambiguous documentary fact identifiers."""

    import pytest

    from src.track_a_legal.v1_five_pillars import (
        build_five_pillars,
    )

    # Both assessments refer to the same fact identifier.
    # Different qualification results must not hide this ambiguity.
    analysis = {
        "case_id": "CASE-S5-DUPLICATE-FACT-001",
        "claim_traceability": [],
        "document_fact_assessments": [
            {
                "fact_id": "FACT-001",
                "eligible_for_established_fact": True,
                "reasons": [],
            },
            {
                "fact_id": "FACT-001",
                "eligible_for_established_fact": False,
                "reasons": ["USER_NOT_CONFIRMED"],
            },
        ],
        "legal_conclusion": None,
    }

    # Fail closed rather than accepting ambiguous fact references.
    with pytest.raises(
        ValueError,
        match="Duplicate document fact_id",
    ):
        build_five_pillars(analysis)


@pytest.mark.parametrize(
    "invalid_analysis",
    [
        None,
        {"case_id": "", "claim_traceability": []},
        {"case_id": "CASE-1"},
        {"case_id": "CASE-1", "claim_traceability": [None]},
        {"case_id": "CASE-1", "claim_traceability": [], "document_fact_assessments": None},
        {"case_id": "CASE-1", "claim_traceability": [], "document_fact_assessments": [None]},
        {"case_id": "CASE-1", "claim_traceability": [], "document_fact_assessments": [{"fact_id": ""}]},
        {"case_id": "CASE-1", "claim_traceability": [], "legal_source_assessments": None},
        {"case_id": "CASE-1", "claim_traceability": [], "legal_temporal_assessments": None},
        {"case_id": "CASE-1", "claim_traceability": [], "legal_temporal_assessments": [None]},
        {"case_id": "CASE-1", "claim_traceability": [], "legal_temporal_assessments": [{}]},
        {"case_id": "CASE-1", "claim_traceability": [], "legal_temporal_assessments": [{"source_id": "SRC-1"}, {"source_id": "SRC-1"}]},
        {"case_id": "CASE-1", "claim_traceability": [], "legal_source_assessments": [None]},
        {"case_id": "CASE-1", "claim_traceability": [], "legal_source_assessments": [{}]},
        {"case_id": "CASE-1", "claim_traceability": [], "legal_source_assessments": [{"source_id": "SRC-1"}, {"source_id": "SRC-1"}]},
    ],
)
def test_five_pillars_rejects_invalid_inputs(invalid_analysis):
    """Reject malformed internal analysis before building legal pillars."""
    from src.track_a_legal.v1_five_pillars import build_five_pillars

    # Invalid data must not produce legal reasoning output.
    with pytest.raises(ValueError):
        build_five_pillars(invalid_analysis)
