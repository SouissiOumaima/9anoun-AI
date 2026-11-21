"""
Case Integrity Validator - Lawyer Track DS4.

Verifie la coherence des references internes d'un dossier.

Cette validation ne constitue pas une verification
juridique des affirmations ou des preuves.
"""


def validate_case_integrity(case: dict) -> None:
    """
    Verifie les references entre affirmations et parties.

    Args:
        case: Dossier structure conforme au contrat Track A.

    Raises:
        ValueError: Une affirmation reference une partie inconnue.
    """

    # Recuperer tous les identifiants des parties.
    party_id_list = [
        party["party_id"]
        for party in case["parties"]
    ]

    # Construire l'ensemble des identifiants uniques.
    party_ids = set(party_id_list)

    # Refuser les identifiants dupliques.
    if len(party_id_list) != len(party_ids):
        raise ValueError("duplicate_party_id")

    # Verifier l'unicite des identifiants des evenements,
    # des affirmations et des preuves.
    collections = (
        ("events", "event_id"),
        ("claims", "claim_id"),
        ("evidence", "evidence_id"),
    )

    for collection_name, identifier_name in collections:

        # Extraire les identifiants de la collection.
        identifiers = [
            item[identifier_name]
            for item in case[collection_name]
        ]

        # Comparer le nombre total et le nombre d'identifiants uniques.
        if len(identifiers) != len(set(identifiers)):
            raise ValueError(f"duplicate_{identifier_name}")

    # Examiner chaque affirmation du dossier.
    for claim in case["claims"]:

        # Recuperer la partie associee a l'affirmation.
        party_id = claim["party_id"]

        # Refuser toute reference vers une partie inexistante.
        if party_id not in party_ids:
            raise ValueError(
                f"unknown_party_id: {party_id}"
            )
