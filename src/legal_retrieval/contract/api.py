"""HTTP wrapper of the contract (for real HTTP proof and DS1 integration).

    uvicorn src.legal_retrieval.contract.api:app --port 8002
"""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import Body, FastAPI
from fastapi.responses import JSONResponse

from .handler import CONTRACT_VERSION, handle

app = FastAPI(title="DS2 Legal Retrieval", version=CONTRACT_VERSION)


@app.get("/health")
def health() -> dict[str, str]:
    """Liveness probe."""
    return {"status": "ok", "contract_version": CONTRACT_VERSION, "mode": "mock"}


@app.post("/legal/search")
def search(request: Annotated[dict[str, Any], Body()]) -> JSONResponse:
    """Same logic as the CLI.

    HTTP code: 200 for ok and SOURCE_MANQUANTE (a valid answer: "no source"),
    422 for a contract refusal (PARAM_INVALIDE), 500 for status "erreur".
    """
    response = handle(request)
    code = 200
    if response["status"] == "erreur":
        code = 500
    elif response["refus"] and response["refus"]["code"] == "PARAM_INVALIDE":
        code = 422
    return JSONResponse(response, status_code=code)
