"""Tests de l'orchestration documentaire DS3 vers DS4."""

from src.track_a_legal.tools.document_evidence_orchestration import (
    collect_document_evidence_links,
)


def test_empty_document_responses_produce_no_links() -> None:
    """Aucun document DS3 ne doit produire aucune association."""

    # Preuve DS4 fictive, sans document DS3 a analyser.
    evidence = [
        {
            "evidence_id": "E1",
            "type": "contract",
            "description": "Contrat fictif.",
            "source": "mock://contract/E1",
        }
    ]

    # Aucune reponse DS3 ni liaison explicite disponible.
    ds3_responses = []
    document_links = {}

    # Executer l'orchestration documentaire.
    result = collect_document_evidence_links(
        evidence,
        ds3_responses,
        document_links,
    )

    # Aucune association ne doit etre inventee.
    assert result == []


def test_valid_explicit_document_link_is_collected() -> None:
    """Collecter une association documentaire explicitement valide."""

    # Preuve DS4 fictive.
    evidence = [
        {
            "evidence_id": "E1",
            "type": "contract",
            "description": "Contrat fictif.",
            "source": "mock://contract/E1",
        }
    ]

    # Reponse DS3 structurellement valide.
    # Le mode live est une donnee du test, pas une preuve d'authenticite.
    ds3_responses = [
        {
            "contract_version": "ds3.v2",
            "status": "ok",
            "mode": "live",
            "computed_by": "document_intelligence.service",
            "operation": "analyze_document",
            "document_id": "doc-001",
            "result": {
                "complete": False,
                "fields": {},
            },
            "citations": [
                {
                    "citation_id": "c1",
                    "document_id": "doc-001",
                    "page": 1,
                    "bbox": None,
                    "excerpt": "Document fictif pour le test",
                }
            ],
        }
    ]

    # Association explicite entre le document DS3 et la preuve DS4.
    document_links = {"doc-001": "E1"}

    # Executer l'orchestration documentaire.
    result = collect_document_evidence_links(
        evidence,
        ds3_responses,
        document_links,
    )

    # Verifier uniquement l'association documentaire.
    # Aucune claim n'est confirmee et aucune conclusion n'est produite.
    assert result == [
        {
            "document_id": "doc-001",
            "evidence_id": "E1",
            "relation": "document_source",
        }
    ]


def test_mock_document_is_not_collected() -> None:
    """Refuser un document DS3 mock malgre une liaison explicite."""

    # Preuve DS4 fictive.
    evidence = [
        {
            "evidence_id": "E1",
            "type": "contract",
            "description": "Contrat fictif.",
            "source": "mock://contract/E1",
        }
    ]

    # Reponse DS3 en mode mock : non exploitable.
    ds3_responses = [
        {
            "contract_version": "ds3.v2",
            "status": "ok",
            "mode": "mock",
            "computed_by": "document_intelligence.mock",
            "operation": "analyze_document",
            "document_id": "doc-001",
            "result": {
                "complete": False,
                "fields": {},
            },
            "citations": [
                {
                    "citation_id": "c1",
                    "document_id": "doc-001",
                    "page": 1,
                    "bbox": None,
                    "excerpt": "Document fictif",
                }
            ],
        }
    ]

    # La liaison existe, mais ne rend pas le document exploitable.
    document_links = {"doc-001": "E1"}

    # Executer l'orchestration.
    result = collect_document_evidence_links(
        evidence,
        ds3_responses,
        document_links,
    )

    # Aucune association ne doit etre produite.
    assert result == []


def test_document_link_to_unknown_evidence_is_rejected() -> None:
    """Refuser une liaison vers une preuve absente du dossier DS4."""

    # Le dossier DS4 contient uniquement la preuve E1.
    evidence = [
        {
            "evidence_id": "E1",
            "type": "contract",
            "description": "Contrat fictif.",
            "source": "mock://contract/E1",
        }
    ]

    # Reponse DS3 structurellement valide.
    ds3_responses = [
        {
            "contract_version": "ds3.v2",
            "status": "ok",
            "mode": "live",
            "computed_by": "document_intelligence.service",
            "operation": "analyze_document",
            "document_id": "doc-001",
            "result": {
                "complete": False,
                "fields": {},
            },
            "citations": [
                {
                    "citation_id": "c1",
                    "document_id": "doc-001",
                    "page": 1,
                    "bbox": None,
                    "excerpt": "Document fictif pour le test",
                }
            ],
        }
    ]

    # E99 ne figure pas dans les preuves DS4 disponibles.
    document_links = {"doc-001": "E99"}

    # Executer l'orchestration documentaire.
    result = collect_document_evidence_links(
        evidence,
        ds3_responses,
        document_links,
    )

    # Ne jamais creer une preuve ou une association inexistante.
    assert result == []


def test_duplicate_document_responses_produce_one_link() -> None:
    """Une reponse DS3 dupliquee ne cree pas deux associations."""

    # Utiliser une copie profonde pour isoler les donnees imbriquees.
    from copy import deepcopy

    # Preuve DS4 fictive.
    evidence = [
        {
            "evidence_id": "E1",
            "type": "contract",
            "description": "Contrat fictif.",
            "source": "mock://contract/E1",
        }
    ]

    # Reponse DS3 structurellement valide.
    ds3_response = {
        "contract_version": "ds3.v2",
        "status": "ok",
        "mode": "live",
        "computed_by": "document_intelligence.service",
        "operation": "analyze_document",
        "document_id": "doc-001",
        "result": {
            "complete": False,
            "fields": {},
        },
        "citations": [
            {
                "citation_id": "c1",
                "document_id": "doc-001",
                "page": 1,
                "bbox": None,
                "excerpt": "Document fictif pour le test",
            }
        ],
    }

    # Simuler la reception de deux copies du meme document.
    ds3_responses = [ds3_response, deepcopy(ds3_response)]

    # Une seule liaison explicite existe.
    document_links = {"doc-001": "E1"}

    # Executer l'orchestration documentaire.
    result = collect_document_evidence_links(
        evidence,
        ds3_responses,
        document_links,
    )

    # La meme association ne doit apparaitre qu'une seule fois.
    assert result == [
        {
            "document_id": "doc-001",
            "evidence_id": "E1",
            "relation": "document_source",
        }
    ]


def test_conflicting_document_responses_are_rejected() -> None:
    """Refuser deux contenus differents avec le meme document_id."""

    # Preuve DS4 disponible.
    evidence = [
        {
            "evidence_id": "E1",
            "type": "contract",
            "description": "Contrat fictif.",
            "source": "mock://contract/E1",
        }
    ]

    # Premiere reponse DS3 structurellement valide.
    first_response = {
        "contract_version": "ds3.v2",
        "status": "ok",
        "mode": "live",
        "computed_by": "document_intelligence.service",
        "operation": "analyze_document",
        "document_id": "doc-001",
        "result": {
            "complete": False,
            "fields": {},
        },
        "citations": [
            {
                "citation_id": "c1",
                "document_id": "doc-001",
                "page": 1,
                "bbox": None,
                "excerpt": "Salaire mensuel : 2000 euros.",
            }
        ],
    }

    # Creer une seconde reponse avec le meme identifiant.
    # Son contenu documentaire est different.
    from copy import deepcopy

    second_response = deepcopy(first_response)
    second_response["citations"][0]["excerpt"] = (
        "Salaire mensuel : 3000 euros."
    )

    # Deux versions distinctes pour un seul document_id.
    ds3_responses = [first_response, second_response]

    # La liaison explicite existe, mais le document est ambigu.
    document_links = {"doc-001": "E1"}

    # Executer l'orchestration documentaire.
    result = collect_document_evidence_links(
        evidence,
        ds3_responses,
        document_links,
    )

    # Refuser toute association issue du document conflictuel.
    assert result == []


def test_conflicting_document_does_not_block_valid_document() -> None:
    """Isoler un document conflictuel sans bloquer les autres."""

    from copy import deepcopy

    # Deux preuves DS4 distinctes.
    evidence = [
        {
            "evidence_id": "E1",
            "type": "contract",
            "description": "Premier contrat fictif.",
            "source": "mock://contract/E1",
        },
        {
            "evidence_id": "E2",
            "type": "contract",
            "description": "Deuxieme contrat fictif.",
            "source": "mock://contract/E2",
        },
    ]

    # Premiere version du document conflictuel.
    doc1 = {
        "contract_version": "ds3.v2",
        "status": "ok",
        "mode": "live",
        "computed_by": "document_intelligence.service",
        "operation": "analyze_document",
        "document_id": "doc-001",
        "result": {"complete": False, "fields": {}},
        "citations": [
            {
                "citation_id": "c1",
                "document_id": "doc-001",
                "page": 1,
                "bbox": None,
                "excerpt": "Salaire : 2000 euros.",
            }
        ],
    }

    # Deuxieme version contradictoire du meme document.
    doc1_conflict = deepcopy(doc1)
    doc1_conflict["citations"][0]["excerpt"] = (
        "Salaire : 3000 euros."
    )

    # Document independant, structurellement valide.
    doc2 = deepcopy(doc1)
    doc2["document_id"] = "doc-002"
    doc2["citations"][0]["document_id"] = "doc-002"
    doc2["citations"][0]["citation_id"] = "c2"
    doc2["citations"][0]["excerpt"] = (
        "Date de signature : 2026-01-01."
    )

    # Les deux documents possedent des liaisons explicites.
    document_links = {
        "doc-001": "E1",
        "doc-002": "E2",
    }

    # Traiter simultanement les documents.
    result = collect_document_evidence_links(
        evidence,
        [doc1, doc1_conflict, doc2],
        document_links,
    )

    # Refuser doc-001 et conserver uniquement doc-002.
    assert result == [
        {
            "document_id": "doc-002",
            "evidence_id": "E2",
            "relation": "document_source",
        }
    ]
