"""Adaptation des réponses DS2 vers les structures internes DS4.

Ce module conserve la traçabilité des sources juridiques.
Il ne certifie pas leur applicabilité et ne produit aucune conclusion.
"""

from datetime import date
from copy import deepcopy
from typing import Any

from src.track_a_legal.v1_ds2_adapter import validate_ds2_response
from src.track_a_legal.tools.legal_source_validation import (
    is_usable_legal_response,
)


def adapt_ds2_to_ds4(
    response: Any,
    reference_date: str | None = None,
) -> dict[str, Any]:
    """Convertir une réponse DS2 validée en références internes DS4."""

    # Refuser toute réponse non conforme au contrat officiel DS2.
    if not (
        validate_ds2_response(response)
        and is_usable_legal_response(response)
    ):
        raise ValueError("Invalid DS2 legal retrieval response.")

    # Contr?ler la date de r?f?rence lorsqu'elle est fournie.
    if reference_date is not None:

        # Exiger une date ISO stricte AAAA-MM-JJ.
        if not isinstance(reference_date, str):
            raise ValueError("Invalid reference_date.")

        try:
            parsed_reference = date.fromisoformat(reference_date)
        except ValueError as exc:
            raise ValueError("Invalid reference_date.") from exc

        if parsed_reference.isoformat() != reference_date:
            raise ValueError("Invalid reference_date format.")

        # Comparer les bornes temporelles des articles DS2.
        for article in response["results"]:

            # Ne pas transformer une d?claration DS2 en preuve juridique.
            if article["applicable_at_reference_date"] is not True:
                continue

            start = article["effective_from"]
            end = article["effective_to"]

            # Refuser une entr?e en vigueur post?rieure au dossier.
            if start is not None:
                if parsed_reference < date.fromisoformat(start):
                    raise ValueError(
                        "Article not yet effective at reference_date."
                    )

            # Refuser une expiration ant?rieure au dossier.
            if end is not None:
                if parsed_reference > date.fromisoformat(end):
                    raise ValueError(
                        "Article expired at reference_date."
                    )


    # Préserver l'ordre des articles et détecter les identifiants ambigus.
    article_ids = [
        article["article_id"]
        for article in response["results"]
    ]

    if len(article_ids) != len(set(article_ids)):
        raise ValueError("Duplicate DS2 article_id.")

    # Copier les citations pour éviter toute mutation des données DS2.
    citations = deepcopy(response["citations"])

    # Le référencement ne prouve pas l'applicabilité juridique.
    # Conserver les m?tadonn?es DS2 sans certifier leur applicabilit?.
    temporal_fields = (
        "article_id",
        "effective_from",
        "effective_to",
        "status",
        "version_group",
        "version",
        "applicable_at_reference_date",
        "modified",
        "amended_by",
        "previous_version_available",
    )

    # Cr?er des copies ind?pendantes pour pr?server les donn?es DS2.
    temporal_sources = [
        {field: deepcopy(article[field]) for field in temporal_fields}
        for article in response["results"]
    ]

    return {
        "legal_sources_used": article_ids,
        "citations": citations,
        "legal_temporal_sources": temporal_sources,
        "legal_conclusion": None,
    }


def build_ds2_pillar_assessments(
    adapted: dict[str, Any],
) -> dict[str, list[dict[str, Any]]]:
    """Pr?parer les ?valuations DS2 destin?es aux cinq piliers."""

    # Refuser les structures incompl?tes.
    if not isinstance(adapted, dict):
        raise ValueError("Invalid adapted DS2 data.")

    sources = adapted.get("legal_temporal_sources")
    source_ids = adapted.get("legal_sources_used")

    if not isinstance(sources, list) or not isinstance(source_ids, list):
        raise ValueError("Missing DS2 source metadata.")

    if len(sources) != len(source_ids):
        raise ValueError("Inconsistent DS2 source metadata.")

    legal_sources = []
    temporal_assessments = []
    seen_ids = set()

    for expected_id, article in zip(source_ids, sources):
        # V?rifier l'identifiant unique de chaque article.
        if not isinstance(article, dict):
            raise ValueError("Invalid DS2 article metadata.")

        article_id = article.get("article_id")

        if (
            not isinstance(article_id, str)
            or not article_id.strip()
            or article_id != expected_id
            or article_id in seen_ids
        ):
            raise ValueError("Invalid or duplicate DS2 article_id.")

        # Reject incomplete metadata before constructing assessments.
        if "status" not in article or not isinstance(article["status"], str):
            raise ValueError("Missing or invalid DS2 article status.")

        seen_ids.add(article_id)

        # Pr?parer la r?gle sans certifier son applicabilit?.
        legal_sources.append({
            "source_id": article_id,
            "status": "pending_applicability_verification",
            "eligible_for_legal_conclusion": False,
        })

        # Pr?server les m?tadonn?es sans en d?duire une validit?.
        temporal_assessments.append({
            "source_id": article_id,
            "temporal_eligibility": "not_confirmed",
            "validity_status_reported": article["status"],
            "reasons": ["INDEPENDENT_TEMPORAL_VERIFICATION_REQUIRED"],
            "ds2_metadata": deepcopy(article),
        })

    return {
        "legal_source_assessments": legal_sources,
        "legal_temporal_assessments": temporal_assessments,
    }
