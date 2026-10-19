"""`render_turntable` (Builder): a still or turntable, only through the guard.

The tier is required and decides frames, resolution and engine; a raw value for
any of them is refused by name. `draft` starts straight away and the reply
carries the estimate; `final` pauses for the owner's yes (the guard's own
approval) and runs only on it. Renders are made of composed rooms and apartment shells
only (rooms-only-renders): a piece, on its own or placed in a room, is refused in plain
words. The render is enqueued on the app loop, never waited for.
"""

from __future__ import annotations

import asyncio
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.agent import house_file, notices
from app.agent.tools.base import AgentTool, Confirmation, ToolContext, parse_args
from app.agent.tools.shared import builds_unavailable
from app.blender import runner, storage
from app.feedback import runs as feedback_runs
from app.render import benchmark_store
from app.render.calibration import calibrate_after_render
from app.render.guard import RenderRefused, RenderTicket, authorise, quote
from app.render.offload import jobs as offload_jobs
from app.render.offload.runtime import (
    confirm_server_sync,
    remote_benchmark_for,
    target_for,
)


class RenderArgs(BaseModel):
    # Extra fields are accepted here only so the guard can refuse them by name.
    model_config = ConfigDict(extra="allow")

    # Kept so an old call gets the plain refusal, not a schema error (rooms-only-renders).
    package_id: str | None = Field(default=None, description="not rendered: renders are made of rooms")
    shell: str | None = Field(
        default=None, description="an apartment's name, to render its shell instead of a piece"
    )
    composition: str | None = Field(
        default=None, description="a composed room's (or apartment's) name, to render that composition"
    )
    version: int | None = Field(default=None, description="a version number; the latest when left out")
    kind: str = Field(default="turntable", description="'turntable' or 'still'")
    tier: str | None = Field(default=None, description="required: draft or final")
    in_room: bool = Field(default=False, description="not rendered: renders are made of rooms")


def _price_args(
    args: RenderArgs, ctx: ToolContext, package_id: str, number: int, record: str = "piece"
) -> dict[str, Any]:
    return {
        "record": record,
        "package_id": package_id,
        "version": number,
        "kind": args.kind,
        "tier": args.tier,
        **benchmark_store.quote_inputs(ctx.deps.engine, ctx.deps.tiers),
        "room": args.in_room,
        "raw_fields": list((args.model_extra or {}).keys()),
    }


# The one sentence the Builder passes on for a piece (rooms-only-renders).
PIECE_REFUSED = (
    "renders are made of rooms, not pieces; offer to compose the room with this piece and render the room "
    "(a piece is looked at in its inspector)"
)


def _target(args: RenderArgs, ctx: ToolContext):
    """`(record, id, folder, version)` of what to render, or a refusal string."""
    if args.package_id or (args.in_room and not args.composition and not args.shell):
        return PIECE_REFUSED
    if sum(bool(target) for target in (args.package_id, args.shell, args.composition)) != 1:
        return (
            "name exactly one target: a shell (an apartment) or a composition (a composed room)"
        )
    if args.composition:
        if args.in_room:
            return "a composed room is already a room; render it without in_room"
        with ctx.deps.session() as session:
            found = house_file.composition_by_scope(session, "room", args.composition) or (
                house_file.composition_by_scope(session, "apartment", args.composition)
            )
            if found is None:
                return f"there is no composition {args.composition!r}; compose the room first"
            slug = found.slug
        root = ctx.deps.render_root
        number = args.version if args.version is not None else (storage.composition_versions(root, slug) or [None])[-1]
        if number is None:
            return f"{args.composition!r} has no version yet; compose it first"
        try:
            folder = storage.composition_version_dir(root, slug, number)
        except ValueError:
            return f"version {number} is not a valid version"
        if not folder.is_dir():
            return f"{args.composition!r} has no version {number}"
        return "room", slug, folder, number
    if args.shell:
        if args.in_room:
            return "an apartment's shell cannot be rendered placed in a room"
        with ctx.deps.session() as session:
            apartment = house_file.find_apartment(session, args.shell)
            if apartment is None:
                known = ", ".join(a.name for a in house_file.apartments(session)) or "none"
                return f"there is no apartment {args.shell!r}; its apartments are: {known}"
            slug = storage.apartment_slug(apartment.name)
        root = ctx.deps.render_root
        number = args.version if args.version is not None else (storage.shell_versions(root, slug) or [None])[-1]
        if number is None:
            return f"{args.shell!r} has no built shell yet; build it first"
        try:
            folder = storage.shell_version_dir(root, slug, number)
        except ValueError:
            return f"version {number} is not a valid version"
        if not folder.is_dir():
            return f"the shell of {args.shell!r} has no version {number}"
        return "shell", slug, folder, number
    return PIECE_REFUSED


def _checked(arguments: dict[str, Any], ctx: ToolContext):
    """`(args, folder, number, price_args, scene_document, priced)` or a refusal string."""
    args, problem = parse_args(RenderArgs, arguments)
    if args is None:
        return problem
    target = _target(args, ctx)
    if isinstance(target, str):
        return target
    record, target_id, folder, number = target
    price_args = _price_args(args, ctx, target_id, number, record)
    # A final goes to the render server when the developer chose it; if the server cannot
    # be used the render is refused here, before any approval, and never moved to the laptop.
    where = target_for(ctx.deps.engine, args.tier)
    try:
        if where == "remote":
            confirm_server_sync(ctx.deps.loop, ctx.deps.offload, ctx.deps.launch)
        price_args["target"] = where
        price_args["remote_benchmark"] = remote_benchmark_for(ctx.deps.engine, where, ctx.deps.offload)
        priced = quote(**price_args)
    except RenderRefused as error:
        return error.reason
    state = storage.read_status(folder) or {}
    if state.get("status") != "succeeded" or not (folder / "model.blend").is_file():
        return (
            f"{target_id} version {number} is not built yet, so it cannot be rendered; "
            "build it first"
        )
    scene_document = None
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
        summary=" ".join(filter(None, [f"A final render needs your approval: {priced.summary}.", priced.warning])),
        proposal={
            "package_id": priced.package_id,
            "version": priced.version,
            "kind": priced.kind,
            "tier": priced.tier.name,
            "estimate_seconds": round(priced.estimate_seconds, 1),
            "estimate": priced.estimate_text,
            "target": priced.target,
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
    run_id = feedback_runs.record_run(deps.engine, ticket.quote, feedback_runs.origin_from(ctx))
    # A room render is followed by the thread's progress until its notice is posted (room-render-notices).
    notices.follow_room(deps, ctx.thread_id, ticket.quote)
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
            on_outcome=lambda outcome: notices.finished(deps, ctx.thread_id, run_id, ticket.quote, outcome),
            offload=deps.offload,
            on_remote_job=lambda record: offload_jobs.record_job(deps.engine, record),
            models_root=settings.upload_root / "models",
        ),
        deps.loop,
    )
    what = "still" if priced.kind == "still" else "turntable"
    label = f"the {args.shell} shell" if args.shell else args.composition
    arrives = "a notice appears"
    note = ""
    if priced.record == "room":
        from app import compositions

        with deps.session() as session:
            placed = house_file.placed_items(session, compositions.read_document(folder) or {})
        stale = [item["name"] for item in placed if item.get("no_longer_approved")]
        if stale:
            note = f" Note: {', '.join(stale)} {'is' if len(stale) == 1 else 'are'} no longer approved."
    return (
        f"Started a {priced.tier.name} {what} of {label} version {number}: "
        f"{priced.estimate_text}. When it finishes, {arrives} in this chat.{note}"
    )


render_turntable = AgentTool(
    name="render_turntable",
    description=(
        "Render a still or a turntable of a composed room (composition) or of an apartment's shell "
        "(shell). Pieces are not rendered: a piece is looked at in its inspector, and shown in a room by "
        "composing that room. A tier is required (draft or final) and decides "
        "frames, resolution and engine; never pass those. "
        "A draft starts now; final waits for the owner's yes."
    ),
    schema=RenderArgs,
    run=run,
    preview=preview,
)
