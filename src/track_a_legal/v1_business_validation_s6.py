"""Automated business-readiness checks for DS4 Track A."""

from __future__ import annotations

from typing import Any
from pathlib import Path
import json

from src.track_a_legal.v1_handler import handle_v1
from src.track_a_legal.v1_reference_validation import (
    validate_v1_references,
)


def evaluate_case_s6(request: dict[str, Any]) -> dict[str, Any]:
    """Evaluate observable safeguards without asserting legal correctness."""

    # Execute the official DS4 response pipeline.
    response = handle_v1(request)
    result = response.get("result")
    checks: dict[str, dict[str, Any]] = {}

    # A failed pipeline cannot receive a positive readiness assessment.
    if response.get("status") != "ok" or not isinstance(result, dict):
        return {
            "case_id": request.get("case_id"),
            "automated_status": "blocked",
            "checks": {},
            "lawyer_status": "pending",
        }

    # Verify that the request identity is preserved.
    checks["S6-C01"] = {
        "passed": (
            response.get("request_id") == request.get("request_id")
            and result.get("case_id") == request.get("case_id")
        ),
    }

    # Verify the structural traceability of timeline entries.
    timeline = result.get("timeline", [])
    checks["S6-C02"] = {
        "passed": isinstance(timeline, list) and all(
            isinstance(event, dict)
            and isinstance(event.get("event_id"), str)
            and isinstance(event.get("source_ids"), list)
            and "date_precision" in event
            for event in timeline
        ),
        "scope": "structural_only",
    }

    # Ensure that no claim is automatically declared verified.
    claims = result.get("claims_analysis", [])
    checks["S6-C03"] = {
        "passed": isinstance(claims, list) and all(
            isinstance(claim, dict)
            and claim.get("status") == "unverified"
            for claim in claims
        ),
    }

    # Reuse the existing reference validator.
    reference_errors = validate_v1_references(request)
    # Compare reference errors with the technical baseline.
    # An expected invalid reference is a successful negative test.
    baseline_path = Path(
        "data/mock_cards/track_a_golden_set_technical_v1.json"
    )
    baseline = json.loads(
        baseline_path.read_text(encoding="utf-8-sig")
    )

    # Match both identifiers to avoid selecting an unrelated case.
    reference = next(
        (
            item for item in baseline["cases"]
            if item["case_id"] == request["case_id"]
            and item["request_id"] == request["request_id"]
        ),
        None,
    )

    expected_errors = (
        reference["expected"].get("reference_errors", [])
        if reference is not None
        else []
    )

    checks["S6-C04"] = {
        "passed": (
            reference is not None
            and isinstance(result.get("evidence_mapping"), list)
            and reference_errors == expected_errors
        ),
        "reference_error_count": len(reference_errors),
        "expected_reference_error_count": len(expected_errors),
        "scope": "technical_reference_regression",
    }

    # Record contract limitations without treating them as valid explanations.
    missing = request.get("missing_information", [])
    contradictions = request.get("contradictions", [])
    checks["S6-C05"] = {
        "passed": (
            (not missing or bool(result.get("missing_evidence")))
            and (not contradictions or bool(result.get("contradictions")))
        ),
        "input_missing_count": len(missing),
        "input_contradiction_count": len(contradictions),
        "scope": "response_explainability",
    }

    # Source applicability needs independent legal review.
    checks["S6-C06"] = {
        "passed": None,
        "status": "requires_legal_review",
    }

    # Reject unsupported automatic legal conclusions.
    checks["S6-C07"] = {
        "passed": (
            result.get("legal_conclusion") is None
            and response.get("citations") == []
        ),
        "scope": "automated_abstention",
    }

    # Only a qualified reviewer can validate legal relevance.
    checks["S6-C08"] = {
        "passed": None,
        "status": "requires_lawyer_review",
    }

    # Summarize only the checks that were actually evaluated.
    evaluated = [
        item["passed"]
        for item in checks.values()
        if isinstance(item.get("passed"), bool)
    ]

    return {
        "case_id": request["case_id"],
        "automated_status": (
            "passed" if evaluated and all(evaluated) else "issues_found"
        ),
        "checks": checks,
        "lawyer_status": "pending",
    }
