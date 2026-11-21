"""Métriques de reconnaissance : CER (taux d'erreur caractère) et WER (taux d'erreur mot)."""

from __future__ import annotations

import unicodedata
from collections.abc import Sequence


def normalize(text: str) -> str:
    """Normalisation commune à la référence et à la prédiction : NFC, espaces fusionnés."""
    return " ".join(unicodedata.normalize("NFC", text).split())


def levenshtein(a: Sequence[str], b: Sequence[str]) -> int:
    """Distance d'édition (insertions, suppressions, substitutions) entre deux séquences."""
    if len(a) < len(b):
        a, b = b, a
    prev = list(range(len(b) + 1))
    for i, x in enumerate(a, 1):
        cur = [i]
        for j, y in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (x != y)))
        prev = cur
    return prev[-1]


def cer(refs: Sequence[str], hyps: Sequence[str]) -> float:
    """CER du corpus = somme des distances / somme des longueurs de référence (en caractères)."""
    errors = sum(levenshtein(normalize(r), normalize(h)) for r, h in zip(refs, hyps, strict=True))
    total = sum(len(normalize(r)) for r in refs)
    return errors / total if total else 0.0


def wer(refs: Sequence[str], hyps: Sequence[str]) -> float:
    """WER du corpus, mots séparés par les espaces."""
    errors = sum(levenshtein(normalize(r).split(), normalize(h).split()) for r, h in zip(refs, hyps, strict=True))
    total = sum(len(normalize(r).split()) for r in refs)
    return errors / total if total else 0.0


def exact_match(refs: Sequence[str], hyps: Sequence[str]) -> float:
    """Part des lignes lues sans aucune erreur."""
    if not refs:
        return 0.0
    return sum(normalize(r) == normalize(h) for r, h in zip(refs, hyps, strict=True)) / len(refs)
