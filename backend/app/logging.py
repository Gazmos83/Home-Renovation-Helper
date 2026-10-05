"""Structured JSON logging.

One machine-parseable record per request, and a record for every unhandled
error. Langfuse tracing sits on top of this; these records stay the transport
for HTTP and, later, Blender-job events.
"""

from __future__ import annotations

import json
import logging
import sys
import time
from datetime import UTC, datetime
from typing import Any

from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.types import ASGIApp

logger = logging.getLogger("app")

_RESERVED = frozenset(logging.LogRecord("", 0, "", 0, "", (), None).__dict__)


class JsonFormatter(logging.Formatter):
    """Render a record as one line of JSON, merging anything in `context`."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(record.created, UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        context = getattr(record, "context", None)
        if isinstance(context, dict):
            payload.update(context)
        if record.exc_info and record.exc_info[0] is not None:
            payload["error_type"] = record.exc_info[0].__name__
        return json.dumps(payload, default=str)


def configure_logging(level: int = logging.INFO) -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())

    root = logging.getLogger()
    for existing in list(root.handlers):
        root.removeHandler(existing)
    root.addHandler(handler)
    root.setLevel(level)

    # Let uvicorn's records flow through the same formatter instead of its own.
    for name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        uvicorn_logger = logging.getLogger(name)
        uvicorn_logger.handlers.clear()
        uvicorn_logger.propagate = True


async def log_requests(request: Request, call_next: Any) -> Response:
    """Emit exactly one record per request, whether it succeeds or raises."""
    started = time.perf_counter()
    try:
        response = await call_next(request)
    except Exception as error:
        logger.exception(
            "request failed",
            extra={
                "context": {
                    "method": request.method,
                    "path": request.url.path,
                    "status": 500,
                    "duration_ms": round((time.perf_counter() - started) * 1000, 3),
                    "error_type": type(error).__name__,
                }
            },
        )
        raise
    logger.info(
        "request",
        extra={
            "context": {
                "method": request.method,
                "path": request.url.path,
                "status": response.status_code,
                "duration_ms": round((time.perf_counter() - started) * 1000, 3),
            }
        },
    )
    return response


async def handle_unexpected_error(request: Request, exc: Exception) -> JSONResponse:
    """Return a generic body; the detail belongs in the log, not the response."""
    logger.error(
        "unhandled error",
        extra={
            "context": {
                "path": request.url.path,
                "error_type": type(exc).__name__,
            }
        },
    )
    return JSONResponse(
        status_code=500, content={"detail": "Internal server error"}
    )


def install(app: ASGIApp) -> None:
    """Attach request logging and the catch-all error handler."""
    app.middleware("http")(log_requests)  # type: ignore[attr-defined]
    app.add_exception_handler(Exception, handle_unexpected_error)  # type: ignore[attr-defined]
