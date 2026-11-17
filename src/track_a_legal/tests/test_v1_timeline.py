
"""Tests unitaires du moteur Timeline DS4 v1."""

from copy import deepcopy

import pytest

from src.track_a_legal.v1_timeline import build_v1_timeline


def create_events():
    """Cr?er des ?v?nements fictifs dans le d?sordre."""

    return [
        {
            "event_id": "EV-003",
            "date": None,
            "date_precision": "unknown",
            "date_reason": "Date absente du document.",
            "description": "?v?nement sans date.",
            "source_ids": ["SRC-003"],
            "evidence_ids": ["EVD-003"],
        },
        {
            "event_id": "EV-002",
            "date": "2025-06-10",
            "date_precision": "exact",
            "date_reason": None,
            "description": "Deuxi?me ?v?nement.",
            "source_ids": ["SRC-002"],
            "evidence_ids": ["EVD-002"],
        },
        {
            "event_id": "EV-001",
            "date": "2024-01-15",
            "date_precision": "exact",
            "date_reason": None,
            "description": "Premier ?v?nement.",
            "source_ids": ["SRC-001"],
            "evidence_ids": ["EVD-001"],
        },
        {
            "event_id": "EV-004",
            "date": None,
            "date_precision": "unknown",
            "date_reason": "Date non communiqu?e.",
            "description": "Autre ?v?nement sans date.",
            "source_ids": ["SRC-004"],
            "evidence_ids": ["EVD-004"],
        },
    ]


def test_sorts_known_dates_chronologically():
    """Les dates connues doivent ?tre class?es."""

    result = build_v1_timeline(create_events())

    assert [
        event["event_id"] for event in result
    ] == ["EV-001", "EV-002", "EV-003", "EV-004"]


def test_preserves_unknown_dates():
    """Les dates inconnues restent null."""

    result = build_v1_timeline(create_events())

    unknown = [
        event for event in result
        if event["date"] is None
    ]

    assert len(unknown) == 2


def test_preserves_unknown_events_order():
    """Les ?v?nements inconnus gardent leur ordre initial."""

    result = build_v1_timeline(create_events())

    unknown_ids = [
        event["event_id"]
        for event in result
        if event["date"] is None
    ]

    assert unknown_ids == ["EV-003", "EV-004"]


def test_rejects_unknown_date_without_reason():
    """Une date inconnue exige une justification."""

    events = create_events()
    events[0]["date_reason"] = "   "

    with pytest.raises(ValueError):
        build_v1_timeline(events)


def test_rejects_invalid_date():
    """Une date impossible doit ?tre rejet?e."""

    events = create_events()
    events[1]["date"] = "2026-02-30"

    with pytest.raises(ValueError):
        build_v1_timeline(events)


def test_preserves_document_references():
    """Les r?f?rences documentaires doivent rester intactes."""

    result = build_v1_timeline(create_events())

    first = result[0]

    assert first["source_ids"] == ["SRC-001"]
    assert first["evidence_ids"] == ["EVD-001"]


def test_does_not_modify_original_events():
    """Les donn?es originales ne doivent pas ?tre modifi?es."""

    events = create_events()
    original = deepcopy(events)

    build_v1_timeline(events)

    assert events == original


def test_rejects_incorrect_precision():
    """Une date connue ne peut pas avoir une pr?cision unknown."""

    events = create_events()
    events[1]["date_precision"] = "unknown"

    with pytest.raises(ValueError):
        build_v1_timeline(events)
