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


def test_document_divergence_is_not_a_proven_contradiction() -> None:
    """Une divergence documentaire ne prouve pas une contradiction."""

    from copy import deepcopy

    # Deux documents fictifs indiquent des salaires differents
    # pour la meme personne et la meme periode.
    document_facts = [
        {
            "fact_id": "F1",
            "subject_id": "P1",
            "property": "monthly_salary",
            "period": "2026-01",
            "unit": "TND",
            "value": "1200.000",
            "document_id": "DOC-001",
            "citation_id": "CIT-001",
        },
        {
            "fact_id": "F2",
            "subject_id": "P1",
            "property": "monthly_salary",
            "period": "2026-01",
            "unit": "TND",
            "value": "1500.000",
            "document_id": "DOC-002",
            "citation_id": "CIT-002",
        },
    ]

    # Conserver une copie des donnees originales.
    original_facts = deepcopy(document_facts)

    # Aucun claim n'est fourni.
    claims = []

    # Tester la nouvelle interface avec des faits documentaires.
    result = detect_contradictions(
        claims,
        document_facts=document_facts,
    )

    # Une divergence potentielle ne suffit pas
    # a etablir une contradiction factuelle.
    assert result == []

    # Verifier l'absence de mutation.
    assert document_facts == original_facts


def test_document_divergences_are_reported_separately() -> None:
    """Les divergences documentaires restent des alertes potentielles."""

    # Importer la nouvelle fonction interne attendue.
    from src.track_a_legal.tools.contradiction_detection import (
        detect_document_divergences,
    )

    # Construire deux faits fictifs de meme contexte.
    document_facts = [
        {
            "fact_id": "F1",
            "subject_id": "P1",
            "property": "monthly_salary",
            "period": "2026-01",
            "unit": "TND",
            "value": "1200.000",
            "document_id": "DOC-001",
            "citation_id": "CIT-001",
        },
        {
            "fact_id": "F2",
            "subject_id": "P1",
            "property": "monthly_salary",
            "period": "2026-01",
            "unit": "TND",
            "value": "1500.000",
            "document_id": "DOC-002",
            "citation_id": "CIT-002",
        },
    ]

    # Executer la detection des divergences potentielles.
    result = detect_document_divergences(document_facts)

    # Verifier le signalement et les references documentaires.
    assert result == [
        {
            "type": "potential_divergence",
            "fact_ids": ["F1", "F2"],
            "document_ids": ["DOC-001", "DOC-002"],
            "citation_ids": ["CIT-001", "CIT-002"],
        }
    ]

    # Aucun statut de contradiction prouvee n'est ajoute.
    assert all(
        item["type"] == "potential_divergence"
        for item in result
    )


def test_document_divergences_preserve_inputs_and_ignore_invalid_values() -> None:
    """L'integration preserve les faits et ignore les valeurs invalides."""

    from copy import deepcopy
    from src.track_a_legal.tools.contradiction_detection import (
        detect_document_divergences,
    )

    # Construire un fait valide et un fait non exploitable.
    facts = [
        {
            "fact_id": "F1",
            "subject_id": "P1",
            "property": "monthly_salary",
            "period": "2026-01",
            "unit": "TND",
            "value": "1200.000",
            "document_id": "DOC-001",
            "citation_id": "CIT-001",
        },
        {
            "fact_id": "F2",
            "subject_id": "P1",
            "property": "monthly_salary",
            "period": "2026-01",
            "unit": "TND",
            "value": "NaN",
            "document_id": "DOC-002",
            "citation_id": "CIT-002",
        },
    ]

    # Conserver une copie independante.
    original_facts = deepcopy(facts)

    # Executer le detecteur documentaire.
    result = detect_document_divergences(facts)

    # Une valeur invalide ne doit produire aucune divergence.
    assert result == []

    # Les donnees d'origine doivent rester intactes.
    assert facts == original_facts
