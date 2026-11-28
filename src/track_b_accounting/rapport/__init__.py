"""Rapport de conformité d'une fiche de paie (opération rapport_conformite du contrat v1, D108, D109).

Assemble des réponses déterministes de calc/ ; aucun montant de convention n'est calculé ici, aucun texte généré.
"""

from .conformite import citations, rapport_conformite
from .rendu import texte_ar, texte_fr

__all__ = ["citations", "rapport_conformite", "texte_ar", "texte_fr"]
