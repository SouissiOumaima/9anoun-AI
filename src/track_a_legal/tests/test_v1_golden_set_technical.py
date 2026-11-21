"""Technical Golden Set regression for fictitious Track A cases."""

import json
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker

from src.track_a_legal.v1_case_analysis import analyze_case_v1
from src.track_a_legal.v1_handler import handle_v1


def test_technical_golden_set_v1() -> None:
    """Validate technical expectations without legal truth labels."""

    # Load the DS4 technical baseline.
    root = Path("data/mock_cards")
    baseline = json.loads(
        (root / "track_a_golden_set_technical_v1.json")
        .read_text(encoding="utf-8-sig")
    )

    # Never treat this dataset as lawyer-validated ground truth.
    assert baseline["validation_level"] == "technical_only"
    assert baseline["lawyer_validated"] is False

    # Load the official response contract.
    schema = json.loads(
        (root / "schemas/track_a_response.v1.schema.json")
        .read_text(encoding="utf-8-sig")
    )
    validator = Draft202012Validator(
        schema,
        format_checker=FormatChecker(),
    )

    # Validate every Case Card against the official Request v1.
    request_schema = json.loads(
        (root / "schemas/track_a_request.v1.schema.json")
        .read_text(encoding="utf-8-sig")
    )
    request_validator = Draft202012Validator(
        request_schema,
        format_checker=FormatChecker(),
    )

    # Check each reference case independently.
    assert baseline["cases"], "Golden Set must not be empty"

    for reference in baseline["cases"]:
        # Locate the requested fictitious Case Card.
        cases = json.loads(
            (root / reference["input_file"])
            .read_text(encoding="utf-8-sig")
        )
        matches = [
            case for case in cases
            if case["case_id"] == reference["case_id"]
            and case["request_id"] == reference["request_id"]
        ]
        assert len(matches) == 1

        # Validate the input before executing the DS4 pipeline.
        case = matches[0]
        request_validator.validate(case)

        # Execute the official handler and internal analysis.
        response = handle_v1(case)
        expected = reference["expected"]

        # Verify both the official contract and request identity.
        assert expected["response_schema_valid"] is True
        validator.validate(response)
        assert response["request_id"] == reference["request_id"]

        # Check internal diagnostics only when explicitly expected.
        diagnostic_keys = (
            "reference_errors",
            "document_fact_assessments",
            "legal_source_assessments",
            "legal_temporal_assessments",
            "legal_version_errors",
            "temporal_consistency_findings",
        )

        if any(key in expected for key in diagnostic_keys):
            analysis = analyze_case_v1(case)

            # Verify unknown or duplicate references when specified.
            if "reference_errors" in expected:
                assert (
                    analysis["reference_errors"]
                    == expected["reference_errors"]
                )

            # Verify documentary eligibility and rejection reasons.
            if "document_fact_assessments" in expected:
                assert (
                    analysis["document_fact_assessments"]
                    == expected["document_fact_assessments"]
                )

            # Verify legal source eligibility and rejection reasons.
            if "legal_source_assessments" in expected:
                assert (
                    analysis["legal_source_assessments"]
                    == expected["legal_source_assessments"]
                )

            # Verify temporal eligibility and missing metadata.
            if "legal_temporal_assessments" in expected:
                assert (
                    analysis["legal_temporal_assessments"]
                    == expected["legal_temporal_assessments"]
                )

            # Verify legal-version consistency diagnostics.
            if "legal_version_errors" in expected:
                assert (
                    analysis["legal_version_errors"]
                    == expected["legal_version_errors"]
                )

            # Verify consistency findings for legal temporal metadata.
            if "temporal_consistency_findings" in expected:
                assert (
                    analysis["temporal_consistency_findings"]
                    == expected["temporal_consistency_findings"]
                )
        assert response["status"] == expected["response_status"]
        assert response["refus"] == expected["refus"]
        assert len(response["citations"]) == expected["citations_count"]

        result = response["result"]
        assert result is not None
        assert result["analysis_status"] == expected["analysis_status"]
        assert result["legal_conclusion"] == expected["legal_conclusion"]
        assert len(result["claims_analysis"]) == expected["claims_count"]

        # No fictitious declaration is considered verified.
        assert all(
            claim["status"] == expected["claims_status"]
            for claim in result["claims_analysis"]
        )
