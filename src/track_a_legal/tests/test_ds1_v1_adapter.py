from copy import deepcopy

import pytest

from src.track_a_legal.v1_handler import handle_v1
from src.track_a_legal.tools.ds1_v1_adapter import (
    DS1TrackAV1Adapter,
    DS1V1ContractError,
)


@pytest.fixture
def payload():
    """Construire une enveloppe DS1 fictive cohérente."""
    request = {
        "contract_version": "track_a.v1",
        "request_id": "REQ-DS1-PYTEST-001",
        "case_id": "CASE-DS1-PYTEST-001",
        "lang": "fr",
        "parties": [],
        "events": [],
        "claims": [],
        "evidence": [],
    }

    return {
        "request_id": request["request_id"],
        "agent": "track_a_legal",
        "operation": "analyze_case",
        "read_only": True,
        "context": {
            "card_type": "case",
            "card_id": request["case_id"],
        },
        "params": {"track_a_request": request},
    }


def test_valid_request_without_mutation(payload):
    """Une analyse préliminaire valide ne modifie pas l'entrée."""
    original = deepcopy(payload)

    response = DS1TrackAV1Adapter()(payload)

    assert response["status"] == "success"
    assert response["citations"] == []
    assert response["data"]["result"]["legal_conclusion"] is None
    assert payload == original


@pytest.mark.parametrize(
    "scenario",
    [
        "wrong_agent",
        "wrong_operation",
        "write_enabled",
        "wrong_card_type",
        "request_id_mismatch",
        "case_id_mismatch",
        "wrong_version",
        "missing_request",
    ],
)
def test_invalid_requests_rejected_before_handler(payload, scenario):
    """Rejeter les requêtes invalides avant toute analyse."""
    calls = []

    def fake_handler(request):
        calls.append(request)
        return {}

    changes = {
        "wrong_agent": lambda p: p.update(agent="other"),
        "wrong_operation": lambda p: p.update(operation="write"),
        "write_enabled": lambda p: p.update(read_only=False),
        "wrong_card_type": lambda p: p["context"].update(card_type="company"),
        "request_id_mismatch": lambda p: p["params"]["track_a_request"].update(
            request_id="OTHER"
        ),
        "case_id_mismatch": lambda p: p["params"]["track_a_request"].update(
            case_id="OTHER"
        ),
        "wrong_version": lambda p: p["params"]["track_a_request"].update(
            contract_version="track_a.v0"
        ),
        "missing_request": lambda p: p["params"].pop("track_a_request"),
    }

    changes[scenario](payload)

    with pytest.raises(DS1V1ContractError):
        DS1TrackAV1Adapter(handler=fake_handler)(payload)

    assert calls == []


@pytest.mark.parametrize(
    "scenario",
    [
        "missing_refusal",
        "missing_error",
        "missing_computed_by",
        "malformed_citations",
        "unauthorized_conclusion",
    ],
)
def test_invalid_responses_rejected(payload, scenario):
    """Valider strictement les réponses DS4 avec le schéma officiel."""
    valid = handle_v1(deepcopy(payload["params"]["track_a_request"]))
    assert valid["status"] == "ok"

    response = deepcopy(valid)

    if scenario == "missing_refusal":
        response.update(status="refus", result=None, refus=None)
    elif scenario == "missing_error":
        response.update(status="erreur", result=None, erreur=None)
    elif scenario == "missing_computed_by":
        response["computed_by"] = None
    elif scenario == "malformed_citations":
        response["citations"] = ["invalid"]
    elif scenario == "unauthorized_conclusion":
        response["result"]["legal_conclusion"] = "Validé"

    with pytest.raises(DS1V1ContractError):
        DS1TrackAV1Adapter(
            handler=lambda request: deepcopy(response)
        )(payload)


def test_valid_refusal(payload):
    """Un refus DS4 conforme est transmis comme refus DS1."""
    response = handle_v1({
        **deepcopy(payload["params"]["track_a_request"]),
        "lang": "invalid",
    })

    assert response["status"] == "refus"

    output = DS1TrackAV1Adapter(
        handler=lambda request: deepcopy(response)
    )(payload)

    assert output["status"] == "refused"
    assert output["data"] is None
    assert output["citations"] == []


def test_valid_internal_error(payload):
    """Une erreur DS4 conforme est transmise comme erreur DS1."""
    response = handle_v1(
        deepcopy(payload["params"]["track_a_request"])
    )

    response["status"] = "erreur"
    response["result"] = None
    response["refus"] = None
    response["citations"] = []
    response["erreur"] = {
        "type": "INTERNAL_ERROR",
        "message_fr": "Erreur interne.",
        "message_ar": "خطأ داخلي.",
    }
    response.pop("case_id", None)

    output = DS1TrackAV1Adapter(
        handler=lambda request: deepcopy(response)
    )(payload)

    assert output["status"] == "error"
    assert output["data"] is None
    assert output["citations"] == []


def test_supported_analysis_requires_citations(payload):
    """Le statut supported exige une citation conforme."""
    response = handle_v1(
        deepcopy(payload["params"]["track_a_request"])
    )

    response["result"]["analysis_status"] = "supported"
    response["citations"] = []

    with pytest.raises(DS1V1ContractError):
        DS1TrackAV1Adapter(
            handler=lambda request: deepcopy(response)
        )(payload)
def test_invalid_language_rejected_before_handler(payload):
    """Une langue invalide doit être refusée avant le handler DS4."""

    calls = []

    def fake_handler(request):
        calls.append(request)
        return {}

    # Injecter une langue non autorisée.
    payload["params"]["track_a_request"]["lang"] = "invalid"

    # Vérifier le refus par l'adaptateur.
    with pytest.raises(DS1V1ContractError):
        DS1TrackAV1Adapter(handler=fake_handler)(payload)

    # Le handler ne doit jamais être appelé.
    assert calls == []