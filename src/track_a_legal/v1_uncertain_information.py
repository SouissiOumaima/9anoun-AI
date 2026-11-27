"""Build traceable uncertainty diagnostics for Track A v1."""

from __future__ import annotations

from typing import Any

from src.track_a_legal.v1_legal_version_validation import (
    classify_version_diagnostics,
)


def build_uncertain_information(
    request: dict[str, Any],
    analysis: dict[str, Any],
) -> list[dict[str, str]]:
    """Expose existing uncertainties without certifying legal sources."""

    result: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()

    def add(reference_id: str, reason: str) -> None:
        # Preserve deterministic order and remove exact duplicates.
        key = (reference_id, reason)

        if key not in seen:
            seen.add(key)
            result.append({
                "reference_id": reference_id,
                "reason": reason,
            })

    # Preserve the existing reference-error contract.
    for error in analysis["reference_errors"]:
        add(
            str(error["reference_id"]),
            f"{error['code']} at {error['path']}",
        )

    # Expose missing information explicitly declared in the request.
    for item in request.get("missing_information", []):
        add(
            item["missing_id"],
            f"MISSING_INFORMATION: {item['field_name']}: "
            f"{item['reason']}",
        )

    # Expose declared contradictions without certifying them.
    for item in request.get("contradictions", []):
        add(
            item["contradiction_id"],
            f"DECLARED_CONTRADICTION: {item['description']}",
        )

    # Expose documentary and legal assessment reasons.
    for collection, identifier in (
        ("document_fact_assessments", "fact_id"),
        ("legal_source_assessments", "source_id"),
        ("legal_temporal_assessments", "source_id"),
    ):
        for item in analysis.get(collection, []):
            for reason in item["reasons"]:
                add(item[identifier], reason)

    # Expose failed or unavailable PDF verification.
    for item in analysis.get("documentary_assessments", []):
        if item["status"] != "text_matched":
            add(
                item["source_id"],
                item["reason"],
            )

    # Reuse the existing version classification.
    classification = classify_version_diagnostics(
        request.get("legal_sources", []),
        request.get("reference_date"),
        diagnostics=analysis.get("legal_version_errors", []),
    )

    # Do not expose historical informational diagnostics as blockers.
    for item in classification["blocking"]:
        add(item["path"], item["code"])

    # Preserve temporal consistency findings.
    for item in analysis.get("temporal_consistency_findings", []):
        for finding in item["findings"]:
            add(
                item["source_id"],
                f"{finding['code']} at {finding['path']}",
            )

    return result
