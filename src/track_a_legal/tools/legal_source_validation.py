"""Contrôles préliminaires des sources juridiques fournies par DS2."""

from datetime import date
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

    # Verifier independamment chaque borne temporelle.
    for result in results:
        start = result.get("effective_from")
        end = result.get("effective_to")

        parsed_dates = []

        for value in (start, end):
            # Une borne inconnue est autorisee par DS2.
            if value is None:
                parsed_dates.append(None)
                continue

            # Imposer le format strict AAAA-MM-JJ.
            if not isinstance(value, str):
                return False
            if len(value) != 10 or value[4] != "-" or value[7] != "-":
                return False
            if not (
                value[:4].isascii() and value[:4].isdigit()
                and value[5:7].isascii() and value[5:7].isdigit()
                and value[8:].isascii() and value[8:].isdigit()
            ):
                return False

            # Rejeter les dates calendaires impossibles.
            try:
                parsed_dates.append(date.fromisoformat(value))
            except ValueError:
                return False

        start_date, end_date = parsed_dates

        # Comparer les bornes seulement si les deux sont connues.
        if start_date is not None and end_date is not None:
            if end_date < start_date:
                return False

    applicable_versions_by_group = set()

    for result in results:
        group = result.get("version_group")
        applicable = result.get("applicable_at_reference_date")

        # Compter uniquement les indicateurs explicitement vrais.
        if isinstance(group, str) and group and applicable is True:
            if group in applicable_versions_by_group:
                return False

            applicable_versions_by_group.add(group)

    # Ce controle ne prouve pas la validite juridique des dates.

    # La réponse a passé les contrôles préliminaires.
    # Cela ne garantit ni la validité juridique ni l'applicabilité.
    return True
