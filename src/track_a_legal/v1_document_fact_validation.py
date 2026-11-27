"""Qualification prudente des faits documentaires DS3."""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any


def assess_document_fact(
    fact: dict[str, Any],
) -> dict[str, Any]:
    """Qualifier un fait DS3 sans inventer de certitude.

    Précondition : le fait respecte le JSON Schema request v1.
    Cette fonction ne vérifie pas l'authenticité du document.
    """

    reasons: list[str] = []

    # Exiger une confirmation explicite de l'utilisateur.
    if fact.get("user_confirmed") is not True:
        reasons.append("USER_NOT_CONFIRMED")

    # Évaluer la confiance sans arrondir sa valeur.
    confidence = fact.get("confidence")

    try:
        score = (
            Decimal(str(confidence))
            if confidence is not None
            and not isinstance(confidence, bool)
            else None
        )
    except (InvalidOperation, ValueError):
        score = None

    if (
        score is None
        or not score.is_finite()
        or score < Decimal("0.90")
        or score > Decimal("1")
    ):
        reasons.append("LOW_OR_MISSING_CONFIDENCE")

    # Vérifier la présence des métadonnées de citation.
    citation = fact.get("citation")

    if not isinstance(citation, dict):
        reasons.append("MISSING_CITATION")
    else:
        required_text = (
            "citation_id",
            "document_id",
            "exact_excerpt",
        )

        for field in required_text:
            value = citation.get(field)

            if not isinstance(value, str) or not value.strip():
                reasons.append("INCOMPLETE_CITATION")
                break

        # Une page connue est nécessaire à la traçabilité.
        page = citation.get("page")

        if (
            not isinstance(page, int)
            or isinstance(page, bool)
            or page < 1
        ):
            reasons.append("MISSING_CITATION_PAGE")

        # Ne jamais associer silencieusement deux documents.
        if citation.get("document_id") != fact.get("document_id"):
            reasons.append("DOCUMENT_ID_MISMATCH")

    # Le résultat est une qualification préliminaire,
    # pas une certification de la source documentaire.
    return {
        "fact_id": fact.get("fact_id"),
        "eligible_for_established_fact": not reasons,
        "reasons": reasons,
    }
