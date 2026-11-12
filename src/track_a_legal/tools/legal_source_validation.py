"""Contrôles préliminaires des sources juridiques fournies par DS2."""

from typing import Any


def is_usable_legal_response(response: Any) -> bool:
    """Vérifier si une réponse DS2 peut passer aux contrôles suivants."""

    # Rejeter toute valeur qui n'est pas un objet JSON.
    if not isinstance(response, dict):
        return False

    # Accepter uniquement une réponse DS2 réussie en mode réel.
    if response.get("contract_version") != "legal_retrieval.v0":
        return False

    if response.get("status") != "ok":
        return False

    if response.get("mode") != "live":
        return False

    # Vérifier que les résultats et citations sont des listes non vides.
    results = response.get("results")
    citations = response.get("citations")

    if not isinstance(results, list) or not results:
        return False

    if not isinstance(citations, list) or not citations:
        return False

    # Chaque résultat doit être un objet contenant une citation.
    # La citation doit elle-même être un objet JSON.
    for result in results:
        if not isinstance(result, dict):
            return False

        if not isinstance(result.get("citation"), dict):
            return False

    # DS2 construit les citations globales dans le même ordre
    # que les citations intégrées aux résultats.
    expected_citations = [result["citation"] for result in results]

    if citations != expected_citations:
        return False

    # La réponse a passé les contrôles préliminaires.
    # Cela ne garantit ni la validité juridique ni l'applicabilité.
    return True
