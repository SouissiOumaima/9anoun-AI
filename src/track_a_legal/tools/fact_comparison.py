"""Comparaison factuelle interne - Lawyer Track DS4."""

from decimal import Decimal, InvalidOperation
from itertools import combinations


def compare_document_facts(facts: list[dict]) -> list[dict]:
    """
    Identifier les divergences potentielles entre faits comparables.

    Les valeurs doivent concerner le meme sujet, la meme
    propriete, la meme periode et la meme unite.

    Les citations sont uniquement conservees comme references.
    Leur authenticite n'est pas verifiee ici.
    """

    # Refuser les collections mal formees.
    if not isinstance(facts, list):
        return []

    # Champs indispensables a une comparaison prudente.
    required_fields = (
        "fact_id",
        "subject_id",
        "property",
        "period",
        "unit",
        "value",
        "document_id",
        "citation_id",
    )

    valid_facts = []

    # Examiner les faits sans modifier les objets originaux.
    for fact in facts:

        if not isinstance(fact, dict):
            continue

        # Exiger des champs textuels non vides.
        if any(
            not isinstance(fact.get(field), str)
            or not fact[field].strip()
            for field in required_fields
        ):
            continue

        valid_facts.append(fact)

    divergences = []

    # Comparer chaque paire une seule fois.
    for first, second in combinations(valid_facts, 2):

        # Ne pas comparer un fait avec lui-meme.
        if first["fact_id"] == second["fact_id"]:
            continue

        # Exiger deux documents distincts.
        if first["document_id"] == second["document_id"]:
            continue

        # Verifier que les deux faits sont comparables.
        context_fields = (
            "subject_id",
            "property",
            "period",
            "unit",
        )

        if any(
            first[field] != second[field]
            for field in context_fields
        ):
            continue

        # Des valeurs identiques ne constituent pas une divergence.
        # Comparer les montants avec une precision decimale exacte.
        # Refuser les valeurs non numeriques ou non finies.
        try:
            first_value = Decimal(first["value"])
            second_value = Decimal(second["value"])
        except InvalidOperation:
            continue

        # NaN et Infinity ne sont pas des montants exploitables.
        if not first_value.is_finite() or not second_value.is_finite():
            continue

        # Deux representations du meme montant sont equivalentes.
        if first_value == second_value:
            continue

        # Signaler uniquement une divergence potentielle.
        # Conserver les references pour une verification ulterieure.
        divergences.append(
            {
                "type": "potential_divergence",
                "fact_ids": [
                    first["fact_id"],
                    second["fact_id"],
                ],
                "document_ids": [
                    first["document_id"],
                    second["document_id"],
                ],
                "citation_ids": [
                    first["citation_id"],
                    second["citation_id"],
                ],
            }
        )

    return divergences
