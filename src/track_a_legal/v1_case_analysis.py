"""Orchestration préparatoire de l'analyse juridique DS4 v1."""

import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker

from src.track_a_legal.v1_document_fact_validation import (
    assess_document_fact,
)
from src.track_a_legal.v1_legal_source_validation import (
    assess_legal_source,
    assess_legal_source_temporally,
)
from src.track_a_legal.v1_legal_version_validation import (
    validate_legal_versions,
)
from src.track_a_legal.v1_temporal_consistency import (
    check_temporal_consistency,
)
from src.track_a_legal.v1_reference_validation import (
    validate_v1_references,
)
from src.track_a_legal.v1_timeline import build_v1_timeline


# Charger le contrat d'entrée depuis la racine du dépôt.
ROOT = Path(__file__).resolve().parents[2]
SCHEMA_PATH = (
    ROOT / "data/mock_cards/schemas/track_a_request.v1.schema.json"
)

SCHEMA = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
VALIDATOR = Draft202012Validator(
    SCHEMA,
    format_checker=FormatChecker(),
)


def analyze_case_v1(request: dict[str, Any]) -> dict[str, Any]:
    """Analyser un dossier v1 sans produire de conclusion juridique."""

    # Étape 1 : valider le contrat d'entrée.
    errors = sorted(
        VALIDATOR.iter_errors(request),
        key=lambda error: str(error.path),
    )
    if errors:
        raise ValueError(
            "Invalid Request v1: " + errors[0].message
        )

    # Étape 2 : vérifier les références internes.
    reference_errors = validate_v1_references(request)

    # Étape 3 : construire la chronologie.
    timeline = build_v1_timeline(request["events"])

    # Étape 4 : qualifier chaque fait documentaire DS3.
    # Aucun fait n'est automatiquement certifié authentique.
    document_fact_assessments = [
        assess_document_fact(fact)
        for fact in request.get("document_facts", [])
    ]

    # Repérer les faits insuffisamment justifiés.
    unqualified_facts = [
        assessment
        for assessment in document_fact_assessments
        if not assessment["eligible_for_established_fact"]
    ]

    # Étape 5 : déterminer un statut provisoire.
    # Une anomalie empêche de considérer le dossier complet.
    # Evaluate legal sources without asserting applicability.
    legal_sources = request.get("legal_sources", [])
    reference_date = request.get("reference_date")

    legal_source_assessments = [
        assess_legal_source(item)
        for item in legal_sources
    ]

    # Keep temporal assessments separate from textual checks.
    legal_temporal_assessments = [
        assess_legal_source_temporally(item, reference_date)
        for item in legal_sources
    ]

    # Detect conflicting or inconsistent legal versions.
    legal_version_errors = (
        validate_legal_versions(legal_sources, reference_date)
        if legal_sources
        else []
    )

    # Preserve temporal findings for each source.
    temporal_consistency_findings = [
        {
            "source_id": item.get("source_id"),
            "findings": check_temporal_consistency(item),
        }
        for item in legal_sources
    ]

    # Identify sources lacking adequate textual support.
    unqualified_legal_sources = [
        item
        for item in legal_source_assessments
        if not item["eligible_for_legal_support"]
    ]

    has_insufficient_evidence = bool(
        reference_errors
        or unqualified_facts
        or unqualified_legal_sources
        or legal_version_errors
        or any(
            item["reasons"]
            for item in legal_temporal_assessments
        )
        or any(
            item["findings"]
            for item in temporal_consistency_findings
        )
    )

    return {
        "case_id": request["case_id"],
        "timeline": timeline,
        "reference_errors": reference_errors,
        "document_fact_assessments": document_fact_assessments,
        "legal_source_assessments": legal_source_assessments,
        "legal_temporal_assessments": legal_temporal_assessments,
        "legal_version_errors": legal_version_errors,
        "temporal_consistency_findings": temporal_consistency_findings,
        "legal_conclusion": None,
        "analysis_status": (
            "contradictory_evidence"
            if request.get("contradictions")
            else (
                "insufficient_evidence"
                if has_insufficient_evidence
                else "preparatory"
            )
        ),
    }
