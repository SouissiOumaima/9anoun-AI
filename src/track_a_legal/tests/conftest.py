"""Fixtures pytest partagees pour les tests DS4."""

import pytest


@pytest.fixture
def valid_ds2_response():
    """Retourner une reponse DS2 fictive conforme au contrat officiel."""

    # Citation synthetique : aucune source juridique reelle.
    citation = {
        "source_file": "synthetic_test.pdf",
        "page": 1,
        "article": "TEST-1",
        "data_file": "data/processed/synthetic_test.json",
        "decision_ref": "D1",
    }

    # Article complet avec les champs requis par legal_retrieval.v0.
    article = {
        "article_id": "TEST-ART-1-v1",
        "source_id": "TEST-SOURCE",
        "source_title": "Source fictive",
        "article_number": 1,
        "hierarchy_path": "TEST",
        "text": "Texte fictif pour validation technique.",
        "page": 1,
        "effective_from": "2024-01-01",
        "effective_to": None,
        "status": "en_vigueur",
        "sector": None,
        "related": [],
        "score": 1.0,
        "version_group": "TEST-ART-1",
        "version": 1,
        "applicable_at_reference_date": True,
        "modified": False,
        "amended_by": None,
        "previous_version_available": False,
        "citation": citation,
    }

    # Enveloppe DS2 complete en mode live simule.
    return {
        "contract_version": "legal_retrieval.v0",
        "request_id": "DS4-TEST-001",
        "status": "ok",
        "mode": "live",
        "computed_by": "legal_retrieval.search.live",
        "citations": [citation],
        "refus": None,
        "results": [article],
    }
