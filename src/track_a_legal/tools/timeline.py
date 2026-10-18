"""
Gestion de la timeline juridique du Lawyer Track (DS4).

Ce module contient les fonctions nécessaires pour construire
la chronologie d'un dossier juridique à partir des événements
reçus par le Case-Analysis Agent.

Important :
- ce module organise les événements ;
- il ne décide pas si un événement est juridiquement vrai ;
- il conserve les références vers les sources disponibles.
"""

from datetime import date


def build_timeline(events: list[dict]) -> list[dict]:
    """
    Construit la timeline chronologique d'un dossier.

    Args:
        events:
            Liste des événements provenant du dossier DS4.

            Chaque événement doit notamment contenir :
            - event_id
            - date
            - description
            - source_ids

    Returns:
        Une nouvelle liste contenant les événements
        classés du plus ancien au plus récent.

    Raises:
        ValueError:
            Si la date d'un événement est absente
            ou n'est pas une date ISO valide YYYY-MM-DD.
    """

    # sorted() crée une nouvelle liste.
    #
    # C'est important : nous ne voulons pas modifier directement
    # les données reçues par DS4.
    timeline = sorted(
        events,
        key=_get_event_date,
    )

    return timeline


def _get_event_date(event: dict) -> date:
    """
    Lit et valide la date d'un événement.

    Cette fonction commence par "_", car elle est destinée
    à être utilisée uniquement à l'intérieur de ce module.

    Args:
        event:
            Événement juridique à examiner.

    Returns:
        Un objet datetime.date utilisable pour le tri.

    Raises:
        ValueError:
            Si le champ "date" est absent ou invalide.
    """

    # On récupère la valeur du champ date.
    date_value = event.get("date")

    # ----------------------------------------------------------
    # Vérification 1 : la date doit être une chaîne de caractères.
    # ----------------------------------------------------------

    if not isinstance(date_value, str):
        raise ValueError(
            "Chaque événement doit contenir une date "
            "au format YYYY-MM-DD."
        )

    # ----------------------------------------------------------
    # Vérification 2 : la chaîne doit représenter une vraie date.
    # ----------------------------------------------------------

    try:
        # Exemple :
        #
        # "2026-09-10"
        #       ↓
        # date(2026, 9, 10)
        #
        # Python pourra ensuite comparer correctement les dates.
        return date.fromisoformat(date_value)

    except ValueError as exc:

        # On ajoute l'identifiant de l'événement dans l'erreur
        # afin de faciliter le débogage.
        event_id = event.get("event_id", "inconnu")

        raise ValueError(
            f"Date invalide pour l'événement "
            f"{event_id}: {date_value}"
        ) from exc