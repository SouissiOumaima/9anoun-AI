"""Validation préliminaire des sources juridiques DS2."""

from __future__ import annotations

from datetime import date
from typing import Any


def assess_legal_source(
    source: dict[str, Any],
) -> dict[str, Any]:
    """Qualifier une source juridique sans certifier son applicabilité."""

    reasons: list[str] = []

    # Vérifier la présence d'un contenu juridique.
    text = source.get("text")
    excerpt = source.get("excerpt")

    available_content = [
        value
        for value in (text, excerpt)
        if isinstance(value, str) and value.strip()
    ]

    if not available_content:
        reasons.append("MISSING_LEGAL_CONTENT")

    # Vérifier les identifiants de la source.
    for field in ("article_id", "reference", "source_id"):
        value = source.get(field)

        if not isinstance(value, str) or not value.strip():
            reasons.append("MISSING_SOURCE_IDENTIFIER")
            break

    # Vérifier la citation juridique.
    citation = source.get("citation")

    if not isinstance(citation, dict):
        reasons.append("MISSING_CITATION")

    else:
        # Vérifier les champs textuels de la citation.
        for field in (
            "citation_id",
            "document",
            "exact_excerpt",
        ):
            value = citation.get(field)

            if not isinstance(value, str) or not value.strip():
                reasons.append("INCOMPLETE_CITATION")
                break

        # Vérifier le numéro de page.
        page = citation.get("page")

        if (
            not isinstance(page, int)
            or isinstance(page, bool)
            or page < 1
        ):
            reasons.append("MISSING_CITATION_PAGE")

        # Vérifier la cohérence entre le texte juridique
        # et l'extrait exact fourni dans la citation.
        exact_excerpt = citation.get("exact_excerpt")

        if (
            isinstance(exact_excerpt, str)
            and exact_excerpt.strip()
            and available_content
            and not any(
                exact_excerpt in content
                for content in available_content
            )
        ):
            reasons.append("CITATION_TEXT_MISMATCH")

    # La présence de métadonnées cohérentes ne garantit
    # ni l'authenticité ni la validité temporelle de la source.
    return {
        "source_id": source.get("source_id"),
        "eligible_for_legal_support": not reasons,
        "reasons": reasons,
    }



def assess_legal_source_temporally(
    source: dict[str, Any],
    reference_date: str | None,
) -> dict[str, Any]:
    """?valuer les limites temporelles d'une source DS2.

    Cette fonction ne certifie pas l'applicabilit? juridique.
    Les statuts de validit? DS2 doivent ?tre normalis?s
    avec l'?quipe avant toute conclusion affirmative.
    """

    reasons: list[str] = []

    # R?utiliser la qualification textuelle existante.
    textual = assess_legal_source(source)

    if not textual["eligible_for_legal_support"]:
        reasons.extend(textual["reasons"])

    # Exiger une date de r?f?rence explicite.
    reference = None

    if reference_date is None:
        reasons.append("REFERENCE_DATE_MISSING")
    else:
        try:
            reference = date.fromisoformat(reference_date)

            # Refuser les formats ISO non canoniques.
            if reference.isoformat() != reference_date:
                raise ValueError("Date non canonique")

        except (TypeError, ValueError):
            reasons.append("INVALID_REFERENCE_DATE")

    # Lire les m?tadonn?es temporelles de DS2.
    citation = source.get("citation")

    metadata = (
        citation if isinstance(citation, dict) else {}
    )

    effective_raw = metadata.get("effective_date")
    validity_status = metadata.get("validity_status")

    # V?rifier la date d'effet ind?pendamment
    # de la validit? d?clar?e par DS2.
    effective = None

    if effective_raw is None:
        reasons.append("EFFECTIVE_DATE_UNKNOWN")
    else:
        try:
            effective = date.fromisoformat(effective_raw)

            if effective.isoformat() != effective_raw:
                raise ValueError("Date non canonique")

        except (TypeError, ValueError):
            reasons.append("INVALID_EFFECTIVE_DATE")

    # Une source future ne peut pas justifier
    # une situation ? une date ant?rieure.
    if (
        reference is not None
        and effective is not None
        and effective > reference
    ):
        reasons.append("NOT_YET_EFFECTIVE")

    # Le statut DS2 est conserv? tel quel.
    # Ne pas inventer la signification de ses valeurs.
    if (
        not isinstance(validity_status, str)
        or not validity_status.strip()
    ):
        reasons.append("TEMPORAL_VALIDITY_UNKNOWN")
    else:
        reasons.append("VALIDITY_STATUS_REQUIRES_REVIEW")

    # Ne pas confirmer l'applicabilit? avant validation
    # des conventions DS2 et des r?gles d'abrogation.
    return {
        "source_id": source.get("source_id"),
        "temporal_eligibility": "not_confirmed",
        "eligible_for_legal_conclusion": False,
        "validity_status_reported": validity_status,
        "reasons": list(dict.fromkeys(reasons)),
    }
