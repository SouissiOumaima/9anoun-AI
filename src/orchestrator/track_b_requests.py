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
    """Return a schema-valid Track B request or fail before calling DS5.

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
    error = best_match(_validator().iter_errors(request))
    if error is not None:
        field = "/".join(str(part) for part in error.absolute_path) or "request"
        raise ToolContractError(f"Track B request is invalid at {field}: {error.message}")
    return request
