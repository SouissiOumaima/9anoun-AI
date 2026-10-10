"""Contract handler of DS2: validated JSON in -> validated JSON out.

Sprint 1 = mock mode: every valid request receives the demo response
(data/mock_cards/legal_retrieval_search_demo.json), truncated to top_k ARTICLES.

Rule "all versions" (decided with the user, D-DS2-7): for every relevant article
ALL its known versions are returned (in force, modified, repealed), so a lawyer
or accountant always sees the old AND the new text. top_k counts articles
(version_group), never individual versions.
The real hybrid search will replace `_search` without changing the contract.
"""

from __future__ import annotations

import copy
import json
from functools import cache, lru_cache
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker

CONTRACT_VERSION = "legal_retrieval.v0"

# handler.py -> contract -> legal_retrieval -> src -> <repo root>
_REPO_ROOT = Path(__file__).resolve().parents[3]
_MOCK_DIR = _REPO_ROOT / "data" / "mock_cards"
_SCHEMA_DIR = _MOCK_DIR / "schemas"


@cache
def _validator(name: str) -> Draft202012Validator:
    """Load a schema once; FormatChecker makes "format": "date" strict."""
    path = _SCHEMA_DIR / f"legal_retrieval_{name}.v0.schema.json"
    schema = json.loads(path.read_text(encoding="utf-8"))
    return Draft202012Validator(schema, format_checker=FormatChecker())


def validation_errors(payload: dict[str, Any], name: str) -> list[str]:
    """Return readable schema errors ([] when the payload is valid)."""
    return [
        f"{'/'.join(map(str, e.absolute_path)) or '<root>'}: {e.message}"
        for e in _validator(name).iter_errors(payload)
    ]


@lru_cache(maxsize=1)
def _demo() -> dict[str, Any]:
    """Demo request/response pair shared with the other roles."""
    data: dict[str, Any] = json.loads(
        (_MOCK_DIR / "legal_retrieval_search_demo.json").read_text(encoding="utf-8"))
    return data


def keep_top_k_articles(results: list[dict[str, Any]], top_k: int) -> list[dict[str, Any]]:
    """Keep the first `top_k` articles WITH ALL THEIR VERSIONS.

    Truncating the flat list would drop old versions (v1) of a kept article.
    """
    groups: list[str] = []  # article order = order of first appearance
    for result in results:
        if result["version_group"] not in groups:
            groups.append(result["version_group"])
    kept = set(groups[:top_k])
    return [r for r in results if r["version_group"] in kept]


def _search(request: dict[str, Any]) -> list[dict[str, Any]]:
    """MOCK search: fixed results. Replaced by hybrid retrieval in Sprint 4."""
    results: list[dict[str, Any]] = copy.deepcopy(_demo()["response"]["results"])
    return keep_top_k_articles(results, request.get("top_k", 10))


def handle(request: dict[str, Any]) -> dict[str, Any]:
    """Validate the request, run the search, validate and return the response.

    Never raises on bad input: returns status="error" so DS1 can fail safely.
    """
    errors = validation_errors(request, "search_request")
    if errors:
        response: dict[str, Any] = {
            "contract_version": CONTRACT_VERSION,
            "request_id": request.get("request_id") if isinstance(request, dict) else None,
            "status": "error", "mode": "mock",
            "error": "; ".join(errors), "results": [],
        }
    else:
        results = _search(request)
        response = {
            "contract_version": CONTRACT_VERSION,
            "request_id": request.get("request_id"),
            # Citation or silence: no result -> explicit no_decisive_source
            "status": "success" if results else "no_decisive_source",
            "mode": "mock", "error": None, "results": results,
        }
    out_errors = validation_errors(response, "search_response")
    if out_errors:  # our own bug: never send an invalid message to others
        raise RuntimeError(f"DS2 produced an invalid response: {out_errors}")
    return response
