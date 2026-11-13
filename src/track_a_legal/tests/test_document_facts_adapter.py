"""Tests de l'adaptateur DS3 vers Document Facts."""

import copy
import json
from pathlib import Path

from src.track_a_legal.tools.document_facts_adapter import (
    extract_document_facts,
)


# Identifier la racine du dépôt.
REPO = Path(__file__).resolve().parents[3]

# Utiliser les exemples officiels DS3.
DEMO_PATH = (
    REPO / "data" / "mock_cards"
    / "document_intelligence_requests_demo.v2.json"
)


def test_extracts_base_salary_with_traceability():
    """Conserver le montant, le sujet et la citation DS3."""

    # Charger une fiche de paie fictive officielle.
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

    # Simuler une réponse live pour le test unitaire.
    # Cela ne prouve pas l'authenticité du document.
    response["mode"] = "live"
    response["computed_by"] = "document_intelligence.service"

    # Fournir explicitement le sujet du dossier.
    facts = extract_document_facts(
        response=response,
        subject_id="P1",
    )

    # Vérifier la transformation du salaire de base.
    base_salary = next(
        fact
        for fact in facts
        if fact["property"] == "base_salary"
    )

    assert base_salary == {
        "fact_id": "doc_7f3a:base_salary",
        "subject_id": "P1",
        "property": "base_salary",
        "period": "2026-03-01/2026-03-31",
        "unit": "TND",
        "value": "424.100",
        "document_id": "doc_7f3a",
        "citation_id": "c7",
    }


def test_rejects_mock_document_response():
    """Une réponse DS3 fictive ne doit produire aucun fait."""

    # Charger les exemples officiels DS3.
    examples = json.loads(
        DEMO_PATH.read_text(encoding="utf-8")
    )

    # Conserver le mode mock fourni par DS3.
    response = copy.deepcopy(
        next(
            item["response"]
            for item in examples
            if item["name"] == "01_ok_fiche_paie"
        )
    )

    # Aucun fait ne doit être produit à partir du mock.
    assert extract_document_facts(
        response=response,
        subject_id="P1",
    ) == []


def test_rejects_empty_subject_id():
    """Un sujet non identifié ne doit produire aucun fait."""

    # Charger la fiche de paie fictive.
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

    # Simuler uniquement les métadonnées live.
    # Cela ne constitue pas une preuve d'authenticité.
    response["mode"] = "live"
    response["computed_by"] = "document_intelligence.service"

    # Refuser un identifiant de sujet vide.
    assert extract_document_facts(
        response=response,
        subject_id="",
    ) == []


def test_rejects_invalid_document_periods():
    """Refuser les périodes impossibles ou incomplètes."""

    # Charger une seule fois les exemples officiels DS3.
    examples = json.loads(
        DEMO_PATH.read_text(encoding="utf-8")
    )

    original_response = next(
        item["response"]
        for item in examples
        if item["name"] == "01_ok_fiche_paie"
    )

    # Définir trois périodes invalides.
    invalid_periods = [
        ("2026-02-30", "2026-03-31"),
        ("2026-04-01", "2026-03-31"),
        (None, "2026-03-31"),
    ]

    for start, end in invalid_periods:
        # Isoler chaque scénario pour éviter les mutations.
        response = copy.deepcopy(original_response)

        # Simuler les métadonnées live pour le test.
        response["mode"] = "live"
        response["computed_by"] = "document_intelligence.service"

        # Injecter la période invalide.
        response["result"]["fields"]["period_start"]["value"] = start
        response["result"]["fields"]["period_end"]["value"] = end

        # Aucun fait ne doit être produit.
        assert extract_document_facts(
            response=response,
            subject_id="P1",
        ) == [], (start, end)


def test_rejects_salary_with_wrong_value_type():
    """Refuser un montant déclaré comme texte par DS3."""

    # Charger les exemples officiels DS3 v2.
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

    # Simuler les métadonnées live pour le test.
    # Cela ne garantit pas une provenance authentique.
    response["mode"] = "live"
    response["computed_by"] = "document_intelligence.service"

    # Conserver une valeur numérique, mais déclarer un type incorrect.
    response["result"]["fields"]["base_salary"]["value_type"] = "texte"

    # L'adaptateur ne doit pas convertir ce champ en fait monétaire.
    facts = extract_document_facts(
        response=response,
        subject_id="P1",
    )

    assert not any(
        fact["property"] == "base_salary"
        for fact in facts
    )


def test_rejects_unknown_period_citation():
    """Refuser une période sans citation documentaire valide."""

    # Charger une fiche de paie fictive officielle.
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

    # Simuler les métadonnées live uniquement pour le test.
    # Cela ne prouve pas l'authenticité du document.
    response["mode"] = "live"
    response["computed_by"] = "document_intelligence.service"

    # Introduire une référence documentaire inexistante.
    response["result"]["fields"]["period_start"][
        "citation_id"
    ] = "citation_inexistante"

    # Aucun fait ne doit utiliser cette période non sourcée.
    assert extract_document_facts(
        response=response,
        subject_id="P1",
    ) == []


def test_rejects_period_with_wrong_date_type():
    """Refuser une periode dont le type DS3 est incorrect."""

    # Charger les exemples officiels DS3.
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

    # Simuler les metadonnees live pour le test.
    # Cela ne garantit pas l'authenticite du document.
    response["mode"] = "live"
    response["computed_by"] = "document_intelligence.service"

    # Conserver une date valide mais declarer un type incorrect.
    response["result"]["fields"]["period_start"][
        "value_type"
    ] = "texte"

    # Aucun fait ne doit etre cree avec cette periode mal typee.
    assert extract_document_facts(
        response=response,
        subject_id="P1",
    ) == []


def test_rejects_salary_with_invalid_confidence():
    """Refuser un montant dont la confiance depasse 1."""

    # Charger les exemples officiels DS3.
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

    # Simuler les metadonnees live pour ce test.
    # Cela ne prouve pas la provenance reelle du document.
    response["mode"] = "live"
    response["computed_by"] = "document_intelligence.service"

    # Introduire un score impossible selon le contrat DS3.
    response["result"]["fields"]["base_salary"][
        "confidence"
    ] = 1.5

    # Extraire les faits documentaires.
    facts = extract_document_facts(
        response=response,
        subject_id="P1",
    )

    # Le salaire invalide ne doit pas devenir un fait.
    assert not any(
        fact["property"] == "base_salary"
        for fact in facts
    )


def test_salary_confidence_boundaries():
    """Verifier les bornes techniques du score de confiance."""

    # Charger l'exemple officiel de fiche de paie.
    examples = json.loads(
        DEMO_PATH.read_text(encoding="utf-8")
    )

    original = next(
        item["response"]
        for item in examples
        if item["name"] == "01_ok_fiche_paie"
    )

    # Chaque scenario indique si le montant doit etre conserve.
    scenarios = [
        (-0.1, False),
        (float("nan"), False),
        (None, False),
        (True, False),
        (0.0, True),
        (1.0, True),
    ]

    for confidence, expected in scenarios:
        # Isoler les modifications de chaque scenario.
        response = copy.deepcopy(original)

        # Simuler uniquement les metadonnees live.
        response["mode"] = "live"
        response["computed_by"] = "document_intelligence.service"

        # Modifier le score du salaire de base.
        response["result"]["fields"]["base_salary"][
            "confidence"
        ] = confidence

        # Executer l'adaptateur.
        facts = extract_document_facts(
            response=response,
            subject_id="P1",
        )

        # Verifier uniquement la presence du salaire de base.
        found = any(
            fact["property"] == "base_salary"
            for fact in facts
        )

        assert found is expected, confidence
