"""Tests des contrôles préliminaires des réponses DS2."""

import pytest

from src.track_a_legal.tools.legal_source_validation import (
    is_usable_legal_response,
)


@pytest.fixture
def valid_response():
    """Construire une réponse DS2 minimale pour les tests préliminaires."""

    return {
        "contract_version": "legal_retrieval.v0",
        "request_id": "ds4-test-001",
        "status": "ok",
        "mode": "live",
        "results": [{"article_id": "ARTICLE-1"}],
        "citations": [{"source_file": "source.pdf"}],
        "refus": None,
    }


def test_accepts_preliminary_live_response(valid_response):
    """Accepter une réponse qui satisfait les contrôles préliminaires."""

    assert is_usable_legal_response(valid_response) is True


@pytest.mark.parametrize(
    "field, value",
    [
        ("contract_version", "unknown.v0"),
        ("status", "refus"),
        ("status", "erreur"),
        ("mode", "mock"),
        ("results", []),
        ("citations", []),
        ("results", None),
        ("citations", None),
    ],
)
def test_rejects_invalid_preliminary_response(valid_response, field, value):
    """Rejeter les réponses qui échouent à un contrôle préliminaire."""

    # Modifier uniquement la copie locale du scénario de test.
    response = valid_response.copy()
    response[field] = value

    assert is_usable_legal_response(response) is False


@pytest.mark.parametrize("response", [None, [], "invalid", 42])
def test_rejects_non_object_response(response):
    """Rejeter les entrées qui ne sont pas des objets JSON."""

    assert is_usable_legal_response(response) is False


def test_rejects_missing_required_field(valid_response):
    """Rejeter une réponse sans champ indispensable au contrôle."""

    # Retirer le mode pour simuler une réponse incomplète.
    response = valid_response.copy()
    response.pop("mode")

    assert is_usable_legal_response(response) is False
