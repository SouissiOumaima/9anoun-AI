"""Build and validate explicit DS1 → DS5 Track B v0 requests."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any, Mapping

from jsonschema import Draft202012Validator
from jsonschema.exceptions import best_match

from .tool_contracts import ToolContractError

_SCHEMA_PATH = Path(__file__).resolve().parents[2] / "data" / "mock_cards" / "schemas" / "track_b_request.v0.schema.json"


@lru_cache(maxsize=1)
def _validator() -> Draft202012Validator:
    schema = json.loads(_SCHEMA_PATH.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema)


def build_track_b_request(
    *, request_id: str, language: str, operation: str, params: Mapping[str, Any]
) -> dict[str, Any]:
    """Return a validated Track B request or fail before calling DS5.

    Values come from a validated form/card extraction; this function never
    infers sector, category, seniority, prime conditions, or dates.
    """

    request = {
        "contract_version": "track_b.v0",
        "request_id": request_id,
        "operation": operation,
        "params": dict(params),
        "lang": language,
    }
    errors = list(_validator().iter_errors(request))
    error = best_match(errors)
    # DS5 decides whether a population is mandatory for the selected grid.
    # The v0 schema still lists it as required, but forwarding this one missing
    # value lets a multi-population grid return its bilingual PARAM_INVALIDE
    # refusal and keeps DS1 compatible with a future single-population sector.
    if error is not None and _only_missing_population(errors, error, operation, params):
        error = None
    if error is not None:
        field = "/".join(str(part) for part in error.absolute_path) or "request"
        raise ToolContractError(f"Track B request is invalid at {field}: {error.message}")
    return request


def _only_missing_population(errors: list[Any], error: Any, operation: str, params: Mapping[str, Any]) -> bool:
    """Allow DS5 to apply its own population rule for a salary-base request."""

    return (
        operation == "salaire_base"
        and "population" not in params
        and len(errors) == 1
        and getattr(error, "validator", None) == "required"
        and list(getattr(error, "absolute_path", ())) == ["params"]
        and "population" in str(getattr(error, "message", ""))
    )
