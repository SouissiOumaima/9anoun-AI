"""Internal five-pillar preparation for the DS4 Lawyer Track.

This module does not produce legal conclusions.
The official Response v1 contract remains unchanged.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any


def build_five_pillars(
    analysis: dict[str, Any],
) -> dict[str, Any]:
    """Organize preliminary case information without legal inference.

    The caller must provide a validated DS4 internal analysis.
    Explicit claim links are preserved, not independently verified.
    """

    # Reject invalid analysis inputs rather than inventing content.
    if not isinstance(analysis, dict):
        raise ValueError("Invalid internal case analysis.")

    case_id = analysis.get("case_id")

    if not isinstance(case_id, str) or not case_id.strip():
        raise ValueError("Missing or invalid case_id.")

    claims = analysis.get("claim_traceability")

    if not isinstance(claims, list):
        raise ValueError("Missing or invalid claim_traceability.")

    # Rebuild declarations with an enforced unverified status.
    # Deep copies prevent changes to the original analysis.
    declarations = []

    for claim in claims:
        if not isinstance(claim, dict):
            raise ValueError("Invalid claim traceability item.")

        declaration = deepcopy(claim)

        # An explicit reference does not establish legal truth.
        declaration["status"] = "unverified"

        declarations.append(declaration)

    # Preserve preliminary DS3 document assessments.
    # These assessments do not authenticate source documents.
    assessments = analysis.get("document_fact_assessments", [])

    if not isinstance(assessments, list):
        raise ValueError("Invalid document_fact_assessments.")

    faits = []
    seen_fact_ids = set()

    for assessment in assessments:
        if not isinstance(assessment, dict):
            raise ValueError("Invalid document fact assessment.")

        # Reject missing or duplicate documentary fact identifiers.
        fact_id = assessment.get("fact_id")

        if not isinstance(fact_id, str) or not fact_id.strip():
            raise ValueError("Missing or invalid document fact_id.")

        if fact_id in seen_fact_ids:
            raise ValueError(
                f"Duplicate document fact_id: {fact_id}"
            )

        seen_fact_ids.add(fact_id)
        # Copy the assessment to avoid mutating the input.
        fact = deepcopy(assessment)

        # Preliminary eligibility is not proof of authenticity.
        if fact.get("eligible_for_established_fact") is True:
            fact["status"] = "pending_authenticity_verification"
        else:
            fact["status"] = "insufficient_documentary_support"

        faits.append(fact)
    # Keep unverified legal reasoning pillars empty.
    # Document assessments are not automatically established facts.
    # Preserve preliminary DS3 legal-source assessments.
    # Textual eligibility does not establish legal applicability.
    source_assessments = analysis.get("legal_source_assessments", [])
    temporal_assessments = analysis.get("legal_temporal_assessments", [])

    if not isinstance(source_assessments, list):
        raise ValueError("Invalid legal_source_assessments.")

    if not isinstance(temporal_assessments, list):
        raise ValueError("Invalid legal_temporal_assessments.")

    # Match temporal assessments using explicit source identifiers.
    temporal_by_source = {}

    for temporal in temporal_assessments:
        if not isinstance(temporal, dict):
            raise ValueError("Invalid legal temporal assessment.")

        source_id = temporal.get("source_id")

        if not isinstance(source_id, str) or not source_id.strip():
            raise ValueError("Missing legal temporal source_id.")

        if source_id in temporal_by_source:
            raise ValueError("Duplicate legal temporal source_id.")

        temporal_by_source[source_id] = temporal

    rules = []
    seen_sources = set()

    for assessment in source_assessments:
        if not isinstance(assessment, dict):
            raise ValueError("Invalid legal source assessment.")

        source_id = assessment.get("source_id")

        if not isinstance(source_id, str) or not source_id.strip():
            raise ValueError("Missing legal source_id.")

        if source_id in seen_sources:
            raise ValueError("Duplicate legal source_id.")

        seen_sources.add(source_id)

        # Preserve DS3 evaluation without modifying its data.
        rule = deepcopy(assessment)
        temporal = temporal_by_source.get(source_id)

        if temporal is not None:
            rule["temporal_eligibility"] = temporal.get(
                "temporal_eligibility"
            )
            rule["validity_status_reported"] = temporal.get(
                "validity_status_reported"
            )
            rule["temporal_reasons"] = deepcopy(
                temporal.get("reasons", [])
            )
            rule["status"] = "pending_applicability_verification"
        else:
            # Missing temporal evidence cannot establish applicability.
            rule["temporal_eligibility"] = "not_assessed"
            rule["validity_status_reported"] = None
            rule["temporal_reasons"] = [
                "TEMPORAL_ASSESSMENT_MISSING"
            ]
            rule["status"] = "temporal_verification_missing"

        # No preliminary assessment can authorize legal conclusions.
        rule["eligible_for_legal_conclusion"] = False

        rules.append(rule)
    # Reject temporal assessments without a matching legal source.
    # Fail closed: inconsistent references cannot support legal reasoning.
    orphan_source_ids = set(temporal_by_source) - seen_sources

    if orphan_source_ids:
        orphan_id = sorted(orphan_source_ids)[0]
        raise ValueError(
            f"Orphan legal temporal source_id: {orphan_id}"
        )

    # Interpretation remains preparatory until legal verification.
    # Never infer applicability or conclusions from source presence.
    if not rules:
        interpretation_status = "blocked"
        interpretation_reason = "insufficient_legal_sources"
    else:
        interpretation_status = "pending_verification"
        interpretation_reason = "additional_legal_verification_required"

    interpretation = [{
        "status": interpretation_status,
        "reason": interpretation_reason,
        "legal_conclusion": None,
        "citation_ids": [],
    }]
    pillars = {
        "faits": faits,
        "declarations": declarations,
        "regles": rules,
        "interpretation": interpretation,
        "strategie": [{
            "status": "blocked",
            "reason": "verified_interpretation_unavailable",
            "recommendations": [],
            "legal_conclusion": None,
        }],
    }

    return {
        "case_id": case_id,
        "pillars": pillars,
        "legal_conclusion": None,
    }
