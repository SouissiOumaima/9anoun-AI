"""HTTP wrapper of the contract (for real HTTP proof and DS1 integration).

    uvicorn src.legal_retrieval.contract.api:app --port 8002
"""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import Body, FastAPI
from fastapi.responses import JSONResponse

from .handler import CONTRACT_VERSION, handle

CONTRACT_LAYER = "legal_retrieval.contract"  # computed_by of a contract refusal

app = FastAPI(title="DS2 Legal Retrieval", version=CONTRACT_VERSION)


@app.get("/health")
def health() -> dict[str, str]:
    """Liveness probe."""
    return {"status": "ok", "contract_version": CONTRACT_VERSION, "mode": "mock"}


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
    code = 200
    if response["status"] == "erreur":
        code = 500
    elif response["status"] == "refus" and response["computed_by"] == CONTRACT_LAYER:
        code = 422  # the caller sent a non-conforming message
    return JSONResponse(response, status_code=code)
