import pytest

"""Tests preliminaires des preuves documentaires DS3."""

from src.track_a_legal.tools.document_source_validation import (
    is_usable_document_response,
)


def test_rejects_mock_document_response():
    """Une reponse mock ne constitue pas une preuve reelle."""

    # Construire une reponse DS3 v2 de demonstration.
    response = {
        "contract_version": "ds3.v2",
        "status": "ok",
        "mode": "mock",
        "computed_by": "document_intelligence.mock",
        "document_id": "doc-001",
        "operation": "analyze_document",
        "result": {
            "complete": True,
            "fields": {},
        },
        "citations": [],
    }

    # DS4 doit refuser une source mock.
    assert is_usable_document_response(response) is False


def test_rejects_live_document_without_citations():
    """Rejeter une reponse live sans preuve documentaire."""

    # Simuler une reponse DS3 v2 issue du service reel.
    response = {
        "contract_version": "ds3.v2",
        "status": "ok",
        "mode": "live",
        "computed_by": "document_intelligence.service",
        "operation": "analyze_document",
        "document_id": "doc-001",
        "result": {
            "complete": True,
            "fields": {
                "employee_name": {
                    "value": "Ahmed",
                    "confidence": 0.96,
                    "citation_id": "c1",
                }
            },
        },
        # La citation c1 est absente de la liste.
        "citations": [],
    }

    # DS4 ne doit pas accepter une preuve introuvable.
    assert is_usable_document_response(response) is False


def test_rejects_unknown_field_citation_id():
    """Rejeter un champ dont la citation est introuvable."""

    # Construire une reponse DS3 live avec une citation existante.
    response = {
        "contract_version": "ds3.v2",
        "status": "ok",
        "mode": "live",
        "computed_by": "document_intelligence.service",
        "operation": "analyze_document",
        "document_id": "doc-001",
        "result": {
            "complete": True,
            "fields": {
                "employee_name": {
                    "value": "Ahmed",
                    "confidence": 0.96,
                    "citation_id": "c999",
                }
            },
        },
        "citations": [
            {
                "citation_id": "c1",
                "document_id": "doc-001",
                "page": 1,
                "bbox": None,
                "excerpt": "Nom: Ahmed",
            }
        ],
    }

    # Le champ reference c999, mais seule c1 existe.
    assert is_usable_document_response(response) is False


def test_rejects_citation_from_another_document():
    """Rejeter une citation provenant d'un autre document."""

    # Construire une reponse DS3 live.
    response = {
        "contract_version": "ds3.v2",
        "status": "ok",
        "mode": "live",
        "computed_by": "document_intelligence.service",
        "operation": "analyze_document",
        "document_id": "doc-001",
        "result": {
            "complete": True,
            "fields": {
                "employee_name": {
                    "value": "Ahmed",
                    "confidence": 0.96,
                    "citation_id": "c1",
                }
            },
        },
        "citations": [
            {
                "citation_id": "c1",
                # Cette citation appartient a un autre document.
                "document_id": "doc-999",
                "page": 1,
                "bbox": None,
                "excerpt": "Nom: Ahmed",
            }
        ],
    }

    # Une citation externe ne doit pas justifier ce document.
    assert is_usable_document_response(response) is False


def test_rejects_field_with_empty_citation_excerpt():
    """Rejeter un champ dont la citation ne contient aucun extrait."""

    # Construire une reponse DS3 live avec une citation vide.
    response = {
        "contract_version": "ds3.v2",
        "status": "ok",
        "mode": "live",
        "computed_by": "document_intelligence.service",
        "operation": "analyze_document",
        "document_id": "doc-001",
        "result": {
            "complete": True,
            "fields": {
                "employee_name": {
                    "value": "Ahmed",
                    "confidence": 0.96,
                    "citation_id": "c1",
                }
            },
        },
        "citations": [
            {
                "citation_id": "c1",
                "document_id": "doc-001",
                "page": 1,
                "bbox": None,
                "excerpt": "   ",
            }
        ],
    }

    # Une citation sans extrait ne peut pas justifier le champ.
    assert is_usable_document_response(response) is False


def test_accepts_null_field_without_treating_it_as_evidence():
    """Accepter un champ inconnu sans le considerer comme une preuve."""

    # Construire une reponse DS3 avec un champ non extrait.
    response = {
        "contract_version": "ds3.v2",
        "status": "ok",
        "mode": "live",
        "computed_by": "document_intelligence.service",
        "operation": "analyze_document",
        "document_id": "doc-001",
        "result": {
            "complete": False,
            "fields": {
                "employee_name": {
                    "value": None,
                    "confidence": None,
                    "citation_id": None,
                }
            },
        },
        "citations": [
            {
                "citation_id": "c1",
                "document_id": "doc-001",
                "page": 1,
                "bbox": None,
                "excerpt": "Document analyse",
            }
        ],
    }

    # La reponse peut etre structurellement exploitable,
    # mais le champ reste inconnu et non confirme.
    assert is_usable_document_response(response) is True


@pytest.mark.parametrize(
    "result",
    [
        None,
        [],
        {"complete": True, "fields": []},
        {"complete": True, "fields": {"employee_name": "Ahmed"}},
    ],
)
def test_rejects_invalid_result_structure(result):
    """Rejeter les structures result et fields non conformes."""

    # Construire une reponse DS3 avec une structure incorrecte.
    response = {
        "contract_version": "ds3.v2",
        "status": "ok",
        "mode": "live",
        "computed_by": "document_intelligence.service",
        "operation": "analyze_document",
        "document_id": "doc-001",
        "result": result,
        "citations": [
            {
                "citation_id": "c1",
                "document_id": "doc-001",
                "page": 1,
                "bbox": None,
                "excerpt": "Document analyse",
            }
        ],
    }

    # DS4 doit rejeter une structure incompatible.
    assert is_usable_document_response(response) is False


def test_accepts_live_wage_grid_with_valid_citation():
    """Accepter une grille DS3 live avec une citation coherente."""

    # Construire une grille conforme a la structure DS3 v2.
    response = {
        "contract_version": "ds3.v2",
        "status": "ok",
        "mode": "live",
        "computed_by": "document_intelligence.service",
        "operation": "extract_wage_grid",
        "document_id": "doc-grid-001",
        "result": {
            "title": "Grille des salaires",
            "sector_ar": "قطاع الحراسة",
            "sector_code": None,
            "effective_date": "2026-01-01",
            "unit": "TND/mois",
            "legal_basis": "Article 43",
            "citation_id": "c1",
            "complete": True,
            "grades": [
                {
                    "grade": 1,
                    "duration_years": 1,
                    "seniority": "0-1",
                }
            ],
            "values": [
                {
                    "category": 1,
                    "grade": 1,
                    "amount": "424.100",
                    "confidence": 0.97,
                    "unreadable_reason": None,
                }
            ],
        },
        "citations": [
            {
                "citation_id": "c1",
                "document_id": "doc-grid-001",
                "page": 21,
                "bbox": None,
                "excerpt": "Grille des salaires applicable",
            }
        ],
    }

    # Une grille valide doit passer les controles preliminaires.
    # Cela ne confirme pas son applicabilite juridique.
    assert is_usable_document_response(response) is True




def test_accepts_partial_document_with_unreadable_field():
    """Conserver les champs cites malgre une zone illisible."""

    # Simuler une extraction DS3 live partiellement lisible.
    response = {
        "contract_version": "ds3.v2",
        "status": "ok",
        "mode": "live",
        "computed_by": "document_intelligence.service",
        "operation": "analyze_document",
        "document_id": "doc-partial-001",
        "citations": [
            {
                "citation_id": "c1",
                "document_id": "doc-partial-001",
                "page": 1,
                "bbox": None,
                "excerpt": "Salaire brut 516.100",
            },
            {
                "citation_id": "c2",
                "document_id": "doc-partial-001",
                "page": 1,
                "bbox": None,
                "excerpt": "",
            },
        ],
        "result": {
            "document_type": "fiche_de_paie",
            "complete": False,
            "fields": {
                "gross_salary": {
                    "value": "516.100",
                    "citation_id": "c1",
                },
                "cnss_employee": {
                    "value": None,
                    "citation_id": "c2",
                    "unreadable_reason": "zone_illisible",
                },
            },
        },
    }

    # Une zone illisible ne doit pas invalider le salaire cite.
    assert is_usable_document_response(response) is True


def test_rejects_wage_grid_with_empty_source_excerpt():
    """Refuser une grille dont la citation principale est illisible."""

    # Construire une reponse DS3 live.
    response = {
        "contract_version": "ds3.v2",
        "status": "ok",
        "mode": "live",
        "computed_by": "document_intelligence.service",
        "operation": "extract_wage_grid",
        "document_id": "doc-grid-empty",
        "citations": [
            {
                "citation_id": "c1",
                "document_id": "doc-grid-empty",
                "page": 21,
                "bbox": None,
                "excerpt": "",
            }
        ],
        "result": {
            "title": "Grille salariale",
            "sector_ar": "قطاع الحراسة",
            "effective_date": "2026-01-01",
            "unit": "TND/mois",
            "legal_basis": "Article 43",
            "citation_id": "c1",
            "complete": True,
            "grades": [{"grade": 1}],
            "values": [
                {
                    "category": 1,
                    "grade": 1,
                    "amount": "424.100",
                    "confidence": 0.97,
                }
            ],
        },
    }

    # Une citation vide ne peut pas justifier un montant salarial.
    assert is_usable_document_response(response) is False
