
"""
Tests automatisés du handler DS4 - Lawyer Track.

Les tests utilisent uniquement des données fictives.
"""

import json
from pathlib import Path

from src.track_a_legal.handler import handle


ROOT = Path(__file__).resolve().parents[3]

DEMO_FILE = ROOT / "data" / "mock_cards" / "track_a_cases_demo.json"


def load_demo_case():
    """Charge le premier dossier fictif."""
    with DEMO_FILE.open(encoding="utf-8") as file:
        cases = json.load(file)

    return cases[0]


def test_handler_valid_request():
    """Une requête valide sans source juridique produit un refus."""

    request = load_demo_case()

    response = handle(request)

    assert response["status"] == "refus"
    assert response["refus"]["code"] == "SOURCE_MANQUANTE"
    assert response["result"] is None
    assert response["citations"] == []


def test_handler_invalid_request():
    """Une requête incomplète est refusée."""

    request = {
        "request_id": "TEST-INVALID-001"
    }

    response = handle(request)

    assert response["status"] == "refus"
    assert response["refus"]["code"] == "PARAM_INVALIDE"
    assert response["result"] is None


def test_handler_request_id():
    """Le handler conserve l'identifiant de la requête."""

    request = load_demo_case()

    response = handle(request)

    assert response["request_id"] == request["request_id"]
    assert response["case_id"] == request["case_id"]

from jsonschema import Draft202012Validator

from src.track_a_legal.handler import RESPONSE_SCHEMA, load_schema


def test_handler_response_schema():
    """La réponse du handler respecte le contrat DS4 v0."""

    request = load_demo_case()

    response = handle(request)

    schema = load_schema(RESPONSE_SCHEMA)

    validator = Draft202012Validator(schema)

    validator.validate(response)

from unittest.mock import patch


def test_handler_technical_error():
    """Une erreur interne produit une réponse sécurisée."""

    request = load_demo_case()

    with patch(
        "src.track_a_legal.handler.analyze_case",
        side_effect=RuntimeError("Erreur interne fictive")
    ):
        response = handle(request)

    assert response["status"] == "erreur"
    assert response["result"] is None
    assert response["citations"] == []
    assert response["refus"] is None

    assert response["erreur"]["type"] == "INTERNAL_ERROR"

    # Aucun détail technique interne ne doit être exposé.
    assert "Erreur interne fictive" not in str(response)

    # La réponse doit respecter le contrat JSON.
    schema = load_schema(RESPONSE_SCHEMA)
    Draft202012Validator(schema).validate(response)
def test_handler_accepts_case_without_evidence():
    """Un dossier sans preuves est accepté, sans conclusion inventée."""

    # Charger un dossier fictif valide
    request = load_demo_case()

    # Supprimer les preuves
    request["evidence"] = []

    # Supprimer les références aux preuves absentes
    for event in request["events"]:
        event["source_ids"] = []

    # Envoyer le dossier au handler DS4
    response = handle(request)

    # Vérifier la réponse
    assert response["status"] == "refus"
    assert response["refus"]["code"] == "SOURCE_MANQUANTE"
    assert response["result"] is None
    assert response["citations"] == []
def test_handler_rejects_nonexistent_evidence_reference():
    """Une reference vers une preuve inexistante ne doit pas etre acceptee."""

    # Charger un dossier fictif valide
    request = load_demo_case()

    # Ajouter une reference vers une preuve inexistante
    request["events"][0]["source_ids"] = ["E99"]

    # Envoyer le dossier au handler
    response = handle(request)

    # Le handler v0 doit signaler une erreur
    assert response["status"] == "erreur"
    assert response["erreur"]["type"] == "INTERNAL_ERROR"

    # Aucune conclusion ni citation ne doit etre inventee
    assert response["result"] is None
    assert response["citations"] == []