"""`restyle_render` (Builder): draft turntables of a composed room in other styles.

Appearance only (restyle-variants): the composition, its items and prices never change, and
a variant is never a final. Renders are made of rooms only (rooms-only-renders): a piece is
not restyled, and a piece target is refused with the render tool's plain sentence. The tier
is required and only `draft` is accepted; one estimate covers the whole batch, then one draft
turntable per variant is rendered on the app loop, never waited for (two-tier-renders).
"""

from __future__ import annotations

import asyncio
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.agent import notices
from app.agent.tools.base import AgentTool, ToolContext, parse_args
from app.agent.tools.shared import builds_unavailable
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
    room_variants,
)
from plugins.render_turntable.tool import PIECE_REFUSED, RenderArgs
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

    # Kept so an old call gets the plain refusal, not a schema error (rooms-only-renders).
    package_id: str | None = Field(default=None, description="not restyled: renders are made of rooms")
    composition: str | None = Field(default=None, description="a composed room's name")
    version: int | None = Field(default=None, description="a version number; the latest when left out")
    tier: str | None = Field(default=None, description="required: draft")
    looks: list[Any] | None = Field(default=None, description="not used: pieces are not restyled")
    slots: list[str] | None = Field(default=None, description="not used: pieces are not restyled")
    variants: list[dict[str, Any]] | None = Field(default=None, description="not used: pieces are not restyled")
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
    if args.package_id:
        return PIECE_REFUSED
    if not args.composition:
        return "name the composed room to restyle (composition)"
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
        "Show a composed room (composition) in other styles, as draft turntables: pass `styles` "
        "(preset ids or 'all'). Appearance only: the room, its items and prices never change. Pieces "
        "are not restyled; a piece's colours and finishes change through a revision with the Designer. "
        "A tier is required and is draft; never pass frame counts, resolutions or "
        "engines. One estimate covers the whole batch."
    ),
    schema=RestyleArgs,
    run=run,
    preview=preview,
)
