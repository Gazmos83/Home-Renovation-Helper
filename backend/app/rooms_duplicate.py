"""Duplicating a measured room under a new name (duplicate-room), with at most one layout version.

The copy takes the room's measurements and notes, outside any apartment. A chosen version of
the room's composition becomes version 1 of the copy's composition, checked again against the
copy as any new composition is, and its headless build starts. Nothing else is copied, and the
source is never changed. Every refusal is checked before anything is committed.
"""

from __future__ import annotations

import dataclasses
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import compositions
from app.agent import house_file
from app.agent.house_file import HouseFileError
from app.blender import storage
from app.blender.lighting import Lighting
from app.db.models import Composition


class RoomDuplicateRefused(ValueError):
    """A duplicate that cannot be made; `code` names the kind, the message says why."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class Plan:
    """A checked duplicate. The new room is flushed in the planning session, not committed."""

    source: str
    name: str
    version: int | None
    proposal: compositions.Proposal | None


def change_line(source: str, version: int) -> str:
    return f"duplicated from {source} v{version}"


def plan(
    session: Session,
    root: Path,
    source: str,
    name: str,
    version: int | None,
    *,
    max_items: int,
    rules,
    lighting: Lighting,
) -> Plan:
    """Check a duplicate and add the new room to `session` (flushed only); raises
    `RoomDuplicateRefused` after rolling the session back."""
    room = house_file.room_by_name(session, source)
    if room is None:
        raise RoomDuplicateRefused("not_found", f"there is no room {source!r}")
    document = None
    if version is not None:
        composition = house_file.composition_by_scope(session, "room", room.name)
        rows = house_file.composition_version_rows(session, composition) if composition is not None else []
        if version not in [row.version for row in rows]:
            raise RoomDuplicateRefused("not_found", f"{room.name} has no layout version {version}")
        document = compositions.read_document(storage.composition_version_dir(root, composition.slug, version))
        if document is None:
            raise RoomDuplicateRefused("not_found", f"{room.name} layout version {version} has no document")
    name = (name or "").strip()
    if not name:
        raise RoomDuplicateRefused("invalid_name", "the copy needs a name")
    wanted = name.casefold()
    if any(other.name.casefold() == wanted for other in house_file.rooms(session)):
        raise RoomDuplicateRefused("name_taken", f"a room is already named {name!r}; choose another name")
    try:
        slug = storage.composition_slug("room", name)
    except storage.InvalidPackageId as error:
        raise RoomDuplicateRefused("invalid_name", str(error)) from None
    # `upsert_room` and `record_composition` would reuse or refuse a slug another room's layout holds.
    in_use = session.scalar(select(Composition.id).where(Composition.slug == slug)) is not None
    if in_use or storage.composition_dir(root, slug).exists():
        raise RoomDuplicateRefused(
            "folder_in_use", f"the name {name!r} gives the layout folder {slug!r}, which is in use; choose another name"
        )
    try:
        house_file.upsert_room(
            session, name, room.corners_mm, room.height_mm, room.openings, room.wall_thickness_mm, room.notes
        )
        proposal = None
        if document is not None:
            proposal = compositions.propose(
                session, render_root=root, room=name, apartment=None, items=list(document.get("items") or []),
                max_items=max_items, rules=rules, floor=document.get("floor"), lighting=lighting,
            )
            proposal = dataclasses.replace(proposal, changes=[change_line(room.name, version)], latest=None)
    except compositions.CompositionRefused as refused:
        session.rollback()
        raise RoomDuplicateRefused("layout_refused", f"layout version {version} cannot be copied: {refused.reason}") from None
    except HouseFileError as error:
        session.rollback()
        raise RoomDuplicateRefused("invalid_room", str(error)) from None
    return Plan(source=room.name, name=name, version=version, proposal=proposal)


def create(session: Session, root: Path, checked: Plan, start: Callable[[str, int], None]) -> dict[str, Any]:
    """Commit the planned room, and write and record its layout version 1 with its build handed
    to `start(slug, version)`."""
    if checked.proposal is None:
        session.commit()
        return {"room": checked.name, "composition": None}
    version = compositions.create_version(session, root, checked.proposal, start)
    composition = house_file.composition_by_scope(session, "room", checked.name)
    return {"room": checked.name, "composition": {"slug": composition.slug, "version": version}}
