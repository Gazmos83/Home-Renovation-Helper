"""Developer panel: model prices per registry slug, refreshed from OpenRouter (dev-panel-insights)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, status

from app.agent.models.prices import (
    PriceRefreshError,
    fetch_prices,
    read_prices,
    store_prices,
)
from app.agent.models.registry import MODELS
from app.api.gate import require_dev

router = APIRouter(prefix="/admin/model-prices", tags=["admin"], dependencies=[Depends(require_dev)])


def _listing(request: Request) -> list[dict[str, Any]]:
    prices = read_prices(request.app.state.engine)
    rows = []
    for entry in MODELS:
        price = prices.get(entry.model_id)
        rows.append(
            {
                "slug": entry.model_id,
                "input_per_million_usd": float(price.input_per_million) if price else None,
                "output_per_million_usd": float(price.output_per_million) if price else None,
                "fetched_at": price.fetched_at.isoformat() if price else None,
            }
        )
    return rows


@router.get("")
def list_prices(request: Request) -> list[dict[str, Any]]:
    return _listing(request)


@router.post("/refresh")
def refresh_prices(request: Request) -> list[dict[str, Any]]:
    slugs = [entry.model_id for entry in MODELS]
    transport = getattr(request.app.state, "price_transport", None)  # a test seam; `None` in production
    try:
        found = fetch_prices(request.app.state.settings, slugs, transport=transport)
    except PriceRefreshError as error:
        raise HTTPException(
            status.HTTP_502_BAD_GATEWAY,
            detail={"failure_class": "price_refresh_failed", "reason": str(error)},
        ) from None
    store_prices(request.app.state.engine, slugs, found)
    return _listing(request)
