"""Controles preliminaires des reponses documentaires DS3."""

from typing import Any


def is_usable_document_response(response: Any) -> bool:
    """Verifier les conditions minimales d'origine DS3."""

    # Refuser les entrees qui ne sont pas des objets JSON.
    if not isinstance(response, dict):
        return False

    # Accepter uniquement le contrat DS3 v2.
    if response.get("contract_version") != "ds3.v2":
        return False

    # Refuser les reponses en erreur ou en refus.
    if response.get("status") != "ok":
        return False

    # Exclure les reponses de demonstration (mock).
    if response.get("mode") != "live":
        return False

    # Verifier le service declare comme producteur.
    if response.get("computed_by") != "document_intelligence.service":
        return False

    # Une preuve documentaire doit contenir des citations.
    citations = response.get("citations")
    if not isinstance(citations, list) or not citations:
        return False

    # Verifier l'identifiant du document analyse.
    document_id = response.get("document_id")

    if not isinstance(document_id, str) or not document_id.strip():
        return False

    # Construire les identifiants des citations disponibles.
    citation_ids = set()

    for citation in citations:
        # Chaque citation doit etre un objet avec un identifiant.
        if not isinstance(citation, dict):
            return False

        # La citation doit appartenir au document analyse.
        if citation.get("document_id") != document_id:
            return False

        # Verifier la presence d'un extrait documentaire exploitable.
        excerpt = citation.get("excerpt")
        if not isinstance(excerpt, str):
            return False

        citation_id = citation.get("citation_id")
        if not isinstance(citation_id, str) or not citation_id.strip():
            return False

        # Eviter les identifiants ambigus.
        if citation_id in citation_ids:
            return False

        citation_ids.add(citation_id)

    # Verifier la structure des champs extraits.
    result = response.get("result")
    if not isinstance(result, dict):
        return False

    # Traiter separement les grilles de salaires DS3.
    if response.get("operation") == "extract_wage_grid":
        # Verifier que la grille renvoie une citation existante.
        if result.get("citation_id") not in citation_ids:
            return False

        # Une grille salariale exige un extrait documentaire lisible.
        grid_citation = next(
            (
                citation
                for citation in citations
                if citation["citation_id"] == result["citation_id"]
            ),
            None,
        )
        if grid_citation is None or not grid_citation["excerpt"].strip():
            return False

        # Verifier la presence des echelons et des montants.
        grades = result.get("grades")
        values = result.get("values")

        if not isinstance(grades, list) or not grades:
            return False

        if not isinstance(values, list) or not values:
            return False

        # Chaque echelon doit posseder un identifiant entier.
        for grade in grades:
            if not isinstance(grade, dict):
                return False
            if type(grade.get("grade")) is not int:
                return False

        # Verifier les montants extraits sans les recalculer.
        for value in values:
            if not isinstance(value, dict):
                return False

            if type(value.get("category")) is not int:
                return False

            if type(value.get("grade")) is not int:
                return False

            amount = value.get("amount")

            # Une valeur absente ne doit jamais etre inventee.
            if amount is not None:
                if not isinstance(amount, str):
                    return False

                # Les montants DS3 utilisent trois decimales.
                import re
                if re.fullmatch(r"-?[0-9]+\.[0-9]{3}", amount) is None:
                    return False

        # Validation documentaire preliminaire uniquement.
        return True

    # Verifier les citations des tableaux extraits.
    tables = result.get("tables", [])

    if not isinstance(tables, list):
        return False

    for table in tables:
        # Chaque tableau doit etre un objet JSON.
        if not isinstance(table, dict):
            return False

        # Chaque tableau doit referencer une citation existante.
        citation_id = table.get("citation_id")
        if not isinstance(citation_id, str):
            return False

        if citation_id not in citation_ids:
            return False

        # La citation doit contenir un extrait documentaire lisible.
        matching_citation = next(
            (
                item
                for item in citations
                if item["citation_id"] == citation_id
            ),
            None,
        )

        if (
            matching_citation is None
            or not matching_citation["excerpt"].strip()
        ):
            return False

    # Verifier les citations des lignes de paie, si presentes.
    pay_lines = result.get("pay_lines", [])

    if not isinstance(pay_lines, list):
        return False

    for pay_line in pay_lines:
        # Chaque ligne de paie doit etre un objet JSON.
        if not isinstance(pay_line, dict):
            return False

        # Toute ligne doit referencer une citation existante.
        citation_id = pay_line.get("citation_id")
        if citation_id not in citation_ids:
            return False

        # La citation utilisee doit contenir un extrait lisible.
        matching_citation = next(
            (
                item
                for item in citations
                if item["citation_id"] == citation_id
            ),
            None,
        )

        if (
            matching_citation is None
            or not matching_citation["excerpt"].strip()
        ):
            return False

    fields = result.get("fields")
    if not isinstance(fields, dict):
        return False

    for field in fields.values():
        if not isinstance(field, dict):
            return False

        # Une valeur inconnue n'est pas une preuve exploitable.
        if field.get("value") is None:
            continue

        # Toute valeur presente doit avoir une citation existante.
        citation_id = field.get("citation_id")
        if citation_id not in citation_ids:
            return False

        # Une valeur extraite exige une citation lisible.
        matching_citation = next(
            (item for item in citations if item["citation_id"] == citation_id),
            None,
        )
        if matching_citation is None or not matching_citation["excerpt"].strip():
            return False

    # Ces controles ne prouvent pas la validite des faits.
    # D'autres validations documentaires restent necessaires.
    return True
