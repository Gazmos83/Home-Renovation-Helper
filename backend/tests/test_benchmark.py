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


# --- the render server's benchmark, target and rate (render-offload) -----------------------------------


@pytest.fixture
def offload_engine(migrated_database: str) -> Iterator:
    engine = make_engine(migrated_database)

    def clear() -> None:
        with Session(engine) as session:
            session.execute(text("DELETE FROM operator_settings WHERE key LIKE 'offload:%'"))
            session.commit()

    clear()
    yield engine
    clear()
    engine.dispose()


def test_the_remote_benchmark_round_trips_and_a_rerun_replaces_it(offload_engine) -> None:
    assert store.read_remote_benchmark(offload_engine) is None
    first = store.write_remote_benchmark(offload_engine, 0.2, 35.0)
    assert store.read_remote_benchmark(offload_engine) == first
    assert first.calibrated is False
    second = store.write_remote_benchmark(offload_engine, 0.3, 30.0)
    assert store.read_remote_benchmark(offload_engine) == second


def test_a_remote_benchmark_must_be_positive(offload_engine) -> None:
    with pytest.raises(ValueError):
        store.write_remote_benchmark(offload_engine, 0, 10)
    with pytest.raises(ValueError):
        store.write_remote_benchmark(offload_engine, 0.2, -1)


def test_the_final_target_defaults_to_local_and_accepts_only_known_values(offload_engine) -> None:
    assert store.read_final_target(offload_engine) == "local"
    store.write_final_target(offload_engine, "remote")
    assert store.read_final_target(offload_engine) == "remote"
    with pytest.raises(ValueError):
        store.write_final_target(offload_engine, "cloud")


def test_the_hourly_rate_is_optional_and_not_negative(offload_engine) -> None:
    assert store.read_hourly_rate(offload_engine) is None
    store.write_hourly_rate(offload_engine, 1.8)
    assert store.read_hourly_rate(offload_engine) == 1.8
    with pytest.raises(ValueError):
        store.write_hourly_rate(offload_engine, -1)


def _final_quote(target: str):
    from app.render.benchmark_store import Benchmark, RemoteBenchmark
    from app.render.guard import authorise
    from app.render.tiers import load_tiers

    return authorise(
        package_id="desk", version=1, kind="turntable", tier="final", tiers=load_tiers(),
        benchmark=Benchmark(2.5, "t"), approval="yes", target=target,
        remote_benchmark=RemoteBenchmark(0.2, 40.0, "t"),
    ).quote


def test_the_first_remote_final_recalibrates_the_servers_rate_without_the_transfer(offload_engine) -> None:
    from app.render.calibration import calibrate_after_render

    store.write_benchmark(offload_engine, 2.5)
    store.write_remote_benchmark(offload_engine, 0.2, 40.0)
    # The job passes the render time alone: 36 frames × 2.25 MP × 0.1 s/MP = 8.1 s.
    assert calibrate_after_render(offload_engine, _final_quote("remote"), 8.1) == pytest.approx(0.1)
    after = store.read_remote_benchmark(offload_engine)
    assert after.seconds_per_megapixel == pytest.approx(0.1) and after.overhead_seconds == 40.0
    assert after.calibrated is True
    assert store.stored_cycles_multiplier(offload_engine) is None  # the laptop's multiplier is untouched
    assert calibrate_after_render(offload_engine, _final_quote("remote"), 99.0) is None
    assert store.read_remote_benchmark(offload_engine).seconds_per_megapixel == pytest.approx(0.1)


def test_a_local_final_still_calibrates_only_the_laptops_multiplier(offload_engine) -> None:
    from app.render.calibration import calibrate_after_render

    store.write_benchmark(offload_engine, 2.5)
    store.write_remote_benchmark(offload_engine, 0.2, 40.0)
    assert calibrate_after_render(offload_engine, _final_quote("local"), 36 * 2.25 * 2.5 * 20) == pytest.approx(20)
    assert store.read_remote_benchmark(offload_engine).calibrated is False


def test_a_remote_benchmark_rerun_makes_the_next_remote_final_calibrate_again(offload_engine) -> None:
    from app.render.calibration import calibrate_after_render

    store.write_remote_benchmark(offload_engine, 0.2, 40.0)
    calibrate_after_render(offload_engine, _final_quote("remote"), 8.1)
    store.write_remote_benchmark(offload_engine, 0.5, 20.0)
    assert store.read_remote_benchmark(offload_engine).calibrated is False
    assert calibrate_after_render(offload_engine, _final_quote("remote"), 16.2) == pytest.approx(0.2)


def test_the_remote_benchmark_ticket_is_the_guards_alone() -> None:
    from app.render.guard import (
        RenderNotAuthorised,
        RenderTicket,
        authorise_remote_benchmark,
    )

    ticket = authorise_remote_benchmark()
    assert ticket.quote.target == "remote" and ticket.quote.tier.engine == "cycles"
    assert (ticket.quote.frames, ticket.quote.tier.resolution) == (1, 1000)
    with pytest.raises(RenderNotAuthorised):
        RenderTicket(ticket.quote)
