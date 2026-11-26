"""Tests de liaison explicite entre documents DS3 et preuves DS4."""

from src.track_a_legal.tools.document_evidence_adapter import (
    link_document_to_evidence,
)


def test_document_without_explicit_link_is_not_associated() -> None:
    """Une preuve DS4 ne doit jamais etre associee par supposition."""

    # Preuve fictive conforme a la structure Track A v0.
    evidence = {
        "evidence_id": "E1",
        "type": "contract",
        "description": "Contrat fictif.",
        "source": "mock://contract/E1",
    }

    # Reponse DS3 valide pour isoler l'absence de liaison.
    # Les donnees restent fictives et ne prouvent aucun fait juridique.
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

    # Aucune association document -> preuve n'a ete declaree.
    document_links = {}

    # Sans liaison explicite, aucun rapprochement n'est autorise.
    result = link_document_to_evidence(
        evidence,
        ds3_response,
        document_links,
    )

    assert result is None


def test_explicit_valid_document_link_is_associated() -> None:
    """Associer un document DS3 valide uniquement via un lien explicite."""

    # Preuve fictive conforme au contrat d'entree Track A v0.
    evidence = {
        "evidence_id": "E1",
        "type": "contract",
        "description": "Contrat fictif.",
        "source": "mock://contract/E1",
    }

    # Reponse DS3 reprenant un scenario accepte par le validateur.
    # Le champ inconnu ne doit pas etre considere comme un fait confirme.
    ds3_response = {
        "contract_version": "ds3.v2",
        "status": "ok",
        "mode": "live",
        "computed_by": "document_intelligence.service",
        "operation": "analyze_document",
        "document_id": "doc-001",
        "result": {
            "complete": False,
            "fields": {
                "employee_name": {
                    "value": None,
                    "confidence": None,
                    "citation_id": None,
                }
            },
        },
        "citations": [
            {
                "citation_id": "c1",
                "document_id": "doc-001",
                "page": 1,
                "bbox": None,
                "excerpt": "Document analyse",
            }
        ],
    }

    # Association fournie explicitement par le systeme appelant.
    document_links = {"doc-001": "E1"}

    # Executer l'adaptateur.
    result = link_document_to_evidence(
        evidence,
        ds3_response,
        document_links,
    )

    # Verifier uniquement la liaison documentaire.
    # Aucune conclusion juridique ni validation des faits.
    assert result == {
        "document_id": "doc-001",
        "evidence_id": "E1",
        "relation": "document_source",
    }


def test_mock_document_is_not_associated() -> None:
    """Refuser une réponse DS3 mock malgré une liaison explicite."""

    # Preuve fictive du Lawyer Track.
    evidence = {
        "evidence_id": "E1",
        "type": "contract",
        "description": "Contrat fictif.",
        "source": "mock://contract/E1",
    }

    # Réponse DS3 de démonstration, non exploitable.
    ds3_response = {
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

    # Une liaison explicite existe, mais ne suffit pas.
    document_links = {"doc-001": "E1"}

    # L'adaptateur doit refuser la réponse mock.
    result = link_document_to_evidence(
        evidence,
        ds3_response,
        document_links,
    )

    assert result is None


def test_document_link_to_wrong_evidence_is_rejected() -> None:
    """Refuser une liaison vers une autre preuve que celle demandee."""

    # Reponse DS3 valide pour tester uniquement le controle de liaison.
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

    # La preuve examinee est E1.
    evidence = {
        "evidence_id": "E1",
        "type": "contract",
        "description": "Contrat fictif.",
        "source": "mock://contract/E1",
    }

    # Le document est explicitement associe a E2, et non E1.
    document_links = {"doc-001": "E2"}

    # L'adaptateur ne doit pas creer de fausse association.
    result = link_document_to_evidence(
        evidence,
        ds3_response,
        document_links,
    )

    assert result is None


def test_document_with_mismatched_citation_is_rejected() -> None:
    """Refuser une citation liee a un autre document DS3."""

    # Preuve DS4 fictive.
    evidence = {
        "evidence_id": "E1",
        "type": "contract",
        "description": "Contrat fictif.",
        "source": "mock://contract/E1",
    }

    # Reponse DS3 avec une citation incoherente.
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
                "document_id": "doc-999",
                "page": 1,
                "bbox": None,
                "excerpt": "Citation fictive",
            }
        ],
    }

    # Liaison explicite correcte, mais citation invalide.
    document_links = {"doc-001": "E1"}

    # Le validateur DS3 doit empecher cette association.
    result = link_document_to_evidence(
        evidence,
        ds3_response,
        document_links,
    )

    assert result is None
