"""The `render.started` and `render.finished` records (render-guard).

Every guarded render emits both as structured log records carrying the package,
version, kind, tier, frames, resolution, engine and estimate — and, at the end,
the actual seconds and outcome. When tracing is configured the same values go
to Langfuse as an event; tracing never affects the render.
"""

from __future__ import annotations

import logging
from typing import Any

from app.observability.langfuse import Tracing
from app.render.guard import RenderQuote

logger = logging.getLogger("app")


def _fields(quote: RenderQuote) -> dict[str, Any]:
    return {
        "package_id": quote.package_id,
        "version": quote.version,
        "kind": quote.kind,
        "room": quote.room,
        "tier": quote.tier.name,
        "frames": quote.frames,
        "resolution": quote.tier.resolution,
        "engine": quote.tier.engine,
        "estimate_seconds": round(quote.estimate_seconds, 3),
    }


def log_render_started(quote: RenderQuote, *, tracing: Tracing | None = None) -> None:
    fields = _fields(quote)
    logger.info("render.started", extra={"context": fields})
    if tracing is not None:
        tracing.record_render(event="started", **fields)


def log_render_finished(
    quote: RenderQuote,
    *,
    actual_seconds: float,
    outcome: str,
    error: str | None = None,
    tracing: Tracing | None = None,
) -> None:
    fields = {
        **_fields(quote),
        "actual_seconds": round(actual_seconds, 3),
        "outcome": outcome,
        **({"error": error} if error else {}),
    }
    logger.info("render.finished", extra={"context": fields})
    if tracing is not None:
        tracing.record_render(event="finished", **fields)
