"""Model prices from OpenRouter's public model list, for the developer panel (dev-panel-insights).

A refresh is one GET of the model list, on the developer's request only. Only
registry slugs are kept; a slug the list does not price (or prices in a form
that cannot be read) has no row and shows "no price", never a guessed one. A
failed refresh changes nothing stored. Costs are estimates at the last fetched
price and appear only on developer routes.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from typing import Any, Final

import httpx
from sqlalchemy import Engine, delete, select
from sqlalchemy.orm import Session

from app.agent.models.openrouter_client import OPENROUTER_BASE_URL
from app.config import Settings
from app.db.models import ModelPrice

MODELS_URL: Final = f"{OPENROUTER_BASE_URL}/models"
TIMEOUT_SECONDS: Final = 10.0
PER_MILLION: Final = Decimal(1_000_000)


class PriceRefreshError(Exception):
    """The model list could not be fetched or read; the stored prices are unchanged."""


@dataclass(frozen=True)
class Price:
    slug: str
    input_per_million: Decimal
    output_per_million: Decimal
    fetched_at: datetime


def _per_million(raw: Any) -> Decimal | None:
    """OpenRouter states dollars per token as a string; a value that is not a finite, non-negative number is none."""
    try:
        value = Decimal(str(raw))
    except (InvalidOperation, ValueError):
        return None
    if not value.is_finite() or value < 0:
        return None
    return value * PER_MILLION


def parse_prices(payload: Any, slugs: Iterable[str]) -> dict[str, tuple[Decimal, Decimal]]:
    """The registry slugs the list prices: slug → (input, output) dollars per million tokens."""
    wanted = set(slugs)
    found: dict[str, tuple[Decimal, Decimal]] = {}
    entries = payload.get("data") if isinstance(payload, Mapping) else None
    if not isinstance(entries, list):
        raise PriceRefreshError("the model list has no data")
    for entry in entries:
        if not isinstance(entry, Mapping) or entry.get("id") not in wanted:
            continue
        pricing = entry.get("pricing")
        if not isinstance(pricing, Mapping):
            continue
        prompt, completion = _per_million(pricing.get("prompt")), _per_million(pricing.get("completion"))
        if prompt is None or completion is None:
            continue
        found[entry["id"]] = (prompt, completion)
    return found


def fetch_prices(
    settings: Settings, slugs: Iterable[str], *, transport: httpx.BaseTransport | None = None
) -> dict[str, tuple[Decimal, Decimal]]:
    """One request to OpenRouter's model list. Raises `PriceRefreshError` on any failure."""
    headers = {"Authorization": f"Bearer {settings.openrouter_api_key.get_secret_value()}"}
    try:
        with httpx.Client(timeout=TIMEOUT_SECONDS, transport=transport, follow_redirects=False) as client:
            response = client.get(MODELS_URL, headers=headers)
            response.raise_for_status()
            payload = response.json()
    except (httpx.HTTPError, ValueError) as error:
        raise PriceRefreshError(f"the model list could not be fetched ({type(error).__name__})") from None
    return parse_prices(payload, slugs)


def store_prices(engine: Engine, slugs: Iterable[str], prices: Mapping[str, tuple[Decimal, Decimal]]) -> datetime:
    """Replace the registry slugs' prices with a refresh's result; a slug it does not price loses its row."""
    now = datetime.now(UTC)
    slugs = list(slugs)
    with Session(engine) as session:
        session.execute(delete(ModelPrice).where(ModelPrice.slug.in_(slugs)))
        for slug, (input_price, output_price) in prices.items():
            session.add(
                ModelPrice(
                    slug=slug, input_per_million=input_price, output_per_million=output_price, fetched_at=now
                )
            )
        session.commit()
    return now


def read_prices(engine: Engine) -> dict[str, Price]:
    with Session(engine) as session:
        rows = session.scalars(select(ModelPrice)).all()
        return {
            row.slug: Price(row.slug, Decimal(row.input_per_million), Decimal(row.output_per_million), row.fetched_at)
            for row in rows
        }


def estimated_cost(price: Price | None, input_tokens: int, output_tokens: int) -> Decimal | None:
    """Tokens times the stored price in dollars, or `None` when the model has no price."""
    if price is None:
        return None
    return (input_tokens * price.input_per_million + output_tokens * price.output_per_million) / PER_MILLION
