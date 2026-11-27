"""Test d'intégration du Mapper DS1 avec l'adaptateur DS4 v1."""

from copy import deepcopy

from src.track_a_legal.tests.test_ds1_case_card_v1_mapper import (
    build_case_card,
)
from src.track_a_legal.tools.ds1_case_card_v1_mapper import (
    map_case_card_to_track_a_v1,
)
from src.track_a_legal.tools.ds1_v1_adapter import DS1TrackAV1Adapter


def test_case_card_mapper_adapter_handler_v1():
    """Valider le parcours DS1 Case Card -> Mapper -> Adapter -> Handler."""

    # Préparer une Case Card fictive et conserver son état initial.
    card = build_case_card()
    original = deepcopy(card)

    # Convertir la carte DS1 en requête DS4 v1.
    request = map_case_card_to_track_a_v1(
        card,
        request_id="REQ-DS1-DS4-INTEGRATION-001",
        language="fr",
    )

    # Construire l'enveloppe attendue par l'adaptateur DS1.
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

    # Exécuter le pipeline DS4 v1 via l'adaptateur.
    response = DS1TrackAV1Adapter()(payload)

    # Vérifier le contrat de réponse normalisé.
    assert response["status"] == "success"
    assert response["error"] is None
    assert response["data"]["computed_by"] == "DS4_Lawyer_Track_v1"

    result = response["data"]["result"]

    # Vérifier les données et la traçabilité des preuves.
    assert result["case_id"] == card["card_id"]
    assert result["analysis_status"] == "preparatory"
    assert len(result["evidence_mapping"]) == 1

    # Aucune conclusion juridique automatique ne doit être inventée.
    assert result["legal_conclusion"] is None
    assert response["citations"] == []

    # Garantir que la Case Card originale reste inchangée.
    assert card == original
