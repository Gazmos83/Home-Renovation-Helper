"""Creating and refreshing captured price-list entries from toom pages.

`capture_from_url` is the paste-a-URL path: the page is read once (robots
checked, under the service's own identity), a `captured` entry is made with the
parsed price and sheet size, and the page's text is indexed for the corpus in the
same transaction. A refusal (robots, 401, 403, 429) is an answer and creates
nothing; it is never retried under another identity.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from urllib.parse import urlsplit

from sqlalchemy.orm import Session

from app.db.models import Provenance, SupplierPrice, SupplierPriceCategory
from app.ingestion.live_fetcher import LiveFetcher
from app.pricing import price_list
from app.pricing.errors import Refused
from app.pricing.price_list import RefreshResult
from app.pricing.product_page import ProductRead, host_permitted, read_product

# Called with (session, url, title, text) inside the capture's transaction.
PageIndexer = Callable[[Session, str, str, str], None]


@dataclass(frozen=True, slots=True)
class CaptureResult:
    outcome: str
    reason: str | None
    entry: SupplierPrice | None
    read: ProductRead | None


def _price_for_unit(read: ProductRead, unit: str) -> int | None:
    # A pack's price is never a per-metre or per-m² price: a 5 m roll is not 4,99 € per metre.
    if unit == "per_m2":
        return read.unit_price_cents
    if unit == "per_metre":
        return read.metre_price_cents
    return read.price_cents


def capture_from_url(
    session: Session,
    fetcher: LiveFetcher,
    url: str,
    *,
    key: str,
    category: str,
    retail_sources: frozenset[str],
    unit: str | None = None,
    indexer: PageIndexer | None = None,
) -> CaptureResult:
    """Read a toom product URL and create a `captured` entry from it."""
    if not host_permitted(url, retail_sources):
        host = urlsplit(url).hostname or url
        raise Refused(f"{host} is not a permitted source; only {', '.join(sorted(retail_sources))} pages can be read")
    read = read_product(fetcher, url)
    if not read.ok:
        return CaptureResult(read.outcome, read.reason, None, read)

    chosen = unit or (
        "per_m2" if category == SupplierPriceCategory.PANEL and read.unit_price_cents is not None else "per_piece"
    )
    price = _price_for_unit(read, chosen)
    if price is None:
        return CaptureResult(
            "unreadable", f"the page states no {chosen.replace('_', ' ')} price", None, read
        )
    if category == SupplierPriceCategory.PANEL:
        missing = [
            name
            for name, value in (
                ("length", read.sheet_length_mm), ("width", read.sheet_width_mm), ("thickness", read.thickness_mm),
            )
            if value is None
        ]
        if missing:
            return CaptureResult("unreadable", f"the page does not state the sheet {', '.join(missing)}", None, read)

    entry = price_list.create_entry(
        session,
        key=key,
        label=read.name or key,
        category=category,
        unit=chosen,
        base_cents=price,
        provenance=Provenance.CAPTURED,
        source_url=url,
        sheet_length_mm=read.sheet_length_mm,
        sheet_width_mm=read.sheet_width_mm,
        thickness_mm=read.thickness_mm,
        captured_at=read.fetched_at,
    )
    if indexer is not None:
        indexer(session, url, read.name or key, read.page_text)
    return CaptureResult("ok", None, entry, read)


def refresh(session: Session, fetcher: LiveFetcher, key: str) -> RefreshResult:
    """Re-read a captured entry's page; only the base price and its time change.

    The override is never touched. A manual or snapshot entry has no page of its
    own to read and is refused as such.
    """
    entry = price_list.get_entry(session, key)
    if entry.provenance != Provenance.CAPTURED or not entry.source_url:
        return RefreshResult(
            "no_source",
            f"a {entry.provenance} entry has no page to read; change its price by hand or override it",
            entry,
        )
    read = read_product(fetcher, entry.source_url)
    if not read.ok:
        return RefreshResult(read.outcome, read.reason, entry)
    price = _price_for_unit(read, entry.unit)
    if price is None:
        return RefreshResult("unreadable", f"the page states no {entry.unit.replace('_', ' ')} price", entry)
    price_list.record_capture(session, entry.key, cents=price, url=entry.source_url, at=read.fetched_at)
    return RefreshResult("ok", None, entry)
