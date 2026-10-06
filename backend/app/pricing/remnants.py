"""The workshop remnant rack (cut-list-pricing spec).

A pricing reads matching rows and names the copies it planned to use. It
does not change `quantity`. The rack changes only when a person adds or
removes a sheet. This module does not import `pricing`, so the packer can
call `matching_stock` without a cycle.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Final
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import RemnantSheet
from app.pricing.errors import NotFound, Refused

_GRAIN_AXES: Final = frozenset({"length", "width"})


@dataclass(frozen=True, slots=True)
class RemnantRecord:
    id: UUID
    material_key: str
    length_mm: int
    width_mm: int
    grain_axis: str
    quantity: int
    added_at: datetime


@dataclass(frozen=True, slots=True)
class RemnantStockRow:
    """The fields the packer needs. `id` stays a UUID here; pricing stringifies it."""

    id: UUID
    length_mm: int
    width_mm: int
    grain_axis: str
    quantity: int


def _record(row: RemnantSheet) -> RemnantRecord:
    return RemnantRecord(
        id=row.id,
        material_key=row.material_key,
        length_mm=row.length_mm,
        width_mm=row.width_mm,
        grain_axis=row.grain_axis,
        quantity=row.quantity,
        added_at=row.added_at,
    )


def _checked(material_key: str, length_mm: int, width_mm: int, grain_axis: str, quantity: int) -> tuple[str, str]:
    key = material_key.strip()
    if not key:
        raise Refused("a remnant needs a material key")
    if length_mm <= 0 or width_mm <= 0:
        raise Refused("a remnant's length and width must be positive")
    if quantity <= 0:
        raise Refused("a remnant's quantity must be positive")
    if grain_axis not in _GRAIN_AXES:
        raise Refused("a remnant's grain axis must be length or width")
    return key, grain_axis


def check_new(material_key: str, length_mm: int, width_mm: int, grain_axis: str, quantity: int) -> None:
    """Refuse a remnant that could not be added, naming why (used to preview an add)."""
    _checked(material_key, length_mm, width_mm, grain_axis, quantity)


def add_remnant(
    session: Session,
    *,
    material_key: str,
    length_mm: int,
    width_mm: int,
    grain_axis: str,
    quantity: int = 1,
) -> RemnantRecord:
    """Add sheets to the rack. Does not rewrite any pricing."""
    key, axis = _checked(material_key, length_mm, width_mm, grain_axis, quantity)
    row = RemnantSheet(
        id=uuid4(),
        material_key=key,
        length_mm=length_mm,
        width_mm=width_mm,
        grain_axis=axis,
        quantity=quantity,
    )
    session.add(row)
    session.flush()
    return _record(row)


def list_remnants(session: Session) -> list[RemnantRecord]:
    """Every remnant, oldest first, so a later plan sees a stable rack."""
    rows = session.execute(
        select(RemnantSheet).order_by(RemnantSheet.added_at, RemnantSheet.id)
    ).scalars()
    return [_record(row) for row in rows]


def matching_stock(session: Session, material_key: str) -> list[RemnantStockRow]:
    """Remnants of one material key, oldest first. Grain filtering is the packer's."""
    rows = session.execute(
        select(RemnantSheet)
        .where(RemnantSheet.material_key == material_key)
        .order_by(RemnantSheet.added_at, RemnantSheet.id)
    ).scalars()
    return [
        RemnantStockRow(
            id=row.id,
            length_mm=row.length_mm,
            width_mm=row.width_mm,
            grain_axis=row.grain_axis,
            quantity=row.quantity,
        )
        for row in rows
    ]


def remove_remnant(session: Session, remnant_id: UUID) -> None:
    """Drop one rack row. A pricing that already named it is left as it was."""
    row = session.get(RemnantSheet, remnant_id)
    if row is None:
        raise NotFound(f"there is no remnant {remnant_id}")
    session.delete(row)
    session.flush()
