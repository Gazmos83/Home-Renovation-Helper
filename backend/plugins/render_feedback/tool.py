"""`record_render_feedback` (Builder, Lighting & materials): the owner's reaction to a render.

The tool proposes the rating it read from the owner's words and records it only
after the owner answers yes. The package is the conversation's bound piece, never
an argument the model supplied; the target defaults to the piece's most recent
succeeded render (feedback-capture design decision 4), a restyle variant included
(two-tier-renders).
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agent.tools.base import AgentTool, Confirmation, ToolContext, parse_args
from app.agent.tools.shared import NOT_APPROVED
from app.blender import storage
from app.db.models import RenderRun
from app.feedback import ratings
from app.feedback.ratings import FeedbackRefused

LABELS = {
    "still": "still",
    "turntable": "turntable",
    "room-still": "still in the room",
    "room-turntable": "turntable in the room",
    "detail-still": "detailed still",
    "detail-turntable": "detailed turntable",
}
FACES = {"up": "thumbs up", "down": "thumbs down"}


def label_of(render_key: str) -> str:
    """How a render is named to the owner: a fixed render's words, or a restyle variant's id."""
    variant = storage.variant_of(render_key)
    return f"restyle {variant}" if variant else LABELS[render_key]


def _variant_matches(value: str, variant_id: str, label: str | None) -> bool:
    """Whether the model's `render` names this variant: its key, its id, its label, or a preset
    name its id starts with ("walnut" for `walnut-draft`)."""
    wanted = storage.variant_of(value) or value
    return wanted.lower() in {variant_id, (label or "").lower()} or variant_id.startswith(f"{wanted.lower()}-")


class FeedbackArgs(BaseModel):
    rating: str = Field(description="'up' or 'down', as the owner reacted")
    comment: str | None = Field(
        default=None, description="the owner's own words about the render, if they gave any"
    )
    render: str | None = Field(
        default=None,
        description=(
            "which render: still, turntable, room-still, room-turntable, detail-still, "
            "detail-turntable, or a restyle variant by its name (e.g. 'walnut'); the most recent "
            "one when left out"
        ),
    )
    version: int | None = Field(default=None, description="a version number; the most recent render's when left out")


def _target(args: FeedbackArgs, ctx: ToolContext) -> RenderRun | str:
    """The run to rate, or a refusal."""
    if not ctx.package_id:
        return "there is no piece bound to this conversation; ask the owner which piece they mean"
    fixed = args.render is None or args.render in storage.RENDER_KEYS
    query = select(RenderRun).where(
        RenderRun.package_id == ctx.package_id, RenderRun.outcome == "succeeded"
    )
    if args.version is not None:
        query = query.where(RenderRun.version == args.version)
    if args.render is not None:
        query = query.where(
            RenderRun.render_key == args.render
            if fixed
            else RenderRun.render_key.startswith(storage.VARIANT_KEY_PREFIX)
        )
    with Session(ctx.deps.engine) as session:
        runs = list(session.scalars(query.order_by(RenderRun.started_at.desc())))
        for found in runs:
            session.expunge(found)
    run = next((found for found in runs if _rateable(found, args, ctx)), None)
    if run is None:
        if not fixed:
            return (
                f"unknown render {args.render!r}; use one of {', '.join(storage.RENDER_KEYS)} "
                "or the name of a restyle variant of this piece"
            )
        return "there is no finished render of this piece to rate yet"
    return run


def _rateable(run: RenderRun, args: FeedbackArgs, ctx: ToolContext) -> bool:
    """A fixed render always; a variant only while its version holds it, and, when the model
    named one, only the variant it named."""
    variant = storage.variant_of(run.render_key)
    if variant is None:
        return True
    root = ctx.deps.render_root
    if not ratings.variant_published(root, run.package_id, run.version, variant):
        return False
    if args.render is None:
        return True
    label = ratings.variant_label(root, run.package_id, run.version, variant)
    return _variant_matches(args.render, variant, label)


def _checked(arguments: dict[str, Any], ctx: ToolContext) -> tuple[FeedbackArgs, RenderRun] | str:
    args, problem = parse_args(FeedbackArgs, arguments)
    if args is None:
        return problem
    if args.rating not in ratings.RATINGS:
        return "the rating must be 'up' or 'down'"
    if args.comment is not None and len(args.comment.strip()) > ratings.MAX_COMMENT_CHARACTERS:
        return f"the comment is longer than {ratings.MAX_COMMENT_CHARACTERS} characters; shorten it"
    run = _target(args, ctx)
    if isinstance(run, str):
        return run
    return args, run


def preview(arguments: dict[str, Any], ctx: ToolContext):
    checked = _checked(arguments, ctx)
    if isinstance(checked, str):
        return checked
    args, run = checked
    what = f"{ctx.package_id} version {run.version} {label_of(run.render_key)} ({run.tier})"
    said = f' with the comment "{args.comment.strip()}"' if args.comment and args.comment.strip() else ""
    return Confirmation(
        subject="render_feedback",
        summary=f"Record a {FACES[args.rating]} on {what}{said}?",
        proposal={
            "package_id": ctx.package_id,
            "version": run.version,
            "render": run.render_key,
            "tier": run.tier,
            "rating": args.rating,
            "comment": args.comment.strip() if args.comment and args.comment.strip() else None,
        },
    )


def run(arguments: dict[str, Any], ctx: ToolContext) -> str:
    if not ctx.approved:
        return NOT_APPROVED
    checked = _checked(arguments, ctx)
    if isinstance(checked, str):
        return checked
    args, target = checked
    try:
        with Session(ctx.deps.engine) as session:
            rated = ratings.rate(
                session,
                package_id=target.package_id,
                version=target.version,
                render_key=target.render_key,
                rating=args.rating,
                comment=args.comment,
                render_root=ctx.deps.render_root,
            )
    except FeedbackRefused as error:
        return error.reason
    tracing = ctx.deps.tracing
    if tracing is not None:
        tracing.record_feedback(
            rating=rated.rating, comment=rated.comment, tier=rated.tier, trace_id=rated.trace_id,
            slot=rated.slot, model=rated.model, package_id=rated.package_id, version=rated.version,
            render_key=rated.render_key,
        )
    return (
        f"Recorded a {FACES[rated.rating]} on {rated.package_id} version {rated.version} "
        f"{label_of(rated.render_key)} ({rated.tier})."
    )


record_render_feedback = AgentTool(
    name="record_render_feedback",
    description=(
        "Record the owner's thumbs up or down, with their comment, on a render of the bound "
        "piece. Use it when the owner reacts to a render in words. It shows what will be "
        "recorded and waits for the owner's yes."
    ),
    schema=FeedbackArgs,
    run=run,
    preview=preview,
)
