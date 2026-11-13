"""Detection interne des contradictions - Lawyer Track DS4."""


def detect_contradictions(claims: list[dict]) -> list[dict]:
    """
    Retourner uniquement les contradictions factuelles verifiees.

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
