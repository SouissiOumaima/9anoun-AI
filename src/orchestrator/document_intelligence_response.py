"""Compatibility and evidence guards for DS3 v1/v2 responses owned by DS1.

This module does not choose business confidence thresholds.  Callers must pass
the threshold accepted for their destination (UI review, DS4 or DS5).  It
does, however, make unsafe fields unusable by default: null values, missing
citations and empty excerpts can never become established facts.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from .tool_contracts import ToolContractError


@dataclass(frozen=True, slots=True)
class FieldAssessment:
    name: str
    usable: bool
    reason: str | None = None


def normalize_ds3_response(response: Mapping[str, Any]) -> dict[str, Any]:
    """Normalize DS3 v1 or proposed v2 to DS1's common tool-response shape."""

    version = response.get("contract_version")
    if version == "ds3.v1":
        return _normalize_v1(response)
    if version == "ds3.v2":
        return _normalize_v2(response)
    raise ToolContractError("DS3 response must use ds3.v1 or ds3.v2")


def assess_document_fields(
    *, result: Mapping[str, Any], citations: list[Mapping[str, Any]], minimum_confidence: float,
) -> list[FieldAssessment]:
    """Assess fields without inferring values or silently picking a threshold."""

    if not 0.0 <= minimum_confidence <= 1.0:
        raise ValueError("minimum_confidence must be between 0 and 1")
    fields = result.get("fields")
    if not isinstance(fields, Mapping):
        return []
    cited = {
        item.get("citation_id"): item for item in citations
        if isinstance(item, Mapping) and isinstance(item.get("citation_id"), str)
    }
    assessments: list[FieldAssessment] = []
    for name, field in fields.items():
        if not isinstance(name, str) or not isinstance(field, Mapping):
            continue
        if field.get("value") is None:
            assessments.append(FieldAssessment(name, False, "value_missing"))
            continue
        confidence = field.get("confidence")
        if not isinstance(confidence, (int, float)) or isinstance(confidence, bool):
            assessments.append(FieldAssessment(name, False, "confidence_missing"))
            continue
        if confidence < minimum_confidence:
            assessments.append(FieldAssessment(name, False, "confidence_below_threshold"))
            continue
        citation = cited.get(field.get("citation_id"))
        if citation is None:
            assessments.append(FieldAssessment(name, False, "citation_missing"))
            continue
        if not isinstance(citation.get("excerpt"), str) or not citation["excerpt"].strip():
            assessments.append(FieldAssessment(name, False, "citation_excerpt_missing"))
            continue
        assessments.append(FieldAssessment(name, True))
    return assessments


def _normalize_v1(response: Mapping[str, Any]) -> dict[str, Any]:
    status = response.get("status")
    if status in {"success", "partial"}:
        result = response.get("result")
        if not isinstance(result, Mapping):
            raise ToolContractError("DS3 v1 successful response requires result")
        return {
            "status": status,
            "data": {
                "result": result, "warnings": list(response.get("warnings", [])),
                "computed_by": "document_intelligence.mock", "mode": response.get("meta", {}).get("mode"),
                "complete": status == "success",
            },
            "citations": list(response.get("citations", [])), "error": None,
        }
    if status == "error":
        return {
            "status": "error", "data": None, "citations": [],
            "error": response.get("error") or {"code": "INTERNAL_ERROR", "retryable": False},
        }
    raise ToolContractError("DS3 v1 response has an invalid status")


def _normalize_v2(response: Mapping[str, Any]) -> dict[str, Any]:
    status = response.get("status")
    if status == "ok":
        result = response.get("result")
        if not isinstance(result, Mapping):
            raise ToolContractError("DS3 v2 ok response requires result")
        complete = result.get("complete")
        if not isinstance(complete, bool):
            raise ToolContractError("DS3 v2 ok response requires result.complete")
        return {
            "status": "success" if complete else "partial",
            "data": {
                "result": result, "warnings": list(response.get("warnings", [])),
                "computed_by": response.get("computed_by"), "mode": response.get("mode"), "complete": complete,
            },
            "citations": list(response.get("citations", [])), "error": None,
        }
    if status == "refus":
        refusal = response.get("refus")
        if not isinstance(refusal, Mapping):
            raise ToolContractError("DS3 v2 refusal requires refus")
        return {"status": "refused", "data": None, "citations": [], "error": dict(refusal)}
    if status == "erreur":
        error = response.get("erreur")
        if not isinstance(error, Mapping):
            raise ToolContractError("DS3 v2 error requires erreur")
        normalized = dict(error)
        if response.get("ds3_code") is not None:
            normalized["ds3_code"] = response["ds3_code"]
        if isinstance(response.get("retryable"), bool):
            normalized["retryable"] = response["retryable"]
        return {"status": "error", "data": None, "citations": [], "error": normalized}
    raise ToolContractError("DS3 v2 response has an invalid status")
