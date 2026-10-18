"""
Evidence Mapping - Lawyer Track (DS4).

Ce module construit les relations explicites entre
les événements d'un dossier et leurs éléments de preuve.

Important :
Le module utilise uniquement les relations présentes
dans les données d'entrée.

Il ne doit jamais inventer une relation entre
une affirmation et une preuve.
"""


def map_event_evidence(
    events: list[dict],
    evidence: list[dict],
) -> list[dict]:
    """
    Construit les relations entre événements et preuves.

    Args:
        events:
            Liste des événements du dossier.

        evidence:
            Liste des éléments de preuve disponibles.

    Returns:
        Une liste de relations explicites entre
        event_id et evidence_id.

    Exemple :
        EV1 possède source_ids = ["E1"]

        Le résultat contient :

        {
            "event_id": "EV1",
            "evidence_id": "E1"
        }
    """

    # ----------------------------------------------------------
    # 1. Récupérer les identifiants des preuves disponibles
    # ----------------------------------------------------------
    #
    # Cela permettra de vérifier qu'une source référencée
    # par un événement existe réellement dans le dossier.

    evidence_ids = {
        item["evidence_id"]
        for item in evidence
    }

    # Liste qui contiendra les relations trouvées.
    mappings = []

    # ----------------------------------------------------------
    # 2. Parcourir les événements
    # ----------------------------------------------------------

    for event in events:

        event_id = event["event_id"]

        # Un événement peut référencer zéro, une ou plusieurs
        # sources via source_ids.
        for source_id in event["source_ids"]:

            # --------------------------------------------------
            # 3. Vérifier que la preuve existe
            # --------------------------------------------------

            if source_id not in evidence_ids:
                raise ValueError(
                    f"La source {source_id} référencée par "
                    f"l'événement {event_id} n'existe pas."
                )

            # --------------------------------------------------
            # 4. Ajouter la relation explicite
            # --------------------------------------------------
            #
            # Nous ne mettons PAS :
            #
            # "supports"
            # "contradicts"
            #
            # car source_ids indique uniquement qu'il existe
            # une relation avec cette source.
            #
            # Il ne dit pas ce que cette preuve démontre.

            mappings.append(
                {
                    "event_id": event_id,
                    "evidence_id": source_id,
                    "relation": "source",
                }
            )

    return mappings