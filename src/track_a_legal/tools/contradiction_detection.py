"""Detection interne des contradictions - Lawyer Track DS4."""


def detect_contradictions(
    claims: list[dict],
    document_facts: list[dict] | None = None,
) -> list[dict]:
    """
    Retourner uniquement les contradictions factuelles verifiees.

    Interface etendue :
    - document_facts est facultatif ;
    - aucune divergence documentaire ne constitue
      automatiquement une contradiction prouvee ;
    - les donnees d'entree restent inchangees.

    Version initiale :
    - aucune source contradictoire verifiee n'est fournie ;
    - aucune contradiction factuelle ne peut etre etablie ;
    - les claims ne sont jamais modifies.

    Cette fonction ne produit aucune conclusion juridique.
    """

    # Les affirmations seules ne permettent pas de prouver
    # une contradiction factuelle.
    # Une future version devra exploiter des preuves verifiees
    # et des references explicites avant tout signalement.
    return []


def detect_document_divergences(
    document_facts: list[dict],
) -> list[dict]:
    """
    Identifier les divergences documentaires potentielles.

    Cette fonction :
    - reutilise le moteur Fact Comparison ;
    - conserve les references documentaires ;
    - ne verifie pas l'authenticite des documents ;
    - ne produit aucune contradiction juridique prouvee ;
    - ne modifie pas les donnees originales.
    """

    # Importer le moteur de comparaison existant.
    from src.track_a_legal.tools.fact_comparison import (
        compare_document_facts,
    )

    # Deleguer la comparaison au composant specialise.
    # Les resultats restent des divergences potentielles.
    return compare_document_facts(document_facts)
