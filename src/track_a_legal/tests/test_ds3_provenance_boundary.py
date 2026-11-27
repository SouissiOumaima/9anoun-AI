"""Tests de caractérisation de la provenance documentaire DS3."""

import copy
import json
from pathlib import Path

from src.track_a_legal.tools.document_source_validation import (
    is_usable_document_response,
)


# Identifier la racine du dépôt.
REPO = Path(__file__).resolve().parents[3]

# Utiliser les exemples officiels locaux.
DEMO_PATH = (
    REPO / "data" / "mock_cards"
    / "document_intelligence_requests_demo.v2.json"
)


def test_declared_live_metadata_does_not_prove_authenticity():
    """Documenter la limite actuelle du contrôle de provenance."""

    # Charger les réponses fictives officielles.
    examples = json.loads(
        DEMO_PATH.read_text(encoding="utf-8")
    )

    # Sélectionner une réponse mock complète.
    original = next(
        item["response"]
        for item in examples
        if item["name"] == "01_ok_fiche_paie"
    )

    # Ne jamais modifier la fixture officielle.
    response = copy.deepcopy(original)

    # Confirmer que DS4 refuse la réponse fictive initiale.
    assert is_usable_document_response(response) is False

    # Simuler des métadonnées live sans exécuter le service DS3.
    response["mode"] = "live"
    response["computed_by"] = "document_intelligence.service"

    # Caractériser le comportement actuel.
    # Ce résultat ne prouve PAS l'authenticité du document.
    assert is_usable_document_response(response) is True
