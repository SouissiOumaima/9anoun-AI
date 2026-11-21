"""Association explicite entre documents DS3 et preuves DS4."""

from typing import Any

from src.track_a_legal.tools.document_source_validation import (
    is_usable_document_response,
)


def link_document_to_evidence(
    evidence: dict,
    ds3_response: Any,
    document_links: dict,
) -> dict | None:
    """Associer un document DS3 a une preuve DS4 si la liaison est valide."""

    # Refuser les entrees dont la structure est incorrecte.
    if not isinstance(evidence, dict):
        return None

    if not isinstance(ds3_response, dict):
        return None

    if not isinstance(document_links, dict):
        return None

    # Recuperer les identifiants des deux systemes.
    evidence_id = evidence.get("evidence_id")
    document_id = ds3_response.get("document_id")

    # Refuser les identifiants absents ou vides.
    if not isinstance(evidence_id, str) or not evidence_id.strip():
        return None

    if not isinstance(document_id, str) or not document_id.strip():
        return None

    # Exiger une association explicite :
    # document_id DS3 -> evidence_id DS4.
    if document_links.get(document_id) != evidence_id:
        return None

    # Reutiliser le validateur documentaire existant.
    # Ne pas considerer une reponse mock comme une preuve exploitable.
    if not is_usable_document_response(ds3_response):
        return None

    # Retourner uniquement une association documentaire.
    # Aucune conclusion juridique n'est produite.
    return {
        "document_id": document_id,
        "evidence_id": evidence_id,
        "relation": "document_source",
    }
