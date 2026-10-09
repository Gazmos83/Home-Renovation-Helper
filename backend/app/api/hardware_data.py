"""Hardware data sheets (design-guidelines). Owner-gated; each change reaches the corpus."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.gate import require_owner
from app.guidelines import datasheets
from app.pricing.errors import NotFound, Refused

router = APIRouter(prefix="/hardware-data", tags=["guidelines"], dependencies=[Depends(require_owner)])


class SheetIn(BaseModel):
    kind: str = Field(max_length=16)
    maker: str = Field(max_length=120)
    model: str = Field(max_length=120)
    values: dict[str, Any] = Field(default_factory=dict)
    source_kind: str = Field(max_length=8)
    page_url: str | None = Field(default=None, max_length=2000)
    datasheet_url: str | None = Field(default=None, max_length=2000)
    citation: str = Field(default="", max_length=500)


class SheetCreate(SheetIn):
    key: str = Field(max_length=128)


def _refusal(error: Refused) -> HTTPException:
    detail: dict[str, Any] = {"failure_class": "refused", "reason": str(error)}
    if getattr(error, "field", None):
        detail["field"] = error.field
    return HTTPException(422, detail=detail)


@router.get("")
def list_hardware_data(request: Request) -> list[dict[str, Any]]:
    with Session(request.app.state.engine) as session:
        return [datasheets.describe_sheet(s) for s in datasheets.list_sheets(session)]


@router.post("", status_code=status.HTTP_201_CREATED)
def create_hardware_data(body: SheetCreate, request: Request) -> dict[str, Any]:
    with Session(request.app.state.engine) as session:
        try:
            sheet = datasheets.create_sheet(session, request.app.state.settings.retail_sources, **body.model_dump())
        except Refused as error:
            raise _refusal(error) from None
        session.commit()
        return datasheets.describe_sheet(sheet)


@router.put("/{sheet_id}")
def update_hardware_data(sheet_id: UUID, body: SheetIn, request: Request) -> dict[str, Any]:
    with Session(request.app.state.engine) as session:
        try:
            sheet = datasheets.update_sheet(
                session, request.app.state.settings.retail_sources, sheet_id, **body.model_dump()
            )
        except NotFound:
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Not Found") from None
        except Refused as error:
            raise _refusal(error) from None
        session.commit()
        return datasheets.describe_sheet(sheet)


@router.delete("/{sheet_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_hardware_data(sheet_id: UUID, request: Request) -> Response:
    with Session(request.app.state.engine) as session:
        try:
            datasheets.delete_sheet(session, sheet_id)
        except NotFound:
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Not Found") from None
        session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
