"""The one supplier price list (price-list spec).

Plain functions over a session and values; `NotFound`/`Refused` carry the reason.
Every price has a provenance (`captured`, `manual`, `snapshot`) and may carry the
owner's override on top; `effective_cents` is the override when set, else the base
price, and both stay readable. Prices are euro cents and are never estimated.
Functions flush but never commit: the caller owns the transaction.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Final

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.models import (
    CutListPricing,
    CutListPricingEntry,
    Provenance,
    SupplierPrice,
    SupplierPriceCategory,
    SupplierPriceUnit,
)
from app.pricing.errors import Conflict, NotFound, Refused

# What the workshop supplies itself: priced at 0 cents, seeded by the migration.
PERSONAL_SUPPLY_KEY: Final = "Personal_Supply"

# What `revise_entry` may change. Never the key, the category or the provenance.
_REVISABLE: Final = frozenset(
    {
        "label",
        "unit",
        "sheet_length_mm",
        "sheet_width_mm",
        "thickness_mm",
        "bundle_length_mm",
        "source_url",
        "base_cents",
    }
)


@dataclass(frozen=True, slots=True)
class RefreshResult:
    outcome: str
    reason: str | None
    entry: SupplierPrice | None


def _now() -> datetime:
    return datetime.now(UTC)


def _category(value: str) -> str:
    try:
        return SupplierPriceCategory(value).value
    except ValueError:
        raise Refused(
            f"unknown category: {value!r}; known categories are "
            f"{', '.join(m.value for m in SupplierPriceCategory)}"
        ) from None


def _unit(value: str) -> str:
    try:
        return SupplierPriceUnit(value).value
    except ValueError:
        raise Refused(
            f"unknown unit: {value!r}; known units are {', '.join(m.value for m in SupplierPriceUnit)}"
        ) from None


def _cents(value: Any, name: str) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise Refused(f"{name} must be a whole number of euro cents, zero or more")
    return value


def _positive(value: Any, name: str) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise Refused(f"{name} must be a positive number of millimetres")
    return value


def _check_panel(category: str, length: int | None, width: int | None, thickness: int | None) -> None:
    if category != SupplierPriceCategory.PANEL:
        return
    missing = [
        label for label, value in (("length", length), ("width", width), ("thickness", thickness)) if value is None
    ]
    if missing:
        raise Refused(f"a panel needs its sheet {', '.join(missing)} (in millimetres)")


def create_entry(
    session: Session,
    *,
    key: str,
    label: str,
    category: str,
    unit: str,
    base_cents: int | None = None,
    provenance: str = Provenance.MANUAL,
    source_url: str | None = None,
    sheet_length_mm: int | None = None,
    sheet_width_mm: int | None = None,
    thickness_mm: int | None = None,
    bundle_length_mm: int | None = None,
    snapshot_id: Any = None,
    captured_at: datetime | None = None,
    source_site: str = "toom",
) -> SupplierPrice:
    """Make an entry. A blank key or label, an unknown category or unit, a panel
    without its sheet size, a negative price or a key already in use is refused."""
    key = (key or "").strip()
    label = (label or "").strip()
    if not key:
        raise Refused("an entry needs a key")
    if not label:
        raise Refused("an entry needs a label")
    if key == PERSONAL_SUPPLY_KEY:
        raise Refused(f"{PERSONAL_SUPPLY_KEY!r} is reserved for what the workshop supplies itself")
    category = _category(category)
    unit = _unit(unit)
    try:
        origin = Provenance(provenance).value
    except ValueError:
        raise Refused(f"unknown provenance: {provenance!r}") from None
    _check_panel(category, sheet_length_mm, sheet_width_mm, thickness_mm)
    if session.scalar(select(SupplierPrice.id).where(SupplierPrice.key == key)) is not None:
        raise Conflict(f"an entry with the key {key!r} already exists")
    now = _now()
    entry = SupplierPrice(
        key=key,
        label=label,
        category=category,
        unit=unit,
        source_site=source_site,
        sheet_length_mm=_positive(sheet_length_mm, "the sheet length"),
        sheet_width_mm=_positive(sheet_width_mm, "the sheet width"),
        thickness_mm=_positive(thickness_mm, "the thickness"),
        bundle_length_mm=_positive(bundle_length_mm, "the bundle length"),
        base_cents=_cents(base_cents, "the price"),
        provenance=origin,
        source_url=source_url,
        captured_at=captured_at or (now if origin == Provenance.CAPTURED else None),
        snapshot_id=snapshot_id,
        created_at=now,
        updated_at=now,
    )
    session.add(entry)
    session.flush()
    return entry


def get_entry(session: Session, key: str) -> SupplierPrice:
    entry = session.scalar(select(SupplierPrice).where(SupplierPrice.key == (key or "").strip()))
    if entry is None:
        raise NotFound(f"there is no price-list entry {key!r}")
    return entry


def list_entries(session: Session, *, category: str | None = None) -> list[SupplierPrice]:
    statement = select(SupplierPrice).order_by(SupplierPrice.category, SupplierPrice.key)
    if category is not None:
        statement = statement.where(SupplierPrice.category == _category(category))
    return list(session.scalars(statement))


def revise_entry(session: Session, entry_key: str, **fields: Any) -> SupplierPrice:
    """Change an entry's label, unit, sheet size, bundle length, source URL or (for a
    manual or snapshot entry) its base price. Never its key, category or provenance."""
    entry = get_entry(session, entry_key)
    unknown = sorted(set(fields) - _REVISABLE)
    if unknown:
        raise Refused(f"{unknown[0]!r} cannot be changed on an entry")
    if entry.key == PERSONAL_SUPPLY_KEY and set(fields) - {"label"}:
        raise Refused(f"{PERSONAL_SUPPLY_KEY!r} can only change its label and its override")
    if "base_cents" in fields and entry.provenance == Provenance.CAPTURED:
        raise Refused("a captured price changes only by refreshing it, or by an override")
    if "unit" in fields and entry.provenance == Provenance.CAPTURED and _unit(fields["unit"]) != entry.unit:
        # The captured price was read for its unit; another unit would keep the wrong figure.
        raise Refused("a captured entry keeps the unit its price was read for; capture the page again for another unit")
    if "label" in fields:
        label = (fields["label"] or "").strip()
        if not label:
            raise Refused("an entry needs a label")
        entry.label = label
    if "unit" in fields:
        entry.unit = _unit(fields["unit"])
    for name in ("sheet_length_mm", "sheet_width_mm", "thickness_mm", "bundle_length_mm"):
        if name in fields:
            setattr(entry, name, _positive(fields[name], name.replace("_", " ")))
    if "source_url" in fields:
        entry.source_url = fields["source_url"]
    if "base_cents" in fields:
        entry.base_cents = _cents(fields["base_cents"], "the price")
    _check_panel(entry.category, entry.sheet_length_mm, entry.sheet_width_mm, entry.thickness_mm)
    entry.updated_at = _now()
    session.flush()
    return entry


def set_override(session: Session, key: str, *, cents: int, note: str | None = None) -> SupplierPrice:
    entry = get_entry(session, key)
    entry.override_cents = _cents(cents, "the override")
    entry.override_note = (note or "").strip() or None
    entry.override_at = _now()
    # Setting the owner's own figure settles a seeded planning figure.
    entry.unconfirmed = False
    entry.updated_at = entry.override_at
    session.flush()
    return entry


def clear_override(session: Session, key: str) -> SupplierPrice:
    entry = get_entry(session, key)
    entry.override_cents = None
    entry.override_note = None
    entry.override_at = None
    entry.updated_at = _now()
    session.flush()
    return entry


def record_capture(
    session: Session, key: str, *, cents: int, url: str, at: datetime | None = None
) -> SupplierPrice:
    """Store a freshly read base price and its source. Never touches the override."""
    entry = get_entry(session, key)
    entry.base_cents = _cents(cents, "the price")
    entry.provenance = Provenance.CAPTURED
    entry.source_url = url
    entry.captured_at = at or _now()
    entry.updated_at = _now()
    session.flush()
    return entry


def pricings_using(session: Session, entry: SupplierPrice) -> list[CutListPricing]:
    return list(
        session.scalars(
            select(CutListPricing)
            .join(CutListPricingEntry, CutListPricingEntry.pricing_id == CutListPricing.id)
            .where(CutListPricingEntry.entry_id == entry.id)
            .order_by(CutListPricing.computed_at)
        )
    )


def delete_entry(session: Session, key: str) -> None:
    """Delete an entry no stored pricing used; the refusal names the pricing that did."""
    entry = get_entry(session, key)
    if entry.key == PERSONAL_SUPPLY_KEY:
        raise Conflict(f"{PERSONAL_SUPPLY_KEY!r} is reserved and cannot be deleted")
    using = pricings_using(session, entry)
    if using:
        first = using[0]
        raise Conflict(
            f"{entry.key!r} was used by the pricing of {first.package_id} version {first.version} "
            f"({first.computed_at:%Y-%m-%d}) and cannot be deleted"
        )
    try:
        session.delete(entry)
        session.flush()
    except IntegrityError:
        session.rollback()
        raise Conflict(f"{entry.key!r} is still referenced and cannot be deleted") from None


def describe(entry: SupplierPrice) -> dict[str, Any]:
    """An entry as a plain dict: both prices, the provenance, and the effective figure."""
    return {
        "key": entry.key,
        "label": entry.label,
        "category": entry.category,
        "unit": entry.unit,
        "sheet_length_mm": entry.sheet_length_mm,
        "sheet_width_mm": entry.sheet_width_mm,
        "thickness_mm": entry.thickness_mm,
        "bundle_length_mm": entry.bundle_length_mm,
        "base_cents": entry.base_cents,
        "provenance": entry.provenance,
        "source_url": entry.source_url,
        "captured_at": entry.captured_at.isoformat() if entry.captured_at else None,
        "snapshot_id": str(entry.snapshot_id) if entry.snapshot_id else None,
        "override_cents": entry.override_cents,
        "override_note": entry.override_note,
        "override_at": entry.override_at.isoformat() if entry.override_at else None,
        "effective_cents": entry.effective_cents,
        "unconfirmed": entry.unconfirmed,
    }
