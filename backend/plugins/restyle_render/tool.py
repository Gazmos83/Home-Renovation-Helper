"""`restyle_render` (Builder): draft turntables of a built version in other looks or styles.

Appearance only (restyle-variants): a piece is shown with other colours and finishes on its
own material slots, a composed room in other styles. The spec, cut list and prices never
change, and a variant is never a final. The tier is required and only `draft` is accepted;
one estimate covers the whole batch, then one draft turntable per variant is rendered on
the app loop, never waited for (two-tier-renders). Each variant of a piece is recorded as a
render run, so the owner can rate it like any render.
"""

from __future__ import annotations

import asyncio
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.agent import notices
from app.agent.tools.base import AgentTool, ToolContext, parse_args
from app.agent.tools.shared import builds_unavailable, read_input
from app.blender import restyle_runner, storage
from app.feedback import runs as feedback_runs
from app.render import benchmark_store
from app.render.estimate import describe
from app.render.guard import (
    FORBIDDEN_FIELDS,
    RenderRefused,
    RenderTicket,
    authorise,
    quote,
)
from app.restyle import store
from app.restyle.presets import APPEARANCE_NOTE, Presets, load_presets
from app.restyle.request import (
    RestyleRefused,
    VariantPlan,
    expand_looks,
    piece_variants,
    room_variants,
)
from plugins.render_turntable.tool import RenderArgs
from plugins.render_turntable.tool import _target as render_target

_PRESETS: Presets | None = None


def presets() -> Presets:
    """The shipped looks and styles, read once."""
    global _PRESETS
    if _PRESETS is None:
        _PRESETS = load_presets()
    return _PRESETS


class RestyleArgs(BaseModel):
    # Extra fields are accepted here only so they can be refused by name.
    model_config = ConfigDict(extra="allow")

    package_id: str | None = Field(default=None, description="the piece's package id")
    composition: str | None = Field(default=None, description="a composed room's name")
    version: int | None = Field(default=None, description="a version number; the latest when left out")
    tier: str | None = Field(default=None, description="required: draft")
    looks: list[Any] | None = Field(
        default=None, description="piece: look preset ids (or 'all'); each becomes one variant on `slots`"
    )
    slots: list[str] | None = Field(default=None, description="piece: the material slots `looks` apply to")
    variants: list[dict[str, Any]] | None = Field(
        default=None, description="piece: explicit variants, each a mapping of slot name to look id"
    )
    styles: list[Any] | None = Field(
        default=None, description="composition: style preset ids (or 'all'), one variant each"
    )


def _unknown_fields(args: RestyleArgs) -> str | None:
    for name in (args.model_extra or {}):
        if name not in FORBIDDEN_FIELDS:
            return f"{name} is not something a restyle takes"
    return None


def _checked(arguments: dict[str, Any], ctx: ToolContext):
    """`(folder, number, record, target_id, plans, ids, quotes)` or a refusal string."""
    args, problem = parse_args(RestyleArgs, arguments)
    if args is None:
        return problem
    unknown = _unknown_fields(args)
    if unknown:
        return unknown
    if bool(args.package_id) == bool(args.composition):
        return "name exactly one target: a package_id (a piece) or a composition (a composed room)"
    target = render_target(
        RenderArgs(package_id=args.package_id, composition=args.composition, version=args.version), ctx
    )
    if isinstance(target, str):
        return target
    record, target_id, folder, number = target
    state = storage.read_status(folder) or {}
    if state.get("status") != "succeeded" or not (folder / "model.blend").is_file():
        return f"{target_id} version {number} is not built yet, so it cannot be restyled; build it first"
    looks = presets()
    try:
        if record == "piece":
            if args.styles:
                return "a piece takes looks, not styles; styles are for a composed room"
            spec = read_input(folder)
            if spec is None:
                return f"{target_id} version {number} has no readable spec to take its slots from"
            variants = list(args.variants or [])
            if args.looks:
                variants += expand_looks(args.looks, args.slots or [], looks)
            plans = piece_variants(spec, variants, looks)
        else:
            if args.looks or args.variants or args.slots:
                return "a composed room takes styles, not looks"
            plans = room_variants(args.styles or [], looks)
    except RestyleRefused as refusal:
        return refusal.reason
    ids = store.allocate_ids(folder, [plan.base_id for plan in plans], str(args.tier))
    price = {
        "package_id": target_id, "version": number, "kind": "turntable", "tier": args.tier,
        "tiers": ctx.deps.tiers, "benchmark": benchmark_store.read_benchmark(ctx.deps.engine),
        "cycles_multiplier": benchmark_store.read_cycles_multiplier(ctx.deps.engine),
        "raw_fields": list((args.model_extra or {}).keys()), "record": record, "source": "restyle",
    }
    try:
        quotes = [quote(**price, variant=variant) for variant in ids]
    except RenderRefused as refusal:
        return refusal.reason
    return folder, number, record, target_id, plans, ids, quotes, price


def preview(arguments: dict[str, Any], ctx: ToolContext) -> str | None:
    checked = _checked(arguments, ctx)
    if isinstance(checked, str):
        return checked
    return builds_unavailable(ctx.deps)


def _reply(
    folder, number: int, target_id: str, plans: list[VariantPlan], quotes, tier: str
) -> str:
    seconds = sum(q.estimate_seconds for q in quotes)
    labels = ", ".join(plan.label for plan in plans)
    overflow = len(store.list_variants(folder)) + len(plans) - store.MAX_VARIANTS
    note = (
        f" A version holds {store.MAX_VARIANTS} variants, so the oldest {overflow} will be replaced."
        if overflow > 0 else ""
    )
    return (
        f"Started {len(plans)} {tier} restyle turntable{'s' if len(plans) != 1 else ''} of {target_id} "
        f"version {number} ({labels}): {describe(seconds)} in all. A notice appears in this chat when "
        f"they finish; they are {APPEARANCE_NOTE}, and the design itself is unchanged.{note}"
    )


def run(arguments: dict[str, Any], ctx: ToolContext) -> str:
    checked = _checked(arguments, ctx)
    if isinstance(checked, str):
        return checked
    folder, number, _record, target_id, plans, ids, quotes, price = checked
    unavailable = builds_unavailable(ctx.deps)
    if unavailable:
        return unavailable
    try:
        tickets: list[RenderTicket] = [authorise(**price, variant=variant) for variant in ids]
    except RenderRefused as refusal:
        return refusal.reason
    deps = ctx.deps
    settings = deps.settings
    origin = feedback_runs.origin_from(ctx)
    jobs = [
        restyle_runner.RestyleJob(
            ticket, plan, variant, run_id=feedback_runs.record_run(deps.engine, ticket.quote, origin)
        )
        for ticket, plan, variant in zip(tickets, plans, ids, strict=True)
    ]
    first = tickets[0].quote
    asyncio.run_coroutine_threadsafe(
        restyle_runner.run_restyle(
            jobs,
            root=settings.render_root,
            blender_bin=settings.blender_bin,
            timeout=settings.blender_timeout_seconds,
            semaphore=deps.semaphore,
            launch=deps.launch,
            models_root=settings.upload_root / "models",
            tracing=deps.tracing,
            on_outcome=lambda outcome: notices.post(deps, ctx.thread_id, first, outcome),
            on_variant=lambda job, outcome: feedback_runs.finish_run(deps.engine, job.run_id, outcome),
        ),
        deps.loop,
    )
    return _reply(folder, number, target_id, plans, quotes, first.tier.name)


restyle_render = AgentTool(
    name="restyle_render",
    description=(
        "Show a built piece in other colours and finishes, or a composed room in other styles, as "
        "draft turntables. Appearance only: the design, materials, cut list and prices never change. "
        "A piece (package_id): pass `slots` (its material slot names) with `looks` (preset ids or "
        "'all'), or explicit `variants`. A composed room (composition): pass `styles` (preset ids or "
        "'all'). A tier is required and is draft; never pass frame counts, resolutions or "
        "engines. One estimate covers the whole batch."
    ),
    schema=RestyleArgs,
    run=run,
    preview=preview,
)
