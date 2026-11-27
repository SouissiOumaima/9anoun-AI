"""Tests de la normalisation des valeurs lues (étape 2 de l'extracteur DS3)."""

from __future__ import annotations

import pytest

from src.document_intelligence.extraction.normalize import (
    EMPLOYMENT_STATUSES,
    PAY_MODES,
    month_period,
    normalize_amount,
    normalize_category,
    normalize_date,
    normalize_enum,
    normalize_hours,
)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("424,100", "424.100"),
        ("424.100", "424.100"),
        ("1 275,000 DT", "1275.000"),
        ("1.275,000", "1275.000"),
        ("1,275.000", "1275.000"),
        ("56", "56.000"),
        ("56,5", "56.500"),
        ("-12,000", "-12.000"),
        ("٤٢٤٫١٠٠", "424.100"),
        ("424,100 د.ت", "424.100"),
    ],
)
def test_amount_is_converted(raw: str, expected: str) -> None:
    assert normalize_amount(raw) == expected


@pytest.mark.parametrize("raw", ["1.275.000", "424,1000", "424,", "abc", "", "12a,000", "1.27,000"])
def test_ambiguous_amount_gives_none(raw: str) -> None:
    assert normalize_amount(raw) is None


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("01/09/2019", "2019-09-01"),
        ("1-9-2019", "2019-09-01"),
        ("01.09.2019", "2019-09-01"),
        ("2019-09-01", "2019-09-01"),
        ("٠١/٠٩/٢٠١٩", "2019-09-01"),
    ],
)
def test_date_is_converted(raw: str, expected: str) -> None:
    assert normalize_date(raw) == expected


@pytest.mark.parametrize("raw", ["01/09/19", "31/02/2026", "septembre 2019", ""])
def test_impossible_or_ambiguous_date_gives_none(raw: str) -> None:
    assert normalize_date(raw) is None


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("Mars 2026", ("2026-03-01", "2026-03-31")),
        ("مارس 2026", ("2026-03-01", "2026-03-31")),
        ("02/2024", ("2024-02-01", "2024-02-29")),
        ("décembre 2025", ("2025-12-01", "2025-12-31")),
        ("Brumaire 2026", None),
    ],
)
def test_month_period(raw: str, expected: tuple[str, str] | None) -> None:
    assert month_period(raw) == expected


@pytest.mark.parametrize(
    ("raw", "expected"),
    [("3", "3"), ("1 ب", "1B"), ("1 أ", "1A"), ("2b", "2B"), ("١٢", "12"), ("1 X", None), ("cat", None)],
)
def test_category(raw: str, expected: str | None) -> None:
    assert normalize_category(raw) == expected


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("208 h", "48"),
        ("208h00", "48"),
        ("173,33 h", "40"),
        ("173.33 heures", "40"),
        ("173,33 س", "40"),
        ("48", "48"),
        ("40 h", "40"),
        ("195 h", None),
        ("à temps partiel", None),
        # unité imprimée (bulletin DS4, contrat v2 : « 208 h/mois → 48 ») : respectée, jamais devinée
        ("48 h/semaine", "48"),
        ("40 heures par semaine", "40"),
        ("48h/sem", "48"),
        ("48 h hebdomadaires", "48"),
        ("208 h/mois", "48"),
        ("173,33 h / mois", "40"),
        ("208 heures par mois", "48"),
        ("48 ساعة في الأسبوع", "48"),
        ("208 ساعة في الشهر", "48"),
        ("42 h/semaine", None),
        ("208 h/semaine", None),
        ("48 h/mois", None),
        ("40 h/semaine, 173,33 h/mois", None),
    ],
)
def test_hours_regime(raw: str, expected: str | None) -> None:
    assert normalize_hours(raw) == expected


def test_enums_only_accept_printed_words() -> None:
    assert normalize_enum("Mensuel", PAY_MODES) == "mensuel"
    assert normalize_enum("شهري", PAY_MODES) == "mensuel"
    assert normalize_enum("قار", EMPLOYMENT_STATUSES) == "permanent"
    assert normalize_enum("CDD", EMPLOYMENT_STATUSES) is None  # interprétation : pas pour DS3
