"""Orchestration des associations documentaires DS3 vers DS4."""

from typing import Any

from src.track_a_legal.tools.document_evidence_adapter import (
    link_document_to_evidence,
)


def collect_document_evidence_links(
    evidence: list[dict],
    ds3_responses: list[Any],
    document_links: dict,
) -> list[dict]:
    """Collecter les associations documentaires explicitement validees."""

    # Ne jamais deduire une liaison sans declaration explicite.
    if not isinstance(document_links, dict):
        return []

    # Refuser les collections documentaires mal formees.
    if not isinstance(ds3_responses, list):
        return []

    if not isinstance(evidence, list):
        return []

    # Memoriser les reponses par identifiant documentaire.
    # Deux contenus differents pour un meme ID constituent un conflit.
    document_versions = {}
    conflicting_document_ids = set()

    for response in ds3_responses:
        # Ignorer les reponses sans structure documentaire exploitable.
        if not isinstance(response, dict):
            continue

        document_id = response.get("document_id")

        # Ne comparer que les identifiants textuels non vides.
        if not isinstance(document_id, str) or not document_id.strip():
            continue

        # Comparer les contenus sans modifier les reponses originales.
        if document_id not in document_versions:
            document_versions[document_id] = response
        elif document_versions[document_id] != response:
            conflicting_document_ids.add(document_id)

    # Conserver uniquement les associations acceptees par l'adaptateur.
    associations = []

    # Memoriser les couples document-preuve deja collectes.
    # Eviter les doublons sans modifier les documents originaux.
    seen_links = set()

    # Examiner chaque reponse documentaire DS3.
    for ds3_response in ds3_responses:

        # Refuser toutes les versions d'un document conflictuel.
        if isinstance(ds3_response, dict):
            document_id = ds3_response.get("document_id")

            if (
                isinstance(document_id, str)
                and document_id in conflicting_document_ids
            ):
                continue

        # Comparer le document aux preuves DS4 disponibles.
        for item in evidence:

            # L'adaptateur verifie la liaison et la reponse DS3.
            association = link_document_to_evidence(
                item,
                ds3_response,
                document_links,
            )

            # Ignorer toute association refusee.
            if association is None:
                continue

            # Identifier l'association documentaire de facon stable.
            link_key = (
                association["document_id"],
                association["evidence_id"],
            )

            # Ignorer les associations deja collectees.
            if link_key in seen_links:
                continue

            # Memoriser l'association avant de l'ajouter.
            seen_links.add(link_key)

            # Ajouter uniquement les metadonnees de liaison.
            # Ne confirmer aucune claim ni conclusion juridique.
            associations.append(association)

    return associations
