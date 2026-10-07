"""The Lighting & materials tools (ladder step 3; photoreal-detail).

`start_detail_pass` pauses for the owner, then copies the built model to
`detail/detail.blend` and opens it in the live Blender. `run_detail_script`
sends one allow-listed script and answers with the scene as text.
`detail_screenshot` is for the owner: the agent is text-only. `render_detail`
renders the detail copy at tier `final` through the render guard, behind the
owner's typed yes. Nothing here reads or writes the spec.

The package always comes from the conversation's bound piece, never from an
argument the model supplied (CLAUDE.md §8).
"""

from __future__ import annotations

import asyncio
import concurrent.futures
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.agent import house_file
from app.agent.tools.base import AgentTool, Confirmation, ToolContext, parse_args
from app.agent.tools.shared import NOT_APPROVED, builds_unavailable, version_folder
from app.blender import runner, storage
from app.feedback import runs as feedback_runs
from app.live.detail_pass import DetailPass, DetailPassError, untrusted
from app.live.socket_client import AddonError, LiveRefused
from app.render import benchmark_store
from app.render.calibration import calibrate_after_render
from app.render.guard import RenderRefused, RenderTicket, authorise, quote
from app.render.offload import jobs as offload_jobs
from app.render.offload.runtime import (
    confirm_server_sync,
    remote_benchmark_for,
    target_for,
)

# One call may run several socket commands, each up to the socket timeout.
LIVE_CALL_SECONDS = 900.0

NO_PASS = (
    "no detail pass has been started for {package} version {version}; "
    "start one first (it needs the owner's confirmation)"
)


class VersionArgs(BaseModel):
    version: int | None = Field(
        default=None, description="a version number; the bound piece's (or the composition's) latest when left out"
    )
    composition: str | None = Field(
        default=None,
        description="a composed room's name, to detail that room (its lighting and look) instead of the bound piece",
    )


class ScriptArgs(VersionArgs):
    code: str = Field(
        description=(
            "Blender Python for the open detail scene: bpy.data, modifiers, materials, node "
            "trees and render settings only. No imports other than bpy, bmesh, mathutils, math, "
            "random; no file access; no rendering."
        )
    )
    purpose: str = Field(max_length=300, description="one sentence: what this script changes")


class RenderDetailArgs(VersionArgs):
    # Extra fields are accepted here only so the guard can refuse them by name.
    model_config = ConfigDict(extra="allow")

    kind: str = Field(default="turntable", description="'turntable' or 'still'")
    tier: str | None = Field(default=None, description="required; a detail render is 'final' only")


def _record(args: VersionArgs) -> str:
    return "room" if args.composition else "piece"


def _folder(ctx: ToolContext, args: VersionArgs) -> tuple[str, Path, int] | str:
    """`(id, folder, version)` of the bound piece, or of the named composition; or a refusal."""
    version = args.version
    if args.composition:
        with ctx.deps.session() as session:
            found = house_file.composition_by_scope(session, "room", args.composition) or (
                house_file.composition_by_scope(session, "apartment", args.composition)
            )
            if found is None:
                return f"there is no composition {args.composition!r}; compose the room first"
            slug = found.slug
        root = ctx.deps.render_root
        number = version if version is not None else (storage.composition_versions(root, slug) or [None])[-1]
        if number is None:
            return f"{args.composition!r} has no version yet"
        try:
            folder = storage.composition_version_dir(root, slug, number)
        except ValueError:
            return f"version {number} is not a valid version"
        if not folder.is_dir():
            return f"{args.composition!r} has no version {number}"
        return slug, folder, number
    if not ctx.package_id:
        return "there is no piece bound to this conversation; ask the owner which piece to detail"
    folder, number, problem = version_folder(ctx.deps, ctx.package_id, version)
    if folder is None or number is None:
        return problem
    return ctx.package_id, folder, number


def _built(folder: Path) -> bool:
    state = storage.read_status(folder) or {}
    return state.get("status") == "succeeded" and (folder / "model.blend").is_file()


def _call(ctx: ToolContext, coroutine: Any) -> Any:
    """Run a coroutine on the app's loop from the tool's thread."""
    loop = ctx.deps.loop
    if loop is None:
        coroutine.close()
        raise DetailPassError(
            "the Blender queue is not running, so the live Blender cannot be used right now"
        )
    future = asyncio.run_coroutine_threadsafe(coroutine, loop)
    try:
        return future.result(timeout=LIVE_CALL_SECONDS)
    except concurrent.futures.TimeoutError:
        future.cancel()
        raise DetailPassError("Blender took too long to answer") from None


def _session(ctx: ToolContext, folder: Path) -> DetailPass:
    return DetailPass(folder, ctx.deps.live, tracing=ctx.deps.tracing)


def _files_route(package_id: str, version: int, name: str, record: str = "piece") -> str:
    if record == "room":
        return f"/compositions/{package_id}/versions/{version}/files/{name}"
    return f"/packages/{package_id}/versions/{version}/files/{name}"


# --- start_detail_pass ---------------------------------------------------------------------------


def start_preview(arguments: dict[str, Any], ctx: ToolContext):
    args, problem = parse_args(VersionArgs, arguments)
    if args is None:
        return problem
    target = _folder(ctx, args)
    if isinstance(target, str):
        return target
    package_id, folder, number = target
    if not _built(folder):
        return (
            f"{package_id} version {number} is not built yet, so it cannot be detailed; "
            "ask for it to be built first"
        )
    continuing = storage.detail_blend_path(folder).is_file()
    return Confirmation(
        subject="detail_pass",
        summary=(
            f"Start a detail pass on {package_id} version {number}? The file open in your live "
            f"Blender will be replaced by "
            + ("the detail copy from the earlier pass" if continuing else "a copy of this version")
            + ". The model, spec and cut list are not changed."
        ),
        proposal={"package_id": package_id, "version": number, "continuing": continuing},
    )


def start_run(arguments: dict[str, Any], ctx: ToolContext) -> str:
    if not ctx.approved:
        return NOT_APPROVED
    args, problem = parse_args(VersionArgs, arguments)
    if args is None:
        return problem
    target = _folder(ctx, args)
    if isinstance(target, str):
        return target
    package_id, folder, number = target
    try:
        report = _call(ctx, _session(ctx, folder).start())
    except DetailPassError as error:
        return error.reason
    except LiveRefused as error:
        return error.reason
    except AddonError as error:
        return f"Blender reported an error:\n{untrusted(error.message)}"
    return (
        f"The detail pass is open on {package_id} version {number} in the owner's Blender. "
        f"The scene:\n{untrusted(report)}"
    )


start_detail_pass = AgentTool(
    name="start_detail_pass",
    description=(
        "Start (or continue) a detail pass on a built version of the bound piece: its model is "
        "copied to a detail file and opened in the owner's live Blender. Needs the owner's "
        "confirmation. Do this before run_detail_script."
    ),
    schema=VersionArgs,
    run=start_run,
    preview=start_preview,
)


# --- run_detail_script ----------------------------------------------------------------------------


def script_run(arguments: dict[str, Any], ctx: ToolContext) -> str:
    args, problem = parse_args(ScriptArgs, arguments)
    if args is None:
        return problem
    target = _folder(ctx, args)
    if isinstance(target, str):
        return target
    package_id, folder, number = target
    if not storage.detail_blend_path(folder).is_file():
        return NO_PASS.format(package=package_id, version=number)
    try:
        return _call(ctx, _session(ctx, folder).run_script(args.code, args.purpose))
    except DetailPassError as error:
        return error.reason


run_detail_script = AgentTool(
    name="run_detail_script",
    description=(
        "Send one Blender Python script to the open detail scene. It is checked against an "
        "allow-list first and refused by name if it uses anything outside bpy.data, modifiers, "
        "materials, node trees or render settings. Answers with the scene as text. Give a "
        "one-sentence purpose."
    ),
    schema=ScriptArgs,
    run=script_run,
)


# --- detail_screenshot ----------------------------------------------------------------------------


def screenshot_run(arguments: dict[str, Any], ctx: ToolContext) -> str:
    args, problem = parse_args(VersionArgs, arguments)
    if args is None:
        return problem
    target = _folder(ctx, args)
    if isinstance(target, str):
        return target
    package_id, folder, number = target
    if not storage.detail_blend_path(folder).is_file():
        return NO_PASS.format(package=package_id, version=number)
    try:
        index, _path = _call(ctx, _session(ctx, folder).screenshot())
    except DetailPassError as error:
        return error.reason
    route = _files_route(package_id, number, f"detail/screens/{index}", _record(args))
    return (
        f"A screenshot was saved for the owner at {route}. You cannot see images: tell the "
        "owner it is there and ask them to say what to change."
    )


detail_screenshot = AgentTool(
    name="detail_screenshot",
    description=(
        "Save a screenshot of the live viewport for the owner to look at. You cannot see it; "
        "use it to let the owner judge a visual change."
    ),
    schema=VersionArgs,
    run=screenshot_run,
)


# --- render_detail ---------------------------------------------------------------------------------


def _price_args(args: RenderDetailArgs, ctx: ToolContext, package_id: str, number: int) -> dict[str, Any]:
    engine = ctx.deps.engine
    return {
        "record": _record(args),
        "package_id": package_id,
        "version": number,
        "kind": args.kind,
        "tier": args.tier,
        "tiers": ctx.deps.tiers,
        "benchmark": benchmark_store.read_benchmark(engine),
        "cycles_multiplier": benchmark_store.read_cycles_multiplier(engine),
        "room": False,
        "raw_fields": list((args.model_extra or {}).keys()),
        "source": "detail",
    }


def _checked(arguments: dict[str, Any], ctx: ToolContext):
    """`(args, package_id, folder, number, price_args, priced)` or a refusal string."""
    args, problem = parse_args(RenderDetailArgs, arguments)
    if args is None:
        return problem
    target = _folder(ctx, args)
    if isinstance(target, str):
        return target
    package_id, folder, number = target
    price_args = _price_args(args, ctx, package_id, number)
    where = target_for(ctx.deps.engine, args.tier)
    try:
        if where == "remote":
            confirm_server_sync(ctx.deps.loop, ctx.deps.offload, ctx.deps.launch)
        price_args["target"] = where
        price_args["remote_benchmark"] = remote_benchmark_for(ctx.deps.engine, where)
        priced = quote(**price_args)
    except RenderRefused as error:
        return error.reason
    if not storage.detail_blend_path(folder).is_file():
        return NO_PASS.format(package=package_id, version=number)
    return args, package_id, folder, number, price_args, priced


def render_preview(arguments: dict[str, Any], ctx: ToolContext):
    checked = _checked(arguments, ctx)
    if isinstance(checked, str):
        return checked
    _args, _package_id, _folder_path, _number, _price, priced = checked
    unavailable = builds_unavailable(ctx.deps)
    if unavailable:
        return unavailable
    return Confirmation(
        subject="detail_render",
        summary=f"A final render of the detailed copy needs your approval: {priced.summary}",
        proposal={
            "package_id": priced.package_id,
            "version": priced.version,
            "kind": priced.kind,
            "tier": priced.tier.name,
            "source": "detail",
            "estimate_seconds": round(priced.estimate_seconds, 1),
            "estimate": priced.estimate_text,
        },
    )


def render_run(arguments: dict[str, Any], ctx: ToolContext) -> str:
    checked = _checked(arguments, ctx)
    if isinstance(checked, str):
        return checked
    _args, package_id, folder, number, price_args, priced = checked
    unavailable = builds_unavailable(ctx.deps)
    if unavailable:
        return unavailable
    try:
        ticket: RenderTicket = authorise(**price_args, approval="yes" if ctx.approved else None)
    except RenderRefused as error:
        return error.reason

    deps = ctx.deps
    settings = deps.settings
    session = _session(ctx, folder)
    runner.mark_render_queued(folder, ticket)
    run_id = feedback_runs.record_run(deps.engine, ticket.quote, feedback_runs.origin_from(ctx))
    asyncio.run_coroutine_threadsafe(
        runner.run_render(
            ticket,
            root=settings.render_root,
            blender_bin=settings.blender_bin,
            timeout=settings.blender_timeout_seconds,
            semaphore=deps.semaphore,
            launch=deps.launch,
            tracing=deps.tracing,
            on_finished=lambda finished, actual: calibrate_after_render(deps.engine, finished, actual),
            before=session.save,
            on_outcome=lambda outcome: feedback_runs.finish_run(deps.engine, run_id, outcome),
            offload=deps.offload,
            on_remote_job=lambda record: offload_jobs.record_job(deps.engine, record),
        ),
        deps.loop,
    )
    what = "still" if priced.kind == "still" else "turntable"
    route = _files_route(
        package_id, number, "detail/still.png" if priced.kind == "still" else "detail/viewer.html", priced.record
    )
    return (
        f"Started a final {what} of the detailed {package_id} version {number}: "
        f"{priced.estimate_text}. When it finishes it will be at {route}."
    )


render_detail = AgentTool(
    name="render_detail",
    description=(
        "Render a still or turntable of the detailed copy of the bound piece. The tier is "
        "required and must be final (check progress with a screenshot instead); never pass "
        "frames, resolution or engine. Waits for the owner's yes and shows the estimate."
    ),
    schema=RenderDetailArgs,
    run=render_run,
    preview=render_preview,
)
