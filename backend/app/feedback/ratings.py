"""The owner's rating of a render (feedback-capture design decisions 2, 5 and 7).

One current rating per render run: rating again replaces it, clearing removes
it. The target is always the latest *succeeded* run of a version's render, so a
re-render starts unrated and a render that never ran cannot be rated.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Final
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.blender import storage
from app.db.models import RenderFeedback, RenderRun
from app.feedback.runs import latest_succeeded_run

RATINGS: Final = ("up", "down")
MAX_COMMENT_CHARACTERS: Final = 1000
RECENT_LIMIT: Final = 5


class FeedbackRefused(Exception):
    """A rating that cannot be recorded. `reason` is safe to show; `status` is HTTP-shaped."""

    def __init__(self, reason: str, *, failure_class: str = "refused", status: int = 422) -> None:
        super().__init__(reason)
        self.reason = reason
        self.failure_class = failure_class
        self.status = status


@dataclass(frozen=True, slots=True)
class Rated:
    """A stored rating with what tracing needs to attribute it. Detached from the session."""

    run_id: UUID
    package_id: str
    version: int
    render_key: str
    tier: str
    trace_id: str | None
    slot: str | None
    model: str | None
    rating: str
    comment: str | None


def _clean_comment(comment: object) -> str | None:
    if comment is None:
        return None
    if not isinstance(comment, str):
        raise FeedbackRefused("the comment must be text", failure_class="invalid_comment")
    cleaned = comment.strip()
    if len(cleaned) > MAX_COMMENT_CHARACTERS:
        raise FeedbackRefused(
            f"the comment is longer than {MAX_COMMENT_CHARACTERS} characters",
            failure_class="invalid_comment",
        )
    return cleaned or None


def _target(session: Session, package_id: str, version: int, render_key: str) -> RenderRun:
    if render_key not in storage.RENDER_KEYS:
        raise FeedbackRefused(
            f"unknown render {render_key!r}; use one of {', '.join(storage.RENDER_KEYS)}",
            failure_class="unknown_render",
            status=404,
        )
    run = latest_succeeded_run(session, package_id, version, render_key)
    if run is None:
        raise FeedbackRefused(
            "the render does not exist yet, so it cannot be rated",
            failure_class="no_render",
            status=409,
        )
    return run


def rate(
    session: Session,
    *,
    package_id: str,
    version: int,
    render_key: str,
    rating: object,
    comment: object = None,
) -> Rated:
    """Store (or replace) the rating of the render's latest succeeded run."""
    if rating not in RATINGS:
        raise FeedbackRefused("the rating must be 'up' or 'down'", failure_class="invalid_rating")
    cleaned = _clean_comment(comment)
    run = _target(session, package_id, version, render_key)
    existing = session.get(RenderFeedback, run.id)
    now = datetime.now(UTC)
    if existing is None:
        session.add(RenderFeedback(run_id=run.id, rating=rating, comment=cleaned))
    else:
        existing.rating = rating
        existing.comment = cleaned
        existing.updated_at = now
    session.commit()
    return Rated(
        run.id, run.package_id, run.version, run.render_key, run.tier,
        run.trace_id, run.slot, run.model, rating, cleaned,
    )


def clear(session: Session, *, package_id: str, version: int, render_key: str) -> bool:
    """Remove the render's rating; whether there was one."""
    run = _target(session, package_id, version, render_key)
    existing = session.get(RenderFeedback, run.id)
    if existing is None:
        return False
    session.delete(existing)
    session.commit()
    return True


def current(
    session: Session, package_id: str, version: int, render_key: str
) -> tuple[RenderRun, RenderFeedback | None] | None:
    """The latest succeeded run of a render and its rating, or `None` with no such run."""
    run = latest_succeeded_run(session, package_id, version, render_key)
    if run is None:
        return None
    return run, session.get(RenderFeedback, run.id)


def recent_for_piece(session: Session, package_id: str, limit: int = RECENT_LIMIT) -> list[dict]:
    """The newest ratings on a piece, for the agents' context."""
    rows = session.execute(
        select(RenderRun, RenderFeedback)
        .join(RenderFeedback, RenderFeedback.run_id == RenderRun.id)
        .where(RenderRun.package_id == package_id)
        .order_by(RenderFeedback.updated_at.desc())
        .limit(limit)
    ).all()
    return [
        {
            "version": run.version,
            "render_key": run.render_key,
            "tier": run.tier,
            "rating": feedback.rating,
            "comment": feedback.comment,
        }
        for run, feedback in rows
    ]


def summary(session: Session, *, days: int = 30) -> list[dict]:
    """Rating counts per slot, model and tier. Renders no agent started group under none."""
    cutoff = datetime.now(UTC) - timedelta(days=days)
    rows = session.execute(
        select(
            RenderRun.slot,
            RenderRun.model,
            RenderRun.tier,
            func.count().filter(RenderFeedback.rating == "up"),
            func.count().filter(RenderFeedback.rating == "down"),
            func.max(RenderFeedback.updated_at).filter(RenderFeedback.comment.is_not(None)),
        )
        .join(RenderFeedback, RenderFeedback.run_id == RenderRun.id)
        .where(RenderFeedback.updated_at >= cutoff)
        .group_by(RenderRun.slot, RenderRun.model, RenderRun.tier)
        .order_by(RenderRun.slot.nulls_last(), RenderRun.model.nulls_last(), RenderRun.tier)
    ).all()
    return [
        {
            "slot": slot,
            "model": model,
            "tier": tier,
            "up": up,
            "down": down,
            "latest_comment_at": latest.isoformat() if latest else None,
        }
        for slot, model, tier, up, down, latest in rows
    ]


def comments(
    session: Session, *, slot: str | None, model: str | None, tier: str, limit: int = 50
) -> list[dict]:
    """The comments of one summary group, newest first."""
    rows = session.execute(
        select(RenderRun, RenderFeedback)
        .join(RenderFeedback, RenderFeedback.run_id == RenderRun.id)
        .where(
            RenderRun.slot.is_(None) if slot is None else RenderRun.slot == slot,
            RenderRun.model.is_(None) if model is None else RenderRun.model == model,
            RenderRun.tier == tier,
            RenderFeedback.comment.is_not(None),
        )
        .order_by(RenderFeedback.updated_at.desc())
        .limit(limit)
    ).all()
    return [
        {
            "package_id": run.package_id,
            "version": run.version,
            "render_key": run.render_key,
            "rating": feedback.rating,
            "comment": feedback.comment,
            "at": feedback.updated_at.isoformat(),
        }
        for run, feedback in rows
    ]
