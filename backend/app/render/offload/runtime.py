"""What the app holds for the render server, and which render goes where (render-offload).

Only a `final` can run remotely, and only when the developer chose `remote` for
finals. There is no fallback: a remote final with no usable server is refused.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field

from sqlalchemy import Engine

from app.blender.launch import Launch
from app.config import Settings
from app.render import benchmark_store
from app.render.benchmark_store import RemoteBenchmark
from app.render.guard import RenderRefused
from app.render.offload.check import (
    CHECK_SECONDS,
    NOT_CONFIGURED,
    UNREACHABLE,
    OffloadChecker,
)
from app.render.offload.transport import OffloadConfig


@dataclass
class OffloadRuntime:
    """The server's connection, its one-job-at-a-time lock and its check cache."""

    config: OffloadConfig
    semaphore: asyncio.Semaphore = field(default_factory=lambda: asyncio.Semaphore(1))
    checker: OffloadChecker = field(default_factory=OffloadChecker)

    @classmethod
    def from_settings(cls, settings: Settings) -> OffloadRuntime | None:
        config = OffloadConfig.from_settings(settings)
        return cls(config) if config is not None else None


def target_for(engine: Engine, tier_name: object) -> str:
    """`remote` for a `final` when the developer chose it, else `local`."""
    if tier_name == "final" and benchmark_store.read_final_target(engine) == "remote":
        return "remote"
    return "local"


async def ensure_server(runtime: OffloadRuntime | None, launch: Launch) -> None:
    """Refuse (never fall back) unless a configured server answers with the pinned Blender."""
    if runtime is None:
        raise RenderRefused(NOT_CONFIGURED, failure_class="offload_not_configured")
    await runtime.checker.check(runtime.config, launch)


def confirm_server_sync(
    loop: asyncio.AbstractEventLoop | None, runtime: OffloadRuntime | None, launch: Launch
) -> None:
    """`ensure_server` for a caller on another thread (a tool, a route). Raises `RenderRefused`."""
    if loop is None:
        raise RenderRefused(
            "the build queue is not running, so the render server cannot be checked right now",
            failure_class="offload_unreachable",
        )
    future = asyncio.run_coroutine_threadsafe(ensure_server(runtime, launch), loop)
    try:
        future.result(timeout=CHECK_SECONDS + 15)
    except TimeoutError:
        future.cancel()
        raise RenderRefused(UNREACHABLE, failure_class="offload_unreachable") from None


def remote_benchmark_for(engine: Engine, target: str) -> RemoteBenchmark | None:
    return benchmark_store.read_remote_benchmark(engine) if target == "remote" else None
