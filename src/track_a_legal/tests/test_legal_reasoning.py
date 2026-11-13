"""Tests du Legal Reasoning Engine - DS4."""

from src.track_a_legal.tools.legal_reasoning import (
    prepare_legal_reasoning,
)


def test_missing_legal_sources_requires_abstention() -> None:
    """Aucune conclusion juridique sans source disponible."""

    # Analyse interne minimale, sans conclusion.
    case_analysis = {
        "case_id": "CASE-TEST-001",
        "claims_analysis": [
            {
                "claim_id": "CL-001",
                "party_id": "P1",
                "text": "Salaire non verse",
                "status": "unverified",
            }
        ],
        "legal_conclusion": None,
    }

    # Aucune reponse juridique DS2 disponible.
    legal_response = None

    # Executer le moteur de raisonnement.
    result = prepare_legal_reasoning(
        case_analysis,
        legal_response,
    )

    # Appliquer le principe Citation ou Silence.
    assert result == {
        "status": "insufficient_sources",
        "legal_conclusion": None,
        "citation_ids": [],
        "reason": "legal_source_unavailable",
    }


def test_usable_legal_sources_require_verification() -> None:
    """Une source DS2 acceptable ne prouve pas une conclusion."""

    # Analyse initiale sans conclusion juridique.
    case_analysis = {
        "case_id": "CASE-TEST-002",
        "claims_analysis": [
            {
                "claim_id": "CL-002",
                "party_id": "P1",
                "text": "Salaire non verse",
                "status": "unverified",
            }
        ],
        "legal_conclusion": None,
    }

    # Reponse DS2 minimale satisfaisant les controles
    # preliminaires actuellement implementes.
    # Ces donnees sont fictives et ne prouvent aucune loi.
    citation = {
        "citation_id": "CIT-TEST-001",
    }

    legal_response = {
        "contract_version": "legal_retrieval.v0",
        "status": "ok",
        "mode": "live",
        "results": [
            {
                "citation": citation,
                "effective_from": "2024-01-01",
                "effective_to": None,
                "version_group": "GROUP-TEST-001",
                "applicable_at_reference_date": True,
            }
        ],
        "citations": [citation],
    }

    # Executer le moteur interne DS4.
    result = prepare_legal_reasoning(
        case_analysis,
        legal_response,
    )

    # Une validation preliminaire ne permet pas
    # de conclure juridiquement.
    assert result == {
        "status": "pending_verification",
        "legal_conclusion": None,
        "citation_ids": [],
        "reason": "additional_legal_verification_required",
    }


def test_missing_case_id_requires_abstention() -> None:
    """Un dossier sans identifiant ne peut pas etre analyse."""

    # Dossier incomplet : case_id absent.
    case_analysis = {
        "claims_analysis": [],
        "legal_conclusion": None,
    }

    # Reponse DS2 fictive passant les controles preliminaires.
    citation = {"citation_id": "CIT-TEST-002"}

    legal_response = {
        "contract_version": "legal_retrieval.v0",
        "status": "ok",
        "mode": "live",
        "results": [
            {
                "citation": citation,
                "effective_from": None,
                "effective_to": None,
                "version_group": "GROUP-TEST-002",
                "applicable_at_reference_date": True,
            }
        ],
        "citations": [citation],
    }

    # Executer le moteur avec un dossier incomplet.
    result = prepare_legal_reasoning(
        case_analysis,
        legal_response,
    )

    # Le moteur doit refuser de poursuivre les controles.
    assert result == {
        "status": "invalid_case",
        "legal_conclusion": None,
        "citation_ids": [],
        "reason": "missing_case_id",
    }
