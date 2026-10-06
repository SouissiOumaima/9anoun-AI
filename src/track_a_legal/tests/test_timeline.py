"""
Tests de la timeline du Case-Analysis Agent (DS4).

Les tests utilisent uniquement des données fictives.
"""

import pytest

from src.track_a_legal.tools.timeline import build_timeline


def create_fake_events() -> list[dict]:
    """
    Crée des événements fictifs volontairement
    placés dans le mauvais ordre chronologique.
    """

    return [
        {
            "event_id": "EV3",
            "date": "2026-09-10",
            "description": "Notification fictive du licenciement.",
            "source_ids": ["E3"],
        },
        {
            "event_id": "EV1",
            "date": "2024-01-01",
            "description": "Début fictif du contrat.",
            "source_ids": ["E1"],
        },
        {
            "event_id": "EV2",
            "date": "2026-09-05",
            "description": "Incident fictif allégué.",
            "source_ids": ["E2"],
        },
    ]


def test_build_timeline_orders_events() -> None:
    """
    Vérifie que les événements sont classés
    du plus ancien au plus récent.
    """

    events = create_fake_events()

    timeline = build_timeline(events)

    assert timeline[0]["event_id"] == "EV1"
    assert timeline[1]["event_id"] == "EV2"
    assert timeline[2]["event_id"] == "EV3"


def test_build_timeline_keeps_source_ids() -> None:
    """
    Vérifie que la construction de la timeline
    ne supprime pas les références vers les sources.

    C'est important pour la traçabilité et la règle
    « Citation ou Silence ».
    """

    events = create_fake_events()

    timeline = build_timeline(events)

    # EV1 doit toujours pointer vers E1.
    assert timeline[0]["source_ids"] == ["E1"]

    # EV2 doit toujours pointer vers E2.
    assert timeline[1]["source_ids"] == ["E2"]

    # EV3 doit toujours pointer vers E3.
    assert timeline[2]["source_ids"] == ["E3"]


def test_build_timeline_does_not_modify_input() -> None:
    """
    Vérifie que la liste originale n'est pas réordonnée.

    Les données reçues par DS4 doivent rester intactes.
    """

    events = create_fake_events()

    # On mémorise l'ordre original.
    original_order = [
        event["event_id"]
        for event in events
    ]

    build_timeline(events)

    # L'ordre original doit rester :
    # EV3, EV1, EV2.
    assert [
        event["event_id"]
        for event in events
    ] == original_order


def test_build_timeline_rejects_invalid_date() -> None:
    """
    Vérifie qu'une date impossible est refusée.
    """

    events = [
        {
            "event_id": "EV-INVALID",
            "date": "2026-99-99",
            "description": "Événement fictif avec date invalide.",
            "source_ids": ["E1"],
        }
    ]

    # Nous attendons explicitement une ValueError.
    with pytest.raises(ValueError):
        build_timeline(events)