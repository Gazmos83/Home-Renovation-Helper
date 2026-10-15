"""The developer's list of RunPod pods the app created (render-pod-lifecycle design decision 8).

A session runs from the pod's creation to its deletion. The cost is worked out when
read, from RunPod's reported hourly price and the pod's lifetime; it is never stored
and never reaches a homeowner response. Writing never raises: the pod's own
lifecycle must not fail because its record could not be kept.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import Engine, select
from sqlalchemy.orm import Session

from app.db.models import RenderPodSession

logger = logging.getLogger("app")

RECENT_LIMIT = 20


def _not_recorded(error: Exception) -> None:
    logger.warning("offload.pod_session_not_recorded", extra={"context": {"error_type": type(error).__name__}})


def open_session(engine: Engine, pod_id: str, gpu_type: str, cost_per_hr: float | None) -> UUID | None:
    try:
        with Session(engine) as session:
            row = RenderPodSession(pod_id=pod_id, gpu_type=gpu_type, cost_per_hr=cost_per_hr, outcome="running")
            session.add(row)
            session.commit()
            return row.id
    except Exception as error:  # noqa: BLE001
        _not_recorded(error)
        return None


def update_session(engine: Engine, session_id: UUID | None, **changes: Any) -> None:
    """Set `ready_at`, `cost_per_hr`, `outcome`, `error` or `deleted_at`; `jobs=+1` adds a job."""
    if session_id is None:
        return
    try:
        with Session(engine) as session:
            row = session.get(RenderPodSession, session_id)
            if row is None:
                return
            for name, value in changes.items():
                if name == "jobs":
                    row.jobs += value
                elif name == "error":
                    row.error = str(value)[:500] if value else None
                else:
                    setattr(row, name, value)
            session.commit()
    except Exception as error:  # noqa: BLE001
        _not_recorded(error)


def close_session(engine: Engine, session_id: UUID | None, outcome: str, error: str | None = None) -> None:
    update_session(engine, session_id, outcome=outcome, error=error, deleted_at=datetime.now(UTC))


def record_orphan(engine: Engine, pod_id: str, gpu_type: str, cost_per_hr: float | None) -> None:
    """A pod found running at startup and deleted: one closed session."""
    session_id = open_session(engine, pod_id, gpu_type, cost_per_hr)
    close_session(engine, session_id, "orphaned")


def cost(row: RenderPodSession, now: datetime) -> float | None:
    """What the pod cost at RunPod's hourly price, to the cent; `None` without a price."""
    if row.cost_per_hr is None:
        return None
    end = row.deleted_at or now
    return round(max((end - row.created_at).total_seconds(), 0) / 3600 * row.cost_per_hr, 2)


def recent_sessions(session: Session, limit: int = RECENT_LIMIT) -> list[dict[str, Any]]:
    now = datetime.now(UTC)
    rows = session.scalars(
        select(RenderPodSession).order_by(RenderPodSession.created_at.desc()).limit(limit)
    ).all()
    return [
        {
            "pod_id": row.pod_id,
            "gpu_type": row.gpu_type,
            "created_at": row.created_at.astimezone(UTC).isoformat(),
            "ready_at": row.ready_at.astimezone(UTC).isoformat() if row.ready_at else None,
            "deleted_at": row.deleted_at.astimezone(UTC).isoformat() if row.deleted_at else None,
            "lifetime_seconds": round(((row.deleted_at or now) - row.created_at).total_seconds()),
            "jobs": row.jobs,
            "outcome": row.outcome,
            "error": row.error,
            "cost_per_hr": row.cost_per_hr,
            "cost_usd": cost(row, now),
        }
        for row in rows
    ]
