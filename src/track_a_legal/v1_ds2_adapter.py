"""Adaptateur contractuel DS2 vers DS4 v1.

Ce module valide les réponses legal_retrieval.v0.
Il ne produit aucune conclusion juridique.
"""

import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator


# Localiser le schéma DS2 versionné dans le dépôt.
_SCHEMA_PATH = (
    Path(__file__).resolve().parents[2]
    / "data"
    / "mock_cards"
    / "schemas"
    / "legal_retrieval_search_response.v0.schema.json"
)


def validate_ds2_response(response: Any) -> bool:
    """Valider strictement une réponse DS2 en mode réel."""

    # Refuser les réponses qui ne sont pas des objets JSON.
    if not isinstance(response, dict):
        return False

    # Refuser les réponses fictives ou non réussies.
    if response.get("mode") != "live":
        return False

    if response.get("status") != "ok":
        return False

    if response.get("contract_version") != "legal_retrieval.v0":
        return False

    # Charger le contrat officiel DS2 depuis le dépôt.
    with _SCHEMA_PATH.open(encoding="utf-8") as schema_file:
        schema = json.load(schema_file)

    # Valider la structure sans modifier la réponse.
    validator = Draft202012Validator(schema)

    return validator.is_valid(response)
