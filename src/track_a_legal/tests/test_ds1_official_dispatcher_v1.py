"""Test d'intégration du dispatcher officiel DS1 avec DS4 v1."""

import json
from copy import deepcopy
from pathlib import Path

import importlib.util
import pytest

# Ignorer ce test uniquement lorsque le dispatcher DS1 est absent.
# Si DS1 est disponible, les erreurs d'intégration restent visibles.
if importlib.util.find_spec("src.orchestrator.hybrid_dispatcher") is None:
    pytest.skip(
        "Dispatcher officiel DS1 absent de cette branche.",
        allow_module_level=True,
    )

from src.orchestrator.hybrid_dispatcher import HybridSpecialistDispatcher
from src.orchestrator.track_a_adapter import TrackAAdapter
from src.track_a_legal.tools.ds1_case_card_v1_mapper import (
    map_case_card_to_track_a_v1,
)
from src.track_a_legal.tools.ds1_version_router import (
    DS1TrackAVersionRouter,
)


def test_official_ds1_case_card_to_ds4_v1_e2e():
    """Valider le parcours complet avec la Case Card officielle DS1."""

    # Charger les données de démonstration officielles DS1.
    root = Path(__file__).resolve().parents[3]
    cards_path = root / "data/mock_cards/orchestrator_cards_demo.json"
    cards = json.loads(cards_path.read_text(encoding="utf-8"))

    # Sélectionner le dossier juridique fictif.
    card = next(
        c for c in cards
        if c.get("card_id") == "case-demo-001"
        and c.get("card_type") == "case"
    )
    original = deepcopy(card)

    # Transformer la Case Card en requête Track A v1.
    request = map_case_card_to_track_a_v1(
        card,
        request_id="REQ-DS1-DS4-OFFICIAL-E2E-001",
        language="fr",
    )

    # Construire l'enveloppe officielle DS1.
    payload = {
        "request_id": request["request_id"],
        "agent": "track_a_legal",
        "operation": "analyze_case",
        "read_only": True,
        "context": {
            "card_type": "case",
            "card_id": card["card_id"],
        },
        "params": {"track_a_request": request},
    }

    # Injecter le Router DS4 dans le dispatcher officiel DS1.
    router = DS1TrackAVersionRouter(v0_adapter=TrackAAdapter())
    dispatcher = HybridSpecialistDispatcher(track_a_adapter=router)

    # Exécuter le parcours complet.
    response = dispatcher(payload)

    # Vérifier le contrat normalisé et les garanties DS4.
    assert response["status"] == "success"
    assert response["error"] is None
    assert response["data"]["computed_by"] == "DS4_Lawyer_Track_v1"

    result = response["data"]["result"]
    assert result["case_id"] == card["card_id"]
    assert result["analysis_status"] == "preparatory"

    # Garantir que la Case Card source n'a pas été modifiée.
    assert card == original
