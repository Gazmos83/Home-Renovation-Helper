"""The render server's benchmark (render-offload design decision 7).

One Cycles frame at 1000 × 1000 of the same reference package the laptop's benchmark
uses, rendered on the server through a guard-minted ticket. It stores the server's
seconds per megapixel and the fixed overhead a job spends outside the render
(upload, start-up, download). Run only on the developer's explicit request, never
automatically, and re-runnable: a new value replaces the old and clears the
calibration, so the next remote final calibrates again.
"""

from __future__ import annotations

import asyncio
import json
import shutil
import time
from pathlib import Path

from sqlalchemy import Engine

from app.blender import storage
from app.blender.launch import Launch, subprocess_launch
from app.blender.runner import _run_on_server, safe_error
from app.render.benchmark import BenchmarkFailed, ensure_reference_build
from app.render.benchmark_store import RemoteBenchmark, write_remote_benchmark
from app.render.guard import (
    BENCHMARK_PACKAGE_ID,
    REMOTE_BENCHMARK_TIER,
    RenderRefused,
    authorise_remote_benchmark,
)
from app.render.offload.runtime import OffloadRuntime, ensure_server


async def run_remote_benchmark(
    engine: Engine,
    *,
    runtime: OffloadRuntime | None,
    root: Path,
    blender_bin: Path,
    timeout: float,
    semaphore: asyncio.Semaphore,
    launch: Launch = subprocess_launch,
) -> RemoteBenchmark:
    try:
        await ensure_server(runtime, launch)
    except RenderRefused as refusal:
        raise BenchmarkFailed(refusal.reason) from None
    assert runtime is not None
    folder, build = await ensure_reference_build(
        root=root, blender_bin=blender_bin, timeout=timeout, semaphore=semaphore, launch=launch
    )
    stage = folder / "remote-frame"
    shutil.rmtree(stage, ignore_errors=True)
    storage.sweep_stale_siblings(stage)

    ticket = authorise_remote_benchmark()
    started = time.perf_counter()
    try:
        result, times = await _run_on_server(
            ticket,
            expected=(BENCHMARK_PACKAGE_ID, 1, "still", False, "piece", "model"),
            offload=runtime, launch=launch, blend=build / "model.blend", folder=folder,
            scene_document=None, stage=stage, limit=timeout * REMOTE_BENCHMARK_TIER.timeout_multiplier,
            begin=lambda: None,
        )
        elapsed = time.perf_counter() - started
        if result.exit_code != 0 or result.timed_out or times is None:
            raise BenchmarkFailed(
                f"the benchmark frame failed on the render server: {safe_error(result.stderr_tail, root)}"
            )
        # Prefer the frame's own render time: Blender's start-up and file load belong to the overhead.
        seconds = times.render_seconds
        try:
            scene = json.loads((stage / "scene.json").read_text(encoding="utf-8"))
            seconds = float(scene.get("render_seconds") or seconds)
        except (FileNotFoundError, json.JSONDecodeError, TypeError, ValueError):
            pass
    finally:
        shutil.rmtree(stage, ignore_errors=True)
    if seconds <= 0:
        raise BenchmarkFailed("the benchmark frame reported no render time")
    return write_remote_benchmark(
        engine, seconds / REMOTE_BENCHMARK_TIER.megapixels, max(0.0, elapsed - seconds)
    )
