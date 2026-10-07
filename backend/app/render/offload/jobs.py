"""The developer's list of renders that ran on the render server (render-offload design decision 8).

The euro figure is worked out when read, from the hourly rate the developer set; it is
never stored and never reaches a homeowner response.
"""

from __future__ import annotations

import logging
from datetime import UTC, timedelta
from typing import Any

from sqlalchemy import Engine, select
from sqlalchemy.orm import Session

from app.db.models import RemoteRenderJob

logger = logging.getLogger("app")

RECENT_LIMIT = 20
HELD_FOR = timedelta(days=365)


def record_job(engine: Engine, record: dict[str, Any]) -> None:
    """Store one finished remote job. Never raises: a finished render stays finished."""
    try:
        with Session(engine) as session:
            session.add(
                RemoteRenderJob(
                    package_id=record["package_id"],
                    version=record["version"],
                    render_key=record["render_key"],
                    estimate_seconds=record["estimate_seconds"],
                    actual_seconds=record.get("actual_seconds"),
                    transfer_seconds=record.get("transfer_seconds"),
                    outcome=record["outcome"],
                    error=(record.get("error") or None) and str(record["error"])[:500],
                )
            )
            session.commit()
    except Exception as error:  # noqa: BLE001 - the job list must not fail a render
        logger.warning(
            "offload.job_not_recorded", extra={"context": {"error_type": type(error).__name__}}
        )


def euros(actual_seconds: float | None, hourly_rate: float | None) -> float | None:
    """What the job cost at the hourly rate, to the cent; `None` without both."""
    if actual_seconds is None or hourly_rate is None:
        return None
    return round(actual_seconds / 3600 * hourly_rate, 2)


def recent_jobs(session: Session, hourly_rate: float | None, limit: int = RECENT_LIMIT) -> list[dict[str, Any]]:
    rows = session.scalars(
        select(RemoteRenderJob).order_by(RemoteRenderJob.started_at.desc()).limit(limit)
    ).all()
    return [
        {
            "package_id": row.package_id,
            "version": row.version,
            "render": row.render_key,
            "estimate_seconds": row.estimate_seconds,
            "actual_seconds": row.actual_seconds,
            "transfer_seconds": row.transfer_seconds,
            "outcome": row.outcome,
            "error": row.error,
            "started_at": row.started_at.astimezone(UTC).isoformat(),
            "cost_eur": euros(row.actual_seconds, hourly_rate),
        }
        for row in rows
    ]
