"""Tests du Legal Reasoning Engine - DS4."""

from copy import deepcopy

from src.track_a_legal.tools.legal_reasoning import (
    prepare_legal_reasoning,
)


def test_missing_legal_sources_requires_abstention() -> None:
    """Aucune conclusion juridique sans source disponible."""

    # Analyse interne minimale, sans conclusion.
    case_analysis = {
        "case_id": "CASE-TEST-001",
        "claims_analysis": [
            {
                "claim_id": "CL-001",
                "party_id": "P1",
                "text": "Salaire non verse",
                "status": "unverified",
            }
        ],
        "legal_conclusion": None,
    }

    # Aucune reponse juridique DS2 disponible.
    legal_response = None

    # Executer le moteur de raisonnement.
    result = prepare_legal_reasoning(
        case_analysis,
        legal_response,
    )

    # Appliquer le principe Citation ou Silence.
    assert result == {
        "status": "insufficient_sources",
        "legal_conclusion": None,
        "citation_ids": [],
        "reason": "legal_source_unavailable",
    }


def test_usable_legal_sources_require_verification(valid_ds2_response) -> None:
    """Une source DS2 acceptable ne prouve pas une conclusion."""

    # Analyse initiale sans conclusion juridique.
    case_analysis = {
        "case_id": "CASE-TEST-002",
        "claims_analysis": [
            {
                "claim_id": "CL-002",
                "party_id": "P1",
                "text": "Salaire non verse",
                "status": "unverified",
            }
        ],
        "legal_conclusion": None,
    }

    # Reponse DS2 minimale satisfaisant les controles
    # preliminaires actuellement implementes.
    # Ces donnees sont fictives et ne prouvent aucune loi.
    legal_response = deepcopy(valid_ds2_response)

    # Executer le moteur interne DS4.
    result = prepare_legal_reasoning(
        case_analysis,
        legal_response,
    )

    # Une validation preliminaire ne permet pas
    # de conclure juridiquement.
    assert result == {
        "status": "pending_verification",
        "legal_conclusion": None,
        "citation_ids": [],
        "reason": "additional_legal_verification_required",
    }


def test_missing_case_id_requires_abstention(valid_ds2_response) -> None:
    """Un dossier sans identifiant ne peut pas etre analyse."""

    # Dossier incomplet : case_id absent.
    case_analysis = {
        "claims_analysis": [],
        "legal_conclusion": None,
    }

    # Reponse DS2 fictive passant les controles preliminaires.
    legal_response = deepcopy(valid_ds2_response)

    # Executer le moteur avec un dossier incomplet.
    result = prepare_legal_reasoning(
        case_analysis,
        legal_response,
    )

    # Le moteur doit refuser de poursuivre les controles.
    assert result == {
        "status": "invalid_case",
        "legal_conclusion": None,
        "citation_ids": [],
        "reason": "missing_case_id",
    }


def test_invalid_case_id_requires_abstention(valid_ds2_response) -> None:
    """Refuser les identifiants vides ou de type incorrect."""

    # Tester plusieurs identifiants invalides.
    invalid_ids = ["", "   ", None, 123, [], {}]

    for invalid_id in invalid_ids:
        # Construire un dossier avec un identifiant invalide.
        case_analysis = {
            "case_id": invalid_id,
            "claims_analysis": [],
            "legal_conclusion": None,
        }

        # Construire une reponse DS2 fictive valide structurellement.
        citation = {"citation_id": "CIT-TEST-003"}

        legal_response = deepcopy(valid_ds2_response)

        # Le moteur doit refuser chaque identifiant invalide.
        result = prepare_legal_reasoning(
            case_analysis,
            legal_response,
        )

        assert result == {
            "status": "invalid_case",
            "legal_conclusion": None,
            "citation_ids": [],
            "reason": "missing_case_id",
        }, f"Identifiant invalide non rejete : {invalid_id!r}"


def test_invalid_claims_analysis_requires_abstention(valid_ds2_response) -> None:
    """Refuser un dossier dont claims_analysis n'est pas une liste."""

    # Dossier avec une structure invalide.
    case_analysis = {
        "case_id": "CASE-TEST-002",
        "claims_analysis": "invalid_claims",
        "legal_conclusion": None,
    }

    # Reponse DS2 fictive, valide structurellement.
    legal_response = deepcopy(valid_ds2_response)

    # Le moteur doit refuser le dossier invalide.
    result = prepare_legal_reasoning(
        case_analysis,
        legal_response,
    )

    assert result == {
        "status": "invalid_case",
        "legal_conclusion": None,
        "citation_ids": [],
        "reason": "invalid_claims_analysis",
    }


def test_incomplete_ds2_contract_requires_abstention(valid_ds2_response):
    """Refuser une reponse DS2 incomplete, meme avec des citations."""

    # Copier la fixture pour ne pas modifier les autres tests.
    from copy import deepcopy

    legal_response = deepcopy(valid_ds2_response)

    # Supprimer un champ obligatoire du contrat officiel DS2.
    del legal_response["results"][0]["source_title"]

    # Fournir un dossier minimal valide pour isoler la validation DS2.
    case_analysis = {
        "case_id": "CASE-TEST-001",
        "claims_analysis": [],
    }

    result = prepare_legal_reasoning(case_analysis, legal_response)

    # Une source non conforme ne peut pas autoriser un raisonnement juridique.
    assert result["status"] == "insufficient_sources"
    assert result["legal_conclusion"] is None
    assert result["citation_ids"] == []


def test_reasoning_rejects_temporally_inconsistent_ds2_sources(
    valid_ds2_response,
):
    """Bloquer le raisonnement si DS2 contredit la date du dossier."""

    # Pr?parer une r?ponse DS2 ind?pendante.
    from copy import deepcopy

    response = deepcopy(valid_ds2_response)

    # Simuler un article applicable seulement ? partir de 2025.
    article = response["results"][0]
    article["effective_from"] = "2025-01-01"
    article["effective_to"] = None
    article["applicable_at_reference_date"] = True

    # Pr?parer un dossier ant?rieur ? cette entr?e en vigueur.
    case_analysis = {
        "case_id": "CASE-TEMPORAL-001",
        "claims_analysis": [],
        "reference_date": "2024-06-01",
    }

    # Le moteur doit d?tecter l'incoh?rence temporelle.
    result = prepare_legal_reasoning(case_analysis, response)

    assert result["status"] == "insufficient_sources"
    assert result["legal_conclusion"] is None
    assert result["citation_ids"] == []
    assert result["reason"] == "legal_source_unavailable"
