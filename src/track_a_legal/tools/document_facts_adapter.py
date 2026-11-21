"""Adaptateur prudent des reponses DS3 vers les faits DS4."""

import re
from datetime import date
from typing import Any

from src.track_a_legal.tools.document_source_validation import (
    is_usable_document_response,
)


# Champs monetaires autorises pour cette premiere version.
MONETARY_FIELDS = (
    "base_salary",
    "gross_salary",
    "cnss_employee",
)


def extract_document_facts(
    response: Any,
    subject_id: str,
) -> list[dict]:
    """Extraire des faits monetaires documentes, sans inference."""

    # Refuser les identifiants de sujet absents ou invalides.
    if not isinstance(subject_id, str) or not subject_id.strip():
        return []

    # Appliquer les controles documentaires existants.
    # Ce controle ne garantit pas l'authenticite de la provenance.
    if not is_usable_document_response(response):
        return []

    # La v1 ne traite que l'analyse de documents.
    if response.get("operation") != "analyze_document":
        return []

    result = response["result"]
    fields = result["fields"]

    # Recuperer les deux bornes explicites de la periode.
    start_field = fields.get("period_start")
    end_field = fields.get("period_end")

    if not isinstance(start_field, dict):
        return []

    if not isinstance(end_field, dict):
        return []

    # Exiger le type date pour les deux bornes de la periode.
    if start_field.get("value_type") != "date":
        return []

    if end_field.get("value_type") != "date":
        return []

    start = start_field.get("value")
    end = end_field.get("value")

    # Exiger deux dates ISO explicites.
    if not isinstance(start, str) or not isinstance(end, str):
        return []

    try:
        start_date = date.fromisoformat(start)
        end_date = date.fromisoformat(end)
    except ValueError:
        return []

    # Eviter une periode inversee.
    if start_date > end_date:
        return []

    # Normaliser la representation interne de la periode.
    period = f"{start_date.isoformat()}/{end_date.isoformat()}"

    # Conserver les references du document.
    document_id = response["document_id"]
    citation_ids = {
        citation["citation_id"]
        for citation in response["citations"]
    }

    facts = []

    # Traiter uniquement les montants explicitement autorises.
    for property_name in MONETARY_FIELDS:
        field = fields.get(property_name)

        if not isinstance(field, dict):
            continue

        # Accepter uniquement les champs monetaires declares par DS3.
        if field.get("value_type") != "montant":
            continue

        # Verifier le score DS3 sans imposer de seuil metier.
        confidence = field.get("confidence")

        if type(confidence) not in (int, float):
            continue

        if not 0.0 <= confidence <= 1.0:
            continue

        value = field.get("value")
        citation_id = field.get("citation_id")

        # Exiger une valeur monetaire au format DS3.
        if not isinstance(value, str):
            continue

        if re.fullmatch(r"-?[0-9]+\.[0-9]{3}", value) is None:
            continue

        # Refuser une citation absente ou inconnue.
        if not isinstance(citation_id, str):
            continue

        if citation_id not in citation_ids:
            continue

        # Produire un fait compatible avec fact_comparison.py.
        facts.append(
            {
                "fact_id": f"{document_id}:{property_name}",
                "subject_id": subject_id,
                "property": property_name,
                "period": period,
                "unit": "TND",
                "value": value,
                "document_id": document_id,
                "citation_id": citation_id,
            }
        )

    return facts
