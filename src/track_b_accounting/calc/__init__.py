"""Fonctions de calcul de paie : chaque montant est renvoyé avec ses sources (règle « Citation ou Silence »).

Règles : docs/DECISIONS.md (D6). Aucune donnée n'est saisie ici : tout vient de data/processed/.
"""
from .models import Citation, Refus, Result
from .primes import prime
from .salary import degre_from_anciennete, salaire_base, table_applicable
from .smig_calc import smig

__all__ = [
    "Citation", "Refus", "Result",
    "degre_from_anciennete", "table_applicable", "salaire_base",
    "prime", "smig",
]
