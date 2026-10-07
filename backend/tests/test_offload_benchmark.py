"""render-offload: the render server's benchmark, with a fake server and fake local build."""

from __future__ import annotations

import asyncio
import json
from collections.abc import Iterator
from pathlib import Path

import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.db.session import make_engine
from app.render import benchmark_store as store
from app.render.benchmark import BenchmarkFailed
from app.render.offload.benchmark import run_remote_benchmark
from app.render.offload.runtime import OffloadRuntime
from tests.blender_fakes import fake_pipeline_launch
from tests.offload_fakes import FakeServer
from tests.test_offload_job import CONFIG


@pytest.fixture
def engine(migrated_database: str) -> Iterator:
    engine = make_engine(migrated_database)

    def clear() -> None:
        with Session(engine) as session:
            session.execute(text("DELETE FROM operator_settings WHERE key LIKE 'offload:%'"))
            session.commit()

    clear()
    yield engine
    clear()
    engine.dispose()


def combined(server: FakeServer, local):
    async def launch(argv, cwd, timeout):
        if argv[0] in ("ssh", "scp"):
            return await server.launch(argv, cwd, timeout)
        return await local(argv, cwd, timeout)

    return launch


def measure(engine, render_root: Path, server: FakeServer, *, runtime="default", calls=None):
    return asyncio.run(
        run_remote_benchmark(
            engine,
            runtime=OffloadRuntime(CONFIG) if runtime == "default" else runtime,
            root=render_root, blender_bin=Path("/fake/blender"), timeout=60,
            semaphore=asyncio.Semaphore(1),
            launch=combined(server, fake_pipeline_launch(calls=calls)),
        )
    )


def test_the_benchmark_renders_one_cycles_frame_remotely_and_stores_the_servers_numbers(
    engine, render_root: Path, tmp_path: Path
) -> None:
    server = FakeServer(tmp_path / "s", delay=0.05)
    local: list[list[str]] = []
    laptop_before = store.read_benchmark(engine)
    result = measure(engine, render_root, server, calls=local)
    [command] = server.render_commands
    for expected in ("render_still.py", "--tier-frames 1", "--tier-resolution 1000",
                     "--tier-engine CYCLES", "--cycles-device OPTIX"):
        assert expected in command
    assert store.read_remote_benchmark(engine) == result
    assert result.seconds_per_megapixel > 0 and result.overhead_seconds >= 0
    assert result.calibrated is False
    # Only the reference build ran on the laptop; no render did.
    assert [c for c in local if any(p.endswith("render_still.py") for p in c)] == []
    assert server.job_folders() == []
    assert store.read_benchmark(engine) == laptop_before  # the laptop's benchmark is untouched


def test_the_servers_own_render_time_is_preferred_when_it_reports_one(
    engine, render_root: Path, tmp_path: Path
) -> None:
    class Reporting(FakeServer):
        async def _render(self, command, timeout):
            outcome = await super()._render(command, timeout)
            job = command.split("&&")[0].replace("cd ", "").strip()
            scene = self.root / job / "out" / "scene.json"
            scene.write_text(json.dumps({"render_seconds": 0.8}), encoding="utf-8")
            return outcome

    result = measure(engine, render_root, Reporting(tmp_path / "s"))
    assert result.seconds_per_megapixel == pytest.approx(0.8 / 1.0)


def test_a_rerun_replaces_the_value_and_clears_the_calibration(engine, render_root: Path, tmp_path: Path) -> None:
    store.write_remote_benchmark(engine, 0.01, 1.0, calibrated=True)
    result = measure(engine, render_root, FakeServer(tmp_path / "s"))
    assert result.calibrated is False
    assert store.read_remote_benchmark(engine).seconds_per_megapixel == result.seconds_per_megapixel != 0.01


def test_an_unreachable_server_stores_nothing(engine, render_root: Path, tmp_path: Path) -> None:
    with pytest.raises(BenchmarkFailed, match="unreachable"):
        measure(engine, render_root, FakeServer(tmp_path / "s", reachable=False))
    assert store.read_remote_benchmark(engine) is None


def test_an_unconfigured_server_stores_nothing(engine, render_root: Path, tmp_path: Path) -> None:
    with pytest.raises(BenchmarkFailed, match="not configured"):
        measure(engine, render_root, FakeServer(tmp_path / "s"), runtime=None)
    assert store.read_remote_benchmark(engine) is None


def test_a_failed_frame_stores_nothing_and_cleans_up(engine, render_root: Path, tmp_path: Path) -> None:
    server = FakeServer(tmp_path / "s", fail_render="render: RuntimeError: no GPU")
    with pytest.raises(BenchmarkFailed, match="no GPU"):
        measure(engine, render_root, server)
    assert store.read_remote_benchmark(engine) is None
    assert server.job_folders() == []
