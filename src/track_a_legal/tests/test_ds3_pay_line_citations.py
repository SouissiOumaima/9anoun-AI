"""Tests de sécurité des citations des lignes de paie DS3."""

import copy
import json
from pathlib import Path

from src.track_a_legal.tools.document_source_validation import (
    is_usable_document_response,
)


# Identifier la racine du dépôt.
REPO = Path(__file__).resolve().parents[3]

# Charger les exemples officiels DS3 v2.
DEMO_PATH = (
    REPO / "data" / "mock_cards"
    / "document_intelligence_requests_demo.v2.json"
)


def test_rejects_unknown_pay_line_citation():
    """Refuser une ligne de paie sans citation existante."""

    # Charger les réponses officielles fictives.
    examples = json.loads(
        DEMO_PATH.read_text(encoding="utf-8")
    )

    # Sélectionner une fiche de paie complète.
    response = copy.deepcopy(
        next(
            item["response"]
            for item in examples
            if item["name"] == "01_ok_fiche_paie"
        )
    )

    # Simuler les métadonnées live pour tester le validateur.
    # Cette réponse ne constitue pas une preuve réelle.
    response["mode"] = "live"
    response["computed_by"] = "document_intelligence.service"

    # Vérifier que la fixture contient une ligne de paie.
    pay_lines = response["result"]["pay_lines"]
    assert pay_lines

    # Remplacer la citation par une référence inexistante.
    pay_lines[0]["citation_id"] = "citation_inexistante"

    # Comportement de sécurité attendu :
    # DS4 doit refuser toute référence documentaire introuvable.
    assert is_usable_document_response(response) is False
