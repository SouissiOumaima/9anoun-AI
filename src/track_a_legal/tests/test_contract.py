"""
Tests du contrat JSON d'entrée du Lawyer Track (DS4).

L'objectif de ce fichier est de vérifier que les dossiers fictifs
présents dans data/mock_cards/track_a_cases_demo.json respectent
le JSON Schema défini par DS4.

Ainsi, si la structure d'un mock devient incorrecte, pytest
détectera automatiquement le problème.
"""

import json
from pathlib import Path

from jsonschema import Draft202012Validator


# -------------------------------------------------------------------
# CHEMINS DES FICHIERS
# -------------------------------------------------------------------

# __file__ représente le fichier actuel :
# src/track_a_legal/tests/test_contract.py
#
# parents[3] permet de remonter jusqu'à la racine du projet :
# 9anoun-AI/
PROJECT_ROOT = Path(__file__).resolve().parents[3]


# Chemin vers notre fichier contenant les dossiers fictifs DS4.
MOCK_FILE = (
    PROJECT_ROOT
    / "data"
    / "mock_cards"
    / "track_a_cases_demo.json"
)


# Chemin vers le contrat JSON Schema d'entrée de DS4.
SCHEMA_FILE = (
    PROJECT_ROOT
    / "data"
    / "mock_cards"
    / "schemas"
    / "track_a_request.v0.schema.json"
)


def load_json(path: Path) -> object:
    """
    Charge un fichier JSON depuis le disque.

    Args:
        path:
            Chemin du fichier JSON à ouvrir.

    Returns:
        Le contenu JSON converti en objet Python.

    Exemple :
        Un objet JSON devient un dictionnaire Python.
        Un tableau JSON devient une liste Python.
    """

    # encoding="utf-8" est important car notre projet
    # peut contenir du français et de l'arabe.
    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def test_track_a_demo_cases_match_request_schema() -> None:
    """
    Vérifie que chaque dossier de démonstration DS4
    respecte le contrat track_a_request.v0.
    """

    # 1. Charger le JSON Schema.
    schema = load_json(SCHEMA_FILE)

    # 2. Charger les dossiers fictifs.
    cases = load_json(MOCK_FILE)

    # Notre fichier de démonstration doit contenir une liste.
    assert isinstance(cases, list)

    # On veut au minimum un cas de démonstration.
    assert len(cases) > 0

    # 3. Créer un validateur utilisant JSON Schema Draft 2020-12.
    validator = Draft202012Validator(schema)

    # 4. Vérifier chaque dossier indépendamment.
    for case in cases:

        # Récupérer toutes les erreurs de validation.
        errors = list(validator.iter_errors(case))

        # Si errors est vide, le dossier est valide.
        #
        # Si une erreur existe, le message affichera les problèmes
        # pour faciliter le débogage.
        assert not errors, "\n".join(
            error.message for error in errors
        )