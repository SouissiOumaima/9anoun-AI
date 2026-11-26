"""Tests de raccordement DS2 vers les cinq piliers DS4."""

from copy import deepcopy

from src.track_a_legal.tools.ds2_to_ds4_adapter import adapt_ds2_to_ds4
from src.track_a_legal.v1_five_pillars import build_five_pillars


def test_ds2_sources_feed_five_pillars_without_legal_conclusion(
    valid_ds2_response,
):
    """Associer chaque article DS2 ? son ?valuation temporelle."""

    # Pr?parer une r?ponse DS2 ind?pendante.
    response = deepcopy(valid_ds2_response)
    adapted = adapt_ds2_to_ds4(response)

    # Construire les donn?es internes destin?es aux cinq piliers.
    # Cette fonction sera impl?ment?e apr?s l'?chec TDD.
    from src.track_a_legal.tools.ds2_to_ds4_adapter import (
        build_ds2_pillar_assessments,
    )

    assessments = build_ds2_pillar_assessments(adapted)

    analysis = {
        "case_id": "CASE-TEST-001",
        "claim_traceability": [],
        **assessments,
    }

    # V?rifier la correspondance entre article et contr?le temporel.
    result = build_five_pillars(analysis)
    rules = result["pillars"]["regles"]

    assert len(rules) == 1
    assert rules[0]["source_id"] == "TEST-ART-1-v1"
    assert rules[0]["eligible_for_legal_conclusion"] is False
    assert rules[0]["temporal_eligibility"] == "not_confirmed"

    # Interdire toute conclusion juridique automatique.
    assert result["legal_conclusion"] is None
    assert result["pillars"]["interpretation"][0]["legal_conclusion"] is None


def test_abrogated_article_remains_unverified(valid_ds2_response):
    """Un article abrog? ne doit pas autoriser une conclusion."""

    # Simuler un article DS2 abrog?.
    response = deepcopy(valid_ds2_response)
    response["results"][0]["status"] = "abroge"
    response["results"][0]["applicable_at_reference_date"] = False

    # Pr?parer les ?valuations internes DS4.
    from src.track_a_legal.tools.ds2_to_ds4_adapter import (
        build_ds2_pillar_assessments,
    )

    adapted = adapt_ds2_to_ds4(response)
    assessments = build_ds2_pillar_assessments(adapted)

    analysis = {
        "case_id": "CASE-ABROGATED-001",
        "claim_traceability": [],
        **assessments,
    }

    # Construire les cinq piliers.
    result = build_five_pillars(analysis)
    rule = result["pillars"]["regles"][0]

    # V?rifier le blocage de la conclusion juridique.
    assert rule["validity_status_reported"] == "abroge"
    assert rule["temporal_eligibility"] == "not_confirmed"
    assert rule["eligible_for_legal_conclusion"] is False
    assert result["legal_conclusion"] is None
