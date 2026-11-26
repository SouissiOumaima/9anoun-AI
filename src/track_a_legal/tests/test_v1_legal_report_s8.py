"""Regression tests for the DS4 S8 legal report generator."""

import json
from copy import deepcopy
from pathlib import Path

import pytest

from src.track_a_legal.v1_case_analysis import analyze_case_v1
from src.track_a_legal.v1_legal_deliverables_s7 import (
    generate_legal_deliverables_s7,
)
from src.track_a_legal.v1_legal_report_s8 import (
    generate_legal_report_s8,
)


# Load the seven fictitious reference cases.
ROOT = Path("data/mock_cards")

CASES = json.loads(
    (ROOT / "track_a_case_cards_v1.json")
    .read_text(encoding="utf-8-sig")
)

EXPECTED_SECTION_IDS = [
    f"S8-{number:02d}" for number in range(1, 11)
]


def build_inputs(case_card):
    """Build the three inputs required by the S8 generator."""

    # Run the existing DS4 analysis and S7 preparation.
    analysis = analyze_case_v1(case_card)
    s7 = generate_legal_deliverables_s7(analysis)

    return analysis, s7


@pytest.mark.parametrize(
    "case_card",
    CASES,
    ids=[case["case_id"] for case in CASES],
)
def test_s8_structure_traceability_and_safety(case_card):
    """Validate all ten sections and legal safety for each case."""

    analysis, s7 = build_inputs(case_card)

    # Preserve original inputs to detect unintended mutations.
    original_case = deepcopy(case_card)
    original_analysis = deepcopy(analysis)
    original_s7 = deepcopy(s7)

    report = generate_legal_report_s8(
        case_card,
        analysis,
        s7,
    )

    # Validate the report identity and version.
    assert report["report_version"] == "track_a_legal_report_s8.v1"
    assert report["case_id"] == case_card["case_id"]

    # Validate the complete section structure and ordering.
    sections = report["sections"]
    assert len(sections) == 10
    assert [
        section["section_id"] for section in sections
    ] == EXPECTED_SECTION_IDS

    # Every section must have the expected structure.
    for section in sections:
        assert set(section) == {
            "section_id",
            "title",
            "content",
        }

    # Legal safety: no automated legal conclusion.
    assert report["document_status"] == "preparatory"
    assert report["lawyer_validated"] is False
    assert report["legal_conclusion"] is None

    # The report must not modify any original input.
    assert case_card == original_case
    assert analysis == original_analysis
    assert s7 == original_s7


@pytest.mark.parametrize(
    "invalid_request,invalid_analysis,invalid_s7",
    [
        ([], {}, {}),
        ({}, [], {}),
        ({}, {}, []),
    ],
    ids=[
        "invalid-request-type",
        "invalid-analysis-type",
        "invalid-s7-type",
    ],
)
def test_s8_rejects_invalid_input_types(
    invalid_request,
    invalid_analysis,
    invalid_s7,
):
    """Reject inputs that are not dictionaries."""

    with pytest.raises(ValueError):
        generate_legal_report_s8(
            invalid_request,
            invalid_analysis,
            invalid_s7,
        )


def test_s8_rejects_missing_case_id():
    """Reject a request without a valid case identifier."""

    case_card = deepcopy(CASES[0])
    case_card.pop("case_id")

    analysis, s7 = build_inputs(CASES[0])

    with pytest.raises(ValueError):
        generate_legal_report_s8(case_card, analysis, s7)


def test_s8_rejects_analysis_case_id_mismatch():
    """Reject an analysis belonging to another case."""

    case_card = CASES[0]
    analysis, s7 = build_inputs(case_card)

    analysis["case_id"] = "CASE-UNKNOWN"

    with pytest.raises(ValueError):
        generate_legal_report_s8(case_card, analysis, s7)


def test_s8_rejects_s7_case_id_mismatch():
    """Reject an S7 deliverable belonging to another case."""

    case_card = CASES[0]
    analysis, s7 = build_inputs(case_card)

    s7["case_id"] = "CASE-UNKNOWN"

    with pytest.raises(ValueError):
        generate_legal_report_s8(case_card, analysis, s7)


def test_s8_rejects_unexpected_lawyer_validation():
    """Never accept an unexpected lawyer validation state."""

    case_card = CASES[0]
    analysis, s7 = build_inputs(case_card)

    s7["lawyer_validated"] = True

    with pytest.raises(ValueError):
        generate_legal_report_s8(case_card, analysis, s7)


def test_s8_rejects_missing_s7_section():
    """Reject an S7 deliverable with a missing section."""

    case_card = CASES[0]
    analysis, s7 = build_inputs(case_card)

    s7["sections"] = [
        section
        for section in s7["sections"]
        if section["section_id"] != "S7-03"
    ]

    with pytest.raises(ValueError):
        generate_legal_report_s8(case_card, analysis, s7)


def test_s8_rejects_duplicate_s7_section():
    """Reject duplicate S7 section identifiers."""

    case_card = CASES[0]
    analysis, s7 = build_inputs(case_card)

    s7["sections"].append(deepcopy(s7["sections"][0]))

    with pytest.raises(ValueError):
        generate_legal_report_s8(case_card, analysis, s7)


def test_s8_rejects_invalid_s7_section_content():
    """Reject malformed S7 section content."""

    case_card = CASES[0]
    analysis, s7 = build_inputs(case_card)

    s7["sections"][0]["content"] = None

    with pytest.raises(ValueError):
        generate_legal_report_s8(case_card, analysis, s7)


def test_s8_rejects_nested_unauthorized_legal_conclusion():
    """S8 must reject a non-null legal conclusion injected into S7."""

    # Reutiliser le premier dossier v1 valide.
    request = deepcopy(CASES[0])
    analysis = analyze_case_v1(request)
    s7 = generate_legal_deliverables_s7(analysis)

    # Simuler une conclusion juridique non validee.
    s7["sections"][3]["content"].append({
        "legal_conclusion": "CONCLUSION_NON_VALIDEE_TEST"
    })

    # Le rapport doit etre refuse, jamais genere.
    with pytest.raises(
        ValueError,
        match="Unauthorized legal conclusion",
    ):
        generate_legal_report_s8(request, analysis, s7)


def test_s8_preserves_explicit_event_evidence_link():
    """Preserve a valid explicit event-evidence link in S8-07."""

    # Selectionner un dossier fictif avec evenement et preuve.
    request = next(
        (
            deepcopy(case)
            for case in CASES
            if case.get("events") and case.get("evidence")
        ),
        None,
    )
    assert request is not None

    # Associer explicitement le premier evenement a une preuve existante.
    event = request["events"][0]
    evidence_id = request["evidence"][0]["evidence_id"]
    event["evidence_ids"] = [evidence_id]

    # Generer le rapport a partir des donnees modifiees en memoire.
    analysis = analyze_case_v1(request)
    s7 = generate_legal_deliverables_s7(analysis)
    report = generate_legal_report_s8(request, analysis, s7)

    # Verifier la conservation exacte du lien dans S8-07.
    section = next(
        item for item in report["sections"]
        if item["section_id"] == "S8-07"
    )

    expected = {
        "event_id": event["event_id"],
        "evidence_id": evidence_id,
        "relation": "explicit_request_link",
    }

    assert expected in section["content"]["explicit_event_evidence_links"]
