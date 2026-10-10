"""Developer panel: token usage per model per day."""

from __future__ import annotations

from collections import defaultdict
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agent.models.prices import estimated_cost, read_prices
from app.api.admin_threads import slot_of
from app.api.gate import require_dev
from app.db.models import ModelUsage

router = APIRouter(prefix="/admin/usage", tags=["admin"], dependencies=[Depends(require_dev)])

SUMMARY_RANGES = (7, 30, 90)


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


@router.get("/summary")
def usage_summary(request: Request, days: int = Query(default=7)) -> dict:
    """Calls, tokens and estimated cost per model, per day and per agent slot (dev-panel-insights).

    A call whose gateway reported no tokens counts its estimate as input and is counted as estimated.
    A model without a stored price adds calls and tokens but no cost, and marks the cost incomplete.
    """
    if days not in SUMMARY_RANGES:
        raise HTTPException(
            422,
            detail={"failure_class": "invalid_range", "field": "days", "reason": "days must be 7, 30 or 90"},
        )
    tz = ZoneInfo(request.app.state.settings.budget_timezone)
    start_local = datetime.now(tz).replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(
        days=days - 1
    )
    prices = read_prices(request.app.state.engine)
    with Session(request.app.state.engine) as session:
        rows = session.scalars(
            select(ModelUsage).where(ModelUsage.created_at >= start_local.astimezone(UTC))
        ).all()
    groups: dict[str, dict[str, dict]] = {"model": {}, "day": {}, "slot": {}}
    incomplete = False
    for row in rows:
        created = row.created_at if row.created_at.tzinfo else row.created_at.replace(tzinfo=UTC)
        estimated = row.input_tokens is None and row.output_tokens is None
        input_tokens = (row.estimated_tokens or 0) if estimated else (row.input_tokens or 0)
        output_tokens = 0 if estimated else (row.output_tokens or 0)
        cost = estimated_cost(prices.get(row.model_id), input_tokens, output_tokens)
        incomplete = incomplete or cost is None
        keys = {
            "model": row.model_id,
            "day": created.astimezone(tz).date().isoformat(),
            "slot": slot_of(row.operation),
        }
        for grouping, key in keys.items():
            bucket = groups[grouping].setdefault(
                key,
                {"key": key, "calls": 0, "input_tokens": 0, "output_tokens": 0, "estimated_calls": 0,
                 "cost_usd": Decimal(0), "cost_complete": True},
            )
            bucket["calls"] += 1
            bucket["input_tokens"] += input_tokens
            bucket["output_tokens"] += output_tokens
            bucket["estimated_calls"] += int(estimated)
            if cost is None:
                bucket["cost_complete"] = False
            else:
                bucket["cost_usd"] += cost
    return {
        "days": days,
        "cost_incomplete": incomplete,
        "label": "estimate at the last fetched price",
        "tracing": bool(getattr(getattr(request.app.state, "tracing", None), "enabled", False)),
        **{
            grouping: [
                {**bucket, "cost_usd": float(round(bucket["cost_usd"], 6))}
                for bucket in sorted(found.values(), key=lambda b: b["key"])
            ]
            for grouping, found in groups.items()
        },
    }
