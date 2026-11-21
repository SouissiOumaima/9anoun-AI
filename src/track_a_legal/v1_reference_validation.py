"""Validation des références croisées du contrat track_a.v1."""

from __future__ import annotations

from typing import Any


def validate_v1_references(
    request: dict[str, Any],
) -> list[dict[str, str]]:
    """Retourner les références inconnues du dossier v1.

    Cette fonction suppose que la structure de la requête
    a déjà été validée par le JSON Schema v1.

    Elle ne contacte ni DS2 ni DS3 et ne modifie pas
    les données reçues.
    """

    errors: list[dict[str, str]] = []

    # Construire les ensembles d'identifiants disponibles.
    parties = {
        item["party_id"]
        for item in request.get("parties", [])
    }

    events = {
        item["event_id"]
        for item in request.get("events", [])
    }

    evidence = {
        item["evidence_id"]
        for item in request.get("evidence", [])
    }

    legal_sources = {
        item["source_id"]
        for item in request.get("legal_sources", [])
    }

    def check_reference(
        value: str,
        valid_ids: set[str],
        path: str,
    ) -> None:
        """Signaler une référence absente de sa collection."""

        if value not in valid_ids:
            errors.append({
                "code": "UNKNOWN_REFERENCE",
                "path": path,
                "reference_id": value,
            })

    def check_reference_list(
        values: list[str],
        valid_ids: set[str],
        path: str,
    ) -> None:
        """Contrôler chaque identifiant d'une liste."""

        for index, value in enumerate(values):
            check_reference(
                value,
                valid_ids,
                f"{path}/{index}",
            )

    # Vérifier les références des demandes juridiques.
    for index, claim in enumerate(request.get("claims", [])):

        prefix = f"claims/{index}"

        check_reference(
            claim["party_id"],
            parties,
            f"{prefix}/party_id",
        )

        check_reference_list(
            claim.get("event_ids", []),
            events,
            f"{prefix}/event_ids",
        )

        check_reference_list(
            claim.get("evidence_ids", []),
            evidence,
            f"{prefix}/evidence_ids",
        )

        check_reference_list(
            claim.get("legal_source_ids", []),
            legal_sources,
            f"{prefix}/legal_source_ids",
        )

    # Vérifier les liens des événements vers les preuves.
    for index, event in enumerate(request.get("events", [])):

        check_reference_list(
            event.get("evidence_ids", []),
            evidence,
            f"events/{index}/evidence_ids",
        )

    # Vérifier les faits documentaires transmis par DS1.
    for index, fact in enumerate(
        request.get("document_facts", [])
    ):

        prefix = f"document_facts/{index}"

        check_reference(
            fact["subject_id"],
            parties,
            f"{prefix}/subject_id",
        )

        check_reference(
            fact["evidence_id"],
            evidence,
            f"{prefix}/evidence_id",
        )


    # V?rifier l'unicit? des identifiants dans chaque collection.
    collections = {
        "parties": "party_id",
        "events": "event_id",
        "claims": "claim_id",
        "evidence": "evidence_id",
        "document_facts": "fact_id",
        "legal_sources": "source_id",
        "missing_information": "missing_id",
        "contradictions": "contradiction_id",
    }

    for collection, id_field in collections.items():
        seen: set[str] = set()

        for index, item in enumerate(request.get(collection, [])):
            identifier = item[id_field]

            if identifier in seen:
                errors.append({
                    "code": "DUPLICATE_ID",
                    "path": f"{collection}/{index}/{id_field}",
                    "reference_id": identifier,
                })

            seen.add(identifier)

    # V?rifier les liens des informations manquantes.
    for index, item in enumerate(
        request.get("missing_information", [])
    ):
        prefix = f"missing_information/{index}"

        check_reference_list(
            item.get("related_event_ids", []),
            events,
            f"{prefix}/related_event_ids",
        )

        check_reference_list(
            item.get("related_claim_ids", []),
            {
                claim["claim_id"]
                for claim in request.get("claims", [])
            },
            f"{prefix}/related_claim_ids",
        )

        check_reference_list(
            item.get("related_evidence_ids", []),
            evidence,
            f"{prefix}/related_evidence_ids",
        )

    # V?rifier les liens explicites des contradictions.
    for index, item in enumerate(
        request.get("contradictions", [])
    ):
        prefix = f"contradictions/{index}"

        check_reference_list(
            item.get("related_event_ids", []),
            events,
            f"{prefix}/related_event_ids",
        )

        check_reference_list(
            item.get("related_claim_ids", []),
            {
                claim["claim_id"]
                for claim in request.get("claims", [])
            },
            f"{prefix}/related_claim_ids",
        )

        check_reference_list(
            item.get("related_evidence_ids", []),
            evidence,
            f"{prefix}/related_evidence_ids",
        )

    # Les source_ids restent hors du contr?le de r?f?rences
    # tant que leur espace d'identifiants n'est pas d?fini.

    return errors
