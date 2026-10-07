"""`record_render_feedback` (Builder, Lighting & materials): the owner's reaction to a render.

The tool proposes the rating it read from the owner's words and records it only
after the owner answers yes. The package is the conversation's bound piece, never
an argument the model supplied; the target defaults to the piece's most recent
succeeded render (feedback-capture design decision 4).
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


class FeedbackArgs(BaseModel):
    rating: str = Field(description="'up' or 'down', as the owner reacted")
    comment: str | None = Field(
        default=None, description="the owner's own words about the render, if they gave any"
    )
    render: str | None = Field(
        default=None,
        description=(
            "which render: still, turntable, room-still, room-turntable, detail-still or "
            "detail-turntable; the most recent one when left out"
        ),
    )
    version: int | None = Field(default=None, description="a version number; the most recent render's when left out")


def _target(args: FeedbackArgs, ctx: ToolContext) -> RenderRun | str:
    """The run to rate, or a refusal."""
    if not ctx.package_id:
        return "there is no piece bound to this conversation; ask the owner which piece they mean"
    if args.render is not None and args.render not in storage.RENDER_KEYS:
        return f"unknown render {args.render!r}; use one of {', '.join(storage.RENDER_KEYS)}"
    query = select(RenderRun).where(
        RenderRun.package_id == ctx.package_id, RenderRun.outcome == "succeeded"
    )
    if args.version is not None:
        query = query.where(RenderRun.version == args.version)
    if args.render is not None:
        query = query.where(RenderRun.render_key == args.render)
    with Session(ctx.deps.engine) as session:
        run = session.scalars(query.order_by(RenderRun.started_at.desc()).limit(1)).first()
        if run is not None:
            session.expunge(run)
    if run is None:
        return "there is no finished render of this piece to rate yet"
    return run


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
    what = f"{ctx.package_id} version {run.version} {LABELS[run.render_key]} ({run.tier})"
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
        f"{LABELS[rated.render_key]} ({rated.tier})."
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
