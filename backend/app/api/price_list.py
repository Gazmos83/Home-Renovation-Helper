"""The price list and its snapshots (price-list spec). Owner-gated.

Prices are euro cents. A pasted toom URL and a refresh each read one retailer
page, so both are rate-limited; a refusal (robots, 401, 403, 429) is an answer
and creates or changes nothing.
"""

from __future__ import annotations

import logging
from datetime import date
from decimal import Decimal
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel, Field, ValidationError
from sqlalchemy.orm import Session

from app.api.gate import require_owner
from app.auth.sessions import AuthSessionRecord
from app.pricing import capture, corpus, price_list, snapshots
from app.pricing.errors import Conflict, NotFound, Refused

logger = logging.getLogger("app")

router = APIRouter(tags=["price list"], dependencies=[Depends(require_owner)])


class EntryIn(BaseModel):
    key: str = Field(max_length=128)
    label: str = Field(max_length=256)
    category: str = Field(max_length=16)
    unit: str = Field(max_length=16)
    base_cents: int | None = Field(default=None, ge=0)
    source_url: str | None = Field(default=None, max_length=2000)
    sheet_length_mm: int | None = Field(default=None, gt=0, le=10_000)
    sheet_width_mm: int | None = Field(default=None, gt=0, le=10_000)
    thickness_mm: int | None = Field(default=None, gt=0, le=1_000)
    bundle_length_mm: int | None = Field(default=None, gt=0, le=100_000)


class EntryPatch(BaseModel):
    label: str | None = Field(default=None, max_length=256)
    unit: str | None = Field(default=None, max_length=16)
    base_cents: int | None = Field(default=None, ge=0)
    source_url: str | None = Field(default=None, max_length=2000)
    sheet_length_mm: int | None = Field(default=None, gt=0, le=10_000)
    sheet_width_mm: int | None = Field(default=None, gt=0, le=10_000)
    thickness_mm: int | None = Field(default=None, gt=0, le=1_000)
    bundle_length_mm: int | None = Field(default=None, gt=0, le=100_000)


class OverrideIn(BaseModel):
    cents: int = Field(ge=0)
    note: str | None = Field(default=None, max_length=1000)


class FromUrlIn(BaseModel):
    url: str = Field(max_length=2000)
    key: str = Field(max_length=128)
    category: str = Field(max_length=16)
    unit: str | None = Field(default=None, max_length=16)


class PrefillIn(BaseModel):
    key: str = Field(max_length=128)
    category: str = Field(max_length=16)
    unit: str = Field(max_length=16)
    sheet_length_mm: int | None = Field(default=None, gt=0, le=10_000)
    sheet_width_mm: int | None = Field(default=None, gt=0, le=10_000)
    thickness_mm: int | None = Field(default=None, gt=0, le=1_000)
    bundle_length_mm: int | None = Field(default=None, gt=0, le=100_000)


class SnapshotBody(BaseModel):
    retailer: str
    url: str
    product_name: str
    price: Decimal | None = None
    currency: str | None = None
    availability: str | None = None
    specification: str
    store_name: str | None = None
    captured_on: date
    prefill: PrefillIn | None = None


def refusal(code: int, failure_class: str, reason: str, **extra: Any) -> HTTPException:
    return HTTPException(code, detail={"failure_class": failure_class, "reason": reason, **extra})


def _guard(error: Exception) -> HTTPException:
    if isinstance(error, NotFound):
        return HTTPException(status.HTTP_404_NOT_FOUND, detail={"failure_class": "not_found", "reason": str(error)})
    if isinstance(error, Conflict):
        return refusal(status.HTTP_409_CONFLICT, "conflict", str(error))
    return refusal(422, "refused", str(error))


def _limit(request: Request, login: AuthSessionRecord, what: str) -> None:
    request.app.state.price_rate_limiter.check([f"{what}:{login.user_id}"])


# --- entries --------------------------------------------------------------------------------


@router.get("/price-list")
def list_entries(request: Request, category: str | None = None) -> list[dict[str, Any]]:
    with Session(request.app.state.engine) as session:
        try:
            return [price_list.describe(e) for e in price_list.list_entries(session, category=category)]
        except Refused as error:
            raise _guard(error) from None


@router.post("/price-list", status_code=status.HTTP_201_CREATED)
def create_entry(body: EntryIn, request: Request) -> dict[str, Any]:
    with Session(request.app.state.engine) as session:
        try:
            entry = price_list.create_entry(session, **body.model_dump(), provenance="manual")
        except Refused as error:
            raise _guard(error) from None
        session.commit()
        return price_list.describe(entry)


@router.post("/price-list/from-url", status_code=status.HTTP_201_CREATED)
def entry_from_url(
    body: FromUrlIn, request: Request, login: Annotated[AuthSessionRecord, Depends(require_owner)]
) -> dict[str, Any]:
    _limit(request, login, "price-fetch")
    settings = request.app.state.settings
    with Session(request.app.state.engine) as session:
        try:
            result = capture.capture_from_url(
                session, request.app.state.live_fetcher, body.url, key=body.key, category=body.category,
                retail_sources=settings.retail_sources, unit=body.unit,
                indexer=lambda s, url, title, text: corpus.index_page(s, url, title, text),
            )
        except Refused as error:
            session.rollback()
            if "not a permitted source" in str(error):
                raise refusal(422, "source_not_permitted", str(error)) from None
            raise _guard(error) from None
        if result.entry is None:
            session.rollback()
            code = {"refused": 409, "excluded": 409, "timeout": 504, "unfetchable": 502}.get(result.outcome, 422)
            raise refusal(code, result.outcome, result.reason or "the page could not be read")
        session.commit()
        return price_list.describe(result.entry)


@router.get("/price-list/{key}")
def read_entry(key: str, request: Request) -> dict[str, Any]:
    with Session(request.app.state.engine) as session:
        try:
            return price_list.describe(price_list.get_entry(session, key))
        except NotFound as error:
            raise _guard(error) from None


@router.patch("/price-list/{key}")
def edit_entry(key: str, body: EntryPatch, request: Request) -> dict[str, Any]:
    with Session(request.app.state.engine) as session:
        try:
            entry = price_list.revise_entry(session, key, **body.model_dump(exclude_unset=True))
        except (NotFound, Refused) as error:
            raise _guard(error) from None
        session.commit()
        return price_list.describe(entry)


@router.delete("/price-list/{key}", status_code=status.HTTP_204_NO_CONTENT)
def delete_entry(key: str, request: Request) -> Response:
    with Session(request.app.state.engine) as session:
        try:
            price_list.delete_entry(session, key)
        except (NotFound, Refused) as error:
            session.rollback()
            raise _guard(error) from None
        session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.put("/price-list/{key}/override")
def put_override(key: str, body: OverrideIn, request: Request) -> dict[str, Any]:
    with Session(request.app.state.engine) as session:
        try:
            entry = price_list.set_override(session, key, cents=body.cents, note=body.note)
        except (NotFound, Refused) as error:
            raise _guard(error) from None
        session.commit()
        return price_list.describe(entry)


@router.delete("/price-list/{key}/override")
def remove_override(key: str, request: Request) -> dict[str, Any]:
    with Session(request.app.state.engine) as session:
        try:
            entry = price_list.clear_override(session, key)
        except NotFound as error:
            raise _guard(error) from None
        session.commit()
        return price_list.describe(entry)


@router.post("/price-list/{key}/refresh")
def refresh_entry(
    key: str, request: Request, login: Annotated[AuthSessionRecord, Depends(require_owner)]
) -> dict[str, Any]:
    _limit(request, login, "price-fetch")
    with Session(request.app.state.engine) as session:
        try:
            result = capture.refresh(session, request.app.state.live_fetcher, key)
        except NotFound as error:
            raise _guard(error) from None
        session.commit()
        return {
            "outcome": result.outcome,
            "reason": result.reason,
            "entry": price_list.describe(result.entry) if result.entry else None,
        }


# --- snapshots -----------------------------------------------------------------------------


def _snapshot_out(row) -> dict[str, Any]:
    return {
        "id": str(row.id),
        "retailer": row.retailer,
        "url": row.url,
        "product_name": row.product_name,
        "price": str(row.price) if row.price is not None else None,
        "currency": row.currency,
        "availability": row.availability,
        "specification": row.specification,
        "store_name": row.store_name,
        "captured_on": row.captured_on.isoformat(),
        "recorded_at": row.recorded_at.isoformat(),
    }


@router.get("/snapshots")
def list_snapshots(request: Request) -> list[dict[str, Any]]:
    with Session(request.app.state.engine) as session:
        return [_snapshot_out(row) for row in snapshots.list_snapshots(session)]


@router.post("/snapshots", status_code=status.HTTP_201_CREATED)
def record_snapshot(
    body: SnapshotBody, request: Request, login: Annotated[AuthSessionRecord, Depends(require_owner)]
) -> dict[str, Any]:
    fields = body.model_dump(exclude={"prefill"})
    try:
        data = snapshots.SnapshotIn(**fields)
    except ValidationError as error:
        first = error.errors()[0]
        field = ".".join(str(part) for part in first["loc"])
        raise refusal(422, "invalid_snapshot", f"{field}: {first['msg']}", field=field) from None
    prefill = snapshots.Prefill(**body.prefill.model_dump()) if body.prefill else None
    with Session(request.app.state.engine) as session:
        try:
            row = snapshots.record_snapshot(session, data, recorded_by=login.user_id, prefill=prefill)
        except snapshots.SnapshotConflict as error:
            session.rollback()
            raise refusal(status.HTTP_409_CONFLICT, "conflict", str(error)) from None
        except Refused as error:
            session.rollback()
            raise _guard(error) from None
        session.commit()
        session.refresh(row)
        return _snapshot_out(row)


@router.delete("/snapshots/{snapshot_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_snapshot(snapshot_id: UUID, request: Request) -> Response:
    with Session(request.app.state.engine) as session:
        try:
            snapshots.delete_snapshot(session, snapshot_id)
        except snapshots.SnapshotNotFound:
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Not Found") from None
        except Refused as error:
            session.rollback()
            raise _guard(error) from None
        session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
