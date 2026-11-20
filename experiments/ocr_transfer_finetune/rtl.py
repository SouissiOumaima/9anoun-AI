"""Ordre logique <-> ordre visuel des lignes arabes, pour les poids pré-entraînés PP-OCRv5 arabe."""

from __future__ import annotations


def is_arabic(c: str) -> bool:
    return "؀" <= c <= "ۿ" or "ݐ" <= c <= "ݿ"


def flip_rtl(text: str) -> str:
    """Passe de l'ordre logique à l'ordre visuel d'une ligne arabe, et inversement (involution).

    Même principe que `pred_reverse` de PaddleOCR : chaque lettre arabe est un jeton, chaque suite de
    caractères non arabes (montant « 424.100 », mot français, espaces) reste un bloc, puis on inverse
    l'ordre des jetons. Différence : PaddleOCR coupe les blocs sur les lettres accentuées (« é ») ; ici
    tout caractère non arabe reste dans son bloc. Une ligne sans lettre arabe n'est pas modifiée.
    """
    if not any(is_arabic(c) for c in text):
        return text
    tokens: list[str] = []
    run = ""
    for c in text:
        if is_arabic(c):
            if run:
                tokens.append(run)
                run = ""
            tokens.append(c)
        else:
            run += c
    if run:
        tokens.append(run)
    return "".join(reversed(tokens))
