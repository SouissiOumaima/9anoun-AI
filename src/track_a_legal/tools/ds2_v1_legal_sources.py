"""Mapping des articles DS2 vers les sources juridiques DS4 v1.

Ce module ne certifie ni les citations ni l'applicabilit? juridique.
"""

from copy import deepcopy
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker

from src.track_a_legal.v1_case_analysis import SCHEMA
from src.track_a_legal.v1_ds2_adapter import validate_ds2_response


def map_ds2_to_v1_legal_sources(response: Any) -> list[dict[str, Any]]:
    """Convertir une r?ponse DS2 LIVE en sources DS4 v1 valid?es."""

    # Refuser toute r?ponse DS2 non conforme au contrat officiel.
    if not validate_ds2_response(response):
        raise ValueError("Invalid DS2 response.")

    # V?rifier le contrat de sortie DS4 v1.
    source_schema = SCHEMA["properties"]["legal_sources"]
    validator = Draft202012Validator(
        source_schema,
        format_checker=FormatChecker(),
    )

    mapped = []
    seen_ids = set()

    for article in response["results"]:
        article_id = article["article_id"]

        # Les cinq piliers exigent une cl? unique par article.
        if not article_id.strip() or article_id in seen_ids:
            raise ValueError("Invalid or duplicate DS2 article_id.")

        seen_ids.add(article_id)


        ds2_citation = article.get("citation")
        citation = None

        if isinstance(ds2_citation, dict):
            document = ds2_citation.get("source_file")
            article_text = article.get("text")
            page = ds2_citation.get("page")

            if (
                isinstance(document, str)
                and document.strip()
                and isinstance(article_text, str)
                and article_text.strip()
                and (
                    page is None
                    or (
                        isinstance(page, int)
                        and not isinstance(page, bool)
                        and page >= 1
                    )
                )
            ):
                citation = {
                    "citation_id": f"DS2-{article_id}",
                    "document": document,
                    "page": page,
                    "exact_excerpt": article_text,
                }

        # Construire une r?f?rence descriptive, non certifi?e.
        number = article["article_number"]
        reference = (
            f"{article['source_id']} - Article {number}"
            if number is not None
            else f"{article['source_id']} - {article_id}"
        )

        # Ne pas fabriquer de page, de citation ou de date.
        source = {
            "article_id": article_id,
            "source_id": article_id,
            "reference": reference,
            "text": deepcopy(article["text"]),
            "citation": citation,
            "effective_date": article["effective_from"],
            "effective_from": article["effective_from"],
            "effective_to": article["effective_to"],
            "validity_status": article["status"],
            "version_group": article["version_group"],
            "version": article["version"],
            "applicable_at_reference_date": article[
                "applicable_at_reference_date"
            ],
        }

        mapped.append(source)

    # Refuser les sources qui ne respectent pas le contrat DS4.
    errors = list(validator.iter_errors(mapped))

    if errors:
        raise ValueError(
            "Invalid DS4 v1 legal sources: "
            + errors[0].message
        )

    return mapped
