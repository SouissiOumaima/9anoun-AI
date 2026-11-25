"""Orchestration DS2 + DS3 vers DS4 v1."""

from src.track_a_legal.tools.ds3_document_provenance import (
    build_document_provenance,
)

from copy import deepcopy
from typing import Any

from src.track_a_legal.tools.ds2_v1_pipeline import (
    run_ds2_ds4_v1_pipeline,
)
from src.track_a_legal.tools.ds3_v1_document_facts import (
    convert_ds3_facts_to_v1,
)


def run_ds2_ds3_ds4_v1_pipeline(
    ds4_request: dict[str, Any],
    ds2_request: dict[str, Any],
    ds3_response: dict[str, Any],
    subject_id: str,
    document_links: dict,
    *,
    include_provenance: bool = False,
) -> dict[str, Any]:
    """Combiner les preuves DS3 et les sources DS2 dans DS4."""

    # Refuser les param?tres de types incorrects.
    if not isinstance(ds4_request, dict):
        raise ValueError("Invalid DS4 request.")

    if not isinstance(ds2_request, dict):
        raise ValueError("Invalid DS2 request.")

    if not isinstance(ds3_response, dict):
        raise ValueError("Invalid DS3 response.")

    if not isinstance(subject_id, str) or not subject_id.strip():
        raise ValueError("Invalid subject ID.")

    if not isinstance(document_links, dict):
        raise ValueError("Invalid document links.")

    # Pr?server int?gralement les donn?es d'origine.
    prepared_request = deepcopy(ds4_request)

    # Interdire le remplacement silencieux de faits existants.
    if prepared_request.get("document_facts"):
        raise ValueError(
            "DS4 request already contains document facts."
        )

    # Convertir uniquement les faits DS3 associ?s ? une preuve.
    document_facts = convert_ds3_facts_to_v1(
        ds3_response=deepcopy(ds3_response),
        subject_id=subject_id,
        evidence=prepared_request.get("evidence", []),
        document_links=deepcopy(document_links),
    )

    # Ne pas masquer un ?chec de conversion.
    if not document_facts:
        raise ValueError(
            "No usable DS3 document facts."
        )

    # Transmettre les faits sans confirmation automatique.
    prepared_request["document_facts"] = document_facts

    # R?utiliser le pipeline DS2 officiel et l'analyse DS4 v1.
    # Aucune conclusion juridique n'est g?n?r?e ici.
    provenance = {}

    # Preserve metadata only for successfully converted facts.
    if include_provenance:
        provenance = build_document_provenance(
            ds3_response,
            subject_id,
        )

        expected_ids = {
            fact["fact_id"] for fact in document_facts
        }

        # Reject missing provenance or unexpected TND facts.
        if not expected_ids.issubset(provenance):
            raise ValueError("Inconsistent document provenance.")

        unexpected_ids = set(provenance) - expected_ids

        if any(
            provenance[fact_id].get("currency") in (None, "TND")
            for fact_id in unexpected_ids
        ):
            raise ValueError("Inconsistent document provenance.")

        # Preserve only facts accepted by the v1 converter.
        provenance = {
            fact_id: item
            for fact_id, item in provenance.items()
            if fact_id in expected_ids
        }

        # Enforce the v1 currency restriction.
        if any(
            item.get("currency") != "TND"
            for item in provenance.values()
        ):
            raise ValueError("Inconsistent document provenance.")

        # Preserve the explicit evidence association.
        for fact in document_facts:
            provenance[fact["fact_id"]]["evidence_id"] = (
                fact["evidence_id"]
            )

    analysis = run_ds2_ds4_v1_pipeline(
        ds4_request=prepared_request,
        ds2_request=deepcopy(ds2_request),
    )

    # Keep provenance outside the official shared response.
    if include_provenance:
        return {
            "analysis": analysis,
            "document_provenance": provenance,
        }

    return analysis
