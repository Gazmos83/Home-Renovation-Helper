"""The render estimate and its wording (render-guard).

    seconds ≈ frames × megapixels × engine_multiplier × benchmark_seconds_per_megapixel

Eevee is the benchmarked base (multiplier 1); Cycles starts at 30 and is
calibrated from the first approved final (`calibrated_multiplier`).
"""

from __future__ import annotations

from typing import Final

from app.render.tiers import Tier

DEFAULT_CYCLES_MULTIPLIER: Final = 30.0


def engine_multiplier(tier: Tier, cycles_multiplier: float) -> float:
    return cycles_multiplier if tier.engine == "cycles" else 1.0


def estimate_seconds(
    tier: Tier,
    seconds_per_megapixel: float,
    cycles_multiplier: float = DEFAULT_CYCLES_MULTIPLIER,
    *,
    frames: int | None = None,
) -> float:
    """`frames` overrides the tier's count (a still is one frame)."""
    return (
        (tier.frames if frames is None else frames)
        * tier.megapixels
        * engine_multiplier(tier, cycles_multiplier)
        * seconds_per_megapixel
    )


def remote_estimate_seconds(
    tier: Tier, seconds_per_megapixel: float, overhead_seconds: float, *, frames: int | None = None
) -> float:
    """A `final` on the render server:
    frames × megapixels × the server's seconds per megapixel + its fixed overhead."""
    return (
        (tier.frames if frames is None else frames) * tier.megapixels * seconds_per_megapixel
        + overhead_seconds
    )


def calibrated_multiplier(
    tier: Tier, actual_seconds: float, seconds_per_megapixel: float, *, frames: int | None = None
) -> float:
    """The Cycles multiplier an actual run implies:
    actual ÷ (frames × megapixels × benchmark)."""
    base = (tier.frames if frames is None else frames) * tier.megapixels * seconds_per_megapixel
    if base <= 0 or actual_seconds <= 0:
        raise ValueError("a calibration needs a positive actual duration and benchmark")
    return actual_seconds / base


def describe(seconds: float) -> str:
    """Human terms: seconds under a minute, otherwise minutes, rounded."""
    if seconds < 59.5:
        whole = max(1, round(seconds))
        return f"about {whole} second{'s' if whole != 1 else ''}"
    minutes = round(seconds / 60)
    return f"about {minutes} minute{'s' if minutes != 1 else ''}"
