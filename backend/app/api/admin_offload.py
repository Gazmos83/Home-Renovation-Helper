"""Developer panel: the render server (render-offload).

Behind the developer gate (404 with the panel off, 401 without the owner's session).
The key file, the known-hosts contents and the RunPod API key are never shown; the
host, port, user, remote Blender path and device are. In pod mode
(render-pod-lifecycle) the GPU type, image and volume id, the pod's state, the idle
time and the pod sessions are shown too, and the pod can be deleted now.
"""

from __future__ import annotations

import asyncio
import re
from typing import Any

from fastapi import APIRouter, Depends, Request, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from app.api.gate import require_dev
from app.api.packages import launcher, refused, require_generation
from app.render import benchmark_store
from app.render.benchmark import BenchmarkFailed
from app.render.offload import jobs, sessions
from app.render.offload.benchmark import run_remote_benchmark
from app.render.offload.check import (
    CHECK_SECONDS,
    PINNED_VERSION,
    SSH_ERROR,
    ask_version,
    reported_version,
)
from app.render.offload.pod import PodBusy
from app.render.offload.runpod import RunPodError
from app.render.offload.transport import Transport, quoted

router = APIRouter(prefix="/admin/offload", tags=["admin"], dependencies=[Depends(require_dev)])

# Ask Cycles itself which GPUs it can use with the configured device type.
GPU_SCRIPT = (
    "import bpy; p = bpy.context.preferences.addons['cycles'].preferences; "
    "p.compute_device_type = {device!r}; p.get_devices(); "
    "print('GPUS:' + ';'.join(d.name for d in p.devices if d.type != 'CPU'))"
)


class TargetIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    target: str


class RateIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    hourly_rate_eur: float


class IdleIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    idle_minutes: int


def _summary(request: Request) -> dict[str, Any]:
    state = request.app.state
    engine = state.engine
    runtime = getattr(state, "offload", None)
    found = benchmark_store.read_remote_benchmark(engine)
    rate = benchmark_store.read_hourly_rate(engine)
    config = runtime.config if runtime else None
    pod = runtime.pod if runtime else None
    with Session(engine) as session:
        recent = jobs.recent_jobs(session, rate)
        pod_sessions = sessions.recent_sessions(session) if pod is not None else []
    return {
        "configured": runtime is not None,
        "mode": None if runtime is None else "pod" if pod is not None else "host",
        "host": config.host if config and pod is None else None,
        "port": config.port if config and pod is None else None,
        "user": config.user if config else None,
        "blender": config.blender if config else None,
        "device": config.device if config else None,
        "pinned_version": PINNED_VERSION,
        "target": benchmark_store.read_final_target(engine),
        "hourly_rate_eur": rate,
        "benchmark": None
        if found is None
        else {
            "seconds_per_megapixel": found.seconds_per_megapixel,
            "overhead_seconds": found.overhead_seconds,
            "measured_at": found.measured_at,
            "calibrated": found.calibrated,
        },
        "jobs": recent,
        "pod": None
        if pod is None
        else {
            "gpu_types": list(pod.settings.gpu_types),
            "image": pod.settings.image,
            "volume_id": pod.settings.volume_id,
            "idle_minutes": benchmark_store.read_idle_minutes(engine),
            **pod.status(),
        },
        "pod_sessions": pod_sessions,
    }


@router.get("")
def read_offload(request: Request) -> dict[str, Any]:
    return _summary(request)


@router.post("/test")
async def test_connection(request: Request) -> dict[str, Any]:
    """Reachability, the server's Blender version and the GPUs Cycles can use there."""
    runtime = getattr(request.app.state, "offload", None)
    if runtime is None:
        raise refused(status.HTTP_409_CONFLICT, "offload_not_configured", "the render server is not configured")
    launch = launcher(request)
    runtime.checker.forget()
    pod = runtime.pod
    if pod is not None and not pod.running:
        return await _test_runpod(pod)
    config = pod.connection if pod is not None and pod.connection is not None else runtime.config
    result = await ask_version(config, launch)
    reachable = not result.timed_out and result.exit_code != SSH_ERROR
    version = reported_version(result) if reachable and result.exit_code == 0 else None
    gpus: list[str] = []
    if version == PINNED_VERSION:  # no point asking a Blender that would be refused anyway
        command = (
            quoted(config.blender, "--background", "--factory-startup", "--python-expr",
                   GPU_SCRIPT.format(device=config.device))
            + " | grep '^GPUS:' >&2"
        )
        listed = await Transport(config, launch).ssh(command, CHECK_SECONDS * 3)
        match = re.search(r"GPUS:(.*)$", listed.stderr_tail)
        gpus = [name for name in (match.group(1).split(";") if match else []) if name]
    return {
        "reachable": reachable,
        "blender_version": version,
        "pinned_version": PINNED_VERSION,
        "version_ok": version == PINNED_VERSION,
        "gpus": gpus,
    }


async def _test_runpod(pod) -> dict[str, Any]:
    """Pod mode with no pod running: RunPod accepts the key and has the volume. Creates nothing."""
    try:
        volume = await asyncio.wait_for(pod.client.get_network_volume(pod.settings.volume_id), CHECK_SECONDS)
    except TimeoutError:
        return {"runpod_ok": False, "volume_found": False, "reason": "RunPod did not answer in time"}
    except RunPodError as error:
        return {"runpod_ok": error.status not in (None, 401), "volume_found": False, "reason": error.reason}
    return {"runpod_ok": True, "volume_found": True, "data_center": volume.data_center_id, "reason": None}


@router.post("/benchmark")
async def run_the_remote_benchmark(request: Request) -> dict[str, Any]:
    require_generation(request)
    settings = request.app.state.settings
    try:
        await run_remote_benchmark(
            request.app.state.engine,
            runtime=getattr(request.app.state, "offload", None),
            root=settings.render_root,
            blender_bin=settings.blender_bin,
            timeout=settings.blender_timeout_seconds,
            semaphore=request.app.state.blender_semaphore,
            launch=launcher(request),
        )
    except BenchmarkFailed as error:
        raise refused(status.HTTP_502_BAD_GATEWAY, "benchmark_failed", str(error)) from None
    return _summary(request)


@router.put("/target")
def set_target(body: TargetIn, request: Request) -> dict[str, Any]:
    if body.target not in benchmark_store.TARGETS:
        raise refused(422, "refused", "the target must be local or remote", field="target")
    if body.target == "remote" and getattr(request.app.state, "offload", None) is None:
        raise refused(
            422, "offload_not_configured",
            "the render server is not configured, so finals cannot be sent there", field="target",
        )
    benchmark_store.write_final_target(request.app.state.engine, body.target)
    return _summary(request)


@router.put("/rate")
def set_rate(body: RateIn, request: Request) -> dict[str, Any]:
    if body.hourly_rate_eur < 0:
        raise refused(422, "refused", "the hourly rate must not be negative", field="hourly_rate_eur")
    benchmark_store.write_hourly_rate(request.app.state.engine, body.hourly_rate_eur)
    return _summary(request)


@router.post("/pod/delete")
async def delete_the_pod(request: Request) -> dict[str, Any]:
    """The developer's "Delete pod now"; refused while a render runs on the pod."""
    runtime = getattr(request.app.state, "offload", None)
    if runtime is None or runtime.pod is None:
        raise refused(status.HTTP_409_CONFLICT, "not_pod_mode", "offload is not in RunPod pod mode")
    try:
        await runtime.pod.delete_now()
    except PodBusy as error:
        raise refused(status.HTTP_409_CONFLICT, "pod_busy", str(error)) from None
    return _summary(request)


@router.put("/idle")
def set_idle(body: IdleIn, request: Request) -> dict[str, Any]:
    try:
        benchmark_store.write_idle_minutes(request.app.state.engine, body.idle_minutes)
    except ValueError as error:
        raise refused(422, "refused", str(error), field="idle_minutes") from None
    return _summary(request)

