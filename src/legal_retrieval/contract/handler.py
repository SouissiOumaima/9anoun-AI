"""Contract handler of DS2: validated JSON in -> validated JSON out.

The response follows the team envelope src/shared/schemas/common.v0.schema.json:
  status "ok"     -> >= 1 article, one citation per article, refus = null
  status "refus"  -> no article, no citation, refus {code, message_fr, message_ar}
  status "erreur" -> unexpected incident, no article, erreur {type, message_fr, message_ar}

Two modes (field "mode" at the root of every response):
- "live": the corpus is ingested on this machine -> real search, article
  reference + BM25 (search/bm25.py, D26);
- "mock": no corpus -> the demo articles
  (data/mock_cards/legal_retrieval_search_demo.json), filtered by sector, then
  truncated to top_k ARTICLES. Never an invented article.

Rule "all versions" (decided with the user, D17): for every relevant article
ALL its known versions are returned (in force, modified, repealed), so a lawyer
or accountant always sees the old AND the new text. top_k counts articles
(version_group), never individual versions.
Dense embeddings + RRF will be added inside search/ without changing the contract.
"""

from __future__ import annotations

import copy
import json
from functools import cache
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker

from ..corpus.store import load_store
from ..search.bm25 import search_live

CONTRACT_VERSION = "legal_retrieval.v0"

# handler.py -> contract -> legal_retrieval -> src -> <repo root>
_REPO_ROOT = Path(__file__).resolve().parents[3]
_MOCK_DIR = _REPO_ROOT / "data" / "mock_cards"
_SCHEMA_DIR = _MOCK_DIR / "schemas"

# Bilingual messages (common.v0: every refus/erreur is given in FR and AR)
_MSG_NO_SOURCE = (
    "Aucun article suffisamment pertinent n'a été trouvé dans le corpus juridique.",
    "لم يتم العثور على أي فصل وثيق الصلة في المدونة القانونية.",
)
_MSG_BAD_REQUEST = (
    "Requête non conforme au contrat legal_retrieval.v0 : {details}",
    "الطلب غير مطابق لعقد legal_retrieval.v0.",
)
_MSG_INTERNAL = (
    "Incident technique dans le service de recherche juridique.",
    "خلل تقني في خدمة البحث القانوني.",
)


@cache
def _validator(name: str) -> Draft202012Validator:
    """Load a schema once; FormatChecker makes "format": "date" strict."""
    path = _SCHEMA_DIR / f"legal_retrieval_{name}.v0.schema.json"
    schema = json.loads(path.read_text(encoding="utf-8"))
    return Draft202012Validator(schema, format_checker=FormatChecker())


def validation_errors(payload: Any, name: str) -> list[str]:
    """Return readable schema errors ([] when the payload is valid)."""
    return [
        f"{'/'.join(map(str, e.absolute_path)) or '<root>'}: {e.message}"
        for e in _validator(name).iter_errors(payload)
    ]


@cache
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
    """MOCK search (no corpus on this machine).

    Sector filter: an article applies to the requested sector, or to all
    sectors (sector = null). A request on another sector gets no article.
    """
    results: list[dict[str, Any]] = copy.deepcopy(_demo()["response"]["results"])
    sector = request.get("sector")
    if sector is not None:
        results = [r for r in results if r["sector"] in (None, sector)]
    return keep_top_k_articles(results, request.get("top_k", 10))


def _envelope(request_id: Any, status: str, computed_by: str) -> dict[str, Any]:
    """Common fields of every response (common.v0 response_envelope)."""
    return {
        "contract_version": CONTRACT_VERSION,
        # common.v0: copy of request_id, null if it was not readable
        "request_id": request_id if isinstance(request_id, str) else None,
        "status": status,
        "citations": [],
        "refus": None,
        "computed_by": computed_by,
        "mode": "mock",
        "results": [],
    }


def _refus(request_id: Any, code: str, fr: str, ar: str, computed_by: str) -> dict[str, Any]:
    """A motivated refusal, always in French AND Arabic."""
    response = _envelope(request_id, "refus", computed_by)
    response["refus"] = {"code": code, "message_fr": fr, "message_ar": ar}
    return response


def handle(request: Any, *, live: bool = True) -> dict[str, Any]:
    """Validate the request, search, validate and return the response.

    Never raises: a bad request gives refus PARAM_INVALIDE (contract refusal,
    like Track B), an internal bug gives status "erreur". DS1 can fail safely.
    live=False forces the mock (demo files shared with the team stay stable).
    """
    request_id = request.get("request_id") if isinstance(request, dict) else None
    try:
        store = load_store() if live else None
        mode = "live" if store is not None else "mock"
        errors = validation_errors(request, "search_request")
        if errors:  # contract refusal: the caller sent a non-conforming message
            fr, ar = _MSG_BAD_REQUEST
            response = _refus(request_id, "PARAM_INVALIDE", fr.format(details="; ".join(errors)),
                              ar, "legal_retrieval.contract")
        else:
            computed_by = f"legal_retrieval.search.{mode}"
            results = search_live(request, store) if store is not None else _search(request)
            if not results:  # Citation or Silence: explicit refusal, never a guess
                response = _refus(request_id, "SOURCE_MANQUANTE", *_MSG_NO_SOURCE, computed_by)
            else:
                response = _envelope(request_id, "ok", computed_by)
                response["results"] = results
                response["citations"] = [r["citation"] for r in results]
        response["mode"] = mode
        out_errors = validation_errors(response, "search_response")
        if out_errors:  # our own bug: never send an invalid message to others
            raise RuntimeError(f"invalid DS2 response: {out_errors}")
        return response
    except Exception:  # noqa: BLE001 - last-resort guard, no internal detail leaked
        response = _envelope(request_id, "erreur", "legal_retrieval.contract")
        response["erreur"] = {"type": "INTERNE", "message_fr": _MSG_INTERNAL[0],
                              "message_ar": _MSG_INTERNAL[1]}
        return response
