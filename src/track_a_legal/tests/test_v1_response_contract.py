"""Tests du contrat JSON Response v1 de DS4."""

import copy
import json
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker


# Localiser la racine du dépôt depuis ce fichier de test.
ROOT = Path(__file__).resolve().parents[3]

# Charger le contrat Response v1.
SCHEMA_PATH = (
    ROOT / "data/mock_cards/schemas/track_a_response.v1.schema.json"
)
SCHEMA = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))

# Valider aussi les formats, notamment les dates.
VALIDATOR = Draft202012Validator(
    SCHEMA,
    format_checker=FormatChecker(),
)


def make_valid_response() -> dict:
    """Construire une réponse préparatoire minimale valide."""
    return {
        "contract_version": "track_a.v1",
        "request_id": "REQ-TEST-001",
        "case_id": "CASE-TEST-001",
        "status": "ok",
        "result": {
            "case_id": "CASE-TEST-001",
            "case_summary": {
                "number_of_parties": 0,
                "number_of_events": 0,
                "number_of_claims": 0,
                "number_of_evidence": 0,
            },
            "parties": [],
            "timeline": [],
            "claims_analysis": [],
            "evidence": [],
            "evidence_mapping": [],
            "contradictions": [],
            "missing_evidence": [],
            "legal_conclusion": None,
            "analysis_status": "preparatory",
        },
        "citations": [],
        "refus": None,
        "computed_by": "DS4",
    }


def test_valid_preparatory_response() -> None:
    """Une réponse préparatoire conforme doit être acceptée."""
    VALIDATOR.validate(make_valid_response())


def test_legal_conclusion_must_remain_null() -> None:
    """Le contrat interdit une conclusion juridique inventée."""
    response = copy.deepcopy(make_valid_response())
    response["result"]["legal_conclusion"] = "Licenciement abusif"

    assert list(VALIDATOR.iter_errors(response))


def test_supported_requires_citation() -> None:
    """Le statut supported exige au moins une citation."""
    response = copy.deepcopy(make_valid_response())
    response["result"]["analysis_status"] = "supported"

    assert list(VALIDATOR.iter_errors(response))
