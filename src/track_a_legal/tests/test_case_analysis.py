"""
Tests du Case Analysis Agent de DS4.

Les données utilisées ici sont entièrement fictives.
"""

from src.track_a_legal.tools.case_analysis import analyze_case


def create_fake_case() -> dict:
    """
    Crée un petit dossier juridique fictif pour les tests.

    Aucun individu ni aucune entreprise réelle n'est utilisé.
    """

    return {
        "contract_version": "track_a.v0",
        "request_id": "REQ-TEST-001",
        "case_id": "CASE-TEST-001",
        "lang": "fr",

        "parties": [
            {
                "party_id": "P1",
                "name": "Salarié Fictif",
                "role": "employee",
            },
            {
                "party_id": "P2",
                "name": "Entreprise Fictive",
                "role": "employer",
            },
        ],

        # Volontairement dans le mauvais ordre
        # afin de tester la timeline.
        "events": [
            {
                "event_id": "EV2",
                "date": "2026-09-10",
                "description": "Notification fictive du licenciement.",
                "source_ids": ["E2"],
            },
            {
                "event_id": "EV1",
                "date": "2024-01-01",
                "description": "Début fictif du contrat.",
                "source_ids": ["E1"],
            },
        ],

        "claims": [
            {
                "claim_id": "C1",
                "party_id": "P1",
                "text": "Le salarié affirme ne pas avoir reçu de préavis.",
            }
        ],

        "evidence": [
            {
                "evidence_id": "E1",
                "type": "contract",
                "description": "Contrat fictif.",
                "source": "mock://contract/E1",
            },
            {
                "evidence_id": "E2",
                "type": "termination_letter",
                "description": "Lettre fictive de licenciement.",
                "source": "mock://letter/E2",
            },
        ],
    }


def test_analyze_case_creates_summary() -> None:
    """Vérifie les statistiques générales du dossier."""

    case = create_fake_case()

    result = analyze_case(case)

    assert result["case_id"] == "CASE-TEST-001"

    assert result["case_summary"]["number_of_parties"] == 2
    assert result["case_summary"]["number_of_events"] == 2
    assert result["case_summary"]["number_of_claims"] == 1
    assert result["case_summary"]["number_of_evidence"] == 2


def test_analyze_case_orders_timeline() -> None:
    """Vérifie que les événements sont classés chronologiquement."""

    case = create_fake_case()

    result = analyze_case(case)

    assert result["timeline"][0]["event_id"] == "EV1"
    assert result["timeline"][1]["event_id"] == "EV2"


def test_claim_is_not_automatically_a_fact() -> None:
    """
    Une affirmation d'une partie doit rester non vérifiée
    tant que l'evidence mapping ne l'a pas analysée.
    """

    case = create_fake_case()

    result = analyze_case(case)

    claim = result["claims_analysis"][0]

    assert claim["claim_id"] == "C1"
    assert claim["status"] == "unverified"


def test_no_legal_conclusion_is_invented() -> None:
    """
    DS4 ne doit pas produire de conclusion juridique
    avant l'analyse des preuves et des sources juridiques.
    """

    case = create_fake_case()

    result = analyze_case(case)

    assert result["legal_conclusion"] is None
def test_analyze_case_includes_evidence_mapping() -> None:
    """
    Vérifie que le Case-Analysis Agent utilise
    correctement l'outil Evidence Mapping.
    """

    # Créer un dossier fictif.
    case = create_fake_case()

    # Exécuter le Case Analysis.
    result = analyze_case(case)

    # Récupérer les relations événements-preuves.
    mappings = result["evidence_mapping"]

    # Notre dossier contient deux relations explicites.
    assert len(mappings) == 2

    # Vérifier les relations trouvées.
    actual_relations = {
        (item["event_id"], item["evidence_id"], item["relation"])
        for item in mappings
    }

    assert actual_relations == {
        ("EV1", "E1", "source"),
        ("EV2", "E2", "source"),
    }

    # Aucune conclusion juridique inventée.
    assert result["legal_conclusion"] is None

def test_incomplete_case_without_evidence() -> None:
    """Un dossier sans preuves ne doit pas produire de conclusion juridique."""

    # 1. Creer un dossier fictif existant
    case = create_fake_case()

    # 2. Supprimer les preuves du dossier
    case["evidence"] = []

    # 3. Supprimer les references aux preuves absentes
    for event in case["events"]:
        event["source_ids"] = []

    # 4. Analyser le dossier incomplet
    result = analyze_case(case)

    # 5. Verifier que DS4 n'invente rien
    assert result["case_summary"]["number_of_evidence"] == 0
    assert result["claims_analysis"][0]["status"] == "unverified"
    assert result["evidence_mapping"] == []
    assert result["legal_conclusion"] is None