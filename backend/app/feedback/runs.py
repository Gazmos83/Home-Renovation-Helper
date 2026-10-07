"""Render runs: the origin of each guarded render (feedback-capture design decision 1).

A run is recorded in the database when a render is handed to the runner, with
the thread, trace, owner's message, slot and model when an agent turn asked for
it. It never goes into the version folder, whose files the homeowner's routes
serve. Recording and finishing a run never raise: a database hiccup must not
stop a render.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import Engine, select
from sqlalchemy.orm import Session

from app.blender import storage
from app.db.models import RenderRun
from app.render.guard import RenderQuote

if TYPE_CHECKING:
    from app.agent.tools.base import ToolContext

logger = logging.getLogger("app")

MAX_PROMPT_CHARACTERS = 2000


@dataclass(frozen=True, slots=True)
class Origin:
    """What an agent turn knew when it started a render."""

    thread_id: UUID | None = None
    trace_id: str | None = None
    prompt: str | None = None
    slot: str | None = None
    model: str | None = None


def origin_from(ctx: ToolContext) -> Origin:
    return Origin(
        thread_id=ctx.thread_id,
        trace_id=ctx.trace_id,
        prompt=ctx.last_message or None,
        slot=ctx.slot,
        model=ctx.model,
    )


def render_key_of(quote: RenderQuote) -> str:
    return storage.render_key(quote.kind, quote.room, quote.source)


def record_run(engine: Engine, quote: RenderQuote, origin: Origin | None = None) -> UUID | None:
    """Insert the run for a quoted render; `None` when it cannot or need not be recorded.

    Only furniture renders are recorded (an apartment shell has no Pieces entry).
    """
    if quote.record != "piece":
        return None
    origin = origin or Origin()
    prompt = origin.prompt[:MAX_PROMPT_CHARACTERS] if origin.prompt else None
    try:
        with Session(engine) as session:
            run = RenderRun(
                package_id=quote.package_id,
                version=quote.version,
                render_key=render_key_of(quote),
                tier=quote.tier.name,
                outcome="queued",
                thread_id=origin.thread_id,
                trace_id=origin.trace_id,
                prompt=prompt,
                slot=origin.slot,
                model=origin.model,
            )
            session.add(run)
            session.commit()
            return run.id
    except Exception as error:  # noqa: BLE001 - a render must not depend on this record
        logger.warning(
            "render.run_not_recorded", extra={"context": {"error_type": type(error).__name__}}
        )
        return None


def finish_run(engine: Engine, run_id: UUID | None, outcome: str) -> None:
    """Set a run's outcome and finish time. Never raises."""
    if run_id is None:
        return
    try:
        with Session(engine) as session:
            run = session.get(RenderRun, run_id)
            if run is None:
                return
            run.outcome = outcome
            run.finished_at = datetime.now(UTC)
            session.commit()
    except Exception as error:  # noqa: BLE001 - a finished render must stay finished
        logger.warning(
            "render.run_not_finished", extra={"context": {"error_type": type(error).__name__}}
        )


def latest_succeeded_run(
    session: Session, package_id: str, version: int, render_key: str
) -> RenderRun | None:
    """The newest run of this render that succeeded, which is what the owner is looking at."""
    return session.scalars(
        select(RenderRun)
        .where(
            RenderRun.package_id == package_id,
            RenderRun.version == version,
            RenderRun.render_key == render_key,
            RenderRun.outcome == "succeeded",
        )
        .order_by(RenderRun.started_at.desc())
        .limit(1)
    ).first()
