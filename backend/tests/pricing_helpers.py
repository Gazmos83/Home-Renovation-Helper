"""Helpers for the pricing tests: a live fetcher over a mock transport, clean tables."""

from __future__ import annotations

from pathlib import Path

import httpx
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.ingestion.live_fetcher import LiveFetcher

FIXTURES = Path(__file__).resolve().parent / "fixtures"


def fixture(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


def make_fetcher(pages: dict[str, tuple[int, str]], *, robots: str = "User-agent: *\nAllow: /\n") -> tuple[LiveFetcher, list[httpx.Request]]:
    """A `LiveFetcher` serving `pages` (path → (status, html)) and a robots.txt."""
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        if request.url.path == "/robots.txt":
            return httpx.Response(200, text=robots, headers={"content-type": "text/plain"})
        status, body = pages.get(request.url.path, (404, "not found"))
        return httpx.Response(status, text=body, headers={"content-type": "text/html"})

    client = httpx.Client(transport=httpx.MockTransport(handler))
    return LiveFetcher(contact="owner@example.com", min_interval_seconds=0.0, client=client), seen


def clean_pricing(engine) -> None:
    """Empty the pricing tables but keep the seeded planning rows (non-manual-by-hand)."""
    with Session(engine) as session:
        session.execute(text("DELETE FROM cut_list_pricing_entries"))
        session.execute(text("DELETE FROM cut_list_pricings"))
        session.execute(text("DELETE FROM remnant_sheets"))
        session.execute(text("DELETE FROM supplier_prices WHERE NOT (unconfirmed OR key = 'Personal_Supply')"))
        session.execute(
            text("UPDATE supplier_prices SET override_cents = NULL, override_note = NULL, override_at = NULL")
        )
        session.execute(text("DELETE FROM product_snapshots"))
        session.execute(text("DELETE FROM chunks"))
        session.execute(text("DELETE FROM guideline_notes"))
        session.execute(text("DELETE FROM store_cut_restrictions"))
        session.execute(text("DELETE FROM store_services"))
        session.execute(text("DELETE FROM stores"))
        session.commit()


