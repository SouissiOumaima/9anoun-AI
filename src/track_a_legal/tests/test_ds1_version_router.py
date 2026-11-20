
"""Tests unitaires du routeur DS1 Track A v0/v1."""

from copy import deepcopy

import pytest

from src.track_a_legal.tools.ds1_version_router import (
    DS1TrackAVersionRouter,
    DS1V1ContractError,
)


def make_payload(version="track_a.v1"):
    """Construire une enveloppe DS1 minimale pour tester le routage."""
    return {
        "agent": "track_a_legal",
        "operation": "analyze_case",
        "params": {
            "track_a_request": {
                "contract_version": version,
                "request_id": "REQ-TEST-001",
                "case_id": "CASE-TEST-001",
            }
        },
    }


@pytest.fixture
def router_and_calls():
    """Injecter deux adaptateurs fictifs pour isoler le routeur."""
    calls = []

    def v0_adapter(payload):
        # Enregistrer l'appel sans modifier la requête.
        calls.append("v0")
        return {"selected": "v0"}

    def v1_adapter(payload):
        calls.append("v1")
        return {"selected": "v1"}

    router = DS1TrackAVersionRouter(
        v0_adapter=v0_adapter,
        v1_adapter=v1_adapter,
    )
    return router, calls


@pytest.mark.parametrize(
    ("version", "expected"),
    [
        ("track_a.v0", "v0"),
        ("track_a.v1", "v1"),
    ],
)
def test_routes_to_correct_adapter(router_and_calls, version, expected):
    """Chaque version doit appeler exclusivement son adaptateur."""
    router, calls = router_and_calls

    result = router(make_payload(version))

    assert result == {"selected": expected}
    assert calls == [expected]


def test_unknown_version_rejected(router_and_calls):
    """Une version inconnue ne doit déclencher aucun adaptateur."""
    router, calls = router_and_calls

    with pytest.raises(DS1V1ContractError):
        router(make_payload("track_a.v2"))

    assert calls == []


@pytest.mark.parametrize(
    "change",
    [
        lambda p: p.update(agent="unknown"),
        lambda p: p.update(operation="delete_case"),
        lambda p: p.update(params=None),
        lambda p: p["params"].update(track_a_request=None),
        lambda p: p["params"]["track_a_request"].pop("contract_version"),
    ],
)
def test_invalid_envelopes_rejected(router_and_calls, change):
    """Les enveloppes invalides doivent être rejetées avant le routage."""
    router, calls = router_and_calls
    payload = make_payload()
    change(payload)

    with pytest.raises(DS1V1ContractError):
        router(payload)

    assert calls == []


def test_non_mapping_payload_rejected(router_and_calls):
    """Le routeur doit refuser une entrée qui n'est pas un mapping."""
    router, calls = router_and_calls

    with pytest.raises(DS1V1ContractError):
        router(None)

    assert calls == []


def test_router_does_not_mutate_payload(router_and_calls):
    """Le routage ne doit pas modifier la requête d'origine."""
    router, _ = router_and_calls
    payload = make_payload()
    original = deepcopy(payload)

    router(payload)

    assert payload == original
