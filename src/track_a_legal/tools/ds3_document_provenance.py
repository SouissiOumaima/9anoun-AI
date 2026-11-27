"""Preserve DS3 documentary provenance outside the shared v1 schema."""

from copy import deepcopy
from typing import Any

from src.track_a_legal.tools.document_facts_adapter import (
    extract_document_facts,
)


def build_document_provenance(
    ds3_response: dict[str, Any],
    subject_id: str,
) -> dict[str, Any]:
    """Preserve original metadata without inferring missing information."""

    # Reuse existing validation and monetary extraction.
    facts = extract_document_facts(ds3_response, subject_id)

    if not facts:
        return {}

    # Index original fields and documentary citations.
    fields = ds3_response["result"]["fields"]

    citations = {
        item["citation_id"]: item
        for item in ds3_response["citations"]
    }

    def preserve_field(field_name):
        """Copy the original field and its associated citation."""

        field = fields[field_name]

        return {
            "field": deepcopy(field),
            "citation": deepcopy(
                citations.get(field.get("citation_id"))
            ),
        }

    provenance = {}

    # Preserve provenance separately for each extracted fact.
    for fact in facts:
        provenance[fact["fact_id"]] = {
            "fact_id": fact["fact_id"],
            "subject_id": fact["subject_id"],
            "document_id": fact["document_id"],
            "currency": fact["unit"],
            "period": fact["period"],
            "monetary_source": preserve_field(fact["property"]),
            "period_start_source": preserve_field("period_start"),
            "period_end_source": preserve_field("period_end"),
            "contract_version": ds3_response["contract_version"],
            "computed_by": ds3_response["computed_by"],
            "mode": ds3_response["mode"],
            "official_authenticity_confirmed": False,
            "user_confirmed": False,
        }

    return provenance
