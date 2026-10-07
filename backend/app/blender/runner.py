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
from collections.abc import Awaitable, Callable, Iterable
from datetime import UTC, datetime
from pathlib import Path
from typing import Final
from uuid import uuid4

from app.blender import storage
from app.blender.launch import Launch, LaunchResult, subprocess_launch
from app.blender.verify import (
    VerificationError,
    verify_build,
    verify_composition,
    verify_frames,
    verify_png,
    verify_shell,
)
from app.observability.langfuse import Tracing
from app.render.guard import RenderNotAuthorised, RenderQuote, RenderTicket
from app.render.offload.job import RemoteFailed, RemoteInputs, RemoteTimes, run_remote
from app.render.offload.runtime import OffloadRuntime
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
CHECK_MODEL_GENERATOR: Final = GENERATORS / "check_model.py"
COMPOSITION_GENERATOR: Final = GENERATORS / "build_composition.py"
COMPOSITION_RENDERER: Final = GENERATORS / "render_composition.py"

# Every script that writes an Eevee or Cycles frame. A build is not on this list
# (it writes a Workbench screenshot; render-guard design decision 5).
RENDER_SCRIPTS: Final = frozenset(
    {STILL_GENERATOR.name, TURNTABLE_GENERATOR.name, ROOM_GENERATOR.name, COMPOSITION_RENDERER.name}
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
    expected: tuple[str, int, str, bool] | tuple[str, int, str, bool, str] | tuple[str, int, str, bool, str, str],
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
        storage.render_key(quote.kind, quote.room, quote.source),
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
    models_root: Path | None = None,
) -> None:
    """Build one version from its stored `input.json`; never raises.

    `record` is `piece` (a furniture package), `shell` (an apartment shell, built
    by its own generator into `shells/<slug>/v<N>/`) or `room` (a room composition
    in `rooms/<slug>/v<N>/`, which also needs the model library's `models_root`).
    """
    shell = record == "shell"
    room = record == "room"
    folder = storage.record_version_dir(root, record, package_id, version)
    script = SHELL_GENERATOR if shell else COMPOSITION_GENERATOR if room else BUILD_GENERATOR
    verify = verify_shell if shell else verify_composition if room else verify_build
    names = storage.SHELL_FILES if shell else storage.COMPOSITION_FILES if room else storage.BUILD_FILES
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
        argv = [str(blender_bin), "--background", "--python", str(script), "--",
                "--spec", str(folder / storage.INPUT_FILE), "--out", str(stage)]
        if room:
            unbuilt = composition_unbuilt_pieces(root, folder)
            if unbuilt:
                raise _NotBuilt(unbuilt)
            argv += ["--pieces", str(root), "--models", str(models_root or root / "models")]
        result = await launch_unguarded(
            argv, cwd=folder, timeout=timeout, semaphore=semaphore, launch=starting,
        )
        if result.exit_code != 0 or result.timed_out:
            error = safe_error(result.stderr_tail, root)
        else:
            try:
                verify(stage)
                _move_build_files(stage, folder, names)
            except (VerificationError, OSError, ValueError) as problem:
                error = safe_error(f"publish: {problem}", root)
    except _NotBuilt as problem:
        error = str(problem)
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


class _NotBuilt(Exception):
    """A composition places a piece version whose build has not succeeded."""

    def __init__(self, unbuilt: list[str]) -> None:
        super().__init__(
            f"{', '.join(unbuilt)} {'is' if len(unbuilt) == 1 else 'are'} not built; "
            "a placed piece must be built before the room is"
        )


def composition_unbuilt_pieces(root: Path, folder: Path) -> list[str]:
    """Each placed piece version without a successful build, as "<package> version <N>"."""
    try:
        document = json.loads((folder / storage.INPUT_FILE).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    unbuilt = []
    for item in document.get("items", []):
        if item.get("type") != "piece":
            continue
        try:
            piece_folder = storage.version_dir(root, item["package_id"], item["version"])
        except (storage.InvalidPackageId, ValueError, KeyError):
            unbuilt.append(f"{item.get('package_id')} version {item.get('version')}")
            continue
        if (storage.read_status(piece_folder) or {}).get("status") != "succeeded":
            unbuilt.append(f"{item['package_id']} version {item['version']}")
    return unbuilt


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


def _notify(on_outcome: Callable[[str], None] | None, outcome: str) -> None:
    if on_outcome is None:
        return
    try:
        on_outcome(outcome)
    except Exception:  # noqa: BLE001 - a finished render must stay finished
        logger.warning("render.outcome_callback_failed")


async def _run_on_server(
    ticket: RenderTicket,
    *,
    expected: tuple,
    offload: OffloadRuntime | None,
    launch: Launch,
    blend: Path,
    folder: Path,
    scene_document: dict | None,
    stage: Path,
    limit: float,
    begin: Callable[[], None],
) -> tuple[LaunchResult, RemoteTimes | None]:
    """Run a ticketed render on the render server, one job at a time, never on the laptop.

    The ticket is checked and spent exactly as for a local render. A failure comes back
    as a failed `LaunchResult` carrying the reason.
    """
    if not isinstance(ticket, RenderTicket):
        raise RenderNotAuthorised("a render needs a ticket issued by the render guard")
    if not ticket.matches(*expected):
        raise RenderNotAuthorised("this render authorisation was issued for a different render")
    ticket.consume()
    if offload is None:
        return LaunchResult(1, "the render server is not configured", False), None
    quote = ticket.quote
    if quote.room:
        script, inputs_blend, package = ROOM_GENERATOR.name, None, folder
    else:
        script = (STILL_GENERATOR if quote.kind == "still" else TURNTABLE_GENERATOR).name
        inputs_blend, package = blend, None
    inputs = RemoteInputs(
        script=script, blend=inputs_blend,
        scene_document=scene_document if quote.room else None, package_dir=package,
    )
    async with offload.semaphore:
        try:
            times = await run_remote(
                config=offload.config, launch=launch, tier=quote.tier, kind=quote.kind,
                inputs=inputs, stage=stage, limit_seconds=limit, on_start=begin,
            )
        except RemoteFailed as failure:
            return LaunchResult(-1 if failure.timed_out else 1, failure.reason, failure.timed_out), None
    return LaunchResult(0, "", False), times


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
    before: Callable[[], Awaitable[object]] | None = None,
    on_outcome: Callable[[str], None] | None = None,
    offload: OffloadRuntime | None = None,
    on_remote_job: Callable[[dict], None] | None = None,
    models_root: Path | None = None,
) -> None:
    """Run one guarded render; never raises (a failure is recorded).

    The ticket decides everything: the tier's frames, resolution and engine are
    the only values that reach argv. `scene_document` is the room document for a
    room render. `on_finished(quote, actual_seconds)` runs after a success (the
    route uses it to calibrate the Cycles multiplier). `before()` runs once ahead
    of the launch — a detail render saves the live Blender's file with it — and
    a failure in it never stops the render. `on_outcome("succeeded" | "failed")`
    runs once when the render is over, whichever way it went. A ticket whose quote
    targets the render server runs there, through `offload`, and is never run on the
    laptop instead; `on_remote_job(record)` then gets the job's numbers.
    """
    quote = ticket.quote
    folder = storage.record_version_dir(root, quote.record, quote.package_id, quote.version)
    detail = quote.source == "detail"
    key = storage.render_key(quote.kind, quote.room, quote.source)
    if detail:
        target = storage.detail_dir(folder)
        blend = storage.detail_blend_path(folder)
    else:
        target = folder / "room" if quote.room else folder
        blend = folder / "model.blend"
    stage_name = folder / f"render-{key}"
    storage.sweep_stale_siblings(stage_name)
    stage = storage.staging_dir(stage_name)
    tier = quote.tier
    limit = timeout * tier.timeout_multiplier

    scene_path: Path | None = None
    remote_times: RemoteTimes | None = None
    try:
        if before is not None:
            try:
                await before()
            except Exception:  # noqa: BLE001 - the render goes on with the file as saved on disk
                logger.warning("render.before_failed")
        if detail and not blend.is_file():
            raise FileNotFoundError("the detail copy detail.blend is missing; start a detail pass first")
        remote = quote.target == "remote"
        if quote.room and scene_document is None:
            raise RenderNotAuthorised("a room render needs its scene document")
        argv: list[str] = []
        if not remote:
            if quote.record == "room" and not detail:
                argv = [str(blender_bin), "--background", "--python", str(COMPOSITION_RENDERER), "--",
                        "--spec", str(folder / storage.INPUT_FILE), "--pieces", str(root),
                        "--models", str(models_root or root / "models"), "--out", str(stage),
                        "--kind", quote.kind]
            elif quote.room:
                scene_path = folder / f".{key}.{uuid4().hex}.scene.json"
                scene_path.write_text(json.dumps(scene_document), encoding="utf-8")
                argv = [str(blender_bin), "--background", "--python", str(ROOM_GENERATOR), "--",
                        "--scene", str(scene_path), "--package", str(folder), "--out", str(stage)]
            else:
                script = STILL_GENERATOR if quote.kind == "still" else TURNTABLE_GENERATOR
                argv = [str(blender_bin), "--background", "--python", str(script), "--",
                        "--blend", str(blend), "--out", str(stage)]
            argv += ["--tier-frames", str(tier.frames), "--tier-resolution", str(tier.resolution),
                     "--tier-engine", tier.blender_engine]

        started_at = {"t": 0.0}

        def begin() -> None:
            # The lock is held by now: this is when the render truly starts.
            started_at["t"] = time.perf_counter()
            storage.write_render_status(
                folder, key, status="running", started_at=_now(), tier=tier.name,
                estimate_seconds=round(quote.estimate_seconds, 3),
            )
            log_render_started(quote, tracing=tracing)

        async def starting(args: list[str], cwd: Path, seconds: float) -> LaunchResult:
            begin()
            return await launch(args, cwd, seconds)

        error: str | None = None
        expected = (
            quote.package_id, quote.version, quote.kind, quote.room, quote.record, quote.source,
        )
        if remote:
            result, remote_times = await _run_on_server(
                ticket, expected=expected, offload=offload, launch=launch, blend=blend,
                folder=folder, scene_document=scene_document, stage=stage, limit=limit, begin=begin,
            )
        else:
            result = await launch_guarded(
                ticket, expected=expected, argv=argv, cwd=folder, timeout=limit,
                semaphore=semaphore, launch=starting,
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
                     "actual_seconds": round(actual, 3), "source": quote.source},
                )
            except (VerificationError, OSError, ValueError, KeyError) as problem:
                error = safe_error(f"publish: {problem}", root)
    except RenderNotAuthorised as refusal:
        storage.write_render_status(
            folder, key, status="failed", finished_at=_now(), error=safe_error(str(refusal), root)
        )
        _notify(on_outcome, "failed")
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
        transfer_seconds=remote_times.transfer_seconds if remote_times else None,
    )
    _notify(on_outcome, "failed" if error else "succeeded")
    if quote.target == "remote" and on_remote_job is not None:
        try:
            on_remote_job(
                {
                    "package_id": quote.package_id, "version": quote.version, "render_key": key,
                    "estimate_seconds": quote.estimate_seconds, "actual_seconds": actual,
                    "transfer_seconds": remote_times.transfer_seconds if remote_times else None,
                    "outcome": "failed" if error else "succeeded", "error": error,
                }
            )
        except Exception:  # noqa: BLE001 - the job list must never fail a finished render
            logger.warning("render.remote_job_not_recorded")
    if on_finished is not None and not error:
        try:
            # A remote final calibrates the server's rate from its render time alone.
            on_finished(quote, remote_times.render_seconds if remote_times else actual)
        except Exception:  # noqa: BLE001 - calibration must never fail a finished render
            logger.warning("render.calibration_failed")


async def run_model_check(
    *,
    model_folder: Path,
    entry: str,
    kind: str,
    blender_bin: Path,
    timeout: float,
    semaphore: asyncio.Semaphore,
    on_done: Callable[[dict | None, str | None], None],
    launch: Launch = subprocess_launch,
) -> None:
    """Import one library model headless and measure it (model-assets); never raises.

    Not a render: no tier applies, and it waits for the same one-process lock and
    timeout as a build. `on_done(report, error)` records the outcome; the report is
    also kept as the model's `check.json`.
    """
    stage = model_folder.parent / f".check-{model_folder.name}"
    shutil.rmtree(stage, ignore_errors=True)
    report: dict | None = None
    error: str | None = None
    try:
        result = await launch_unguarded(
            [str(blender_bin), "--background", "--factory-startup", "--python", str(CHECK_MODEL_GENERATOR), "--",
             "--model", str(model_folder / entry), "--kind", kind, "--out", str(stage)],
            cwd=model_folder, timeout=timeout, semaphore=semaphore, launch=launch,
        )
        if result.timed_out:
            error = "the model check took too long"
        elif result.exit_code != 0:
            error = "the model could not be imported: " + safe_error(result.stderr_tail, model_folder.parent)
        else:
            report = json.loads((stage / "check.json").read_text(encoding="utf-8"))
            os.replace(stage / "check.json", model_folder / "check.json")
    except Exception as problem:  # noqa: BLE001 - a background job must record, not raise
        error = f"the model check failed: {type(problem).__name__}"
    finally:
        shutil.rmtree(stage, ignore_errors=True)
    try:
        on_done(report, error)
    except Exception:  # noqa: BLE001 - recording must never crash the worker
        logger.warning("model_check.not_recorded")
    logger.info("model_check.finished", extra={"context": {"outcome": "failed" if error else "measured"}})
