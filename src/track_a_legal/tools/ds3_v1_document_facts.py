"""Conversion prudente des faits DS3 vers le contrat DS4 v1."""

from typing import Any

from src.track_a_legal.tools.document_facts_adapter import (
    extract_document_facts,
)
from src.track_a_legal.tools.document_evidence_orchestration import (
    collect_document_evidence_links,
)


def convert_ds3_facts_to_v1(
    ds3_response: dict[str, Any],
    subject_id: str,
    evidence: list[dict],
    document_links: dict,
) -> list[dict]:
    """Convertir uniquement les faits reli?s ? une preuve explicite."""

    # V?rifier les associations ? l'aide du composant DS4 existant.
    associations = collect_document_evidence_links(
        evidence,
        [ds3_response],
        document_links,
    )

    if len(associations) != 1:
        return []

    association = associations[0]

    # Extraire les faits mon?taires sans inf?rence.
    facts = extract_document_facts(
        ds3_response,
        subject_id,
    )

    # Indexer les citations officielles du document.
    citations = {
        item["citation_id"]: item
        for item in ds3_response["citations"]
    }

    # Acc?der aux champs d'origine pour conserver leur confiance.
    fields = ds3_response["result"]["fields"]

    converted = []

    for fact in facts:
        field_name = fact["property"]
        original_field = fields[field_name]
        original_citation = citations[fact["citation_id"]]

        # Ne jamais fabriquer de page ou d'extrait.
        excerpt = original_citation.get("excerpt")
        page = original_citation.get("page")

        citation = None
        warnings = ["USER_CONFIRMATION_REQUIRED"]

        if (
            isinstance(page, int)
            and not isinstance(page, bool)
            and page >= 1
            and isinstance(excerpt, str)
            and excerpt.strip()
            and original_citation.get("document_id")
                == fact["document_id"]
        ):
            citation = {
                "citation_id": fact["citation_id"],
                "document_id": fact["document_id"],
                "page": page,
                "exact_excerpt": excerpt,
            }
        else:
            warnings.append("INCOMPLETE_DOCUMENT_CITATION")

        # Pr?server la valeur et la confiance originales.
        converted.append({
            "fact_id": fact["fact_id"],
            "subject_id": fact["subject_id"],
            "evidence_id": association["evidence_id"],
            "document_id": fact["document_id"],
            "field_name": field_name,
            "value": fact["value"],
            "confidence": original_field["confidence"],
            "user_confirmed": False,
            "citation": citation,
            "warnings": warnings,
        })

    return converted
