"""The owner's guideline notes (design-guidelines). Owner-gated; each change reaches the corpus."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.gate import require_owner
from app.guidelines import notes
from app.pricing.errors import NotFound, Refused

router = APIRouter(prefix="/guideline-notes", tags=["guidelines"], dependencies=[Depends(require_owner)])


class NoteIn(BaseModel):
    title: str = Field(max_length=200)
    body: str = Field(max_length=5000)
    citation: str = Field(max_length=500)
    value: float | None = None
    unit: str | None = Field(default=None, max_length=24)


def _refusal(code: int, failure_class: str, reason: str) -> HTTPException:
    return HTTPException(code, detail={"failure_class": failure_class, "reason": reason})


@router.get("")
def list_guideline_notes(request: Request) -> list[dict[str, Any]]:
    with Session(request.app.state.engine) as session:
        return [notes.describe_note(n) for n in notes.list_notes(session)]


@router.post("", status_code=status.HTTP_201_CREATED)
def create_guideline_note(body: NoteIn, request: Request) -> dict[str, Any]:
    with Session(request.app.state.engine) as session:
        try:
            note = notes.create_note(session, **body.model_dump())
        except Refused as error:
            raise _refusal(422, "refused", str(error)) from None
        session.commit()
        return notes.describe_note(note)


@router.put("/{note_id}")
def update_guideline_note(note_id: UUID, body: NoteIn, request: Request) -> dict[str, Any]:
    with Session(request.app.state.engine) as session:
        try:
            note = notes.update_note(session, note_id, **body.model_dump())
        except NotFound:
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Not Found") from None
        except Refused as error:
            raise _refusal(422, "refused", str(error)) from None
        session.commit()
        return notes.describe_note(note)


@router.delete("/{note_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_guideline_note(note_id: UUID, request: Request) -> Response:
    with Session(request.app.state.engine) as session:
        try:
            notes.delete_note(session, note_id)
        except NotFound:
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Not Found") from None
        session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
