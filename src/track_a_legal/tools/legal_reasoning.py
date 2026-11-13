"""Legal Reasoning Engine - Lawyer Track DS4.

Version initiale : preparation securisee du raisonnement.
Aucune conclusion juridique n'est produite automatiquement.
"""

from typing import Any

from src.track_a_legal.tools.legal_source_validation import (
    is_usable_legal_response,
)


def prepare_legal_reasoning(
    case_analysis: dict,
    legal_response: Any,
) -> dict:
    """
    Preparer le raisonnement juridique sans inventer de conclusion.

    Args:
        case_analysis: analyse structuree du dossier DS4.
        legal_response: reponse de recherche juridique DS2.

    Returns:
        Decision interne d'abstention ou de poursuite des controles.

    Important :
        Une validation structurelle DS2 ne prouve pas
        l'authenticite ni l'applicabilite des sources.
    """

    # Rejeter les sources absentes ou structurellement invalides.
    if not is_usable_legal_response(legal_response):
        return {
            "status": "insufficient_sources",
            "legal_conclusion": None,
            "citation_ids": [],
            "reason": "legal_source_unavailable",
        }

    # Les sources ont passe les controles preliminaires.
    # Les controles de pertinence et d'applicabilite restent
    # necessaires avant tout raisonnement juridique.
    return {
        "status": "pending_verification",
        "legal_conclusion": None,
        "citation_ids": [],
        "reason": "additional_legal_verification_required",
    }
