"""Tests du detecteur interne de couverture documentaire DS4."""

from src.track_a_legal.tools.missing_evidence import (
    detect_missing_event_evidence,
)


def test_event_without_source_is_reported() -> None:
    """Un evenement sans source explicite doit etre signale."""

    # Construire un evenement fictif sans reference documentaire.
    events = [
        {
            "event_id": "EV1",
            "date": "2026-09-10",
            "description": "Evenement fictif.",
            "source_ids": [],
        }
    ]

    # Aucune preuve n'est fournie dans ce dossier.
    evidence = []

    # Identifier les evenements sans preuve referencee.
    result = detect_missing_event_evidence(events, evidence)

    # Le resultat doit identifier l'evenement concerne.
    assert result == [
        {
            "event_id": "EV1",
            "reason": "no_source_reference",
        }
    ]


def test_event_with_unknown_source_is_reported() -> None:
    """Une reference vers une preuve inexistante doit etre signalee."""

    # L'evenement reference une preuve E99 absente du dossier.
    events = [
        {
            "event_id": "EV1",
            "date": "2026-09-10",
            "description": "Evenement fictif.",
            "source_ids": ["E99"],
        }
    ]

    # Seule la preuve E1 existe.
    evidence = [
        {
            "evidence_id": "E1",
            "type": "contract",
            "description": "Contrat fictif.",
            "source": "mock://contract/E1",
        }
    ]

    # Detecter les references documentaires manquantes.
    result = detect_missing_event_evidence(events, evidence)

    # Identifier precisement la reference introuvable.
    assert result == [
        {
            "event_id": "EV1",
            "reason": "unknown_source_reference",
            "source_id": "E99",
        }
    ]


def test_event_with_existing_source_is_not_reported() -> None:
    """Une reference existante ne doit pas etre signalee."""

    # Creer un evenement avec une reference explicite.
    events = [
        {
            "event_id": "EV1",
            "date": "2026-09-10",
            "description": "Evenement fictif.",
            "source_ids": ["E1"],
        }
    ]

    # La preuve E1 est presente dans le dossier.
    evidence = [
        {
            "evidence_id": "E1",
            "type": "contract",
            "description": "Contrat fictif.",
            "source": "mock://contract/E1",
        }
    ]

    # Verifier uniquement la couverture des references.
    result = detect_missing_event_evidence(events, evidence)

    # Aucune lacune de reference n'est detectee.
    # Cela ne signifie pas que le fait est juridiquement prouve.
    assert result == []


def test_mixed_case_reports_only_missing_references() -> None:
    """Signaler uniquement les lacunes d'un dossier mixte."""

    # EV1 est reference correctement.
    # EV2 ne possede aucune reference.
    # EV3 contient une reference valide et une inconnue.
    events = [
        {
            "event_id": "EV1",
            "date": "2026-09-01",
            "description": "Evenement documente.",
            "source_ids": ["E1"],
        },
        {
            "event_id": "EV2",
            "date": "2026-09-02",
            "description": "Evenement sans reference.",
            "source_ids": [],
        },
        {
            "event_id": "EV3",
            "date": "2026-09-03",
            "description": "Evenement partiellement reference.",
            "source_ids": ["E1", "E99"],
        },
    ]

    # Une seule preuve est presente.
    evidence = [
        {
            "evidence_id": "E1",
            "type": "contract",
            "description": "Contrat fictif.",
            "source": "mock://contract/E1",
        }
    ]

    # Executer la detection documentaire.
    result = detect_missing_event_evidence(events, evidence)

    # Conserver l'ordre et signaler uniquement les lacunes.
    assert result == [
        {
            "event_id": "EV2",
            "reason": "no_source_reference",
        },
        {
            "event_id": "EV3",
            "reason": "unknown_source_reference",
            "source_id": "E99",
        },
    ]


def test_missing_evidence_does_not_modify_inputs() -> None:
    """La detection ne doit modifier ni les evenements ni les preuves."""

    from copy import deepcopy

    # Construire un dossier fictif avec une reference inconnue.
    events = [
        {
            "event_id": "EV1",
            "date": "2026-09-10",
            "description": "Evenement fictif.",
            "source_ids": ["E1", "E99"],
        }
    ]

    evidence = [
        {
            "evidence_id": "E1",
            "type": "contract",
            "description": "Contrat fictif.",
            "source": "mock://contract/E1",
        }
    ]

    # Sauvegarder des copies independantes.
    original_events = deepcopy(events)
    original_evidence = deepcopy(evidence)

    # Executer la detection documentaire.
    result = detect_missing_event_evidence(events, evidence)

    # Verifier le signalement attendu.
    assert result == [
        {
            "event_id": "EV1",
            "reason": "unknown_source_reference",
            "source_id": "E99",
        }
    ]

    # Verifier que les donnees d'entree restent identiques.
    assert events == original_events
    assert evidence == original_evidence
