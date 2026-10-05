"""`render_turntable` (Builder): a still or turntable, only through the guard.

The tier is required and decides frames, resolution and engine; a raw value for
any of them is refused by name. `draft` and `preview` start straight away and
the reply carries the estimate; `final` pauses for the owner's yes (the guard's
own approval) and runs only on it. The render is enqueued on the app loop, never
waited for.
"""

from __future__ import annotations

import asyncio
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.agent.tools.base import AgentTool, Confirmation, ToolContext, parse_args
from app.agent.tools.shared import builds_unavailable, version_folder
from app.blender import runner, storage
from app.packages import service
from app.render import benchmark_store
from app.render.calibration import calibrate_after_render
from app.render.guard import RenderRefused, RenderTicket, authorise, quote


class RenderArgs(BaseModel):
    # Extra fields are accepted here only so the guard can refuse them by name.
    model_config = ConfigDict(extra="allow")

    package_id: str
    version: int | None = Field(default=None, description="a version number; the latest when left out")
    kind: str = Field(default="turntable", description="'turntable' or 'still'")
    tier: str | None = Field(default=None, description="required: draft, preview or final")
    room: dict[str, Any] | None = Field(
        default=None, description="the room document from room_fit, to render the piece in its room"
    )


def viewer_route(package_id: str, version: int, kind: str, room: bool) -> str:
    base = f"/packages/{package_id}/versions/{version}/files/"
    prefix = "room/" if room else ""
    return base + prefix + ("still.png" if kind == "still" else "viewer.html")


def _price_args(args: RenderArgs, ctx: ToolContext, package_id: str, number: int) -> dict[str, Any]:
    engine = ctx.deps.engine
    return {
        "package_id": package_id,
        "version": number,
        "kind": args.kind,
        "tier": args.tier,
        "tiers": ctx.deps.tiers,
        "benchmark": benchmark_store.read_benchmark(engine),
        "cycles_multiplier": benchmark_store.read_cycles_multiplier(engine),
        "room": args.room is not None,
        "raw_fields": list((args.model_extra or {}).keys()),
    }


def _checked(arguments: dict[str, Any], ctx: ToolContext):
    """`(args, folder, number, price_args, scene_document, priced)` or a refusal string."""
    args, problem = parse_args(RenderArgs, arguments)
    if args is None:
        return problem
    folder, number, problem = version_folder(ctx.deps, args.package_id, args.version)
    if folder is None or number is None:
        return problem
    price_args = _price_args(args, ctx, args.package_id, number)
    try:
        priced = quote(**price_args)
    except RenderRefused as error:
        return error.reason
    state = storage.read_status(folder) or {}
    if state.get("status") != "succeeded" or not (folder / "model.blend").is_file():
        return (
            f"{args.package_id} version {number} is not built yet, so it cannot be rendered; "
            "build it first"
        )
    scene_document = None
    if args.room is not None:
        try:
            scene_document = service.room_scene_document(folder, args.kind, args.room)
        except service.RoomDocumentRefused as error:
            return f"the room document is not usable: {error}"
    return args, folder, number, price_args, scene_document, priced


def preview(arguments: dict[str, Any], ctx: ToolContext) -> Confirmation | str | None:
    checked = _checked(arguments, ctx)
    if isinstance(checked, str):
        return checked
    _args, _folder, _number, _price, _scene, priced = checked
    unavailable = builds_unavailable(ctx.deps)
    if unavailable:
        return unavailable
    if priced.tier.name != "final":
        return None
    return Confirmation(
        subject="final_render",
        summary=f"A final render needs your approval: {priced.summary}",
        proposal={
            "package_id": priced.package_id,
            "version": priced.version,
            "kind": priced.kind,
            "tier": priced.tier.name,
            "estimate_seconds": round(priced.estimate_seconds, 1),
            "estimate": priced.estimate_text,
        },
    )


def run(arguments: dict[str, Any], ctx: ToolContext) -> str:
    checked = _checked(arguments, ctx)
    if isinstance(checked, str):
        return checked
    args, folder, number, price_args, scene_document, priced = checked
    unavailable = builds_unavailable(ctx.deps)
    if unavailable:
        return unavailable
    try:
        ticket: RenderTicket = authorise(**price_args, approval="yes" if ctx.approved else None)
    except RenderRefused as error:
        return error.reason

    deps = ctx.deps
    settings = deps.settings
    runner.mark_render_queued(folder, ticket)
    asyncio.run_coroutine_threadsafe(
        runner.run_render(
            ticket,
            root=settings.render_root,
            blender_bin=settings.blender_bin,
            timeout=settings.blender_timeout_seconds,
            semaphore=deps.semaphore,
            launch=deps.launch,
            scene_document=scene_document,
            tracing=deps.tracing,
            on_finished=lambda finished, actual: calibrate_after_render(deps.engine, finished, actual),
        ),
        deps.loop,
    )
    what = "still" if priced.kind == "still" else "turntable"
    return (
        f"Started a {priced.tier.name} {what} of {args.package_id} version {number}: "
        f"{priced.estimate_text}. When it finishes it will be at "
        f"{viewer_route(args.package_id, number, priced.kind, scene_document is not None)}."
    )


render_turntable = AgentTool(
    name="render_turntable",
    description=(
        "Render a still or a turntable of a built piece. A tier is required (draft, preview or "
        "final) and decides frames, resolution and engine; never pass those. Optionally pass the "
        "room document from room_fit to render the piece in its room. Draft and preview start "
        "now; final waits for the owner's yes."
    ),
    schema=RenderArgs,
    run=run,
    preview=preview,
)
