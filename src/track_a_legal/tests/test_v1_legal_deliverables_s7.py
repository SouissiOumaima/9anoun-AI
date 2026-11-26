"""Regression tests for preliminary S7 legal deliverables."""

import copy
import json
from pathlib import Path

import pytest

from src.track_a_legal.v1_case_analysis import analyze_case_v1
from src.track_a_legal.v1_five_pillars import build_five_pillars
from src.track_a_legal.v1_legal_deliverables_s7 import (
    generate_legal_deliverables_s7,
)


# Charger les dossiers fictifs de reference.
CASES = json.loads(
    Path("data/mock_cards/track_a_case_cards_v1.json")
    .read_text(encoding="utf-8-sig")
)

SECTION_MAPPING = {
    "S7-01": "faits",
    "S7-02": "declarations",
    "S7-03": "regles",
    "S7-04": "interpretation",
    "S7-05": "strategie",
}


@pytest.mark.parametrize("case_data", CASES, ids=lambda c: c["case_id"])
def test_s7_structure_traceability_and_safety(case_data):
    """Verifier les cinq sections et les limitations juridiques."""

    analysis = analyze_case_v1(case_data)
    original_analysis = copy.deepcopy(analysis)

    pillars = build_five_pillars(analysis)
    document = generate_legal_deliverables_s7(analysis)

    # Le generateur ne doit pas modifier l'analyse originale.
    assert analysis == original_analysis

    # Verifier la structure et la conservation exacte des donnees.
    assert document["case_id"] == case_data["case_id"]
    assert len(document["sections"]) == 5

    for section in document["sections"]:
        source = SECTION_MAPPING[section["section_id"]]
        assert section["content"] == pillars["pillars"][source]

    # Aucune validation juridique ne peut etre inventee.
    assert document["document_status"] == "preparatory"
    assert document["lawyer_validated"] is False
    assert document["legal_conclusion"] is None

    for section in document["sections"][3:]:
        for item in section["content"]:
            assert item["legal_conclusion"] is None


def test_s7_rejects_invalid_analysis():
    """Refuser les donnees d'analyse invalides."""

    with pytest.raises(ValueError):
        generate_legal_deliverables_s7(None)


def test_s7_rejects_missing_claim_traceability():
    """Refuser une analyse privee de tracabilite."""

    with pytest.raises(ValueError):
        generate_legal_deliverables_s7({"case_id": "CASE-INVALID"})


@pytest.mark.parametrize("case_data", CASES, ids=lambda c: c["case_id"])
def test_s7_no_nested_legal_conclusions(case_data):
    """Interdire les conclusions juridiques non nulles dans les livrables."""

    # Construire un livrable a partir du dossier fictif.
    analysis = analyze_case_v1(case_data)
    document = generate_legal_deliverables_s7(analysis)

    def inspect(value):
        # Parcourir tous les dictionnaires et listes imbriques.
        if isinstance(value, dict):
            for key, item in value.items():
                if key == "legal_conclusion":
                    assert item is None
                inspect(item)

        elif isinstance(value, list):
            for item in value:
                inspect(item)

    # Verifier l'ensemble du document, pas uniquement sa racine.
    inspect(document)

    # Aucune validation par avocat ne doit etre attribuee.
    assert document["lawyer_validated"] is False
