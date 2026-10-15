"""Deterministic seniority calculation for DS1-prepared payroll requests."""

from __future__ import annotations

from datetime import date
from decimal import Decimal, ROUND_DOWN


class SeniorityError(ValueError):
    """A documented hire date and an explicit reference date are required."""


def calculate_seniority_years(*, hire_date: str, reference_date: str) -> Decimal:
    """Return elapsed calendar years, preserving exact anniversary boundaries.

    The result is truncated to six decimal places.  If it is exactly a grid
    boundary, DS5 retains the final refusal/clarification decision; DS1 never
    shifts it by a day to force a calculation.
    """

    try:
        hired = date.fromisoformat(hire_date)
        reference = date.fromisoformat(reference_date)
    except (TypeError, ValueError) as error:
        raise SeniorityError("hire_date and reference_date must use ISO YYYY-MM-DD") from error
    if hired > reference:
        raise SeniorityError("hire_date cannot be after reference_date")
    anniversary_year = reference.year
    try:
        anniversary = hired.replace(year=anniversary_year)
    except ValueError:  # 29 February in a non-leap reference year
        anniversary = date(anniversary_year, 2, 28)
    completed_years = anniversary_year - hired.year
    if anniversary > reference:
        completed_years -= 1
        try:
            anniversary = hired.replace(year=anniversary_year - 1)
        except ValueError:
            anniversary = date(anniversary_year - 1, 2, 28)
    try:
        next_anniversary = hired.replace(year=anniversary.year + 1)
    except ValueError:
        next_anniversary = date(anniversary.year + 1, 2, 28)
    fraction = Decimal((reference - anniversary).days) / Decimal((next_anniversary - anniversary).days)
    # DS5's agreed rule is strict: never round upward into a higher grid band.
    return (Decimal(completed_years) + fraction).quantize(Decimal("0.000001"), rounding=ROUND_DOWN)
