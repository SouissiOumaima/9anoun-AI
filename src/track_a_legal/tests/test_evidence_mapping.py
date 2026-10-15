"""
Tests de l'Evidence Mapping du Lawyer Track (DS4).

Objectif :
Vérifier les relations explicites entre les événements
et les preuves d'un dossier juridique fictif.

Aucune relation juridique n'est inventée.
"""

import pytest

from src.track_a_legal.tools.evidence_mapping import map_event_evidence


def create_fake_evidence() -> list[dict]:
    """
    Crée trois preuves fictives.
    """

    return [
        {
            "evidence_id": "E1",
            "type": "contract",
            "description": "Contrat de travail fictif.",
            "source": "mock://documents/contrat_001",
        },
        {
            "evidence_id": "E2",
            "type": "email",
            "description": "Email fictif.",
            "source": "mock://documents/email_001",
        },
        {
            "evidence_id": "E3",
            "type": "termination_letter",
            "description": "Lettre fictive de licenciement.",
            "source": "mock://documents/lettre_001",
        },
    ]


def test_map_event_evidence_single_source() -> None:
    """
    Vérifie qu'un événement est relié à sa source.
    """

    events = [
        {
            "event_id": "EV1",
            "date": "2024-01-01",
            "description": "Début du contrat fictif.",
            "source_ids": ["E1"],
        }
    ]

    result = map_event_evidence(
        events,
        create_fake_evidence(),
    )

    assert result == [
        {
            "event_id": "EV1",
            "evidence_id": "E1",
            "relation": "source",
        }
    ]


def test_map_event_evidence_multiple_sources() -> None:
    """
    Vérifie qu'un événement peut référencer
    plusieurs éléments de preuve.
    """

    events = [
        {
            "event_id": "EV2",
            "date": "2026-09-05",
            "description": "Incident fictif allégué.",
            "source_ids": ["E2", "E3"],
        }
    ]

    result = map_event_evidence(
        events,
        create_fake_evidence(),
    )

    assert len(result) == 2

    assert result[0]["evidence_id"] == "E2"
    assert result[1]["evidence_id"] == "E3"

    assert all(
        item["relation"] == "source"
        for item in result
    )


def test_map_event_evidence_missing_source() -> None:
    """
    Vérifie qu'une référence inexistante
    provoque une erreur.
    """

    events = [
        {
            "event_id": "EV3",
            "date": "2026-09-10",
            "description": "Notification fictive.",
            "source_ids": ["E99"],
        }
    ]

    with pytest.raises(ValueError, match="E99"):
        map_event_evidence(
            events,
            create_fake_evidence(),
        )


def test_map_event_evidence_without_sources() -> None:
    """
    Vérifie qu'un événement sans source
    ne produit aucune relation inventée.
    """

    events = [
        {
            "event_id": "EV4",
            "date": "2026-09-11",
            "description": "Déclaration fictive sans source.",
            "source_ids": [],
        }
    ]

    result = map_event_evidence(
        events,
        create_fake_evidence(),
    )

    assert result == []

def test_multiple_sources_do_not_invent_relations() -> None:
    """Deux preuves ne doivent pas créer de relation supposée."""

    events = [
        {
            "event_id": "EV-CONFLICT-001",
            "date": "2026-09-10",
            "description": "Date de licenciement contestée.",
            "source_ids": ["E2", "E3"],
        }
    ]

    result = map_event_evidence(
        events,
        create_fake_evidence(),
    )

    assert len(result) == 2

    assert {item["evidence_id"] for item in result} == {"E2", "E3"}

    assert all(
        item["relation"] == "source"
        for item in result
    )

    assert not any(
        item["relation"] in ("supports", "contradicts")
        for item in result
    )