"""The unauthenticated health endpoint (service-foundation).

Reports whether the process is up and whether its database accepts a trivial
query, so "process down" and "process up, database down" are distinguishable.
The body never carries a stack trace or a connection string.
"""

from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from app.db.session import database_reachable

router = APIRouter(tags=["operations"])

HEALTHY = "ok"


@router.get("/health")
def health(request: Request) -> JSONResponse:
    reachable = database_reachable(request.app.state.engine)
    return JSONResponse(
        status_code=200 if reachable else 503,
        content={
            "service": HEALTHY,
            "database": "reachable" if reachable else "unreachable",
        },
    )
