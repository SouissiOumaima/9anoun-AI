import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator, FormatChecker


# Localiser le schéma depuis la racine du dépôt.
ROOT = Path(__file__).resolve().parents[3]
SCHEMA_PATH = ROOT / "data/mock_cards/schemas/track_a_lawyer_review_decisions_s9.v1.schema.json"


@pytest.fixture
def validator():
    """Charger et vérifier le schéma JSON S9."""
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8-sig"))
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema, format_checker=FormatChecker())


@pytest.fixture
def document():
    """Créer un document fictif sans décision juridique."""
    return {
        "contract_version": "track_a_lawyer_review_decisions_s9.v1",
        "source_dataset_version": "track_a_golden_set_lawyer_s9.v1",
        "lawyer_validated": False,
        "reviews": [{
            "case_id": "CASE-A-001",
            "criterion_id": "S6-C02",
            "review_status": "pending",
            "reviewer_id": None,
            "review_date": None,
            "decision": None,
            "comments": None,
            "supporting_references": []
        }]
    }


def test_pending_valid(validator, document):
    """Une évaluation en attente est autorisée."""
    assert validator.is_valid(document)


def test_completed_valid(validator, document):
    """Une décision humaine fictive complète est acceptée techniquement."""
    review = document["reviews"][0]
    review.update({
        "review_status": "completed",
        "reviewer_id": "REVIEWER-TEST",
        "review_date": "2026-11-20",
        "decision": "approved",
        "comments": "Exemple fictif pour test uniquement."
    })
    assert validator.is_valid(document)


def test_missing_reviewer_rejected(validator, document):
    """Une décision sans relecteur doit être refusée."""
    review = document["reviews"][0]
    review.update({
        "review_status": "completed",
        "review_date": "2026-11-20",
        "decision": "approved",
        "comments": "Test fictif."
    })
    assert not validator.is_valid(document)


def test_pending_decision_rejected(validator, document):
    """Une décision ne peut pas être enregistrée avec pending."""
    document["reviews"][0]["decision"] = "approved"
    assert not validator.is_valid(document)


def test_invalid_date_rejected(validator, document):
    """Une date incorrecte doit être refusée."""
    review = document["reviews"][0]
    review.update({
        "review_status": "completed",
        "reviewer_id": "REVIEWER-TEST",
        "review_date": "2026-99-99",
        "decision": "approved",
        "comments": "Test fictif."
    })
    assert not validator.is_valid(document)


def test_automatic_validation_rejected(validator, document):
    """Le contrat ne doit jamais déclarer une validation juridique."""
    document["lawyer_validated"] = True
    assert not validator.is_valid(document)
