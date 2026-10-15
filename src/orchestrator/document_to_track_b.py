"""Safe DS3-v2 to DS5 prefill generation owned by DS1.

The output is a reviewable *candidate*, never an automatic DS5 call.  Facts
must have been explicitly selected by the user in DS1, while sector comes only
from the Company Card and population/prime interpretation remain user inputs.
"""

from __future__ import annotations

from typing import Any, Mapping

from .seniority import SeniorityError, calculate_seniority_years


def build_payroll_prefill(
    *, fields: Mapping[str, Mapping[str, Any]], confirmed_fields: set[str], company_sector: str | None,
) -> dict[str, Any]:
    """Build non-executable DS5 candidates using only confirmed DS3 facts."""

    def value(name: str) -> str | None:
        item = fields.get(name)
        raw = item.get("value") if isinstance(item, Mapping) and name in confirmed_fields else None
        return raw if isinstance(raw, str) and raw else None

    date, mode, hours = value("period_start"), value("pay_mode"), value("work_hours_regime")
    out: dict[str, Any] = {"candidates": [], "required_user_inputs": []}
    if date and mode and hours and hours in {"40", "48"}:
        out["candidates"].append({
            "operation": "smig", "params": {"mode": mode, "regime_heures": int(hours), "date": date},
            "ready": True,
        })

    category, hire_date = value("category"), value("hire_date")
    base_params: dict[str, Any] = {}
    if company_sector:
        base_params["secteur"] = company_sector
    if category:
        base_params["categorie"] = category
    if date:
        base_params["date"] = date
    proposed_values: dict[str, str] = {}
    if hire_date and date:
        try:
            proposed_values["anciennete_annees"] = str(calculate_seniority_years(
                hire_date=hire_date, reference_date=date,
            ))
        except SeniorityError:
            pass
    missing = [key for key in ("secteur", "population", "categorie", "anciennete_annees", "date") if key not in base_params]
    if "population" not in missing:
        raise AssertionError("population is an interpretation and must not be inferred from DS3")
    out["candidates"].append({
        "operation": "salaire_base", "params": base_params, "ready": False, "missing": missing,
        "proposed_values": proposed_values,
    })
    prime_params = {"secteur": company_sector, "date": date}
    if all(isinstance(value, str) and value for value in prime_params.values()):
        out["candidates"].append({
            "operation": "prime", "params": prime_params, "ready": False,
            "missing": ["code", "groupe (si la prime le requiert)"],
        })
    out["required_user_inputs"] = [
        "population (suggestion DS1 à confirmer)",
        "code de prime et groupe, si une prime est demandée",
    ]
    return out
