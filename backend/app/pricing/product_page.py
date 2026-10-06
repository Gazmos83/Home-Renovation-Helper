"""Reading one toom product page into an entry's facts (price-list spec).

toom renders a product page's price in the browser, so an honest server-side
fetch usually carries a name, a specification table and a breadcrumb but no
price. The price is therefore read from the page when it is there (the page
state or its structured data) and otherwise from the category listing the
breadcrumb names, where the product's tile states it. A figure that cannot be
found either way is reported as missing — never guessed (CLAUDE.md §5a).

Every fetch is robots-checked and refused or unreadable pages say so as values;
nothing here raises for an ordinary failure.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Final
from urllib.parse import urljoin, urlsplit

from bs4 import BeautifulSoup

from app.ingestion.extract import extract_text
from app.ingestion.live_fetcher import FetchResult, LiveFetcher
from app.ingestion.live_listing_parser import (
    ListingBlock,
    find_block,
    parse_listing_blocks,
)
from app.ingestion.live_spec_parser import parse_specifications

# Which hosts belong to which configured retail source.
SOURCE_HOSTS: Final[dict[str, frozenset[str]]] = {"toom": frozenset({"toom.de", "www.toom.de"})}

_PRODUCT_PATH = re.compile(r"^/p/[a-z0-9-]+/\d+", re.IGNORECASE)
_STATE_PRICE = re.compile(r'"price"\s*:\s*"?(\d{1,5}(?:[.,]\d{1,2})?)"?')
_PRICE = re.compile(r"(\d{1,4}(?:\.\d{3})*|\d+),(\d{2})")
_DIMENSIONS = re.compile(r"(\d{2,5})\s*x\s*(\d{2,5})\s*x\s*(\d{1,4})\s*mm", re.IGNORECASE)
_NUMBER_UNIT = re.compile(r"(\d+(?:,\d+)?)\s*(mm|cm|m)\b")


@dataclass(frozen=True, slots=True)
class ProductRead:
    """What reading a product URL found. `outcome` is `ok` or a stated failure."""

    outcome: str
    url: str
    reason: str | None = None
    name: str | None = None
    price_cents: int | None = None
    unit_price_cents: int | None = None
    sheet_length_mm: int | None = None
    sheet_width_mm: int | None = None
    thickness_mm: int | None = None
    fetched_at: datetime | None = None
    page_text: str = ""
    missing: tuple[str, ...] = field(default=())

    @property
    def ok(self) -> bool:
        return self.outcome == "ok"


def host_permitted(url: str, retail_sources: frozenset[str]) -> bool:
    host = (urlsplit(url).hostname or "").lower()
    return any(host in SOURCE_HOSTS.get(source, frozenset()) for source in retail_sources)


def to_cents(text: str | None) -> int | None:
    """`'36,49'` or `'1.249,00 €'` → 3649 / 124900, else `None`."""
    if not text:
        return None
    match = _PRICE.search(text.replace("\xa0", " "))
    if match is None:
        plain = re.fullmatch(r"\s*(\d{1,5})[.](\d{1,2})\s*", text)
        if plain is None:
            return None
        return int(plain.group(1)) * 100 + int(plain.group(2).ljust(2, "0"))
    return int(match.group(1).replace(".", "")) * 100 + int(match.group(2))


def _mm(value: str, unit: str) -> int | None:
    number = float(value.replace(",", "."))
    factor = {"mm": 1, "cm": 10, "m": 1000}[unit]
    result = round(number * factor)
    return result if result > 0 else None


def _page_price(html: str) -> int | None:
    """A price the page itself carries: its state script or structured data."""
    soup = BeautifulSoup(html, "html.parser")
    for script in soup.find_all("script"):
        text = script.string or ""
        if script.get("type") == "application/ld+json":
            try:
                document = json.loads(text)
            except ValueError:
                continue
            offers = document.get("offers") if isinstance(document, dict) else None
            if isinstance(offers, dict) and offers.get("price") is not None:
                return to_cents(str(offers["price"]).replace(".", ","))
        elif "__PRODUCT_STATE__" in text:
            found = _STATE_PRICE.search(text)
            if found:
                return to_cents(found.group(1).replace(".", ","))
    return None


def _listing_url(html: str, base_url: str) -> str | None:
    """The category listing the breadcrumb ends in (the entry before the product)."""
    soup = BeautifulSoup(html, "html.parser")
    for script in soup.find_all("script", attrs={"type": "application/ld+json"}):
        try:
            document = json.loads(script.string or "")
        except ValueError:
            continue
        if not isinstance(document, dict) or document.get("@type") != "BreadcrumbList":
            continue
        items = [i.get("item", {}).get("@id") for i in document.get("itemListElement", [])]
        categories = [i for i in items if isinstance(i, str) and "/c/" in i]
        if categories:
            return urljoin(base_url, categories[-1])
    return None


def _dimensions(html: str, name: str | None) -> tuple[int | None, int | None, int | None]:
    """Sheet length, width and thickness in mm, from the name or the specification table."""
    if name:
        found = _DIMENSIONS.search(name)
        if found:
            return int(found.group(1)), int(found.group(2)), int(found.group(3))
    length = width = thickness = None
    for attribute in parse_specifications(html).attributes:
        match = _NUMBER_UNIT.search(attribute.value)
        if match is None:
            continue
        key = attribute.key.casefold()
        value = _mm(match.group(1), match.group(2))
        if key.startswith(("länge", "laenge")):
            length = value
        elif key.startswith("breite"):
            width = value
        elif key.startswith(("stärke", "staerke", "dicke", "höhe")):
            thickness = thickness or value
    return length, width, thickness


def parse_product_page(html: str) -> dict[str, Any]:
    """The facts a product page states: name, price (if rendered), dimensions, breadcrumb listing."""
    soup = BeautifulSoup(html, "html.parser")
    heading = soup.find("h1")
    name = heading.get_text(" ", strip=True) if heading else None
    length, width, thickness = _dimensions(html, name)
    return {
        "name": name,
        "price_cents": _page_price(html),
        "sheet_length_mm": length,
        "sheet_width_mm": width,
        "thickness_mm": thickness,
        "text": extract_text(html),
    }


def _tile_for(blocks: list[ListingBlock], url: str, name: str | None) -> ListingBlock | None:
    path = urlsplit(url).path
    exact = next((b for b in blocks if urlsplit(b.url).path == path), None)
    if exact is not None:
        return exact
    return find_block(blocks, name) if name else None


def read_product(fetcher: LiveFetcher, url: str) -> ProductRead:
    """Fetch and read one product URL; failures are values, never exceptions."""
    if not _PRODUCT_PATH.match(urlsplit(url).path or ""):
        return ProductRead("unreadable", url, reason="this is not a toom product page (/p/<name>/<number>)")
    page = fetcher.fetch(url)
    if not page.ok or page.html is None:
        return ProductRead(page.outcome, url, reason=page.reason)

    facts = parse_product_page(page.html)
    price = facts["price_cents"]
    unit_price: int | None = None
    if facts["name"] is None:
        return ProductRead("unreadable", url, reason="the page names no product", fetched_at=page.fetched_at)

    if price is None:
        listing_url = _listing_url(page.html, url)
        if listing_url is not None:
            listing: FetchResult = fetcher.fetch(listing_url)
            if listing.ok and listing.html is not None:
                tile = _tile_for(parse_listing_blocks(listing.html), url, facts["name"])
                if tile is not None:
                    price = to_cents(tile.price)
                    unit_price = to_cents(tile.unit_price)
            elif listing.outcome in ("refused", "excluded"):
                return ProductRead(
                    listing.outcome, url, reason=f"its category listing: {listing.reason}",
                    name=facts["name"], fetched_at=page.fetched_at,
                )
    missing = tuple(
        label
        for label, value in (("price", price),)
        if value is None
    )
    return ProductRead(
        "ok" if price is not None else "unreadable",
        url,
        reason=None if price is not None else "no price could be read from the page or its category listing",
        name=facts["name"],
        price_cents=price,
        unit_price_cents=unit_price,
        sheet_length_mm=facts["sheet_length_mm"],
        sheet_width_mm=facts["sheet_width_mm"],
        thickness_mm=facts["thickness_mm"],
        fetched_at=page.fetched_at,
        page_text=facts["text"],
        missing=missing,
    )
