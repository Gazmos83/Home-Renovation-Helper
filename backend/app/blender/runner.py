"""Launching Blender processes (render-guard design decisions 1, 4 and 11).

Two doors, and only one of them is for renders:

* `launch_unguarded` runs a *build* (or any non-render script). It refuses any
  argv that names a render script.
* `launch_guarded` runs a render script, and only for a `RenderTicket` the
  guard minted for exactly that package/version/kind, not yet used.

Both take the process-wide semaphore, so at most one Blender runs at a time.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import shutil
import time
from collections.abc import Callable, Iterable
from datetime import UTC, datetime
from pathlib import Path
from typing import Final
from uuid import uuid4

from app.blender import storage
from app.blender.launch import Launch, LaunchResult, subprocess_launch
from app.blender.verify import (
    VerificationError,
    verify_build,
    verify_frames,
    verify_png,
    verify_shell,
)
from app.observability.langfuse import Tracing
from app.render.guard import RenderNotAuthorised, RenderQuote, RenderTicket
from app.render.records import log_render_finished, log_render_started

__all__ = [
    "BUILD_GENERATOR",
    "RENDER_SCRIPTS",
    "Launch",
    "LaunchResult",
    "launch_guarded",
    "launch_unguarded",
    "safe_error",
    "subprocess_launch",
]

logger = logging.getLogger("app")

MAX_ERROR_LENGTH: Final = 500

GENERATORS: Final = Path(__file__).resolve().parent / "generators"
BUILD_GENERATOR: Final = GENERATORS / "build_custom_build.py"
STILL_GENERATOR: Final = GENERATORS / "render_still.py"
TURNTABLE_GENERATOR: Final = GENERATORS / "render_turntable.py"
ROOM_GENERATOR: Final = GENERATORS / "build_room_scene.py"
SHELL_GENERATOR: Final = GENERATORS / "build_shell.py"

# Every script that writes an Eevee or Cycles frame. A build is not on this list
# (it writes a Workbench screenshot; render-guard design decision 5).
RENDER_SCRIPTS: Final = frozenset(
    {STILL_GENERATOR.name, TURNTABLE_GENERATOR.name, ROOM_GENERATOR.name}
)


def _names_a_render_script(argv: list[str]) -> bool:
    return any(Path(part).name in RENDER_SCRIPTS for part in argv)


async def launch_unguarded(
    argv: list[str],
    *,
    cwd: Path,
    timeout: float,
    semaphore: asyncio.Semaphore,
    launch: Launch = subprocess_launch,
) -> LaunchResult:
    """Run a non-render Blender script. Refuses a render script outright."""
    if _names_a_render_script(argv):
        raise RenderNotAuthorised("a render script needs a guard ticket; use launch_guarded")
    async with semaphore:
        return await launch(argv, cwd, timeout)


async def launch_guarded(
    ticket: object,
    *,
    expected: tuple[str, int, str, bool] | tuple[str, int, str, bool, str],
    argv: list[str],
    cwd: Path,
    timeout: float,
    semaphore: asyncio.Semaphore,
    launch: Launch = subprocess_launch,
) -> LaunchResult:
    """Run a render script for exactly one valid, unused ticket.

    `expected` is (id, version, kind, room, record): a ticket minted for another
    request is refused, and the ticket is consumed before the process starts, so
    a second launch with it is refused too.
    """
    if not isinstance(ticket, RenderTicket):
        raise RenderNotAuthorised("a render needs a ticket issued by the render guard")
    if not ticket.matches(*expected):
        raise RenderNotAuthorised("this render authorisation was issued for a different render")
    ticket.consume()
    async with semaphore:
        return await launch(argv, cwd, timeout)


def safe_error(message: str, root: Path | None) -> str:
    """An owner-safe one-liner: no host path, no traceback, bounded length."""
    text = (message or "").strip() or "the run failed with no diagnostic"
    if root is not None:
        text = text.replace(str(root) + "/", "").replace(str(root), "")
    if len(text) > MAX_ERROR_LENGTH:
        text = text[: MAX_ERROR_LENGTH - 1].rstrip() + "…"
    return text


# --- the lifecycle ---------------------------------------------------------------------------
#
# `status.json` per version: the build's `status` at the top, each render's own
# entry under `renders`. Every run writes into a staging directory, verifies it,
# and only then publishes; a failure leaves nothing published and no staging
# directory behind.


def _now() -> str:
    return datetime.now(UTC).isoformat()


def mark_build_queued(version_folder: Path) -> None:
    storage.write_status(version_folder, status="queued", kind="build", error=None)


def mark_render_queued(version_folder: Path, ticket: RenderTicket) -> None:
    quote = ticket.quote
    storage.write_render_status(
        version_folder,
        storage.render_key(quote.kind, quote.room),
        status="queued",
        tier=quote.tier.name,
        estimate_seconds=round(quote.estimate_seconds, 3),
        actual_seconds=None,
        started_at=None,
        finished_at=None,
        error=None,
    )


def _move_build_files(stage: Path, version_folder: Path, names: Iterable[str] = storage.BUILD_FILES) -> None:
    """Move the verified build files into the version folder, undoing the ones
    already moved if a move fails, so a failure publishes nothing. The version's
    status stays `running` until all are in place."""
    moved: list[Path] = []
    try:
        for name in names:
            target = version_folder / name
            os.replace(stage / name, target)
            moved.append(target)
    except OSError:
        for path in moved:
            path.unlink(missing_ok=True)
        raise


async def run_build(
    *,
    root: Path,
    blender_bin: Path,
    timeout: float,
    package_id: str,
    version: int,
    semaphore: asyncio.Semaphore,
    launch: Launch = subprocess_launch,
    record: str = "piece",
) -> None:
    """Build one version from its stored `input.json`; never raises.

    `record` is `piece` (a furniture package) or `shell` (an apartment shell,
    built by its own generator into `shells/<slug>/v<N>/`).
    """
    shell = record == "shell"
    folder = storage.record_version_dir(root, record, package_id, version)
    script = SHELL_GENERATOR if shell else BUILD_GENERATOR
    verify = verify_shell if shell else verify_build
    names = storage.SHELL_FILES if shell else storage.BUILD_FILES
    context = {"package_id": package_id, "version": version, "kind": "build", "record": record}

    def running() -> None:
        storage.write_status(folder, status="running", started_at=_now(), error=None)
        logger.info("build.started", extra={"context": context})

    async def starting(argv: list[str], cwd: Path, limit: float) -> LaunchResult:
        running()
        return await launch(argv, cwd, limit)

    stage = folder / ".build-out"
    storage.sweep_stale_siblings(stage)
    shutil.rmtree(stage, ignore_errors=True)
    started = time.perf_counter()
    error: str | None = None
    try:
        result = await launch_unguarded(
            [str(blender_bin), "--background", "--python", str(script), "--",
             "--spec", str(folder / storage.INPUT_FILE), "--out", str(stage)],
            cwd=folder, timeout=timeout, semaphore=semaphore, launch=starting,
        )
        if result.exit_code != 0 or result.timed_out:
            error = safe_error(result.stderr_tail, root)
        else:
            try:
                verify(stage)
                _move_build_files(stage, folder, names)
            except (VerificationError, OSError, ValueError) as problem:
                error = safe_error(f"publish: {problem}", root)
    except Exception as problem:  # noqa: BLE001 - a background job must record, not raise
        error = safe_error(f"build: {type(problem).__name__}: {problem}", root)
    finally:
        shutil.rmtree(stage, ignore_errors=True)
        storage.sweep_stale_siblings(stage)

    elapsed = round(time.perf_counter() - started, 3)
    storage.write_status(
        folder,
        status="failed" if error else "succeeded",
        finished_at=_now(),
        error=error,
    )
    logger.info(
        "build.finished",
        extra={"context": {**context, "outcome": "failed" if error else "succeeded",
                           "elapsed_seconds": elapsed, **({"error": error} if error else {})}},
    )


def _verify_render(stage: Path, kind: str, tier_resolution: int, tier_frames: int) -> None:
    json.loads((stage / "scene.json").read_text(encoding="utf-8"))
    if kind == "still":
        verify_png(stage / "still.png", (tier_resolution, tier_resolution))
        return
    verify_frames(stage, tier_frames, tier_resolution)
    viewer = stage / "viewer.html"
    if not viewer.is_file() or viewer.stat().st_size == 0:
        raise VerificationError("viewer.html is missing or empty")


def _publish_render(stage: Path, target: Path, kind: str, record: dict) -> None:
    """Replace this kind's files in `target` and merge its scene record."""
    target.mkdir(exist_ok=True)
    if kind == "still":
        os.replace(stage / "still.png", target / "still.png")
    else:
        existing = target / "frames"
        retired = None
        if existing.exists():
            retired = target / f".frames.old-{uuid4().hex}"
            os.replace(existing, retired)
        os.replace(stage / "frames", target / "frames")
        os.replace(stage / "viewer.html", target / "viewer.html")
        if retired is not None:
            shutil.rmtree(retired, ignore_errors=True)
    try:
        produced = json.loads((stage / "scene.json").read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        produced = {}
    storage.merge_scene_record(target, kind, {**produced, **record})


async def run_render(
    ticket: RenderTicket,
    *,
    root: Path,
    blender_bin: Path,
    timeout: float,
    semaphore: asyncio.Semaphore,
    launch: Launch = subprocess_launch,
    scene_document: dict | None = None,
    tracing: Tracing | None = None,
    on_finished: Callable[[RenderQuote, float], None] | None = None,
) -> None:
    """Run one guarded render; never raises (a failure is recorded).

    The ticket decides everything: the tier's frames, resolution and engine are
    the only values that reach argv. `scene_document` is the room document for a
    room render. `on_finished(quote, actual_seconds)` runs after a success (the
    route uses it to calibrate the Cycles multiplier).
    """
    quote = ticket.quote
    folder = storage.record_version_dir(root, quote.record, quote.package_id, quote.version)
    key = storage.render_key(quote.kind, quote.room)
    target = folder / "room" if quote.room else folder
    stage_name = folder / f"render-{key}"
    storage.sweep_stale_siblings(stage_name)
    stage = storage.staging_dir(stage_name)
    tier = quote.tier
    limit = timeout * tier.timeout_multiplier

    scene_path: Path | None = None
    try:
        if quote.room:
            if scene_document is None:
                raise RenderNotAuthorised("a room render needs its scene document")
            scene_path = folder / f".{key}.{uuid4().hex}.scene.json"
            scene_path.write_text(json.dumps(scene_document), encoding="utf-8")
            argv = [str(blender_bin), "--background", "--python", str(ROOM_GENERATOR), "--",
                    "--scene", str(scene_path), "--package", str(folder), "--out", str(stage)]
        else:
            script = STILL_GENERATOR if quote.kind == "still" else TURNTABLE_GENERATOR
            argv = [str(blender_bin), "--background", "--python", str(script), "--",
                    "--blend", str(folder / "model.blend"), "--out", str(stage)]
        argv += ["--tier-frames", str(tier.frames), "--tier-resolution", str(tier.resolution),
                 "--tier-engine", tier.blender_engine]

        started_at = {"t": 0.0}

        async def starting(args: list[str], cwd: Path, seconds: float) -> LaunchResult:
            # The semaphore is held by now: this is when the render truly starts.
            started_at["t"] = time.perf_counter()
            storage.write_render_status(
                folder, key, status="running", started_at=_now(), tier=tier.name,
                estimate_seconds=round(quote.estimate_seconds, 3),
            )
            log_render_started(quote, tracing=tracing)
            return await launch(args, cwd, seconds)

        error: str | None = None
        result = await launch_guarded(
            ticket,
            expected=(quote.package_id, quote.version, quote.kind, quote.room, quote.record),
            argv=argv, cwd=folder, timeout=limit, semaphore=semaphore, launch=starting,
        )
        actual = time.perf_counter() - started_at["t"] if started_at["t"] else 0.0
        if result.exit_code != 0 or result.timed_out:
            error = safe_error(result.stderr_tail, root)
        else:
            try:
                _verify_render(stage, quote.kind, tier.resolution, tier.frames)
                _publish_render(
                    stage, target, quote.kind,
                    {"tier": tier.name, "estimate_seconds": round(quote.estimate_seconds, 3),
                     "actual_seconds": round(actual, 3)},
                )
            except (VerificationError, OSError, ValueError, KeyError) as problem:
                error = safe_error(f"publish: {problem}", root)
    except RenderNotAuthorised as refusal:
        storage.write_render_status(
            folder, key, status="failed", finished_at=_now(), error=safe_error(str(refusal), root)
        )
        raise
    except Exception as problem:  # noqa: BLE001 - a background job must record, not raise
        actual = 0.0
        error = safe_error(f"render: {type(problem).__name__}: {problem}", root)
    finally:
        shutil.rmtree(stage, ignore_errors=True)
        if scene_path is not None:
            scene_path.unlink(missing_ok=True)
        storage.sweep_stale_siblings(stage_name)

    storage.write_render_status(
        folder, key,
        status="failed" if error else "succeeded",
        finished_at=_now(),
        actual_seconds=round(actual, 3),
        error=error,
    )
    log_render_finished(
        quote, actual_seconds=actual, outcome="failed" if error else "succeeded",
        error=error, tracing=tracing,
    )
    if on_finished is not None and not error:
        try:
            on_finished(quote, actual)
        except Exception:  # noqa: BLE001 - calibration must never fail a finished render
            logger.warning("render.calibration_failed")
