"""Tests de sécurité des citations des tableaux DS3."""

import copy
import json
from pathlib import Path

from jsonschema import Draft202012Validator

from src.track_a_legal.tools.document_source_validation import (
    is_usable_document_response,
)


# Identifier la racine du dépôt.
REPO = Path(__file__).resolve().parents[3]

# Localiser les ressources officielles DS3 v2.
DEMO_PATH = (
    REPO / "data" / "mock_cards"
    / "document_intelligence_requests_demo.v2.json"
)

SCHEMA_PATH = (
    REPO / "data" / "mock_cards" / "schemas"
    / "document_intelligence_response.v2.schema.json"
)


def test_rejects_unknown_table_citation():
    """Refuser un tableau dont la citation est inexistante."""

    # Charger une réponse fictive officielle.
    examples = json.loads(
        DEMO_PATH.read_text(encoding="utf-8")
    )

    response = copy.deepcopy(
        next(
            item["response"]
            for item in examples
            if item["name"] == "01_ok_fiche_paie"
        )
    )

    # Simuler les métadonnées live pour tester DS4.
    # Cette réponse ne constitue pas une preuve réelle.
    response["mode"] = "live"
    response["computed_by"] = "document_intelligence.service"

    # Construire un tableau respectant ExtractedTable.
    # TableCell ne possède pas de citation individuelle.
    response["result"]["tables"] = [
        {
            "table_id": "table_test_001",
            "title": "Tableau fictif",
            "citation_id": "citation_inexistante",
            "n_rows": 1,
            "n_cols": 1,
            "cells": [
                {
                    "row": 0,
                    "col": 0,
                    "value": "100.000",
                    "confidence": 0.95,
                }
            ],
        }
    ]

    # Vérifier que la réponse reste conforme au schéma.
    schema = json.loads(
        SCHEMA_PATH.read_text(encoding="utf-8")
    )
    validator = Draft202012Validator(schema)

    assert validator.is_valid(response), (
        "La fixture doit respecter le schéma DS3 v2."
    )

    # DS4 doit rejeter un tableau sans citation existante.
    assert is_usable_document_response(response) is False
