"""Fixtures for the agent tests: tool dependencies, a loop thread, a clean house file."""

from __future__ import annotations

import asyncio
import threading
from collections.abc import Iterator
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.agent.tools.base import ToolContext, ToolDeps
from app.config import Settings
from app.db.session import make_engine
from app.render import benchmark_store
from app.render.tiers import load_tiers
from tests.blender_fakes import fake_pipeline_launch

HOUSE_TABLES = (
    "piece_versions, pieces, rooms, preferences, generator_extension_requests, threads"
)


def clean_house_file(engine) -> None:
    with Session(engine) as session:
        session.execute(text(f"TRUNCATE TABLE {HOUSE_TABLES} CASCADE"))
        session.execute(text("DELETE FROM operator_settings WHERE key LIKE 'render:%'"))
        session.commit()


class LoopThread:
    """An event loop on a thread, standing in for the app's loop."""

    def __init__(self) -> None:
        self.loop = asyncio.new_event_loop()
        self._thread = threading.Thread(target=self.loop.run_forever, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self.loop.call_soon_threadsafe(self.loop.stop)
        self._thread.join(timeout=5)
        self.loop.close()


@pytest.fixture
def loop_thread() -> Iterator[LoopThread]:
    thread = LoopThread()
    yield thread
    thread.stop()


@pytest.fixture
def tool_state(
    migrated_database: str, render_root: Path, fake_blender: Path, loop_thread: LoopThread
) -> Iterator[SimpleNamespace]:
    """An `app.state`-shaped object with a fake launcher and a stored benchmark."""
    engine = make_engine(migrated_database)
    clean_house_file(engine)
    benchmark_store.write_benchmark(engine, 2.5, blender_version="5.2.1 LTS")
    settings = Settings(
        database_url=migrated_database,
        openrouter_api_key="sk-or-test",
        cors_origins="http://localhost:5173",
        owner_email="owner@example.com",
        owner_password="an-initial-owner-password",
        gateway_probe_enabled=False,
        render_root=render_root,
        blender_bin=fake_blender,
        _env_file=None,
    )
    state = SimpleNamespace(
        engine=engine,
        settings=settings,
        tiers=load_tiers(),
        blender_semaphore=asyncio.Semaphore(1),
        blender_launch=fake_pipeline_launch(),
        loop=loop_thread.loop,
        tracing=None,
        launched=[],
    )
    state.blender_launch = fake_pipeline_launch(calls=state.launched)
    yield state
    clean_house_file(engine)
    engine.dispose()


@pytest.fixture
def tool_deps(tool_state: SimpleNamespace) -> ToolDeps:
    return ToolDeps(tool_state)


@pytest.fixture
def make_ctx(tool_deps: ToolDeps):
    def make(**fields) -> ToolContext:
        return ToolContext(deps=tool_deps, owner_id=uuid4(), **fields)

    return make


def wait_for_status(folder: Path, wanted: str = "succeeded", seconds: float = 10.0) -> dict:
    """Poll a version's `status.json` until it reads `wanted` (or fail)."""
    import time

    from app.blender import storage

    deadline = time.monotonic() + seconds
    state: dict = {}
    while time.monotonic() < deadline:
        state = storage.read_status(folder) or {}
        if state.get("status") == wanted:
            return state
        time.sleep(0.05)
    raise AssertionError(f"{folder.name} never reached {wanted!r}; last status {state}")
