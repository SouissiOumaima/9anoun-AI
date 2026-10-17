"""Prepare explicit Track B parameters from an authorized active card."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from .card_repository import CardNotFoundError, MockCardRepository
from .models import ActiveContext, UserIdentity
from .sector_mapping import is_active_ds5_sector


@dataclass(frozen=True, slots=True)
class PreparedTrackBOperation:
    """Reviewable form values; callers execute only when ``missing`` is empty."""

    operation: str
    params: Mapping[str, Any]
    missing: tuple[str, ...] = ()

    @property
    def ready(self) -> bool:
        return not self.missing


class CardToTrackBMapper:
    """Read only the authorized active card; never infer missing payroll values."""

    def __init__(self, repository: MockCardRepository) -> None:
        self._repository = repository

    def prepare_salary_base(
        self, *, actor: UserIdentity, context: ActiveContext, employee_id: str, date: str | None
    ) -> PreparedTrackBOperation:
        card = self._repository.read_active_card(actor=actor, context=context)
        employees = card.data.get("employees", [])
        employee = next((item for item in employees if item.get("employee_id") == employee_id), None)
        if employee is None:
            raise CardNotFoundError("employee was not found in the active card")
        profile = employee.get("track_b_profile", {})
        values = {
            "secteur": _active_sector(profile.get("secteur")),
            "population": profile.get("population"),
            "categorie": profile.get("categorie"),
            "anciennete_annees": profile.get("anciennete_annees"),
            "date": date,
        }
        return _prepared("salaire_base", values)

    def prepare_prime(
        self,
        *,
        actor: UserIdentity,
        context: ActiveContext,
        code: str | None,
        date: str | None,
        extra_params: Mapping[str, Any] | None = None,
    ) -> PreparedTrackBOperation:
        card = self._repository.read_active_card(actor=actor, context=context)
        defaults = card.data.get("track_b_defaults", {})
        values: dict[str, Any] = {
            "secteur": _active_sector(defaults.get("secteur")),
            "code": code,
            "date": date,
        }
        # A card value can be displayed as a suggestion by the UI, but the
        # transport group remains an interpretation the user must confirm.
        if code == "prime_transport" and "groupe" not in (extra_params or {}):
            values["groupe"] = None
        values.update(extra_params or {})
        return _prepared("prime", values)


def _prepared(operation: str, values: Mapping[str, Any]) -> PreparedTrackBOperation:
    missing = tuple(key for key, value in values.items() if value is None or value == "")
    return PreparedTrackBOperation(operation, {key: value for key, value in values.items() if value is not None and value != ""}, missing)


def _active_sector(value: Any) -> str | None:
    """Use Card sector data only when D30 declares the DS5 grid active."""

    return value if isinstance(value, str) and is_active_ds5_sector(value) else None
