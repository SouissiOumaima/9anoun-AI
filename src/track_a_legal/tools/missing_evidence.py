"""Detection interne des lacunes de couverture documentaire DS4."""


def detect_missing_event_evidence(
    events: list[dict],
    evidence: list[dict],
) -> list[dict]:
    """
    Identifier les evenements sans reference documentaire exploitable.

    Cette fonction ne determine pas si un fait est juridiquement prouve.
    Elle signale uniquement les references absentes ou inconnues.
    """

    # Construire l'ensemble des identifiants de preuves disponibles.
    available_evidence_ids = {
        item["evidence_id"]
        for item in evidence
    }

    # Conserver les signalements dans l'ordre des evenements.
    missing = []

    # Examiner chaque evenement du dossier.
    for event in events:

        # Recuperer les references explicites.
        source_ids = event["source_ids"]

        # Cas 1 : aucune reference documentaire.
        if not source_ids:
            missing.append(
                {
                    "event_id": event["event_id"],
                    "reason": "no_source_reference",
                }
            )
            continue

        # Cas 2 : reference vers une preuve absente.
        for source_id in source_ids:
            if source_id not in available_evidence_ids:
                missing.append(
                    {
                        "event_id": event["event_id"],
                        "reason": "unknown_source_reference",
                        "source_id": source_id,
                    }
                )

    # Ne jamais produire de conclusion juridique.
    return missing
