"""HTTP wrapper of the contract (for real HTTP proof and DS1 integration).

    uvicorn src.legal_retrieval.contract.api:app --port 8002
"""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import Body, FastAPI
from fastapi.responses import JSONResponse

from ..corpus.store import load_store
from .get_article import get_article
from .handler import CONTRACT_VERSION, handle

CONTRACT_LAYER = "legal_retrieval.contract"  # computed_by of a contract refusal

app = FastAPI(title="DS2 Legal Retrieval", version=CONTRACT_VERSION)


@app.get("/health")
def health() -> dict[str, str]:
    """Liveness probe."""
    # search and get_article are live as soon as the corpus is ingested on this machine
    mode = "live" if load_store() is not None else "mock"
    return {"status": "ok", "contract_version": CONTRACT_VERSION, "mode": mode,
            "get_article_mode": mode}


@app.post("/legal/search")
def search(request: Annotated[dict[str, Any], Body()]) -> JSONResponse:
    """Same logic as the CLI.

    HTTP code: 200 for ok and for every BUSINESS refusal (a valid answer,
    e.g. SOURCE_MANQUANTE), 422 only when the CONTRACT layer refused the
    request (computed_by = "legal_retrieval.contract"), 500 for "erreur".
    Based on computed_by, not on the refusal code (review of PR #6, DS5): a
    business refusal that one day uses PARAM_INVALIDE must stay a 200.
    """
    response = handle(request)
    return JSONResponse(response, status_code=_http_code(response))


def _http_code(response: dict[str, Any]) -> int:
    """200 ok / business refusal, 422 contract refusal, 500 erreur (same for all routes)."""
    if response["status"] == "erreur":
        return 500
    if response["status"] == "refus" and response["computed_by"] == CONTRACT_LAYER:
        return 422  # the caller sent a non-conforming message
    return 200


@app.post("/legal/article")
def article(request: Annotated[dict[str, Any], Body()]) -> JSONResponse:
    """get_article (D22): one article by reference, all its versions."""
    response = get_article(request)
    return JSONResponse(response, status_code=_http_code(response))
