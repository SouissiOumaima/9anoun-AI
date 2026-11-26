"""Tests de comparaison factuelle interne DS4."""

from src.track_a_legal.tools.fact_comparison import (
    compare_document_facts,
)


def test_different_periods_are_not_divergent() -> None:
    """Des montants differents sur deux periodes ne sont pas incompatibles."""

    # Utiliser des donnees fictives et explicitement sourcees.
    facts = [
        {
            "fact_id": "F1",
            "subject_id": "P1",
            "property": "monthly_salary",
            "unit": "TND",
            "period": "2026-01",
            "value": "1200.000",
            "document_id": "DOC-001",
            "citation_id": "CIT-001",
        },
        {
            "fact_id": "F2",
            "subject_id": "P1",
            "property": "monthly_salary",
            "unit": "TND",
            "period": "2026-02",
            "value": "1500.000",
            "document_id": "DOC-002",
            "citation_id": "CIT-002",
        },
    ]

    # Comparer uniquement les faits fournis.
    result = compare_document_facts(facts)

    # Les periodes distinctes ne constituent pas une divergence.
    assert result == []


def test_same_context_different_values_are_flagged() -> None:
    """Signaler une divergence potentielle avec ses references."""

    # Deux valeurs fictives concernent exactement le meme contexte.
    facts = [
        {
            "fact_id": "F1",
            "subject_id": "P1",
            "property": "monthly_salary",
            "period": "2026-01",
            "unit": "TND",
            "value": "1200.000",
            "document_id": "DOC-001",
            "citation_id": "CIT-001",
        },
        {
            "fact_id": "F2",
            "subject_id": "P1",
            "property": "monthly_salary",
            "period": "2026-01",
            "unit": "TND",
            "value": "1500.000",
            "document_id": "DOC-002",
            "citation_id": "CIT-002",
        },
    ]

    # Comparer les faits sans conclure sur leur validite juridique.
    result = compare_document_facts(facts)

    # Exiger une divergence potentielle explicitement traceable.
    assert result == [
        {
            "type": "potential_divergence",
            "fact_ids": ["F1", "F2"],
            "document_ids": ["DOC-001", "DOC-002"],
            "citation_ids": ["CIT-001", "CIT-002"],
        }
    ]


def test_equivalent_numeric_values_are_not_divergent() -> None:
    """Des montants numeriquement egaux ne sont pas divergents."""

    # Deux documents fictifs indiquent le meme montant
    # avec des representations numeriques differentes.
    facts = [
        {
            "fact_id": "F1",
            "subject_id": "P1",
            "property": "monthly_salary",
            "period": "2026-01",
            "unit": "TND",
            "value": "1200.000",
            "document_id": "DOC-001",
            "citation_id": "CIT-001",
        },
        {
            "fact_id": "F2",
            "subject_id": "P1",
            "property": "monthly_salary",
            "period": "2026-01",
            "unit": "TND",
            "value": "1200.00",
            "document_id": "DOC-002",
            "citation_id": "CIT-002",
        },
    ]

    # Executer la comparaison factuelle.
    result = compare_document_facts(facts)

    # Les deux valeurs representent le meme montant.
    # Aucune divergence potentielle ne doit etre signalee.
    assert result == []


def test_invalid_numeric_values_are_ignored() -> None:
    """Les valeurs invalides ne doivent pas produire de divergence."""

    # Tester plusieurs valeurs qui ne constituent pas
    # des montants numeriques exploitables.
    invalid_values = ["NaN", "Infinity", "abc", None, ""]

    for invalid_value in invalid_values:

        # Construire deux faits comparables sur le contexte,
        # mais dont l'un contient une valeur invalide.
        facts = [
            {
                "fact_id": "F1",
                "subject_id": "P1",
                "property": "monthly_salary",
                "period": "2026-01",
                "unit": "TND",
                "value": "1200.000",
                "document_id": "DOC-001",
                "citation_id": "CIT-001",
            },
            {
                "fact_id": "F2",
                "subject_id": "P1",
                "property": "monthly_salary",
                "period": "2026-01",
                "unit": "TND",
                "value": invalid_value,
                "document_id": "DOC-002",
                "citation_id": "CIT-002",
            },
        ]

        # Aucune valeur invalide ne doit produire
        # de signalement de divergence.
        assert compare_document_facts(facts) == []


def test_fact_comparison_does_not_modify_inputs() -> None:
    """La comparaison doit conserver les faits originaux."""

    from copy import deepcopy

    # Construire deux faits fictifs comparables.
    facts = [
        {
            "fact_id": "F1",
            "subject_id": "P1",
            "property": "monthly_salary",
            "period": "2026-01",
            "unit": "TND",
            "value": "1200.000",
            "document_id": "DOC-001",
            "citation_id": "CIT-001",
        },
        {
            "fact_id": "F2",
            "subject_id": "P1",
            "property": "monthly_salary",
            "period": "2026-01",
            "unit": "TND",
            "value": "1500.000",
            "document_id": "DOC-002",
            "citation_id": "CIT-002",
        },
    ]

    # Sauvegarder une copie independante des donnees.
    original_facts = deepcopy(facts)

    # Executer la comparaison.
    result = compare_document_facts(facts)

    # Verifier qu'une divergence potentielle est detectee.
    assert len(result) == 1
    assert result[0]["type"] == "potential_divergence"

    # Verifier que les faits originaux restent intacts.
    assert facts == original_facts


def test_different_contexts_are_not_divergent() -> None:
    """Des faits de contextes differents ne sont pas divergents."""

    # Tester separement chaque dimension du contexte.
    different_contexts = [
        ("subject_id", "P2"),
        ("property", "annual_bonus"),
        ("unit", "EUR"),
    ]

    for field, different_value in different_contexts:

        # Premier fait : salaire mensuel fictif.
        first = {
            "fact_id": "F1",
            "subject_id": "P1",
            "property": "monthly_salary",
            "period": "2026-01",
            "unit": "TND",
            "value": "1200.000",
            "document_id": "DOC-001",
            "citation_id": "CIT-001",
        }

        # Second fait : montant different.
        second = {
            "fact_id": "F2",
            "subject_id": "P1",
            "property": "monthly_salary",
            "period": "2026-01",
            "unit": "TND",
            "value": "1500.000",
            "document_id": "DOC-002",
            "citation_id": "CIT-002",
        }

        # Modifier une seule dimension du contexte.
        second[field] = different_value

        # Les deux faits ne sont plus directement comparables.
        assert compare_document_facts([first, second]) == [], field


def test_fact_comparison_preserves_document_traceability() -> None:
    """Les divergences conservent les references des faits et documents."""

    from copy import deepcopy

    # Construire deux faits fictifs du meme contexte.
    first = {
        "fact_id": "F1",
        "subject_id": "P1",
        "property": "monthly_salary",
        "period": "2026-01",
        "unit": "TND",
        "value": "1200.000",
        "document_id": "DOC-001",
        "citation_id": "CIT-001",
    }

    second = {
        "fact_id": "F2",
        "subject_id": "P1",
        "property": "monthly_salary",
        "period": "2026-01",
        "unit": "TND",
        "value": "1500.000",
        "document_id": "DOC-002",
        "citation_id": "CIT-002",
    }

    # Cas 1 : deux faits du meme document.
    same_document = deepcopy(second)
    same_document["document_id"] = "DOC-001"

    assert compare_document_facts([first, same_document]) == []

    # Cas 2 : deux faits portant le meme identifiant.
    same_fact_id = deepcopy(second)
    same_fact_id["fact_id"] = "F1"

    assert compare_document_facts([first, same_fact_id]) == []

    # Cas 3 : divergence entre deux documents distincts.
    result = compare_document_facts([first, second])

    # Verifier la structure et les references exactes.
    assert result == [
        {
            "type": "potential_divergence",
            "fact_ids": ["F1", "F2"],
            "document_ids": ["DOC-001", "DOC-002"],
            "citation_ids": ["CIT-001", "CIT-002"],
        }
    ]
