"""The owner's guideline notes, mirrored into the corpus as `guideline` passages (source `owner`)."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.chunk_store import delete_page_chunks
from app.db.models import GuidelineNote
from app.guidelines.ingest import CATEGORY
from app.pricing.corpus import index_page
from app.pricing.errors import NotFound, Refused

OWNER_SOURCE = "owner"


def note_url(note_id: UUID) -> str:
    return f"owner-note:{note_id}"


def _clean(title: str, body: str, citation: str, value: float | None, unit: str | None) -> tuple[str, str, str, str | None]:
    title, body, citation = title.strip(), body.strip(), citation.strip()
    if not title or not body:
        raise Refused("a note needs a title and a text")
    if not citation:
        raise Refused("a note needs a source citation (for example a book and page)")
    if value is not None and not (unit and unit.strip()):
        raise Refused("a number needs its unit")
    return title, body, citation, (unit.strip() if unit and unit.strip() else None)


def _index(session: Session, note: GuidelineNote) -> None:
    number = f"\nWert: {note.value:g} {note.unit}" if note.value is not None else ""
    text = f"{note.title}\n{note.body}{number}\nQuelle: {note.citation}"
    index_page(
        session, note_url(note.id), note.title, text,
        source_site=OWNER_SOURCE, category=CATEGORY, section=f"Quelle: {note.citation}",
    )


def create_note(
    session: Session, *, title: str, body: str, citation: str, value: float | None = None, unit: str | None = None
) -> GuidelineNote:
    title, body, citation, unit = _clean(title, body, citation, value, unit)
    note = GuidelineNote(title=title, body=body, citation=citation, value=value, unit=unit)
    session.add(note)
    session.flush()
    _index(session, note)
    return note


def get_note(session: Session, note_id: UUID) -> GuidelineNote:
    note = session.get(GuidelineNote, note_id)
    if note is None:
        raise NotFound(f"no guideline note {note_id}")
    return note


def update_note(
    session: Session, note_id: UUID, *, title: str, body: str, citation: str,
    value: float | None = None, unit: str | None = None,
) -> GuidelineNote:
    note = get_note(session, note_id)
    note.title, note.body, note.citation, note.unit = _clean(title, body, citation, value, unit)
    note.value = value
    note.updated_at = datetime.now(UTC)
    session.flush()
    _index(session, note)
    return note


def delete_note(session: Session, note_id: UUID) -> None:
    note = get_note(session, note_id)
    delete_page_chunks(session, note_url(note.id))
    session.delete(note)
    session.flush()


def list_notes(session: Session) -> list[GuidelineNote]:
    return list(session.scalars(select(GuidelineNote).order_by(GuidelineNote.created_at, GuidelineNote.id)))


def describe_note(note: GuidelineNote) -> dict[str, Any]:
    return {
        "id": str(note.id), "title": note.title, "body": note.body, "value": note.value, "unit": note.unit,
        "citation": note.citation, "created_at": note.created_at.isoformat(), "updated_at": note.updated_at.isoformat(),
    }
