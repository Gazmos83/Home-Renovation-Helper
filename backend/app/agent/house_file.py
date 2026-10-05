"""The house file: the owner's long-term memory (CLAUDE.md §9a).

Rooms, preferences, pieces and their versions, generator-extension requests and
the thread index. Every writer here is called only by a confirmed action (a
`record_brief`, `create_piece` or `revise_package` that the owner answered
`yes`), never by a model directly. Functions flush but never commit: the caller
owns the transaction.

A package created directly through the package routes has no `pieces` row; it
is still listed, read through from its folders, without a brief.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.blender import storage
from app.blender.room_contract import normalise_room_shell
from app.blender.spec_contract import SpecValidationError
from app.db.models import (
    GeneratorExtensionRequest,
    Piece,
    PieceVersion,
    Preference,
    Room,
    Thread,
)


class HouseFileError(ValueError):
    """A house-file write refused, with a reason naming the problem."""


def _now() -> datetime:
    return datetime.now(UTC)


def _whole(number: float) -> int | float:
    return int(number) if float(number).is_integer() else number


# --- rooms ---------------------------------------------------------------


def validate_room(
    name: str,
    corners_mm: Any,
    height_mm: Any,
    openings: Any = None,
    wall_thickness_mm: Any = None,
) -> dict[str, Any]:
    """The normalised room, or `HouseFileError` naming what is wrong.

    Held to the same rules as a room-scene document: convex outline, openings on
    their wall and below the ceiling, no sill on a door.
    """
    name = (name or "").strip()
    if not name:
        raise HouseFileError("a room needs a name")
    room: dict[str, Any] = {"corners": corners_mm, "height_mm": height_mm}
    if wall_thickness_mm is not None:
        room["wall_thickness_mm"] = wall_thickness_mm
    try:
        shell, normalised = normalise_room_shell(room, openings)
    except SpecValidationError as error:
        raise HouseFileError(str(error)) from None
    return {
        "name": name,
        "corners_mm": [[_whole(x), _whole(y)] for x, y in shell["corners"]],
        "height_mm": _whole(shell["height_mm"]),
        "wall_thickness_mm": _whole(shell["wall_thickness_mm"]),
        "openings": [
            {key: _whole(value) if isinstance(value, float) else value for key, value in o.items()}
            for o in normalised
        ],
    }


def upsert_room(
    session: Session,
    name: str,
    corners_mm: Any,
    height_mm: Any,
    openings: Any = None,
    wall_thickness_mm: Any = None,
    notes: str = "",
) -> Room:
    """Store a room by its unique name, replacing the measurements of one that exists."""
    valid = validate_room(name, corners_mm, height_mm, openings, wall_thickness_mm)
    room = session.scalar(select(Room).where(Room.name == valid["name"]))
    if room is None:
        room = Room(name=valid["name"])
        session.add(room)
    room.corners_mm = valid["corners_mm"]
    room.height_mm = valid["height_mm"]
    room.wall_thickness_mm = valid["wall_thickness_mm"]
    room.openings = valid["openings"]
    room.notes = notes
    room.updated_at = _now()
    session.flush()
    return room


def room_by_name(session: Session, name: str) -> Room | None:
    return session.scalar(select(Room).where(Room.name == (name or "").strip()))


def rooms(session: Session) -> list[Room]:
    return list(session.scalars(select(Room).order_by(Room.name)))


def describe_room(room: Room) -> dict[str, Any]:
    return {
        "name": room.name,
        "corners_mm": room.corners_mm,
        "height_mm": room.height_mm,
        "wall_thickness_mm": room.wall_thickness_mm,
        "openings": room.openings,
        "notes": room.notes,
    }


# --- preferences -----------------------------------------------------------


def set_preference(session: Session, key: str, value: str) -> None:
    key = (key or "").strip()
    if not key or len(key) > 64:
        raise HouseFileError("a preference key is 1 to 64 characters")
    row = session.get(Preference, key)
    if row is None:
        session.add(Preference(key=key, value=str(value), updated_at=_now()))
    else:
        row.value = str(value)
        row.updated_at = _now()
    session.flush()


def preferences(session: Session) -> dict[str, str]:
    return {row.key: row.value for row in session.scalars(select(Preference).order_by(Preference.key))}


# --- pieces and versions -----------------------------------------------------


def record_piece(
    session: Session,
    package_id: str,
    name: str,
    brief: dict[str, Any] | None = None,
    room_id: UUID | None = None,
) -> Piece:
    package_id = storage.validate_package_id(package_id)
    if session.get(Piece, package_id) is not None:
        raise HouseFileError(f"piece {package_id!r} is already recorded")
    piece = Piece(package_id=package_id, name=name, brief=brief or {}, room_id=room_id)
    session.add(piece)
    session.flush()
    return piece


def record_version(
    session: Session,
    package_id: str,
    version: int,
    revised_from: int | None = None,
    changes: list[str] | None = None,
) -> PieceVersion:
    if session.get(Piece, package_id) is None:
        raise HouseFileError(f"piece {package_id!r} is not recorded")
    row = PieceVersion(
        package_id=package_id, version=version, revised_from=revised_from, changes=changes or []
    )
    session.add(row)
    session.flush()
    return row


def pieces(session: Session, root: Path) -> list[dict[str, Any]]:
    """Every piece: the recorded ones, then packages found only as folders."""
    recorded = {piece.package_id: piece for piece in session.scalars(select(Piece))}
    records: dict[str, list[PieceVersion]] = {}
    for row in session.scalars(select(PieceVersion).order_by(PieceVersion.version)):
        records.setdefault(row.package_id, []).append(row)
    folders = dict(storage.list_packages(root))

    listing = []
    for package_id in sorted(set(recorded) | set(folders)):
        piece = recorded.get(package_id)
        numbers = sorted(set(folders.get(package_id, [])) | {r.version for r in records.get(package_id, [])})
        latest = numbers[-1] if numbers else None
        state = None
        if latest is not None:
            try:
                state = (storage.read_status(storage.version_dir(root, package_id, latest)) or {}).get(
                    "status"
                )
            except (storage.InvalidPackageId, ValueError):
                state = None
        listing.append(
            {
                "package_id": package_id,
                "name": piece.name if piece else package_id,
                "has_brief": bool(piece and piece.brief),
                "brief": piece.brief if piece else None,
                "room_id": piece.room_id if piece else None,
                "latest_version": latest,
                "status": state,
                "versions": [
                    {"version": r.version, "revised_from": r.revised_from, "changes": r.changes}
                    for r in records.get(package_id, [])
                ],
            }
        )
    return listing


# --- generator-extension requests ----------------------------------------------


def record_extension_request(
    session: Session, field: str, request: str, package_id: str | None = None
) -> GeneratorExtensionRequest:
    row = GeneratorExtensionRequest(field=field[:200], request=request, package_id=package_id)
    session.add(row)
    session.flush()
    return row


def open_extension_requests(session: Session) -> list[GeneratorExtensionRequest]:
    return list(
        session.scalars(
            select(GeneratorExtensionRequest)
            .where(GeneratorExtensionRequest.status == "open")
            .order_by(GeneratorExtensionRequest.created_at)
        )
    )


# --- threads ---------------------------------------------------------------------


def create_thread(session: Session, title: str = "", package_id: str | None = None) -> Thread:
    if package_id is not None:
        package_id = storage.validate_package_id(package_id)
    now = _now()
    thread = Thread(title=title.strip()[:200], package_id=package_id, created_at=now, last_turn_at=now)
    session.add(thread)
    session.flush()
    return thread


def get_thread(session: Session, thread_id: UUID) -> Thread | None:
    return session.get(Thread, thread_id)


def list_threads(session: Session) -> list[Thread]:
    return list(session.scalars(select(Thread).order_by(Thread.last_turn_at.desc())))


def touch_thread(session: Session, thread_id: UUID, package_id: str | None = None) -> None:
    thread = session.get(Thread, thread_id)
    if thread is None:
        return
    thread.last_turn_at = _now()
    if package_id:
        thread.package_id = package_id
    session.flush()
