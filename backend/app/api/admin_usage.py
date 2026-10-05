"""Developer panel: token usage per model per day."""

from __future__ import annotations

from collections import defaultdict
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.gate import require_dev
from app.db.models import ModelUsage

router = APIRouter(prefix="/admin/usage", tags=["admin"], dependencies=[Depends(require_dev)])


@router.get("")
def usage(request: Request, days: int = Query(default=1, ge=1, le=31)) -> list[dict]:
    tz = ZoneInfo(request.app.state.settings.budget_timezone)
    start_local = datetime.now(tz).replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(
        days=days - 1
    )
    with Session(request.app.state.engine) as session:
        rows = session.scalars(
            select(ModelUsage).where(ModelUsage.created_at >= start_local.astimezone(UTC))
        ).all()
    totals: dict[tuple[str, str], dict[str, int]] = defaultdict(
        lambda: {"input_tokens": 0, "output_tokens": 0, "calls": 0}
    )
    for row in rows:
        created = row.created_at
        if created.tzinfo is None:
            created = created.replace(tzinfo=UTC)
        day = created.astimezone(tz).date().isoformat()
        bucket = totals[(row.model_id, day)]
        if row.input_tokens is None and row.output_tokens is None:
            bucket["input_tokens"] += row.estimated_tokens or 0
        else:
            bucket["input_tokens"] += row.input_tokens or 0
            bucket["output_tokens"] += row.output_tokens or 0
        bucket["calls"] += 1
    return [
        {"model": model, "day": day, **counts}
        for (model, day), counts in sorted(totals.items(), key=lambda item: (item[0][1], item[0][0]), reverse=True)
    ]
