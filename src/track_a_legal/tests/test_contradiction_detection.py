"""Tests du detecteur interne de contradictions DS4."""

from src.track_a_legal.tools.contradiction_detection import (
    detect_contradictions,
)


def test_opposite_unverified_claims_are_not_proven_contradictions() -> None:
    """Deux declarations opposees ne prouvent aucune contradiction factuelle."""

    # Deux parties presentent des versions opposees d'un evenement.
    claims = [
        {
            "claim_id": "C1",
            "party_id": "P1",
            "text": "Le salarie affirme avoir travaille le 10 septembre.",
            "status": "unverified",
        },
        {
            "claim_id": "C2",
            "party_id": "P2",
            "text": "L'employeur affirme que le salarie n'a pas travaille le 10 septembre.",
            "status": "unverified",
        },
    ]

    # Executer la detection sans preuve documentaire verifiee.
    result = detect_contradictions(claims)

    # Ne pas transformer des allegations opposees en faits etablis.
    assert result == []

    # Conserver le statut initial de chaque affirmation.
    assert all(claim["status"] == "unverified" for claim in claims)


def test_contradiction_detection_does_not_modify_claims() -> None:
    """Le detecteur ne doit pas modifier les affirmations recues."""

    from copy import deepcopy

    # Construire deux affirmations fictives non verifiees.
    claims = [
        {
            "claim_id": "C1",
            "party_id": "P1",
            "text": "Le salaire a ete verse.",
            "status": "unverified",
        },
        {
            "claim_id": "C2",
            "party_id": "P2",
            "text": "Le salaire n'a pas ete verse.",
            "status": "unverified",
        },
    ]

    # Conserver une copie independante des donnees.
    original_claims = deepcopy(claims)

    # Executer le detecteur.
    result = detect_contradictions(claims)

    # Aucune contradiction factuelle ne peut etre etablie.
    assert result == []

    # Les affirmations originales doivent rester intactes.
    assert claims == original_claims
