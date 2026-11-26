"""Tests d'integration DS3 vers Fact Comparison."""

import copy
import json
from pathlib import Path

from src.track_a_legal.tools.document_facts_adapter import (
    extract_document_facts,
)
from src.track_a_legal.tools.fact_comparison import (
    compare_document_facts,
)


# Localiser les exemples officiels DS3 v2.
REPO = Path(__file__).resolve().parents[3]
DEMO_PATH = (
    REPO / "data" / "mock_cards"
    / "document_intelligence_requests_demo.v2.json"
)


def test_detects_salary_divergence_between_documents():
    """Detecter une divergence entre deux documents fictifs."""

    # Charger la fiche de paie de demonstration.
    examples = json.loads(
        DEMO_PATH.read_text(encoding="utf-8")
    )

    original = next(
        item["response"]
        for item in examples
        if item["name"] == "01_ok_fiche_paie"
    )

    # Construire deux documents independants.
    first = copy.deepcopy(original)
    second = copy.deepcopy(original)

    # Simuler les metadonnees live pour ce test.
    # Ces modifications ne prouvent aucune authenticite.
    for response in (first, second):
        response["mode"] = "live"
        response["computed_by"] = "document_intelligence.service"

    # Donner un identifiant distinct au second document.
    second["document_id"] = "doc_test_002"

    # Mettre a jour les references documentaires des citations.
    for citation in second["citations"]:
        citation["document_id"] = "doc_test_002"

    # Modifier uniquement le salaire de base du second document.
    second["result"]["fields"]["base_salary"][
        "value"
    ] = "500.000"

    # Extraire les faits pour le meme sujet explicite.
    facts = (
        extract_document_facts(first, subject_id="P1")
        + extract_document_facts(second, subject_id="P1")
    )

    # Comparer les faits documentaires.
    divergences = compare_document_facts(facts)

    # Verifier la divergence du salaire de base.
    assert any(
        item["type"] == "potential_divergence"
        and item["fact_ids"] == [
            "doc_7f3a:base_salary",
            "doc_test_002:base_salary",
        ]
        and item["citation_ids"] == ["c7", "c7"]
        for item in divergences
    )


def test_no_false_salary_divergence():
    """Eviter les divergences entre faits non comparables."""

    # Charger l'exemple officiel DS3.
    examples = json.loads(
        DEMO_PATH.read_text(encoding="utf-8")
    )

    original = next(
        item["response"]
        for item in examples
        if item["name"] == "01_ok_fiche_paie"
    )

    # Construire deux documents fictifs independants.
    first = copy.deepcopy(original)
    second = copy.deepcopy(original)

    for response in (first, second):
        # Simuler les metadonnees live pour le test uniquement.
        response["mode"] = "live"
        response["computed_by"] = "document_intelligence.service"

    # Associer le second document a un identifiant distinct.
    second["document_id"] = "doc_test_002"

    for citation in second["citations"]:
        citation["document_id"] = "doc_test_002"

    # Scenario 1 : salaires identiques, meme personne et periode.
    facts = (
        extract_document_facts(first, subject_id="P1")
        + extract_document_facts(second, subject_id="P1")
    )

    assert compare_document_facts(facts) == []

    # Scenario 2 : salaires differents, personnes differentes.
    second["result"]["fields"]["base_salary"]["value"] = "500.000"

    facts = (
        extract_document_facts(first, subject_id="P1")
        + extract_document_facts(second, subject_id="P2")
    )

    assert compare_document_facts(facts) == []

    # Scenario 3 : salaires differents, periodes differentes.
    second["result"]["fields"]["period_start"]["value"] = "2026-04-01"
    second["result"]["fields"]["period_end"]["value"] = "2026-04-30"

    facts = (
        extract_document_facts(first, subject_id="P1")
        + extract_document_facts(second, subject_id="P1")
    )

    assert compare_document_facts(facts) == []
