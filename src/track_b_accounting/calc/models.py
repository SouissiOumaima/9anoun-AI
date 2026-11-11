"""Types de retour des calculs : un montant n'existe jamais sans au moins une Citation."""
from __future__ import annotations

import datetime as dt
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from decimal import ROUND_HALF_UP, Decimal

MILLIME = Decimal("0.001")


def arrondi_millime(x: Decimal) -> Decimal:
    """Arrondi au millime, ROUND_HALF_UP (D6). Refuse tout autre type que Decimal."""
    if not isinstance(x, Decimal):
        raise TypeError(f"montant attendu en Decimal, reçu {type(x).__name__}")
    return x.quantize(MILLIME, rounding=ROUND_HALF_UP)


@dataclass(frozen=True)
class Citation:
    source_file: str              # PDF source (data/raw/pdf/...) — cité, jamais lu par les calculs
    page: int | None
    article: str | None
    data_file: str                # fichier vérifié réellement lu (data/processed/...)
    decision_ref: str             # entrée de docs/DECISIONS.md qui documente la vérification


@dataclass(frozen=True)
class Result:
    montant: Decimal
    unite: str
    detail: dict = field(default_factory=dict)
    citations: list[Citation] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not isinstance(self.montant, Decimal):
            raise TypeError(f"Result.montant doit être un Decimal, reçu {type(self.montant).__name__}")
        if not self.citations or not all(isinstance(c, Citation) for c in self.citations):
            raise ValueError("Result sans Citation interdit (règle « Citation ou Silence »)")


class Refus(Exception):
    """Refus motivé de calculer, bilingue FR/AR."""

    SOURCE_MANQUANTE = "SOURCE_MANQUANTE"
    HORS_SCOPE = "HORS_SCOPE"
    PARAM_INVALIDE = "PARAM_INVALIDE"
    CODES = (SOURCE_MANQUANTE, HORS_SCOPE, PARAM_INVALIDE)

    def __init__(self, code: str, message_fr: str, message_ar: str) -> None:
        if code not in self.CODES:
            raise ValueError(f"code de refus inconnu : {code!r}")
        super().__init__(f"[{code}] {message_fr}")
        self.code = code
        self.message_fr = message_fr
        self.message_ar = message_ar


def parse_date(date: object) -> dt.date:
    """Accepte un datetime.date (pas un datetime) ou une chaîne ISO AAAA-MM-JJ."""
    if isinstance(date, dt.datetime):
        raise Refus(Refus.PARAM_INVALIDE, "La date doit être un jour (AAAA-MM-JJ), sans heure.",
                    "يجب أن يكون التاريخ يومًا (سنة-شهر-يوم) دون توقيت.")
    if isinstance(date, dt.date):
        return date
    if isinstance(date, str):
        try:
            return dt.date.fromisoformat(date)
        except ValueError:
            pass
    raise Refus(Refus.PARAM_INVALIDE, f"Date invalide : {date!r} (format attendu AAAA-MM-JJ).",
                f"تاريخ غير صالح: {date!r} (الصيغة المطلوبة سنة-شهر-يوم).")


def plus_recent_avant(items: Iterable[dict], date: dt.date,
                      cle: Callable[[dict], str] = lambda x: x["effective_date"]) -> dict | None:
    """Élément dont la date d'effet est la plus récente ≤ date ; None si la date précède tout."""
    candidats = [i for i in items if dt.date.fromisoformat(cle(i)) <= date]
    return max(candidats, key=lambda i: dt.date.fromisoformat(cle(i)), default=None)
