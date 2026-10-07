"""Pricing a version, the remnant rack and the home store (cut-list-pricing). Owner-gated.

A pricing is an immutable record; repricing makes a new one. The rack and the
home store's restrictions change only by the owner. Money is euro cents.
"""

from __future__ import annotations

from typing import Annotated, Any, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.gate import require_owner
from app.auth.sessions import AuthSessionRecord
from app.blender import storage
from app.pricing import remnants, store
from app.pricing.errors import NotApproved, NotFound, Refused
from app.pricing.pricing import (
    describe_pricing,
    get_pricing,
    list_pricings,
    price_cut_list,
)

router = APIRouter(tags=["pricing"], dependencies=[Depends(require_owner)])


class PricingIn(BaseModel):
    delivery_key: str | None = Field(default=None, max_length=128)
    cut_charge_mode: Literal["shared", "per_cut"] | None = None


class RemnantIn(BaseModel):
    material_key: str = Field(max_length=128)
    length_mm: int = Field(gt=0, le=10_000)
    width_mm: int = Field(gt=0, le=10_000)
    grain_axis: Literal["length", "width"]
    quantity: int = Field(default=1, ge=1, le=1_000)


class RestrictionIn(BaseModel):
    numeric_value: float | None = None
    text_value: str | None = Field(default=None, max_length=500)
    note: str | None = Field(default=None, max_length=1000)


def _refusal(code: int, failure_class: str, reason: str) -> HTTPException:
    return HTTPException(code, detail={"failure_class": failure_class, "reason": reason})


def _version_exists(request: Request, package_id: str, version: int) -> None:
    try:
        folder = storage.version_dir(request.app.state.settings.render_root, package_id, version)
    except (storage.InvalidPackageId, ValueError):
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Not Found") from None
    if not folder.is_dir():
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Not Found")


# --- pricings -------------------------------------------------------------------------------


@router.post("/packages/{package_id}/versions/{version}/pricings", status_code=status.HTTP_201_CREATED)
def create_pricing(package_id: str, version: int, body: PricingIn, request: Request) -> dict[str, Any]:
    _version_exists(request, package_id, version)
    settings = request.app.state.settings
    with Session(request.app.state.engine) as session:
        try:
            row = price_cut_list(
                session, settings.render_root, package_id, version, settings,
                delivery_key=body.delivery_key, cut_charge_mode=body.cut_charge_mode,
            )
        except store.UnknownStore as error:
            raise _refusal(status.HTTP_404_NOT_FOUND, "unknown_store", str(error)) from None
        except NotApproved as error:
            raise _refusal(status.HTTP_409_CONFLICT, "not_approved", str(error)) from None
        except Refused as error:
            raise _refusal(422, "refused", str(error)) from None
        session.commit()
        return describe_pricing(session, row)


@router.get("/packages/{package_id}/versions/{version}/pricings")
def list_version_pricings(package_id: str, version: int, request: Request) -> list[dict[str, Any]]:
    _version_exists(request, package_id, version)
    with Session(request.app.state.engine) as session:
        return [describe_pricing(session, row) for row in list_pricings(session, package_id, version)]


@router.get("/pricings/{pricing_id}")
def read_pricing(pricing_id: UUID, request: Request) -> dict[str, Any]:
    with Session(request.app.state.engine) as session:
        try:
            return describe_pricing(session, get_pricing(session, pricing_id))
        except NotFound:
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Not Found") from None


# --- the remnant rack -------------------------------------------------------------------------


def _remnant_out(record) -> dict[str, Any]:
    return {
        "id": str(record.id), "material_key": record.material_key, "length_mm": record.length_mm,
        "width_mm": record.width_mm, "grain_axis": record.grain_axis, "quantity": record.quantity,
        "added_at": record.added_at.isoformat(),
    }


@router.get("/remnants")
def list_remnants(request: Request) -> list[dict[str, Any]]:
    with Session(request.app.state.engine) as session:
        return [_remnant_out(r) for r in remnants.list_remnants(session)]


@router.post("/remnants", status_code=status.HTTP_201_CREATED)
def add_remnant(body: RemnantIn, request: Request) -> dict[str, Any]:
    with Session(request.app.state.engine) as session:
        try:
            record = remnants.add_remnant(session, **body.model_dump())
        except Refused as error:
            raise _refusal(422, "refused", str(error)) from None
        session.commit()
        return _remnant_out(record)


@router.delete("/remnants/{remnant_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_remnant(remnant_id: UUID, request: Request) -> Response:
    with Session(request.app.state.engine) as session:
        try:
            remnants.remove_remnant(session, remnant_id)
        except NotFound:
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Not Found") from None
        session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# --- the home store ---------------------------------------------------------------------------


def _home(request: Request) -> str:
    return request.app.state.settings.toom_home_store


@router.get("/stores/home")
def read_home_store(request: Request) -> dict[str, Any]:
    key = _home(request)
    with Session(request.app.state.engine) as session:
        try:
            record = store.require_store(session, key)
        except store.UnknownStore as error:
            raise _refusal(status.HTTP_404_NOT_FOUND, "unknown_store", str(error)) from None
        return {
            "store_key": record.store_key,
            "name": record.name,
            "address": record.address,
            "market_id": record.market_id,
            "captured_at": record.captured_at.isoformat(),
            "services": [
                {
                    "service": s.service, "availability": s.availability.value, "price_cents": s.price_cents,
                    "captured_at": s.captured_at.isoformat(),
                }
                for s in store.store_services(session, key)
            ],
            "restrictions": [
                {
                    "restriction": r.restriction.value, "numeric_value": r.numeric_value,
                    "text_value": r.text_value, "recorded_by": r.recorded_by,
                    "recorded_at": r.recorded_at.isoformat(), "note": r.note,
                }
                for r in store.store_restrictions(session, key)
            ],
        }


def _kind(value: str) -> store.RestrictionKind:
    try:
        return store.RestrictionKind(value)
    except ValueError:
        known = ", ".join(k.value for k in store.RestrictionKind)
        raise _refusal(422, "unknown_restriction", f"unknown restriction {value!r}; known: {known}") from None


@router.put("/stores/home/restrictions/{kind}")
def put_restriction(
    kind: str, body: RestrictionIn, request: Request, login: Annotated[AuthSessionRecord, Depends(require_owner)]
) -> dict[str, Any]:
    restriction = _kind(kind)
    with Session(request.app.state.engine) as session:
        try:
            record = store.record_restriction(
                session, _home(request), restriction, numeric_value=body.numeric_value,
                text_value=body.text_value, recorded_by=login.email, note=body.note,
            )
        except store.UnknownStore as error:
            raise _refusal(status.HTTP_404_NOT_FOUND, "unknown_store", str(error)) from None
        except store.RestrictionValueError as error:
            raise _refusal(422, "invalid_restriction", str(error)) from None
        session.commit()
        return {
            "restriction": record.restriction.value, "numeric_value": record.numeric_value,
            "text_value": record.text_value, "recorded_by": record.recorded_by,
            "recorded_at": record.recorded_at.isoformat(), "note": record.note,
        }


@router.delete("/stores/home/restrictions/{kind}", status_code=status.HTTP_204_NO_CONTENT)
def delete_restriction(kind: str, request: Request) -> Response:
    restriction = _kind(kind)
    with Session(request.app.state.engine) as session:
        try:
            removed = store.delete_restriction(session, _home(request), restriction)
        except store.UnknownStore as error:
            raise _refusal(status.HTTP_404_NOT_FOUND, "unknown_store", str(error)) from None
        if not removed:
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Not Found")
        session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
