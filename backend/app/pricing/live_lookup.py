"""A live look at a toom category listing (catalog-knowledge spec).

Reads the category listing for price, unit price, delivery and the stock line,
then the product's own page for its specification table. The store scope is
toom's own `market_id` cookie for the home store; the store a stock line names is
read from the page, never assumed. Every outcome — a figure, `not_found`, or a
fetch failure — is a readable value; nothing here raises for an ordinary failure.
A failed lookup states why and never a price.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Final
from urllib.parse import urljoin

from sqlalchemy.orm import Session

from app.agent.prompts import Passage
from app.config import Settings
from app.db.models import Store
from app.ingestion.live_fetcher import LiveFetcher
from app.ingestion.live_listing_parser import (
    ORDERABLE_VERB,
    OUT_OF_STOCK_VERB,
    ListingBlock,
    find_block,
    parse_listing_blocks,
)
from app.ingestion.live_spec_parser import parse_specifications
from app.ingestion.sources import get_source
from app.retrieval import search_knowledge

logger = logging.getLogger("app")

_FAILURE_REASON: Final[dict[str, str]] = {
    "timeout": "the page did not respond within the time budget",
    "refused": "the retailer refused the request",
    "excluded": "the page is excluded by the retailer's published crawling rules",
    "unfetchable": "the page could not be fetched",
}


@dataclass(frozen=True, slots=True)
class LiveListing:
    outcome: str
    reason: str | None = None
    result: dict[str, Any] = field(default_factory=dict)
    passages: tuple[Passage, ...] = ()

    @property
    def ok(self) -> bool:
        return self.outcome == "ok"


def _cents(price: str | None) -> int | None:
    from app.pricing.product_page import to_cents

    return to_cents(price)


def _availability(block: ListingBlock) -> str:
    if block.stock_store is None:
        return "unknown"
    if block.stock_verb == OUT_OF_STOCK_VERB:
        return "out_of_stock"
    if block.stock_verb == ORDERABLE_VERB:
        # Orderable is not confirmed in stock at this store: not claimed as stock.
        return "unknown"
    return "in_stock"


def _failure(outcome: str, reason: str, query: str, url: str | None) -> LiveListing:
    logger.info("live listing lookup", extra={"context": {"outcome": outcome, "reason": reason}})
    return LiveListing(outcome=outcome, reason=reason, result={"product_name": query, "url": url})


def resolve_listing_url(
    session: Session, settings: Settings, query: str, listing_url: str | None
) -> tuple[str | None, str | None]:
    """The absolute listing URL to read, or `(None, reason)` when none resolves."""
    source = get_source(next(iter(sorted(settings.retail_sources))))
    if listing_url is not None:
        return urljoin(source.base_url, listing_url), None
    hits = search_knowledge(session, query, limit=5, sources=[source.name], categories=[source.default_category])
    hit = hits[0] if hits else None
    if hit is None:
        return None, "the catalog holds no listing for this product; give a /c/ category path"
    return hit.url, None


def check_listing(
    session: Session,
    fetcher: LiveFetcher,
    settings: Settings,
    query: str,
    listing_url: str | None = None,
) -> LiveListing:
    source = get_source(next(iter(sorted(settings.retail_sources))))
    store = session.get(Store, settings.toom_home_store)
    market_id = store.market_id if store else None

    url, reason = resolve_listing_url(session, settings, query, listing_url)
    if url is None:
        return _failure("not_found", reason or "no listing could be resolved", query, None)

    listing = fetcher.fetch(url, market_id=market_id)
    if not listing.ok or listing.html is None:
        return _failure(listing.outcome, listing.reason or _FAILURE_REASON.get(listing.outcome, "failed"), query, url)
    blocks = parse_listing_blocks(listing.html)
    if not blocks:
        return _failure("unreadable", "the expected product listing structure was not found", query, url)
    block = find_block(blocks, query)
    if block is None:
        return _failure("not_found", "the product was not found on that page", query, url)

    checked_at = listing.fetched_at.isoformat() if listing.fetched_at else ""
    passages = [Passage(content=block.text, url=url, scraped_at=checked_at, source_site=source.name, category="live")]
    product_url = urljoin(url, block.url)
    product = fetcher.fetch(product_url)
    attributes: dict[str, dict[str, str | None]] = {}
    specs_outcome = product.outcome
    specs_reason = None if product.ok else (product.reason or _FAILURE_REASON.get(product.outcome))
    if product.ok and product.html is not None:
        specs = parse_specifications(product.html)
        if specs.readable:
            specs_outcome = "ok"
            attributes = {a.key: {"value": a.value, "group": a.group} for a in specs.attributes}
            passages.append(Passage(
                content=specs.region_text, url=product_url,
                scraped_at=product.fetched_at.isoformat() if product.fetched_at else "",
                source_site=source.name, category="live",
            ))
        else:
            specs_outcome, specs_reason = "unreadable", "the product page carries no specification table"

    scoped = bool(store and store.market_id and block.stock_store and block.stock_store.casefold() in store.name.casefold())
    result = {
        "product_name": block.name,
        "url": url,
        "product_url": product_url,
        "price_cents": _cents(block.price),
        "unit_price": block.unit_price,
        "delivery": block.delivery,
        "availability": _availability(block),
        "stock_store": block.stock_store,
        "checked_at": checked_at,
        "scoped_to_home_store": scoped,
        "attributes": attributes,
        "specs_outcome": specs_outcome,
        "specs_reason": specs_reason,
    }
    return LiveListing(outcome="ok", result=result, passages=tuple(passages))
