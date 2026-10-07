"""
Case Analysis - Lawyer Track (DS4).

Ce module constitue le moteur principal d'analyse d'un dossier
juridique pour Track A.

Il organise les différentes informations du dossier avant
les étapes plus avancées :

- evidence mapping ;
- détection des contradictions ;
- détection des preuves manquantes ;
- analyse des règles juridiques ;
- rédaction juridique.

Important :
Une affirmation ("claim") n'est jamais automatiquement
considérée comme un fait établi.
"""

from src.track_a_legal.tools.timeline import build_timeline
from src.track_a_legal.tools.evidence_mapping import map_event_evidence

def analyze_case(case: dict) -> dict:
    """
    Produit une première analyse structurée d'un dossier juridique.

    Args:
        case:
            Dossier conforme au contrat track_a_request.v0.

    Returns:
        Un dictionnaire contenant une vue structurée du dossier.

    Important :
        Cette fonction ne produit pas encore
        de conclusion juridique.
    """

    # ----------------------------------------------------------
    # 1. Identification du dossier
    # ----------------------------------------------------------

    case_id = case["case_id"]

    # ----------------------------------------------------------
    # 2. Récupération des parties
    # ----------------------------------------------------------

    parties = case["parties"]

    # ----------------------------------------------------------
    # 3. Construction de la timeline
    # ----------------------------------------------------------
    #
    # La logique de construction de la timeline est maintenant
    # déléguée à l'outil spécialisé timeline.py.
    #
    # Le Case-Analysis Agent orchestre les outils DS4,
    # mais ne contient pas toute leur logique interne.

    timeline = build_timeline(case["events"])

    # ----------------------------------------------------------
    # 4. Analyse initiale des claims
    # ----------------------------------------------------------
    #
    # Une claim représente une affirmation faite par une partie.
    #
    # Elle ne doit pas être considérée comme vraie
    # tant que les preuves n'ont pas été analysées.

    claims = []

    for claim in case["claims"]:
        claims.append(
            {
                "claim_id": claim["claim_id"],
                "party_id": claim["party_id"],
                "text": claim["text"],
                "status": "unverified",
            }
        )

    # ----------------------------------------------------------
    # 5. Inventaire des preuves
    # ----------------------------------------------------------

    evidence = case["evidence"]
    # ----------------------------------------------------------
# 6. Construction des relations événements-preuves
# ----------------------------------------------------------
#
# Nous utilisons uniquement les références explicites
# présentes dans source_ids.
#
# Aucune preuve n'est automatiquement considérée comme
# confirmant ou contredisant une affirmation.
    evidence_mapping = map_event_evidence(
        case["events"],
        evidence,
    )

    # ----------------------------------------------------------
    # 6. Construction du résultat
    # ----------------------------------------------------------

    analysis = {
        "case_id": case_id,
        "case_summary": {
            "number_of_parties": len(parties),
            "number_of_events": len(timeline),
            "number_of_claims": len(claims),
            "number_of_evidence": len(evidence),
        },
        "parties": parties,
        "timeline": timeline,
        "claims_analysis": claims,
        "evidence": evidence,
        "evidence_mapping": evidence_mapping,
        "contradictions": [],
        "missing_evidence": [],
        "legal_conclusion": None,
    }

    return analysis