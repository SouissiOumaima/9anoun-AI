"""S7: preliminary legal deliverables without automated legal conclusions."""

from copy import deepcopy
from typing import Any

from src.track_a_legal.v1_five_pillars import build_five_pillars


def generate_legal_deliverables_s7(
    analysis: dict[str, Any],
) -> dict[str, Any]:
    """Build traceable preparatory deliverables from a validated analysis."""

    if not isinstance(analysis, dict):
        raise ValueError("Invalid DS4 analysis.")

    # Reutiliser les cinq piliers existants sans modifier l'analyse.
    five_pillars = build_five_pillars(deepcopy(analysis))
    pillars = five_pillars["pillars"]

    # Conserver les donnees et les incertitudes sans inference nouvelle.
    sections = [
        {
            "section_id": "S7-01",
            "title": "Faits du dossier",
            "content": deepcopy(pillars["faits"]),
        },
        {
            "section_id": "S7-02",
            "title": "Declarations et demandes",
            "content": deepcopy(pillars["declarations"]),
        },
        {
            "section_id": "S7-03",
            "title": "Regles et sources juridiques",
            "content": deepcopy(pillars["regles"]),
        },
        {
            "section_id": "S7-04",
            "title": "Interpretation juridique",
            "content": deepcopy(pillars["interpretation"]),
        },
        {
            "section_id": "S7-05",
            "title": "Strategie juridique",
            "content": deepcopy(pillars["strategie"]),
        },
    ]

    # La validation par avocat reste obligatoire.
    return {
        "deliverable_version": "track_a_legal_deliverables_s7.v1",
        "case_id": five_pillars["case_id"],
        "document_status": "preparatory",
        "lawyer_validated": False,
        "sections": sections,
        "legal_conclusion": None,
    }
