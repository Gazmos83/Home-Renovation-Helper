"""render-guard: the first-launch benchmark, with a fake launcher and for real."""

from __future__ import annotations

import asyncio
import json
from collections.abc import Iterator
from pathlib import Path

import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.blender import storage
from app.blender.launch import LaunchResult
from app.blender.runner import launch_guarded, launch_unguarded
from app.db.session import make_engine
from app.render import benchmark_store as store
from app.render.benchmark import BenchmarkFailed, run_benchmark
from app.render.guard import RenderNotAuthorised, authorise_benchmark
from tests.blender_fakes import (
    arg_value,
    fake_failure_launch,
    out_dir_from_argv,
    png_bytes,
    write_build_files,
)

BIN = Path("/fake/blender")


@pytest.fixture
def engine(migrated_database: str) -> Iterator:
    engine = make_engine(migrated_database)
    with Session(engine) as session:
        session.execute(text("DELETE FROM operator_settings WHERE key LIKE 'render:%'"))
        session.commit()
    yield engine
    engine.dispose()


def fake_benchmark_launch(calls: list[list[str]], *, render_seconds: float | None = 2.4):
    """A build writes the six files; the benchmark frame writes a 1000² PNG."""

    async def _launch(argv: list[str], cwd: Path, timeout: float) -> LaunchResult:
        calls.append(argv)
        out = out_dir_from_argv(argv)
        if any(part.endswith("build_custom_build.py") for part in argv):
            write_build_files(out)
        else:
            assert arg_value(argv, "--tier-resolution") == "1000"
            assert arg_value(argv, "--tier-engine") == "BLENDER_EEVEE"
            out.mkdir()
            (out / "still.png").write_bytes(png_bytes(1000, 1000))
            scene = {"blender_version": "5.2.1 LTS"}
            if render_seconds is not None:
                scene["render_seconds"] = render_seconds
            (out / "scene.json").write_text(json.dumps(scene), encoding="utf-8")
        return LaunchResult(0, "", False)

    return _launch


def _run(engine, root: Path, launch) -> object:
    return asyncio.run(
        run_benchmark(engine, root=root, blender_bin=BIN, timeout=60,
                      semaphore=asyncio.Semaphore(1), launch=launch)
    )


def test_the_benchmark_stores_seconds_per_megapixel_and_keeps_the_frame(engine, render_root) -> None:
    calls: list[list[str]] = []
    result = _run(engine, render_root, fake_benchmark_launch(calls))
    assert result.seconds_per_megapixel == pytest.approx(2.4)
    assert result.blender_version == "5.2.1 LTS"
    assert store.read_benchmark(engine).seconds_per_megapixel == pytest.approx(2.4)
    assert (render_root / "benchmark" / "frame" / "still.png").is_file()
    assert len(calls) == 2, "one build, one frame"


def test_a_rerun_reuses_the_build_and_replaces_the_value(engine, render_root) -> None:
    _run(engine, render_root, fake_benchmark_launch([], render_seconds=2.4))
    calls: list[list[str]] = []
    result = _run(engine, render_root, fake_benchmark_launch(calls, render_seconds=3.0))
    assert result.seconds_per_megapixel == pytest.approx(3.0)
    assert store.read_benchmark(engine).seconds_per_megapixel == pytest.approx(3.0)
    assert len(calls) == 1, "the reference build is kept; only the frame is re-rendered"


def test_without_a_reported_render_time_the_wall_clock_is_used(engine, render_root) -> None:
    result = _run(engine, render_root, fake_benchmark_launch([], render_seconds=None))
    assert result.seconds_per_megapixel > 0


def test_a_failed_build_stores_nothing(engine, render_root) -> None:
    with pytest.raises(BenchmarkFailed, match="reference build failed"):
        _run(engine, render_root, fake_failure_launch)
    assert store.read_benchmark(engine) is None


def test_the_benchmark_frame_goes_through_the_guard(render_root) -> None:
    """The ticket the benchmark uses is single-use and bound to its own request."""
    ticket = authorise_benchmark()
    semaphore = asyncio.Semaphore(1)
    calls: list[list[str]] = []

    async def go(expected):
        return await launch_guarded(
            ticket, expected=expected, argv=["blender"], cwd=render_root, timeout=1,
            semaphore=semaphore, launch=fake_benchmark_launch(calls),
        )

    with pytest.raises(RenderNotAuthorised, match="different render"):
        asyncio.run(go(("desk", 1, "still", False)))
    assert not ticket.consumed and calls == []


def test_the_build_door_refuses_a_render_script(render_root) -> None:
    async def go():
        return await launch_unguarded(
            ["blender", "--python", "/x/generators/render_turntable.py"],
            cwd=render_root, timeout=1, semaphore=asyncio.Semaphore(1),
        )

    with pytest.raises(RenderNotAuthorised, match="needs a guard ticket"):
        asyncio.run(go())


def test_benchmark_is_a_reserved_package_id() -> None:
    with pytest.raises(storage.InvalidPackageId):
        storage.validate_package_id("benchmark")


@pytest.mark.blender
def test_the_real_benchmark_reports_a_positive_number(blender_bin, engine, render_root) -> None:
    """One Eevee frame at 1000 × 1000: the §6 first-launch benchmark itself."""
    result = asyncio.run(
        run_benchmark(engine, root=render_root, blender_bin=blender_bin, timeout=600,
                      semaphore=asyncio.Semaphore(1))
    )
    assert result.seconds_per_megapixel > 0
    assert (render_root / "benchmark" / "frame" / "still.png").stat().st_size > 0
    print(f"benchmark: {result.seconds_per_megapixel:.2f} s/MP")
