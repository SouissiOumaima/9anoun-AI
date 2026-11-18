"""Tests unitaires du moteur Case Analysis v1."""

import copy

import pytest

from src.track_a_legal.v1_case_analysis import analyze_case_v1


def make_valid_request() -> dict:
    """Créer un dossier fictif minimal conforme au contrat v1."""
    return {
        "contract_version": "track_a.v1",
        "request_id": "REQ-TEST-001",
        "case_id": "CASE-TEST-001",
        "lang": "fr",
        "parties": [],
        "events": [],
        "claims": [],
        "evidence": [],
    }


def test_valid_request_is_preparatory() -> None:
    """Un dossier minimal valide doit rester préparatoire."""
    result = analyze_case_v1(make_valid_request())

    assert result["case_id"] == "CASE-TEST-001"
    assert result["timeline"] == []
    assert result["reference_errors"] == []
    assert result["analysis_status"] == "preparatory"
    assert result["legal_conclusion"] is None


def test_invalid_contract_version_is_rejected() -> None:
    """Une version de contrat incorrecte doit être refusée."""
    request = copy.deepcopy(make_valid_request())
    request["contract_version"] = "track_a.v0"

    with pytest.raises(ValueError, match="Invalid Request v1"):
        analyze_case_v1(request)


def make_document_fact() -> dict:
    """Construire un fait DS3 fictif avec une citation traçable."""
    return {
        "fact_id": "FACT-001",
        "subject_id": "PARTY-001",
        "evidence_id": "EVID-001",
        "document_id": "DOC-001",
        "field_name": "salary",
        "value": "1500",
        "confidence": 0.95,
        "user_confirmed": True,
        "citation": {
            "citation_id": "CIT-001",
            "document_id": "DOC-001",
            "exact_excerpt": "Salaire mensuel : 1500",
            "page": 1,
        },
        "warnings": [],
    }


def test_confirmed_document_fact() -> None:
    """Un fait confirmé et correctement cité est éligible."""
    request = make_valid_request()

    # Déclarer les références internes utilisées par le fait.
    request["parties"] = [
        {
            "party_id": "PARTY-001",
            "name": "Personne fictive",
            "role": "employee",
        }
    ]
    request["evidence"] = [
        {
            "evidence_id": "EVID-001",
            "type": "document",
            "description": "Document fictif",
            "source": "DOC-001",
        }
    ]
    request["document_facts"] = [make_document_fact()]

    result = analyze_case_v1(request)

    assessment = result["document_fact_assessments"][0]
    assert assessment["fact_id"] == "FACT-001"
    assert assessment["eligible_for_established_fact"] is True
    assert assessment["reasons"] == []
    assert result["analysis_status"] == "preparatory"
    assert result["legal_conclusion"] is None


def test_unconfirmed_document_fact() -> None:
    """Un fait non confirmé doit rester insuffisamment justifié."""
    request = make_valid_request()

    request["parties"] = [
        {
            "party_id": "PARTY-001",
            "name": "Personne fictive",
            "role": "employee",
        }
    ]
    request["evidence"] = [
        {
            "evidence_id": "EVID-001",
            "type": "document",
            "description": "Document fictif",
            "source": "DOC-001",
        }
    ]

    fact = make_document_fact()
    fact["user_confirmed"] = False
    request["document_facts"] = [fact]

    result = analyze_case_v1(request)

    assessment = result["document_fact_assessments"][0]
    assert assessment["eligible_for_established_fact"] is False
    assert "USER_NOT_CONFIRMED" in assessment["reasons"]
    assert result["analysis_status"] == "insufficient_evidence"
    assert result["legal_conclusion"] is None


def test_legal_source_without_citation() -> None:
    """A legal source without citation cannot support analysis."""
    request = make_valid_request()

    # Explicit reference date for temporal checks.
    request["reference_date"] = "2026-11-17"

    # Fictitious legal source with deliberately missing citation.
    request["legal_sources"] = [
        {
            "article_id": "ART-001",
            "reference": "Reference fictive",
            "source_id": "SRC-001",
            "text": "Texte juridique fictif pour test.",
        }
    ]

    result = analyze_case_v1(request)

    # Verify textual source qualification.
    assessment = result["legal_source_assessments"][0]

    assert assessment["source_id"] == "SRC-001"
    assert assessment["eligible_for_legal_support"] is False
    assert "MISSING_CITATION" in assessment["reasons"]

    # No legal conclusion may be generated.
    assert result["analysis_status"] == "insufficient_evidence"
    assert result["legal_conclusion"] is None


def test_future_legal_version_is_flagged() -> None:
    """A future legal version must not support an earlier case."""
    request = make_valid_request()

    # The case predates the legal source's effective period.
    request["reference_date"] = "2026-01-15"

    # Fictitious source with a traceable textual citation.
    request["legal_sources"] = [
        {
            "article_id": "ART-002",
            "reference": "Reference juridique fictive",
            "source_id": "SRC-002",
            "text": "Disposition fictive pour test temporel.",
            "citation": {
                "citation_id": "CIT-002",
                "document": "Document juridique fictif",
                "exact_excerpt": "Disposition fictive",
                "page": 1,
            },
            "effective_from": "2026-06-01",
            "effective_to": None,
            "version_group": "GROUP-002",
            "version": 2,
            "applicable_at_reference_date": False,
        }
    ]

    result = analyze_case_v1(request)

    # The text may be correctly cited, but the version is future.
    assert (
        result["legal_source_assessments"][0][
            "eligible_for_legal_support"
        ]
        is True
    )

    # Check both temporal validators independently.
    temporal = result["legal_temporal_assessments"][0]
    assert temporal["eligible_for_legal_conclusion"] is False

    version_codes = {
        error["code"]
        for error in result["legal_version_errors"]
    }
    assert "NOT_YET_EFFECTIVE" in version_codes

    # The engine must not produce a legal conclusion.
    assert result["analysis_status"] == "insufficient_evidence"
    assert result["legal_conclusion"] is None


def test_multiple_applicable_legal_versions() -> None:
    """Flag two versions declared applicable to the same case date."""
    request = make_valid_request()

    # Use an explicit reference date.
    request["reference_date"] = "2026-11-17"

    # Both fictitious versions claim applicability to the same date.
    request["legal_sources"] = [
        {
            "article_id": "ART-003",
            "reference": "Reference fictive - version 1",
            "source_id": "SRC-003-V1",
            "text": "Disposition fictive version un.",
            "citation": {
                "citation_id": "CIT-003-V1",
                "document": "Document juridique fictif",
                "page": 1,
                "exact_excerpt": "Disposition fictive version un.",
            },
            "effective_from": "2025-01-01",
            "effective_to": None,
            "version_group": "GROUP-003",
            "version": 1,
            "applicable_at_reference_date": True,
        },
        {
            "article_id": "ART-003",
            "reference": "Reference fictive - version 2",
            "source_id": "SRC-003-V2",
            "text": "Disposition fictive version deux.",
            "citation": {
                "citation_id": "CIT-003-V2",
                "document": "Document juridique fictif",
                "page": 2,
                "exact_excerpt": "Disposition fictive version deux.",
            },
            "effective_from": "2026-01-01",
            "effective_to": None,
            "version_group": "GROUP-003",
            "version": 2,
            "applicable_at_reference_date": True,
        },
    ]

    # Execute the integrated Case Analysis v1 engine.
    result = analyze_case_v1(request)

    # Both sources have traceable textual citations.
    assert all(
        item["eligible_for_legal_support"]
        for item in result["legal_source_assessments"]
    )

    # Detect contradictory applicability declarations.
    codes = {
        error["code"]
        for error in result["legal_version_errors"]
    }
    assert "MULTIPLE_APPLICABLE_VERSIONS" in codes

    # Do not infer a legal conclusion from conflicting versions.
    assert result["analysis_status"] == "insufficient_evidence"
    assert result["legal_conclusion"] is None



def test_explicit_contradiction_takes_priority():
    """Preserve reference errors while flagging explicit contradictions."""
    from src.track_a_legal.v1_case_analysis import analyze_case_v1

    # Construct a valid fictitious request with an unknown party.
    request = {
        "contract_version": "track_a.v1",
        "request_id": "REQ-PRIORITY-001",
        "case_id": "CASE-PRIORITY-001",
        "lang": "fr",
        "parties": [],
        "events": [],
        "claims": [
            {
                "claim_id": "CLM-001",
                "party_id": "PARTY-UNKNOWN",
                "text": "Demande fictive pour tester les references.",
            }
        ],
        "evidence": [],
        "contradictions": [
            {
                "contradiction_id": "CONTRA-001",
                "description": "Deux sources sont contradictoires.",
                "source_ids": ["SRC-001", "SRC-002"],
            }
        ],
    }

    # Both conditions must be preserved in the internal analysis.
    result = analyze_case_v1(request)

    assert result["reference_errors"]
    assert result["analysis_status"] == "contradictory_evidence"

    # No legal conclusion is permitted from this unresolved case.
    assert result["legal_conclusion"] is None


def test_case_analysis_integrates_five_pillars() -> None:
    """Integrate S5 internally without producing legal conclusions."""

    request = make_valid_request()

    # Run the official Request v1 validation and internal analysis.
    result = analyze_case_v1(request)

    # The internal analysis must contain the S5 engine output.
    assert "five_pillars" in result

    pillars = result["five_pillars"]["pillars"]

    # Verify all five expected pillars.
    assert set(pillars) == {
        "faits",
        "declarations",
        "regles",
        "interpretation",
        "strategie",
    }

    # No sources: interpretation and strategy must abstain.
    assert pillars["interpretation"][0]["status"] == "blocked"
    assert pillars["strategie"][0]["status"] == "blocked"

    # No legal conclusion may be inferred.
    assert result["legal_conclusion"] is None
    assert result["five_pillars"]["legal_conclusion"] is None

def test_duplicate_claim_id_is_reported_in_v1_analysis() -> None:
    """Duplicate claim IDs must be reported without legal conclusions."""

    # Start from a valid fictitious Request v1.
    request = make_valid_request()

    # Declare the party referenced by both claims.
    request["parties"] = [
        {
            "party_id": "PARTY-001",
            "name": "Personne fictive",
            "role": "employee",
        }
    ]

    # Intentionally duplicate the claim identifier.
    request["claims"] = [
        {
            "claim_id": "CLAIM-001",
            "party_id": "PARTY-001",
            "text": "Première déclaration fictive.",
        },
        {
            "claim_id": "CLAIM-001",
            "party_id": "PARTY-001",
            "text": "Deuxième déclaration fictive.",
        },
    ]

    # Run the complete internal analysis.
    result = analyze_case_v1(request)

    # Verify the explicit duplicate-ID error.
    assert any(
        error["code"] == "DUPLICATE_ID"
        and error["path"] == "claims/1/claim_id"
        and error["reference_id"] == "CLAIM-001"
        for error in result["reference_errors"]
    )

    # An ambiguous case cannot remain preparatory.
    assert result["analysis_status"] == "insufficient_evidence"

    # Never generate a legal conclusion.
    assert result["legal_conclusion"] is None
    assert result["five_pillars"]["legal_conclusion"] is None

    # S5 must keep every declaration unverified.
    declarations = result["five_pillars"]["pillars"]["declarations"]
    assert len(declarations) == 2
    assert all(
        declaration["status"] == "unverified"
        for declaration in declarations
    )
