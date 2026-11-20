"""Regression tests for DS2 source traceability in DS4 v1."""

from copy import deepcopy

from src.track_a_legal.v1_handler import handle_v1
from src.track_a_legal.tests.test_v1_case_analysis import (
    make_valid_request,
)


def test_handler_preserves_ds2_article_ids():
    """Preserve article identifiers without asserting legal validity."""

    # Construire une requ?te DS4 valide.
    request = make_valid_request()

    # Utiliser des sources fictives pour un test reproductible.
    request["legal_sources"] = [
        {
            "article_id": "TEST-ART-001",
            "source_id": "TEST-ART-001",
            "reference": "TEST - Article 1",
            "text": "Texte juridique fictif de test.",
        },
        {
            "article_id": "TEST-ART-002",
            "source_id": "TEST-ART-002",
            "reference": "TEST - Article 2",
            "text": "Deuxieme texte juridique fictif.",
        },
    ]

    # V?rifier que le handler ne modifie pas la requ?te.
    original = deepcopy(request)
    response = handle_v1(request)

    assert response["status"] == "ok"
    assert response["result"]["legal_sources_used"] == [
        "TEST-ART-001",
        "TEST-ART-002",
    ]
    assert response["result"]["legal_conclusion"] is None
    assert response["citations"] == []
    assert request == original


def test_handler_without_legal_sources():
    """An empty legal-source list must remain traceable."""

    # Pr?parer une requ?te sans source juridique.
    request = make_valid_request()
    request["legal_sources"] = []

    response = handle_v1(request)

    assert response["status"] == "ok"
    assert response["result"]["legal_sources_used"] == []
    assert response["result"]["legal_conclusion"] is None
