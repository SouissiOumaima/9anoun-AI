# Tests conservés côté DS4 pour protéger les attentes du consommateur envers DS3 v2.
﻿"""Tests de conformité des réponses de démonstration DS3 v2."""

import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator


# Identifier la racine du dépôt.
REPO = Path(__file__).resolve().parents[3]

# Chemin du schéma officiel DS3 v2.
SCHEMA_PATH = (
    REPO
    / "data"
    / "mock_cards"
    / "schemas"
    / "document_intelligence_response.v2.schema.json"
)

# Chemin des exemples officiels DS3 v2.
DEMO_PATH = (
    REPO
    / "data"
    / "mock_cards"
    / "document_intelligence_requests_demo.v2.json"
)


def load_ds3_examples():
    """Charger les exemples depuis le fichier local versionné."""

    return json.loads(
        DEMO_PATH.read_text(encoding="utf-8")
    )


def test_ds3_v2_schema_is_valid():
    """Vérifier que le schéma officiel est bien formé."""

    schema = json.loads(
        SCHEMA_PATH.read_text(encoding="utf-8")
    )

    Draft202012Validator.check_schema(schema)


@pytest.mark.parametrize(
    "example",
    load_ds3_examples(),
    ids=lambda example: example["name"],
)
def test_ds3_v2_demo_response_matches_schema(example):
    """Vérifier chaque réponse avec le schéma officiel DS3 v2."""

    schema = json.loads(
        SCHEMA_PATH.read_text(encoding="utf-8")
    )

    validator = Draft202012Validator(schema)

    # Échouer si la réponse ne respecte pas le contrat.
    validator.validate(example["response"])
