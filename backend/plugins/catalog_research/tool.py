"""Catalogue lookup tools (Researcher): search, live listing, comparison.

Everything retrieved or fetched reaches the model only inside the
untrusted-content delimiters, attributed and dated. A lookup that fails says why
and states no price; nothing here invents a figure.
"""

from __future__ import annotations

import logging
from typing import Any, Final

from pydantic import BaseModel, Field, field_validator

from app.agent.prompts import Passage, wrap_passages
from app.agent.tools.base import AgentTool, ToolContext, parse_args
from app.pricing.live_lookup import LiveListing, check_listing
from app.retrieval import search_knowledge

logger = logging.getLogger("app")

MAX_QUERY_LENGTH: Final = 400
# Everything in the corpus except the guideline passages (`search_guidelines`).
CATALOG_CATEGORIES: Final = ["catalog", "policy", "guide", "product", "store", "manual_snapshot"]

NOTHING_FOUND: Final = (
    "No catalog content matched that question. Tell the owner you do not have this "
    "information rather than describing what might be the case."
)
LOOKUP_FAILED: Final = (
    "The catalog knowledge store could not be consulted. Answer with what you already have "
    "and tell the owner that catalog knowledge was unavailable for this question."
)
DATED_NOTE: Final = (
    "These passages are dated catalog content, not a current price or stock figure. Label "
    "them as such, and quote the date and source of anything you use."
)
NO_FETCHER: Final = "live retailer lookups are not available on this host right now"


class SearchCatalogArgs(BaseModel):
    query: str = Field(
        min_length=1, max_length=MAX_QUERY_LENGTH,
        description="what to look up in the toom catalogue, in the owner's own words; not a URL",
    )

    @field_validator("query", mode="after")
    @classmethod
    def _not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("query must not be blank")
        return value.strip()


class CheckListingArgs(BaseModel):
    query: str = Field(min_length=1, max_length=MAX_QUERY_LENGTH, description="the product, by name or article number")
    listing_url: str | None = Field(
        default=None, description="a toom category listing path starting with /c/; resolved from the catalog when left out"
    )

    @field_validator("listing_url", mode="after")
    @classmethod
    def _category_path_only(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        if not value.startswith("/c/"):
            raise ValueError("listing_url must be a /c/ category path")
        return value


class CompareProductsArgs(BaseModel):
    queries: list[str] = Field(min_length=2, max_length=4, description="two to four products to compare, by name")


def _euros(cents: int | None) -> str:
    return "not stated" if cents is None else f"{cents // 100},{cents % 100:02d} EUR"


def _facts(listing: LiveListing) -> str:
    result = listing.result
    if not listing.ok:
        return (
            f"Live lookup for {result.get('product_name')!r} failed ({listing.outcome}): {listing.reason}. "
            "No current price or stock is established; say so plainly and state no price."
        )
    lines = [
        f"{result['product_name']} — checked {result['checked_at'] or 'at an unknown time'}",
        f"Price (pack): {_euros(result['price_cents'])}"
        + (f"; per unit: {result['unit_price']}" if result.get("unit_price") else ""),
        f"Stock: {result['availability']}"
        + (f" at {result['stock_store']}" if result.get("stock_store") else "")
        + ("" if result.get("scoped_to_home_store") else " (not confirmed for the home store)"),
        f"Delivery to home: {'yes' if result['delivery'] else 'no'}",
    ]
    return "\n".join(lines)


def _passages_of(listing: LiveListing) -> str:
    return wrap_passages(listing.passages) if listing.passages else ""


def run_search(arguments: dict[str, Any], ctx: ToolContext) -> str:
    args, problem = parse_args(SearchCatalogArgs, arguments)
    if args is None:
        return problem
    try:
        with ctx.deps.session() as session:
            hits = search_knowledge(session, args.query, limit=5, categories=CATALOG_CATEGORIES)
    except Exception as error:  # noqa: BLE001 - a lookup failure is a stated inability, not a crash
        logger.warning("catalog search failed", extra={"context": {"error_type": type(error).__name__}})
        return LOOKUP_FAILED
    return search_result(hits)


def search_result(hits: list[Any]) -> str:
    """What the model is given for these hits (also read by the offline eval)."""
    if not hits:
        return NOTHING_FOUND
    return DATED_NOTE + "\n\n" + wrap_passages([Passage.from_hit(hit) for hit in hits])


def run_listing(arguments: dict[str, Any], ctx: ToolContext) -> str:
    args, problem = parse_args(CheckListingArgs, arguments)
    if args is None:
        return problem
    fetcher = ctx.deps.live_fetcher
    if fetcher is None:
        return NO_FETCHER
    with ctx.deps.session() as session:
        listing = check_listing(session, fetcher, ctx.deps.settings, args.query, args.listing_url)
    return "\n\n".join(part for part in (_facts(listing), _passages_of(listing)) if part)


def run_compare(arguments: dict[str, Any], ctx: ToolContext) -> str:
    args, problem = parse_args(CompareProductsArgs, arguments)
    if args is None:
        return problem
    fetcher = ctx.deps.live_fetcher
    blocks = []
    with ctx.deps.session() as session:
        for query in (q.strip() for q in args.queries):
            if not query or len(query) > MAX_QUERY_LENGTH:
                return "each product to compare needs a short, non-blank name"
            if fetcher is None:
                listing = LiveListing("unfetchable", NO_FETCHER, {"product_name": query})
            else:
                listing = check_listing(session, fetcher, ctx.deps.settings, query)
            blocks.append(f"### {query}\n{_facts(listing)}")
    return "Comparison, from live listings only (a failed lookup states no price):\n\n" + "\n\n".join(blocks)


search_catalog_knowledge = AgentTool(
    name="search_catalog_knowledge",
    description=(
        "Search the ingested toom catalogue and the owner's snapshots for product facts "
        "(sizes, materials, policies, services). Results are dated catalog content, never a "
        "current price or stock."
    ),
    schema=SearchCatalogArgs,
    run=run_search,
)

check_live_listing = AgentTool(
    name="check_live_listing",
    description=(
        "Read a toom category listing for a product's current pack price, unit price, delivery and "
        "stock, plus its specification table. Use it for what something costs now. A failed "
        "lookup says why and states no price."
    ),
    schema=CheckListingArgs,
    run=run_listing,
)

compare_products = AgentTool(
    name="compare_products",
    description="Compare two to four products from their live listings. A failed lookup states no price.",
    schema=CompareProductsArgs,
    run=run_compare,
)
