"""One render on the render server (render-offload design decisions 3, 4 and 5).

Upload one archive (the generator bundle, the blend file, and for a room render the
room document and package files), run the same generator Blender runs on the laptop
with the tier's values, copy the output back into the local staging folder, and clean
up the server's job folder whatever happened. The caller then verifies and publishes
exactly as for a local render, so nothing from the server is trusted more than a file
the laptop made: only the expected PNG names survive, and `viewer.html` is written
here, never copied.
"""

from __future__ import annotations

import logging
import shutil
import tarfile
import tempfile
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Final
from uuid import uuid4

from app.blender.launch import Launch
from app.render.offload.bundle import BACKEND_ROOT, bundle_files
from app.render.offload.transport import (
    REMOTE_ROOT,
    OffloadConfig,
    Transport,
    job_path,
    quoted,
)
from app.render.tiers import Tier
from app.render.viewer import render_viewer

logger = logging.getLogger("app")

ARCHIVE: Final = "bundle.tar.gz"
SETUP_SECONDS: Final = 60.0
TRANSFER_SECONDS: Final = 600.0
CLEANUP_SECONDS: Final = 60.0
TIMEOUT_EXIT: Final = 124  # what coreutils `timeout` exits with
# Anything older than a day under the job root is a leftover of a killed job.
SWEEP_STALE: Final = f"find {REMOTE_ROOT} -mindepth 1 -maxdepth 1 -mmin +1440 -exec rm -rf {{}} +"
EXPECTED_TOP_LEVEL: Final = frozenset({"frames", "viewer.html", "scene.json", "still.png"})


class RemoteFailed(Exception):
    """The remote job failed. `reason` is safe to show; `timed_out` marks a timeout."""

    def __init__(self, reason: str, *, timed_out: bool = False) -> None:
        super().__init__(reason)
        self.reason = reason
        self.timed_out = timed_out


@dataclass(frozen=True, slots=True)
class RemoteTimes:
    render_seconds: float
    transfer_seconds: float


@dataclass(frozen=True, slots=True)
class RemoteInputs:
    """What the generator needs on the server, by local path."""

    script: str  # a generator file name under app/blender/generators
    blend: Path | None = None  # still and turntable
    scene_document: dict | None = None  # room render
    package_dir: Path | None = None  # room render: holds model.glb and spec.json
    dimensions: bool = False  # a piece's own turntable shows its dimension lines


def _build_archive(path: Path, inputs: RemoteInputs, backend: Path) -> None:
    import json

    with tarfile.open(path, "w:gz") as archive:
        for relative in bundle_files(backend):
            archive.add(backend / relative, arcname=f"backend/{relative.as_posix()}")
        if inputs.blend is not None:
            archive.add(inputs.blend, arcname="input.blend")
        if inputs.package_dir is not None:
            for name in ("model.glb", "spec.json"):
                archive.add(inputs.package_dir / name, arcname=f"package/{name}")
        if inputs.scene_document is not None:
            scene = Path(path.parent) / "scene.json"
            scene.write_text(json.dumps(inputs.scene_document), encoding="utf-8")
            archive.add(scene, arcname="scene.json")


def render_command(config: OffloadConfig, tier: Tier, inputs: RemoteInputs, limit_seconds: float) -> str:
    """The one command run on the server: the generator, with the tier's values only."""
    script = f"backend/app/blender/generators/{inputs.script}"
    source = (
        ["--scene", "scene.json", "--package", "package"]
        if inputs.scene_document is not None
        else ["--blend", "input.blend"]
    )
    return quoted(
        "timeout", "-k", 10, int(limit_seconds),
        config.blender, "--background", "--python", script, "--",
        *source, "--out", "out",
        *(["--dimensions"] if inputs.dimensions else []),
        "--tier-frames", tier.frames, "--tier-resolution", tier.resolution,
        "--tier-engine", tier.blender_engine, "--cycles-device", config.device,
    )


def _sanitise(stage: Path, kind: str, tier: Tier) -> None:
    """Keep only what a generator makes, and write the viewer here."""
    if not stage.is_dir():
        raise RemoteFailed("the render server returned no output")
    unexpected = sorted(entry.name for entry in stage.iterdir() if entry.name not in EXPECTED_TOP_LEVEL)
    if unexpected:
        raise RemoteFailed(f"the render server returned an unexpected file: {unexpected[0]}")
    if any(entry.is_symlink() for entry in stage.rglob("*")):
        raise RemoteFailed("the render server returned a link instead of a file")
    if kind == "turntable":
        (stage / "viewer.html").write_text(
            render_viewer(
                tier.frames, title="Package", meta=f"{tier.resolution}×{tier.resolution} {tier.blender_engine}"
            ),
            encoding="utf-8",
        )


async def run_remote(
    *,
    config: OffloadConfig,
    launch: Launch,
    tier: Tier,
    kind: str,
    inputs: RemoteInputs,
    stage: Path,
    limit_seconds: float,
    job_id: str | None = None,
    backend: Path = BACKEND_ROOT,
    on_start: Callable[[], None] | None = None,
) -> RemoteTimes:
    """Run one render on the server and leave its output in `stage` (which must not exist).

    Raises `RemoteFailed` with a reason; the server's job folder is removed either way.
    """
    transport = Transport(config, launch)
    job = job_id or uuid4().hex
    remote = job_path(job)
    transfer = 0.0
    render_seconds = 0.0
    if on_start is not None:
        on_start()
    try:
        with tempfile.TemporaryDirectory(prefix="hra-offload-") as scratch:
            archive = Path(scratch) / ARCHIVE
            _build_archive(archive, inputs, backend)

            made = await transport.ssh(
                f"mkdir -p {quoted(REMOTE_ROOT)} && {SWEEP_STALE}; mkdir {quoted(remote)}", SETUP_SECONDS
            )
            if made.exit_code != 0 or made.timed_out:
                raise RemoteFailed("the render server could not prepare a folder for the render")

            started = time.perf_counter()
            sent = await transport.put(archive, f"{remote}/{ARCHIVE}", TRANSFER_SECONDS)
            transfer += time.perf_counter() - started
            if sent.exit_code != 0 or sent.timed_out:
                raise RemoteFailed("the model could not be copied to the render server")
            unpacked = await transport.ssh(
                f"cd {quoted(remote)} && tar xzf {ARCHIVE} && rm {ARCHIVE}", SETUP_SECONDS
            )
            if unpacked.exit_code != 0 or unpacked.timed_out:
                raise RemoteFailed("the render server could not unpack the model")

            started = time.perf_counter()
            ran = await transport.ssh(
                f"cd {quoted(remote)} && {render_command(config, tier, inputs, limit_seconds)}",
                limit_seconds + 60,
            )
            render_seconds = time.perf_counter() - started
            if ran.timed_out or ran.exit_code == TIMEOUT_EXIT:
                raise RemoteFailed(
                    f"the render exceeded {int(limit_seconds)} seconds on the render server and was stopped",
                    timed_out=True,
                )
            if ran.exit_code != 0:
                raise RemoteFailed(f"the render failed on the render server: {ran.stderr_tail}"[:500])

            started = time.perf_counter()
            fetched = await transport.get(f"{remote}/out", stage, TRANSFER_SECONDS)
            transfer += time.perf_counter() - started
            if fetched.exit_code != 0 or fetched.timed_out:
                shutil.rmtree(stage, ignore_errors=True)
                raise RemoteFailed("the finished render could not be copied back from the render server")
            _sanitise(stage, kind, tier)
        return RemoteTimes(render_seconds=render_seconds, transfer_seconds=transfer)
    finally:
        try:
            await transport.ssh(f"rm -rf {quoted(remote)}", CLEANUP_SECONDS)
        except Exception:  # noqa: BLE001 - cleanup must not hide the render's own outcome
            logger.warning("offload.cleanup_failed")
