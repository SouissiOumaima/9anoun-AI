"""Tests de coherence interne des dossiers juridiques DS4."""

import pytest

from src.track_a_legal.tools.case_integrity import validate_case_integrity
from src.track_a_legal.tests.test_case_analysis import create_fake_case


def test_rejects_claim_with_unknown_party() -> None:
    """Une affirmation ne peut pas referencer une partie inexistante."""

    # Construire un dossier juridique fictif valide.
    case = create_fake_case()

    # Introduire une reference vers une partie inexistante.
    case["claims"][0]["party_id"] = "P99"

    # La validation doit refuser cette incoherence.
    with pytest.raises(ValueError, match="unknown_party_id"):
        validate_case_integrity(case)

def test_rejects_duplicate_party_id() -> None:
    """Deux parties ne doivent pas partager le meme identifiant."""

    # Construire un dossier fictif valide.
    case = create_fake_case()

    # Attribuer le meme identifiant aux deux parties.
    case["parties"][1]["party_id"] = "P1"

    # Le validateur doit refuser cet identifiant duplique.
    with pytest.raises(ValueError, match="duplicate_party_id"):
        validate_case_integrity(case)

def test_rejects_duplicate_event_id() -> None:
    """Deux evenements ne doivent pas partager le meme identifiant."""

    # Construire un dossier valide.
    case = create_fake_case()

    # Dupliquer l'identifiant du premier evenement.
    case["events"][1]["event_id"] = case["events"][0]["event_id"]

    # Verifier que le doublon est refuse.
    with pytest.raises(ValueError, match="duplicate_event_id"):
        validate_case_integrity(case)


def test_rejects_duplicate_claim_id() -> None:
    """Deux affirmations ne doivent pas partager le meme identifiant."""

    # Construire un dossier valide.
    case = create_fake_case()

    # Ajouter une seconde affirmation avec le meme identifiant.
    case["claims"].append({
        "claim_id": "C1",
        "party_id": "P2",
        "text": "Deuxieme affirmation fictive.",
    })

    # Verifier que le doublon est refuse.
    with pytest.raises(ValueError, match="duplicate_claim_id"):
        validate_case_integrity(case)


def test_rejects_duplicate_evidence_id() -> None:
    """Deux preuves ne doivent pas partager le meme identifiant."""

    # Construire un dossier valide.
    case = create_fake_case()

    # Dupliquer l'identifiant de la premiere preuve.
    case["evidence"][1]["evidence_id"] = case["evidence"][0]["evidence_id"]

    # Verifier que le doublon est refuse.
    with pytest.raises(ValueError, match="duplicate_evidence_id"):
        validate_case_integrity(case)
