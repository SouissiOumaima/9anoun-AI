"""Tests de non-régression des métadonnées temporelles DS2."""

from src.track_a_legal.v1_legal_source_validation import (
    assess_legal_source_temporally,
)


def test_temporal_metadata_is_read_from_legal_source_root():
    """Lire les dates et statuts selon le contrat Request v1."""

    # Source juridique fictive avec citation traçable.
    source = {
        "article_id": "ART-TEST-001",
        "reference": "Article fictif 1",
        "source_id": "SRC-TEST-001",
        "text": "Disposition fictive pour test.",
        "citation": {
            "citation_id": "CIT-TEST-001",
            "document": "document-fictif.pdf",
            "page": 1,
            "exact_excerpt": "Disposition fictive pour test.",
        },
        "effective_date": "2026-01-01",
        "validity_status": "statut-fictif-a-verifier",
    }

    # Évaluer la source à une date postérieure.
    result = assess_legal_source_temporally(
        source,
        reference_date="2026-11-17",
    )

    # Les métadonnées présentes ne doivent pas être
    # considérées comme manquantes.
    assert "EFFECTIVE_DATE_UNKNOWN" not in result["reasons"]
    assert "TEMPORAL_VALIDITY_UNKNOWN" not in result["reasons"]

    # Le statut est rapporté sans être interprété.
    assert (
        result["validity_status_reported"]
        == "statut-fictif-a-verifier"
    )

    # Une vérification technique ne certifie jamais
    # l'applicabilité juridique.
    assert result["eligible_for_legal_conclusion"] is False
    assert result["temporal_eligibility"] == "not_confirmed"


def test_root_effective_date_divergence_is_detected():
    """Detect a mismatch between root-level temporal dates."""
    from src.track_a_legal.v1_temporal_consistency import (
        check_temporal_consistency,
    )

    # Both dates belong to the legal source, not its citation.
    source = {
        "source_id": "SRC-TEST-002",
        "effective_date": "2026-01-01",
        "effective_from": "2026-02-01",
        "citation": {
            "citation_id": "CIT-TEST-002",
            "document": "document-fictif.pdf",
            "page": 1,
            "exact_excerpt": "Disposition fictive.",
        },
    }

    # A disagreement must be reported without a legal conclusion.
    findings = check_temporal_consistency(source)

    assert {
        "code": "EFFECTIVE_DATE_DIVERGENCE",
        "path": "effective_date",
    } in findings
