"""Calibrating the Cycles multiplier from the first finished `final`."""

from __future__ import annotations

import logging

from sqlalchemy import Engine

from app.render.benchmark_store import (
    read_benchmark,
    read_remote_benchmark,
    stored_cycles_multiplier,
    write_cycles_multiplier,
    write_remote_benchmark,
)
from app.render.estimate import calibrated_multiplier
from app.render.guard import RenderQuote

logger = logging.getLogger("app")


def calibrate_remote(engine: Engine, quote: RenderQuote, render_seconds: float) -> float | None:
    """Replace the remote benchmark's seconds per megapixel with what the first
    approved remote final implies. `render_seconds` is the render alone: transfer and
    start-up are the benchmark's overhead. Later remote finals leave it alone."""
    benchmark = read_remote_benchmark(engine)
    if benchmark is None or benchmark.calibrated or render_seconds <= 0:
        return None
    base = quote.frames * quote.tier.megapixels
    if base <= 0:
        return None
    value = render_seconds / base
    write_remote_benchmark(
        engine, value, benchmark.overhead_seconds, calibrated=True, measured_at=benchmark.measured_at
    )
    logger.info("render.remote_calibrated", extra={"context": {"seconds_per_megapixel": round(value, 3)}})
    return value


def calibrate_after_render(engine: Engine, quote: RenderQuote, actual_seconds: float) -> float | None:
    """Replace the default multiplier of 30 with what the first Cycles render
    implies. Later finals leave it alone. Returns the new value, or `None`.

    A render on the render server calibrates the server's own benchmark instead and
    never the laptop's multiplier."""
    if quote.target == "remote":
        return calibrate_remote(engine, quote, actual_seconds)
    if quote.tier.engine != "cycles" or actual_seconds <= 0:
        return None
    if stored_cycles_multiplier(engine) is not None:
        return None
    benchmark = read_benchmark(engine)
    if benchmark is None:
        return None
    value = calibrated_multiplier(
        quote.tier, actual_seconds, benchmark.seconds_per_megapixel, frames=quote.frames
    )
    write_cycles_multiplier(engine, value)
    logger.info("render.cycles_calibrated", extra={"context": {"multiplier": round(value, 3)}})
    return value
