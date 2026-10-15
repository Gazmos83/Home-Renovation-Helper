"""What the app holds for the render server, and which render goes where (render-offload).

Only a `final` can run remotely, and only when the developer chose `remote` for
finals. There is no fallback: a remote final with no usable server is refused.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field, replace

from pydantic import SecretStr
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
from app.render.offload.pod import PodManager, PodSettings
from app.render.offload.runpod import RunPodClient
from app.render.offload.transport import OffloadConfig


@dataclass
class OffloadRuntime:
    """The server's connection, its one-job-at-a-time lock and its check cache."""

    config: OffloadConfig
    semaphore: asyncio.Semaphore = field(default_factory=lambda: asyncio.Semaphore(1))
    checker: OffloadChecker = field(default_factory=OffloadChecker)
    # Pod mode only (render-pod-lifecycle): the pod the app creates and deletes.
    pod: PodManager | None = None

    @classmethod
    def from_settings(cls, settings: Settings, engine: Engine | None = None) -> OffloadRuntime | None:
        config = OffloadConfig.from_settings(settings)
        if config is None:
            return None
        runtime = cls(config)
        if settings.render_offload_mode == "pod":
            runtime.pod = PodManager(
                client=RunPodClient(settings.render_offload_runpod_api_key or SecretStr("")),
                settings=PodSettings(
                    gpu_types=settings.render_offload_runpod_gpu_types,
                    image=settings.render_offload_runpod_image or "",
                    volume_id=settings.render_offload_runpod_network_volume_id or "",
                ),
                template=config,
                semaphore=runtime.semaphore,
                engine=engine,
            )
        return runtime


def target_for(engine: Engine, tier_name: object) -> str:
    """`remote` for a `final` when the developer chose it, else `local`."""
    if tier_name == "final" and benchmark_store.read_final_target(engine) == "remote":
        return "remote"
    return "local"


async def ensure_server(runtime: OffloadRuntime | None, launch: Launch) -> None:
    """Refuse (never fall back) unless a configured server answers with the pinned Blender."""
    if runtime is None:
        raise RenderRefused(NOT_CONFIGURED, failure_class="offload_not_configured")
    pod = runtime.pod
    if pod is None:
        await runtime.checker.check(runtime.config, launch)
    elif pod.running and pod.connection is not None:
        await runtime.checker.check(pod.connection, launch)
    else:
        # No pod yet: it is created only after the owner approves the render.
        await runtime.checker.check_runpod(pod.client, pod.settings.volume_id)


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


def remote_benchmark_for(
    engine: Engine, target: str, offload: OffloadRuntime | None = None
) -> RemoteBenchmark | None:
    """The server's numbers for a remote quote. In pod mode with no pod running, the
    pod's start-up (last measured, else 180 s) is added to the overhead, because it will
    be paid before the render (render-pod-lifecycle). The stored benchmark is unchanged."""
    if target != "remote":
        return None
    benchmark = benchmark_store.read_remote_benchmark(engine)
    pod = offload.pod if offload is not None else None
    if benchmark is None or pod is None or pod.running:
        return benchmark
    return replace(
        benchmark, overhead_seconds=benchmark.overhead_seconds + benchmark_store.read_boot_seconds(engine)
    )
