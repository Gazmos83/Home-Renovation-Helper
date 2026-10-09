"""Hardware data sheets: the cited drilling values of one hinge or shelf-pin item.

A measured value is one number (`{"value": 35}`) or a range (`{"min": 80, "max": 120}`), as its
source gives it, and is never narrowed. A count is one whole number. Each sheet is mirrored into
the corpus as a `guideline` passage (source `owner`, URL `owner-datasheet:<key>`).
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated, Any, Final
from urllib.parse import urlsplit
from uuid import UUID

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    ValidationError,
    model_validator,
)
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.chunk_store import delete_page_chunks
from app.db.models import HardwareDataSheet
from app.guidelines.ingest import CATEGORY
from app.guidelines.notes import OWNER_SOURCE
from app.pricing.errors import NotFound, Refused
from app.pricing.product_page import SOURCE_HOSTS

KINDS: Final = ("hinge", "shelf_pin")
SOURCE_KINDS: Final = ("toom", "manual")
_KEY = r"^[a-z0-9](?:[a-z0-9-]{0,126}[a-z0-9])?$"


class FieldRefused(Refused):
    """A refusal that names the form field it is about, so the page can show it beside that field."""

    def __init__(self, message: str, field: str) -> None:
        super().__init__(message)
        self.field = field


class Measure(BaseModel):
    """One measured value in mm: exact (`value`) or a range (`min` below `max`)."""

    model_config = ConfigDict(extra="forbid")

    value: float | None = Field(default=None, gt=0)
    min: float | None = Field(default=None, gt=0)
    max: float | None = Field(default=None, gt=0)

    @model_validator(mode="after")
    def _one_form(self) -> Measure:
        ranged = self.min is not None or self.max is not None
        if self.value is not None and ranged:
            raise ValueError("give either one value or a min and a max, not both")
        if self.value is None and not ranged:
            raise ValueError("give a value, or a min and a max")
        if ranged:
            if self.min is None or self.max is None:
                raise ValueError("a range needs both a min and a max")
            if self.min >= self.max:
                raise ValueError("a range needs min below max")
        return self


class CountRow(BaseModel):
    model_config = ConfigDict(extra="forbid")

    max_height_mm: int = Field(gt=0)
    hinges: int = Field(ge=1, le=20)


class HingeValues(BaseModel):
    model_config = ConfigDict(extra="forbid")

    cup_diameter_mm: Measure | None = None
    cup_depth_mm: Measure | None = None
    cup_edge_distance_mm: Measure | None = None
    end_distance_mm: Measure | None = None
    count_table: Annotated[list[CountRow], Field(max_length=12)] | None = None
    plate_item: Annotated[str, StringConstraints(pattern=_KEY)] | None = None
    plate_setback_mm: Measure | None = None
    plate_hole_spacing_mm: Measure | None = None


class ShelfPinValues(BaseModel):
    model_config = ConfigDict(extra="forbid")

    hole_diameter_mm: Measure | None = None
    hole_depth_mm: Measure | None = None
    pitch_mm: Measure | None = None
    first_hole_mm: Measure | None = None
    last_hole_mm: Measure | None = None
    front_setback_mm: Measure | None = None
    rear_setback_mm: Measure | None = None
    pins_per_shelf: int | None = Field(default=None, ge=1, le=64, strict=True)


_MODELS: Final[dict[str, type[BaseModel]]] = {"hinge": HingeValues, "shelf_pin": ShelfPinValues}
_COUNTS: Final = frozenset({"pins_per_shelf", "count_table"})


def validate_values(kind: str, raw: dict[str, Any]) -> dict[str, Any]:
    """The kind's values, validated and reduced to the fields given; refused naming the field."""
    model = _MODELS.get(kind)
    if model is None:
        raise Refused(f"unknown data-sheet kind {kind!r}; use one of {', '.join(KINDS)}")
    try:
        return model.model_validate(raw).model_dump(exclude_none=True, exclude_unset=True)
    except ValidationError as error:
        first = error.errors()[0]
        field = str(first["loc"][0]) if first["loc"] else "values"
        if field in _COUNTS:
            raise FieldRefused(f"{field} is a count and must be whole numbers, never a range", "values") from None
        if first["type"] == "extra_forbidden":
            raise FieldRefused(f"{field} is not a {kind} value", "values") from None
        detail = str(first["msg"]).removeprefix("Value error, ")
        raise FieldRefused(f"{field}: {detail}", "values") from None


def _norm(text: str | None) -> str:
    return (text or "").strip().casefold()


def _clean_source(
    session: Session, retail_sources: frozenset[str], *, key: str, maker: str, model: str,
    source_kind: str, page_url: str | None, datasheet_url: str | None, citation: str,
) -> tuple[str | None, str | None, str]:
    if source_kind not in SOURCE_KINDS:
        raise Refused(f"unknown source kind {source_kind!r}; use toom or manual")
    page_url = (page_url or "").strip() or None
    datasheet_url = (datasheet_url or "").strip() or None
    citation = citation.strip()
    if source_kind == "toom":
        if page_url is None:
            raise FieldRefused("a toom source needs the toom product page URL", "page_url")
        host = (urlsplit(page_url).hostname or "").lower()
        allowed = SOURCE_HOSTS["toom"] if "toom" in retail_sources else frozenset()
        if host not in allowed:
            raise FieldRefused(
                f"a toom source must be a toom page; {host or page_url!r} is not a retail source", "page_url"
            )
        citation = citation or page_url
    elif not citation:
        raise FieldRefused(
            "a manual source needs a citation of the item's own data sheet (document, page, date)", "citation"
        )
    for other in session.scalars(select(HardwareDataSheet).where(HardwareDataSheet.key != key)):
        shared = [
            value for value in (page_url, datasheet_url, citation)
            if value and _norm(value) in {_norm(other.page_url), _norm(other.datasheet_url), _norm(other.citation)}
        ]
        if shared and (_norm(other.maker), _norm(other.model)) != (_norm(maker), _norm(model)):
            raise FieldRefused(
                f"this source belongs to {other.maker} {other.model} ({other.key}); "
                f"it cannot back {maker} {model}",
                "citation" if source_kind == "manual" else "page_url",
            )
    return page_url, datasheet_url, citation


def format_measure(measure: dict[str, Any]) -> str:
    if "value" in measure:
        return f"{measure['value']:g} mm"
    return f"{measure['min']:g}–{measure['max']:g} mm"


def sheet_url(key: str) -> str:
    return f"owner-datasheet:{key}"


def _passage(sheet: HardwareDataSheet) -> str:
    lines = [f"Hardware data sheet {sheet.key}: {sheet.maker} {sheet.model} ({sheet.kind.replace('_', ' ')})"]
    for field, value in sheet.values.items():
        if isinstance(value, dict):
            lines.append(f"{field}: {format_measure(value)}")
        elif field == "count_table":
            rows = ", ".join(f"up to {row['max_height_mm']} mm: {row['hinges']}" for row in value)
            lines.append(f"{field}: {rows}")
        else:
            lines.append(f"{field}: {value}")
    lines.append(f"Quelle: {sheet.citation}")
    return "\n".join(lines)


def _index(session: Session, sheet: HardwareDataSheet) -> None:
    from app.pricing.corpus import index_page

    index_page(
        session, sheet_url(sheet.key), f"{sheet.maker} {sheet.model} data sheet", _passage(sheet),
        source_site=OWNER_SOURCE, category=CATEGORY, section=f"Quelle: {sheet.citation}",
    )


def create_sheet(
    session: Session, retail_sources: frozenset[str], *, key: str, kind: str, maker: str, model: str,
    values: dict[str, Any], source_kind: str, citation: str = "", page_url: str | None = None,
    datasheet_url: str | None = None,
) -> HardwareDataSheet:
    key, maker, model = key.strip(), maker.strip(), model.strip()
    if not key or not maker or not model:
        raise Refused("a data sheet needs a key, a maker and a model")
    if session.scalar(select(HardwareDataSheet).where(HardwareDataSheet.key == key)) is not None:
        raise Refused(f"a data sheet for {key!r} already exists")
    clean = validate_values(kind, values)
    page_url, datasheet_url, citation = _clean_source(
        session, retail_sources, key=key, maker=maker, model=model, source_kind=source_kind,
        page_url=page_url, datasheet_url=datasheet_url, citation=citation,
    )
    sheet = HardwareDataSheet(
        key=key, kind=kind, maker=maker, model=model, values=clean, source_kind=source_kind,
        page_url=page_url, datasheet_url=datasheet_url, citation=citation,
    )
    session.add(sheet)
    session.flush()
    _index(session, sheet)
    return sheet


def get_sheet(session: Session, sheet_id: UUID) -> HardwareDataSheet:
    sheet = session.get(HardwareDataSheet, sheet_id)
    if sheet is None:
        raise NotFound(f"no hardware data sheet {sheet_id}")
    return sheet


def update_sheet(
    session: Session, retail_sources: frozenset[str], sheet_id: UUID, *, kind: str, maker: str, model: str,
    values: dict[str, Any], source_kind: str, citation: str = "", page_url: str | None = None,
    datasheet_url: str | None = None,
) -> HardwareDataSheet:
    sheet = get_sheet(session, sheet_id)
    maker, model = maker.strip(), model.strip()
    if not maker or not model:
        raise Refused("a data sheet needs a maker and a model")
    clean = validate_values(kind, values)
    page_url, datasheet_url, citation = _clean_source(
        session, retail_sources, key=sheet.key, maker=maker, model=model, source_kind=source_kind,
        page_url=page_url, datasheet_url=datasheet_url, citation=citation,
    )
    sheet.kind, sheet.maker, sheet.model, sheet.values = kind, maker, model, clean
    sheet.source_kind, sheet.page_url, sheet.datasheet_url, sheet.citation = (
        source_kind, page_url, datasheet_url, citation,
    )
    sheet.updated_at = datetime.now(UTC)
    session.flush()
    _index(session, sheet)
    return sheet


def delete_sheet(session: Session, sheet_id: UUID) -> None:
    sheet = get_sheet(session, sheet_id)
    delete_page_chunks(session, sheet_url(sheet.key))
    session.delete(sheet)
    session.flush()


def list_sheets(session: Session) -> list[HardwareDataSheet]:
    return list(session.scalars(select(HardwareDataSheet).order_by(HardwareDataSheet.key)))


def sheet_for_key(session: Session, key: str) -> HardwareDataSheet | None:
    return session.scalar(select(HardwareDataSheet).where(HardwareDataSheet.key == key))


def describe_sheet(sheet: HardwareDataSheet) -> dict[str, Any]:
    return {
        "id": str(sheet.id), "key": sheet.key, "kind": sheet.kind, "maker": sheet.maker, "model": sheet.model,
        "values": sheet.values, "source_kind": sheet.source_kind, "page_url": sheet.page_url,
        "datasheet_url": sheet.datasheet_url, "citation": sheet.citation,
        "created_at": sheet.created_at.isoformat(), "updated_at": sheet.updated_at.isoformat(),
    }


