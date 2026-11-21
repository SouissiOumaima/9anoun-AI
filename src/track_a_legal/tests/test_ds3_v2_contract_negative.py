"""Tests négatifs de conformité du contrat DS3 v2."""

import copy
import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator


# Identifier la racine du dépôt.
REPO = Path(__file__).resolve().parents[3]

# Charger le schéma officiel.
SCHEMA_PATH = (
    REPO / "data" / "mock_cards" / "schemas"
    / "document_intelligence_response.v2.schema.json"
)

# Charger les exemples officiels.
DEMO_PATH = (
    REPO / "data" / "mock_cards"
    / "document_intelligence_requests_demo.v2.json"
)


@pytest.fixture
def validator():
    """Construire le validateur JSON Schema DS3 v2."""

    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    return Draft202012Validator(schema)


@pytest.fixture
def valid_response():
    """Copier une réponse officielle valide pour chaque test."""

    examples = json.loads(DEMO_PATH.read_text(encoding="utf-8"))

    # Sélectionner la fiche de paie complète.
    response = next(
        item["response"]
        for item in examples
        if item["name"] == "01_ok_fiche_paie"
    )

    # Éviter toute modification des données originales.
    return copy.deepcopy(response)


def test_rejects_wrong_contract_version(validator, valid_response):
    """Rejeter une version différente de ds3.v2."""

    valid_response["contract_version"] = "ds3.v1"

    assert not validator.is_valid(valid_response)


def test_rejects_missing_request_id(validator, valid_response):
    """Rejeter une réponse sans champ obligatoire request_id."""

    del valid_response["request_id"]

    assert not validator.is_valid(valid_response)


def test_rejects_confidence_above_one(validator, valid_response):
    """Rejeter une confiance documentaire hors intervalle."""

    valid_response["result"]["fields"]["employee_name"]["confidence"] = 1.5

    assert not validator.is_valid(valid_response)
