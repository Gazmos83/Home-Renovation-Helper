"""The first-launch benchmark (render-guard design decision 3).

Builds the shipped fold-down-desk template into `<render root>/benchmark/build`
(once), renders one Eevee frame of it at 1000 × 1000, and stores the frame's own
render seconds as seconds-per-megapixel. Run only on the owner's explicit
request — the developer-gated route or `python -m app.render.benchmark` — never
at startup, and re-runnable: a new value replaces the old one.

The frame is the one render outside the tiers; it still goes through the guard
(`authorise_benchmark`) and the launcher's ticket check.
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
from app.blender.runner import (
    BUILD_GENERATOR,
    STILL_GENERATOR,
    launch_guarded,
    launch_unguarded,
    safe_error,
)
from app.blender.schemas import CustomBuildSpec
from app.render.benchmark_store import Benchmark, write_benchmark
from app.render.guard import BENCHMARK_PACKAGE_ID, BENCHMARK_TIER, authorise_benchmark

TEMPLATE = Path(__file__).resolve().parents[2] / "fixtures/packages/templates/fold-down-desk.json"


class BenchmarkFailed(RuntimeError):
    """The benchmark could not be measured. The message is safe to show."""


def _build_spec(path: Path) -> None:
    document = json.loads(TEMPLATE.read_text(encoding="utf-8"))
    normalised = CustomBuildSpec.model_validate(document).model_dump(mode="json")
    path.write_text(json.dumps(normalised), encoding="utf-8")


def _blender_version(blender_bin: Path, result_dir: Path) -> str | None:
    try:
        scene = json.loads((result_dir / "scene.json").read_text(encoding="utf-8"))
        return scene.get("blender_version")
    except (FileNotFoundError, json.JSONDecodeError):
        return None


async def ensure_reference_build(
    *,
    root: Path,
    blender_bin: Path,
    timeout: float,
    semaphore: asyncio.Semaphore,
    launch: Launch = subprocess_launch,
) -> tuple[Path, Path]:
    """Build the reference package once (a build, not a render); `(benchmark folder, build folder)`."""
    folder = storage.resolve(root, storage.BENCHMARK_DIRNAME)
    folder.mkdir(parents=True, exist_ok=True)
    build = folder / "build"
    if not (build / "model.blend").is_file():
        shutil.rmtree(build, ignore_errors=True)
        storage.sweep_stale_siblings(build)
        spec = folder / ".spec.json"
        _build_spec(spec)
        try:
            built = await launch_unguarded(
                [str(blender_bin), "--background", "--python", str(BUILD_GENERATOR), "--",
                 "--spec", str(spec), "--out", str(build)],
                cwd=folder, timeout=timeout, semaphore=semaphore, launch=launch,
            )
        finally:
            spec.unlink(missing_ok=True)
        if built.exit_code != 0 or built.timed_out:
            raise BenchmarkFailed(f"the reference build failed: {safe_error(built.stderr_tail, root)}")
    return folder, build


async def run_benchmark(
    engine: Engine,
    *,
    root: Path,
    blender_bin: Path,
    timeout: float,
    semaphore: asyncio.Semaphore,
    launch: Launch = subprocess_launch,
) -> Benchmark:
    folder, build = await ensure_reference_build(
        root=root, blender_bin=blender_bin, timeout=timeout, semaphore=semaphore, launch=launch
    )
    frame = folder / "frame"

    shutil.rmtree(frame, ignore_errors=True)
    storage.sweep_stale_siblings(frame)
    ticket = authorise_benchmark()
    started = time.perf_counter()
    rendered = await launch_guarded(
        ticket,
        expected=(BENCHMARK_PACKAGE_ID, 1, "still", False),
        argv=[str(blender_bin), "--background", "--python", str(STILL_GENERATOR), "--",
              "--blend", str(build / "model.blend"), "--out", str(frame),
              "--tier-frames", str(BENCHMARK_TIER.frames),
              "--tier-resolution", str(BENCHMARK_TIER.resolution),
              "--tier-engine", BENCHMARK_TIER.blender_engine],
        cwd=folder, timeout=timeout, semaphore=semaphore, launch=launch,
    )
    elapsed = time.perf_counter() - started
    if rendered.exit_code != 0 or rendered.timed_out:
        raise BenchmarkFailed(f"the benchmark frame failed: {safe_error(rendered.stderr_tail, root)}")

    # Prefer the frame's own render time: Blender's start-up and file load would
    # otherwise be billed to every future frame.
    seconds = elapsed
    try:
        scene = json.loads((frame / "scene.json").read_text(encoding="utf-8"))
        seconds = float(scene.get("render_seconds") or elapsed)
    except (FileNotFoundError, json.JSONDecodeError, TypeError, ValueError):
        pass
    if seconds <= 0:
        raise BenchmarkFailed("the benchmark frame reported no render time")
    return write_benchmark(
        engine,
        seconds / BENCHMARK_TIER.megapixels,
        blender_version=_blender_version(blender_bin, frame),
    )


def main() -> int:
    """`python -m app.render.benchmark`: measure and store the benchmark."""
    from app.config import get_settings
    from app.db.session import make_engine

    settings = get_settings()
    if not settings.generation_enabled:
        print(f"Blender is not available at {settings.blender_bin}")
        return 1
    engine = make_engine(settings.database_url)
    try:
        result = asyncio.run(
            run_benchmark(
                engine,
                root=settings.render_root,
                blender_bin=settings.blender_bin,
                timeout=settings.blender_timeout_seconds,
                semaphore=asyncio.Semaphore(1),
            )
        )
    except BenchmarkFailed as error:
        print(f"benchmark failed: {error}")
        return 1
    finally:
        engine.dispose()
    print(f"benchmark: {result.seconds_per_megapixel:.2f} seconds per megapixel")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
