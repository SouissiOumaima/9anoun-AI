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
    """Same logic as the CLI; invalid request -> HTTP 422 + status=error."""
    response = handle(request)
    return JSONResponse(response, status_code=422 if response["status"] == "error" else 200)
