"""Manual product snapshots (price-list spec).

The owner types what a retailer's product page said on a given day, for a page
the crawl cannot reach. Recording one never fetches anything and never enables
crawling or live lookup for that retailer: the retailer here is a free-form
slug, not a `RETAIL_SOURCES` entry.

`product_snapshots` is the record of what was typed. Each snapshot is also
rendered into the corpus as ordinary, dated, attributed chunks (category
`manual_snapshot`) so catalog search can retrieve it, and may prefill a
`snapshot`-provenance price-list entry. Re-recording the same URL replaces its
chunks but keeps every prior snapshot row. Functions flush; the caller commits.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Final
from uuid import UUID

from pydantic import BaseModel, field_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.chunk_store import IncomingChunk, replace_page_chunks
from app.db.models import Chunk, ProductSnapshot, Provenance, SupplierPrice
from app.embedding import embed
from app.ingestion.extract import chunk_text
from app.pricing import price_list
from app.pricing.errors import Conflict, Refused

CATEGORY: Final = "manual_snapshot"

_RETAILER_PATTERN: Final = re.compile(r"^[a-z0-9][a-z0-9-]{1,31}$")
_CURRENCY_PATTERN: Final = re.compile(r"^[A-Z]{3}$")


class SnapshotValidationError(ValueError):
    """A snapshot cannot be recorded as given. `field` names what failed."""

    def __init__(self, field: str, message: str) -> None:
        self.field = field
        super().__init__(message)


class SnapshotConflict(Exception):
    """The product URL already carries chunks from a source other than a manual snapshot."""

    def __init__(self, url: str) -> None:
        self.url = url
        super().__init__(
            f"{url!r} already holds catalog content from another source; "
            "a manual snapshot cannot replace it"
        )


class SnapshotNotFound(Exception):
    def __init__(self, snapshot_id: UUID) -> None:
        self.snapshot_id = snapshot_id
        super().__init__(f"no snapshot {snapshot_id}")


class SnapshotIn(BaseModel):
    """What an administrator submits. Every field is validated before anything is stored."""

    retailer: str
    url: str
    product_name: str
    price: Decimal | None = None
    currency: str | None = None
    availability: str | None = None
    specification: str
    store_name: str | None = None
    captured_on: date

    @field_validator("retailer")
    @classmethod
    def _retailer_is_a_slug(cls, value: str) -> str:
        if not _RETAILER_PATTERN.match(value):
            raise ValueError(
                "retailer must be lowercase letters, digits and hyphens, 2-32 characters"
            )
        return value

    @field_validator("url")
    @classmethod
    def _url_is_absolute(cls, value: str) -> str:
        if not value.startswith(("http://", "https://")):
            raise ValueError("url must be an absolute http or https URL")
        return value

    @field_validator("product_name", "specification")
    @classmethod
    def _not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("must not be blank")
        return value

    @field_validator("price")
    @classmethod
    def _price_non_negative(cls, value: Decimal | None) -> Decimal | None:
        if value is not None and value < 0:
            raise ValueError("must not be negative")
        return value

    @field_validator("currency")
    @classmethod
    def _currency_shape(cls, value: str | None) -> str | None:
        if value is not None and not _CURRENCY_PATTERN.match(value):
            raise ValueError("must be a 3-letter currency code, e.g. EUR")
        return value

    @field_validator("captured_on")
    @classmethod
    def _not_future(cls, value: date) -> date:
        if value > datetime.now(UTC).date():
            raise ValueError("must not be in the future")
        return value


@dataclass(frozen=True, slots=True)
class Prefill:
    """Make a `snapshot` entry from the snapshot: its price becomes the base price."""

    key: str
    category: str
    unit: str
    sheet_length_mm: int | None = None
    sheet_width_mm: int | None = None
    thickness_mm: int | None = None
    bundle_length_mm: int | None = None


def render_snapshot_text(data: SnapshotIn) -> str:
    """The fixed, attributed text a snapshot becomes in the knowledge store.

    Opens with a line naming the retailer, product and capture date, so a
    retrieved passage reads as a dated record rather than a live listing.
    """
    opening = (
        f"Manually recorded snapshot of {data.retailer}'s page for "
        f"{data.product_name!r}, captured on {data.captured_on.isoformat()}."
    )
    lines = [opening, f"Product: {data.product_name}"]
    if data.price is not None:
        currency = data.currency or ""
        lines.append(f"Price as published: {data.price} {currency}".rstrip())
    if data.availability:
        lines.append(f"Availability as published: {data.availability}")
    if data.store_name:
        lines.append(f"Store: {data.store_name}")
    lines.append("Specification:")
    lines.append(data.specification)
    return "\n".join(lines)


def _existing_categories(session: Session, url: str) -> set[str]:
    rows = session.execute(select(Chunk.category).where(Chunk.url == url).distinct())
    return {row[0] for row in rows}


def _write_chunks(session: Session, data: SnapshotIn) -> None:
    """(Re)write `data`'s knowledge-store chunks for its URL."""
    text = render_snapshot_text(data)
    pieces = chunk_text(text)
    vectors = embed(pieces) if pieces else []
    scraped_at = datetime.combine(data.captured_on, datetime.min.time(), tzinfo=UTC)
    incoming = [
        IncomingChunk(
            content=piece,
            embedding=vector,
            source_site=data.retailer,
            url=data.url,
            category=CATEGORY,
            chunk_index=index,
            scraped_at=scraped_at,
        )
        for index, (piece, vector) in enumerate(zip(pieces, vectors, strict=True))
    ]
    replace_page_chunks(session, data.url, incoming, page_length=len(incoming))


def record_snapshot(
    session: Session,
    data: SnapshotIn,
    *,
    recorded_by: UUID | None,
    prefill: Prefill | None = None,
) -> ProductSnapshot:
    """Insert the snapshot row, (re)write its corpus chunks and, when asked, prefill an entry.

    Refuses (`SnapshotConflict`) a URL that already carries chunks from
    ingestion or live lookup, so a manual snapshot can never overwrite crawled
    knowledge under the same key. A prefill needs a price; its entry is made in
    the same transaction, so a refusal of the entry leaves no snapshot behind.
    """
    other_categories = _existing_categories(session, data.url) - {CATEGORY}
    if other_categories:
        raise SnapshotConflict(data.url)

    row = ProductSnapshot(
        retailer=data.retailer,
        url=data.url,
        product_name=data.product_name,
        price=data.price,
        currency=data.currency,
        availability=data.availability,
        specification=data.specification,
        store_name=data.store_name,
        captured_on=data.captured_on,
        recorded_by_id=recorded_by,
    )
    session.add(row)
    session.flush()

    if prefill is not None:
        if data.price is None:
            raise Refused("a snapshot needs a price to prefill an entry")
        price_list.create_entry(
            session,
            key=prefill.key,
            label=data.product_name,
            category=prefill.category,
            unit=prefill.unit,
            base_cents=int((data.price * 100).to_integral_value()),
            provenance=Provenance.SNAPSHOT,
            source_url=data.url,
            sheet_length_mm=prefill.sheet_length_mm,
            sheet_width_mm=prefill.sheet_width_mm,
            thickness_mm=prefill.thickness_mm,
            bundle_length_mm=prefill.bundle_length_mm,
            snapshot_id=row.id,
            captured_at=datetime.combine(data.captured_on, datetime.min.time(), tzinfo=UTC),
            source_site=data.retailer,
        )

    _write_chunks(session, data)
    session.flush()
    return row


def list_snapshots(session: Session) -> list[ProductSnapshot]:
    return list(
        session.execute(select(ProductSnapshot).order_by(ProductSnapshot.recorded_at.desc())).scalars()
    )


def delete_snapshot(session: Session, snapshot_id: UUID) -> None:
    """Remove a snapshot row, then re-derive or drop that URL's chunks.

    If a newer snapshot for the same URL exists, its chunks already are (or
    become) what is stored; if this was the only one, the manual-snapshot
    chunks for that URL are removed.
    """
    row = session.get(ProductSnapshot, snapshot_id)
    if row is None:
        raise SnapshotNotFound(snapshot_id)
    referenced = session.scalar(select(SupplierPrice.key).where(SupplierPrice.snapshot_id == snapshot_id))
    if referenced is not None:
        raise Conflict(f"the price-list entry {referenced!r} was made from this snapshot; delete or revise it first")

    url = row.url
    session.delete(row)
    session.flush()

    newer = session.execute(
        select(ProductSnapshot)
        .where(ProductSnapshot.url == url)
        .order_by(ProductSnapshot.captured_on.desc(), ProductSnapshot.recorded_at.desc())
        .limit(1)
    ).scalar_one_or_none()

    if newer is not None:
        data = SnapshotIn(
            retailer=newer.retailer,
            url=newer.url,
            product_name=newer.product_name,
            price=newer.price,
            currency=newer.currency,
            availability=newer.availability,
            specification=newer.specification,
            store_name=newer.store_name,
            captured_on=newer.captured_on,
        )
        _write_chunks(session, data)
    else:
        session.execute(
            Chunk.__table__.delete().where(Chunk.url == url, Chunk.category == CATEGORY)
        )
    session.flush()
