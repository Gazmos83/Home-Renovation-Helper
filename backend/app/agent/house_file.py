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

import json
import re
import shutil
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import UUID

from sqlalchemy import delete, func, or_, select, update
from sqlalchemy.orm import Session

from app.blender import storage
from app.blender.room_contract import normalise_room_shell
from app.blender.shell_contract import ShellContext, normalise_shell
from app.blender.spec_contract import SpecValidationError
from app.db import scope as account_scope
from app.db.models import (
    Apartment,
    Composition,
    CompositionVersion,
    CutListPricing,
    CutListPricingEntry,
    GeneratorExtensionRequest,
    Piece,
    PieceVersion,
    Preference,
    RenderFeedback,
    RenderRun,
    Review,
    ReviewItem,
    Room,
    Thread,
    ThreadNotice,
    ThreadPiece,
    ThreadRoomRender,
    VersionVerdict,
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

    Held to the same rules as a room-scene document: a simple outline (convex or not), openings on
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
    apartment_id: UUID | None = None,
) -> Room:
    """Store a room by its unique name, replacing the measurements of one that exists.

    Without `apartment_id` a stored room keeps the apartment it belongs to.
    """
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
    if apartment_id is not None:
        room.apartment_id = apartment_id
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


# --- apartments ------------------------------------------------------------------------


def apartment_by_name(session: Session, name: str) -> Apartment | None:
    return session.scalar(select(Apartment).where(Apartment.name == (name or "").strip()))


def find_apartment(session: Session, name_or_slug: str) -> Apartment | None:
    """An apartment by its name, or by the slug its shell folders use."""
    text = (name_or_slug or "").strip()
    found = apartment_by_name(session, text)
    if found is not None:
        return found
    for apartment in apartments(session):
        try:
            if storage.apartment_slug(apartment.name) == text:
                return apartment
        except storage.InvalidPackageId:
            continue
    return None


def apartments(session: Session) -> list[Apartment]:
    return list(session.scalars(select(Apartment).order_by(Apartment.name)))


def rooms_of(session: Session, apartment: Apartment) -> list[Room]:
    return list(session.scalars(select(Room).where(Room.apartment_id == apartment.id).order_by(Room.name)))


def validate_apartment(
    name: str,
    ceiling_height_mm: Any,
    wall_thickness_mm: Any,
    rooms: list[dict[str, Any]],
    printed_areas_m2: dict[str, float] | None = None,
) -> ShellContext:
    """The normalised apartment (walls and plausibility warnings), or `HouseFileError`.

    Each room is held to the room rules, and rooms of one apartment must not
    overlap in area. `rooms` items carry `name`, `corners_mm`, and optionally
    `height_mm` and `openings`.
    """
    document = {
        "kind": "apartment_shell",
        "schema_version": 1,
        "units": "mm",
        "apartment": {
            "name": name,
            "ceiling_height_mm": ceiling_height_mm,
            "wall_thickness_mm": wall_thickness_mm if wall_thickness_mm is not None else 100,
        },
        "rooms": [
            {
                "name": room.get("name"),
                "corners": room.get("corners_mm"),
                **({"height_mm": room["height_mm"]} if room.get("height_mm") is not None else {}),
                "openings": room.get("openings") or [],
            }
            for room in rooms
        ],
    }
    try:
        return normalise_shell(document, printed_areas_m2=printed_areas_m2)
    except SpecValidationError as error:
        raise HouseFileError(str(error)) from None


def _width_depth(corners_mm: Any) -> list[int | float]:
    xs = [point[0] for point in corners_mm]
    ys = [point[1] for point in corners_mm]
    return [_whole(max(xs) - min(xs)), _whole(max(ys) - min(ys))]


def apartment_replacement(
    session: Session, render_root: Path, name: str, rooms: list[dict[str, Any]]
) -> dict[str, Any] | None:
    """What a plan read replacing the stored apartment `name` changes, or `None` when none is stored.

    Lists each room in both with its stored and read width and depth, the rooms the read
    adds, and the stored rooms it does not name with the pieces in them and their room
    composition. Refused with `HouseFileError` while a composition of a removed room or of
    the apartment is building or rendering.
    """
    apartment = apartment_by_name(session, name)
    if apartment is None:
        return None
    read = {(room.get("name") or "").strip(): room for room in rooms}
    stored = rooms_of(session, apartment)
    removed_rooms = [room for room in stored if room.name not in read]
    watched = [composition_by_scope(session, "apartment", apartment.name)]
    watched += [composition_by_scope(session, "room", room.name) for room in removed_rooms]
    for composition in watched:
        if composition is not None and _composition_busy(render_root, composition):
            raise HouseFileError(
                f"the composition of {composition.name} is building or rendering; "
                "read the plan again once that has finished"
            )
    stored_names = {room.name for room in stored}
    removed = []
    for room in removed_rooms:
        composition = composition_by_scope(session, "room", room.name)
        removed.append(
            {
                "name": room.name,
                "pieces": list(
                    session.scalars(
                        select(Piece.package_id).where(Piece.room_id == room.id).order_by(Piece.package_id)
                    )
                ),
                "composition": (
                    {"name": composition.name, "versions": len(composition_version_rows(session, composition))}
                    if composition is not None
                    else None
                ),
            }
        )
    return {
        "apartment": apartment.name,
        "rooms": [
            {"name": room.name, "stored": _width_depth(room.corners_mm), "read": _width_depth(read[room.name]["corners_mm"])}
            for room in stored
            if room.name in read
        ],
        "new": [room_name for room_name in read if room_name not in stored_names],
        "removed": removed,
    }


def upsert_apartment(
    session: Session,
    name: str,
    ceiling_height_mm: Any,
    wall_thickness_mm: Any,
    rooms: list[dict[str, Any]],
    notes: str = "",
    *,
    replace: bool = False,
    render_root: Path | None = None,
) -> Apartment:
    """Store an apartment and its rooms in one plan frame; rooms of the same name are replaced.

    Rooms already in the apartment that are not named here stay and are checked
    for overlap with the new ones. Flushes; the caller commits.

    With `replace` (and `render_root`) the read replaces the stored apartment: overlap is
    checked among the read's rooms only, and each stored room it does not name is deleted
    as `delete_room` deletes it. Refused as `apartment_replacement` refuses. Like
    `delete_room`, this mode commits.
    """
    name = (name or "").strip()
    apartment = apartment_by_name(session, name)
    kept = []
    replacement = None
    if replace:
        if render_root is None:
            raise ValueError("replacing an apartment needs the render root")
        replacement = apartment_replacement(session, render_root, name, rooms)
    elif apartment is not None:
        named = {(room.get("name") or "").strip() for room in rooms}
        kept = [
            {
                "name": room.name,
                "corners_mm": room.corners_mm,
                "height_mm": room.height_mm,
                "openings": room.openings,
            }
            for room in rooms_of(session, apartment)
            if room.name not in named
        ]
    context = validate_apartment(name, ceiling_height_mm, wall_thickness_mm, [*kept, *rooms])
    if apartment is None:
        _refuse_folder_in_use(session, Apartment, storage.apartment_slug(name), name)
        apartment = Apartment(name=name)
        session.add(apartment)
    apartment.ceiling_height_mm = _whole(context.ceiling_height_mm)
    apartment.wall_thickness_mm = _whole(context.wall_thickness_mm)
    apartment.notes = notes
    apartment.updated_at = _now()
    session.flush()
    new_names = {(room.get("name") or "").strip() for room in rooms}
    for shell_room in context.rooms:
        if shell_room.name not in new_names:
            continue
        upsert_room(
            session,
            shell_room.name,
            [list(c) for c in shell_room.corners],
            shell_room.height_mm,
            list(shell_room.openings),
            context.wall_thickness_mm,
            apartment_id=apartment.id,
        )
    if replace:
        removed = [room_by_name(session, room["name"]) for room in (replacement or {}).get("removed", [])]
        _settle_removal(session, _remove_rooms(session, render_root, removed))
    return apartment


def apartment_shell_document(session: Session, apartment: Apartment) -> dict[str, Any]:
    """The normalised shell document for a stored apartment, or `HouseFileError`."""
    rooms = rooms_of(session, apartment)
    if not rooms:
        raise HouseFileError("this apartment has no rooms to build")
    context = validate_apartment(
        apartment.name,
        apartment.ceiling_height_mm,
        apartment.wall_thickness_mm,
        [
            {"name": r.name, "corners_mm": r.corners_mm, "height_mm": r.height_mm, "openings": r.openings}
            for r in rooms
        ],
    )
    return context.input_document()


def describe_apartment(session: Session, apartment: Apartment) -> dict[str, Any]:
    return {
        "name": apartment.name,
        "ceiling_height_mm": apartment.ceiling_height_mm,
        "wall_thickness_mm": apartment.wall_thickness_mm,
        "rooms": [describe_room(room) for room in rooms_of(session, apartment)],
        "notes": apartment.notes,
    }


# --- preferences -----------------------------------------------------------


def set_preference(session: Session, key: str, value: str) -> None:
    key = (key or "").strip()
    if not key or len(key) > 64:
        raise HouseFileError("a preference key is 1 to 64 characters")
    row = session.scalars(select(Preference).where(Preference.key == key)).one_or_none()
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
    *,
    slot: str | None = None,
    model: str | None = None,
) -> PieceVersion:
    """Record a version; `slot` and `model` name the agent whose tool made it (version-verdict)."""
    if session.get(Piece, package_id) is None:
        raise HouseFileError(f"piece {package_id!r} is not recorded")
    row = PieceVersion(
        package_id=package_id, version=version, revised_from=revised_from, changes=changes or [],
        slot=slot, model=model,
    )
    session.add(row)
    session.flush()
    return row


def version_row(session: Session, package_id: str, version: int) -> PieceVersion | None:
    return session.get(PieceVersion, (package_id, version))


def approved_version_of(session: Session, package_id: str) -> int | None:
    """The piece's approved version number, or `None` when none is approved."""
    return session.scalar(
        select(PieceVersion.version).where(
            PieceVersion.package_id == package_id, PieceVersion.approved_at.is_not(None)
        )
    )


def approve_version(session: Session, package_id: str, version: int) -> PieceVersion:
    """Approve one version, clearing any other approval of the piece, in the caller's transaction.

    Approving an approved version changes nothing. A version with no record is refused.
    """
    row = version_row(session, package_id, version)
    if row is None:
        raise HouseFileError(f"version {version} of {package_id!r} is not recorded in the house file")
    if row.approved_at is not None:
        return row
    session.execute(
        update(PieceVersion)
        .where(PieceVersion.package_id == package_id, PieceVersion.approved_at.is_not(None))
        .values(approved_at=None)
    )
    row.approved_at = _now()
    session.flush()
    return row


def raised_height_limit(brief: dict[str, Any], height: float, version: int) -> dict[str, Any]:
    """The brief with `max_piece_height_mm` raised to an approved version's height when that is taller,
    naming the version; else the brief as it was (brief-height-follows-approved-version)."""
    limit = brief.get("max_piece_height_mm")
    millimetres = round(height)
    if not isinstance(limit, int | float) or isinstance(limit, bool) or millimetres <= limit:
        return brief
    return {**brief, "max_piece_height_mm": millimetres, "max_piece_height_from_version": version}


def raise_brief_height_limit(session: Session, package_id: str, version: int, height: float) -> bool:
    """Store `raised_height_limit` on the piece; whether the brief changed. The caller commits."""
    piece = session.get(Piece, package_id)
    if piece is None:
        return False
    raised = raised_height_limit(dict(piece.brief or {}), height, version)
    if raised == (piece.brief or {}):
        return False
    piece.brief = raised
    session.flush()
    return True


_HEIGHT_LIMIT = re.compile(r"max_piece_height_mm\D{0,6}(\d+(?:\.\d+)?)")


def dismiss_outdated_height_items(session: Session, package_id: str, version: int, limit: float) -> int:
    """Dismiss the version's open review items that expect a height limit below `limit`; how many.

    Matches the key name and the figure in the item's expected text; no text is rewritten and no
    other item changes (brief-height-follows-approved-version). The caller commits."""
    items = session.scalars(
        select(ReviewItem)
        .join(Review, Review.id == ReviewItem.review_id)
        .where(Review.package_id == package_id, Review.version == version, ReviewItem.status == "open")
    )
    changed = 0
    for item in items:
        found = _HEIGHT_LIMIT.search(item.expected or "")
        if found and float(found.group(1)) < limit:
            item.status = "dismissed"
            item.status_at = _now()
            changed += 1
    session.flush()
    return changed


def unapprove_version(
    session: Session, package_id: str, version: int, *, root: Path | None = None
) -> PieceVersion:
    """Clear a version's approval; unapproving an unapproved version changes nothing.

    Refused when the version is placed in an approved composition version (room-version-approval).
    """
    row = version_row(session, package_id, version)
    if row is None:
        raise HouseFileError(f"version {version} of {package_id!r} is not recorded in the house file")
    if row.approved_at is not None:
        if root is not None:
            placed = _approved_rooms_placing(session, root, package_id, version)
            if placed:
                named = ", ".join(placed)
                raise HouseFileError(
                    f"{package_id} version {version} is placed in the approved room composition "
                    f"{named}; unapprove {placed[0]} first"
                )
        row.approved_at = None
        session.flush()
    return row


def visible_packages(session: Session, folders: list[tuple[str, list[int]]]) -> list[tuple[str, list[int]]]:
    """The package folders this account may see: its own recorded pieces, and for the
    owner also folders no account has recorded (a member never sees those)."""
    seen = set(session.scalars(select(Piece.package_id)))
    if account_scope.current() is None:
        every_account = {account_scope.ALL_ACCOUNTS: True}
        recorded_anywhere = set(session.scalars(select(Piece.package_id).execution_options(**every_account)))
        return [(p, v) for p, v in folders if p in seen or p not in recorded_anywhere]
    return [(p, v) for p, v in folders if p in seen]


def pieces(session: Session, root: Path) -> list[dict[str, Any]]:
    """Every piece of this account: the recorded ones, then packages found only as folders."""
    recorded = {piece.package_id: piece for piece in session.scalars(select(Piece))}
    records: dict[str, list[PieceVersion]] = {}
    for row in session.scalars(select(PieceVersion).order_by(PieceVersion.version)):
        if row.package_id in recorded:
            records.setdefault(row.package_id, []).append(row)
    folders = dict(visible_packages(session, list(storage.list_packages(root))))

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
                "approved_version": next(
                    (r.version for r in records.get(package_id, []) if r.approved_at is not None), None
                ),
                "versions": [
                    {
                        "version": r.version,
                        "revised_from": r.revised_from,
                        "changes": r.changes,
                        "approved_at": r.approved_at.isoformat() if r.approved_at else None,
                    }
                    for r in records.get(package_id, [])
                ],
            }
        )
    return listing


# --- deleting a version (version-cleanup-and-inspection) ------------------------------


class VersionMissing(HouseFileError):
    """The version has neither a folder nor a record."""


def _version_refusal(session: Session, root: Path, package_id: str, version: int) -> str | None:
    """Why the version cannot be deleted now, in plain words, or `None`."""
    from app.compositions import pieces_in_use

    row = version_row(session, package_id, version)
    if row is not None and row.approved_at is not None:
        return f"{package_id} version {version} is approved; unapprove version {version} first"
    placed = pieces_in_use(root, package_id, version)
    if placed:
        return (
            f"{package_id} version {version} is placed in the room composition "
            f"{', '.join(placed)}; it cannot be deleted while it is placed"
        )
    return _busy_refusal(session, root, package_id, version)


def _busy_refusal(session: Session, root: Path, package_id: str, version: int) -> str | None:
    """Why a version still building or rendering cannot be deleted now, or `None`."""
    state = storage.read_status(storage.version_dir(root, package_id, version)) or {}
    if state.get("status") in _BUSY:
        return f"{package_id} version {version} is still building; delete it once the build has finished"
    rendering = any((entry or {}).get("status") in _BUSY for entry in (state.get("renders") or {}).values())
    rendering = rendering or session.scalar(
        select(func.count()).select_from(RenderRun).where(
            RenderRun.package_id == package_id, RenderRun.version == version, RenderRun.outcome.in_(_BUSY)
        )
    )
    if rendering:
        return f"{package_id} version {version} is still rendering; delete it once the render has finished"
    return None


def delete_version(session: Session, root: Path, package_id: str, version: int) -> bool:
    """Delete one piece version with its folder and records; whether the piece went too.

    Refuses with `HouseFileError` (nothing changed) when the version is approved, placed
    in a room composition, or still building or rendering, and with `VersionMissing` when
    it has neither a folder nor a record. Removes the version's reviews and their items,
    render runs and their feedback, its verdict, pricings and their entries, and its record, and clears
    the piece and version from notices naming it. When no version is left, the piece is
    removed and every conversation unbound from it. Like `delete_room` this commits: the
    folder is moved aside first, removed after the commit and moved back if it fails.
    """
    package_id = storage.validate_package_id(package_id)
    folder = storage.version_dir(root, package_id, version)
    recorded = {
        row.version for row in session.scalars(select(PieceVersion).where(PieceVersion.package_id == package_id))
    }
    on_disk = set(storage.versions(root, package_id))
    if version not in recorded and version not in on_disk:
        raise VersionMissing(f"{package_id} has no version {version}")
    reason = _version_refusal(session, root, package_id, version)
    if reason is not None:
        raise HouseFileError(reason)

    last = not ((recorded | on_disk) - {version})
    hidden = storage.move_version_aside(root, package_id, version) if folder.is_dir() else None
    try:
        _remove_version_rows(session, package_id, version)
        if last:
            session.execute(delete(ThreadPiece).where(ThreadPiece.package_id == package_id))
            session.execute(update(Thread).where(Thread.package_id == package_id).values(package_id=None))
            session.execute(delete(Piece).where(Piece.package_id == package_id))
        session.commit()
    except Exception:
        session.rollback()
        if hidden is not None:
            storage.move_version_back(root, package_id, version, hidden)
        raise
    if hidden is not None:
        storage.discard_version(root, package_id, hidden)
    return last


def _remove_version_rows(session: Session, package_id: str, version: int) -> None:
    """Delete the records one version owns and clear notices naming it; no commit."""
    reviews = select(Review.id).where(Review.package_id == package_id, Review.version == version)
    session.execute(delete(ReviewItem).where(ReviewItem.review_id.in_(reviews)))
    session.execute(delete(Review).where(Review.package_id == package_id, Review.version == version))
    runs = select(RenderRun.id).where(RenderRun.package_id == package_id, RenderRun.version == version)
    session.execute(delete(RenderFeedback).where(RenderFeedback.run_id.in_(runs)))
    session.execute(delete(RenderRun).where(RenderRun.package_id == package_id, RenderRun.version == version))
    session.execute(
        delete(VersionVerdict).where(VersionVerdict.package_id == package_id, VersionVerdict.version == version)
    )
    pricings = select(CutListPricing.id).where(
        CutListPricing.package_id == package_id, CutListPricing.version == version
    )
    session.execute(delete(CutListPricingEntry).where(CutListPricingEntry.pricing_id.in_(pricings)))
    session.execute(
        delete(CutListPricing).where(CutListPricing.package_id == package_id, CutListPricing.version == version)
    )
    session.execute(
        update(ThreadNotice)
        .where(ThreadNotice.package_id == package_id, ThreadNotice.version == version)
        .values(package_id=None, version=None)
    )
    session.execute(delete(PieceVersion).where(PieceVersion.package_id == package_id, PieceVersion.version == version))


# --- deleting a whole piece (delete-piece) --------------------------------------------


class PieceMissing(HouseFileError):
    """The piece has neither a folder nor a record."""


def _piece_versions(session: Session, root: Path, package_id: str) -> list[int]:
    recorded = {
        row.version for row in session.scalars(select(PieceVersion).where(PieceVersion.package_id == package_id))
    }
    return sorted(recorded | set(storage.versions(root, package_id)))


def _piece_conversations(session: Session, package_id: str) -> list[UUID]:
    """Every conversation bound to the piece, or holding it as a build while bound to no
    other piece, oldest first, once each."""
    return list(
        dict.fromkeys(
            session.scalars(
                select(Thread.id)
                .outerjoin(ThreadPiece, ThreadPiece.thread_id == Thread.id)
                .where(
                    (Thread.package_id == package_id)
                    | ((ThreadPiece.package_id == package_id) & Thread.package_id.is_(None))
                )
                .order_by(Thread.created_at)
            )
        )
    )


def piece_deletion(session: Session, root: Path, package_id: str) -> dict[str, Any]:
    """What deleting the whole piece removes, and the first reason it cannot be deleted now.

    Approved versions do not refuse (the owner's decision of 2026-10-17); placed, building
    and rendering versions do, as for a version delete. Raises `PieceMissing` when the
    piece has neither a folder nor a record.
    """
    from app.compositions import pieces_in_use

    package_id = storage.validate_package_id(package_id)
    piece = session.get(Piece, package_id)
    numbers = _piece_versions(session, root, package_id)
    if piece is None and not numbers:
        raise PieceMissing(f"there is no piece {package_id}")
    priced = set(session.scalars(select(CutListPricing.version).where(CutListPricing.package_id == package_id)))
    approved = [
        {"version": row.version, "priced": row.version in priced}
        for row in session.scalars(
            select(PieceVersion)
            .where(PieceVersion.package_id == package_id, PieceVersion.approved_at.is_not(None))
            .order_by(PieceVersion.version)
        )
    ]
    refusal = None
    for version in numbers:
        placed = pieces_in_use(root, package_id, version)
        if placed:
            refusal = (
                f"{package_id} version {version} is placed in the room composition "
                f"{', '.join(placed)}; remove it from the composition first"
            )
            break
    if refusal is None:
        for version in numbers:
            reason = _busy_refusal(session, root, package_id, version)
            if reason is not None:
                refusal = reason
                break
    return {
        "package_id": package_id,
        "name": piece.name if piece else package_id,
        "versions": numbers,
        "approved": approved,
        "conversations": [str(thread_id) for thread_id in _piece_conversations(session, package_id)],
        "refusal": refusal,
    }


def delete_piece(session: Session, root: Path, package_id: str, thread_ids: Sequence[UUID]) -> None:
    """Delete a whole piece: every version's records, its piece record, its conversation
    links and the index rows of `thread_ids` (their memory is forgotten by the caller
    first), then its folder after the commit, which frees the id.

    Refuses with `HouseFileError` (nothing changed) as `piece_deletion` does. Engineering
    records and generator-extension requests are kept. Like `delete_version` this commits.
    """
    summary = piece_deletion(session, root, package_id)
    if summary["refusal"] is not None:
        raise HouseFileError(summary["refusal"])
    package_id = summary["package_id"]
    folder = storage.package_dir(root, package_id)
    hidden = storage.move_package_aside(root, package_id) if folder.is_dir() else None
    try:
        for version in summary["versions"]:
            _remove_version_rows(session, package_id, version)
        session.execute(delete(ThreadPiece).where(ThreadPiece.package_id == package_id))
        if thread_ids:
            session.execute(delete(Thread).where(Thread.id.in_(list(thread_ids))))
        session.execute(update(Thread).where(Thread.package_id == package_id).values(package_id=None))
        session.execute(delete(Piece).where(Piece.package_id == package_id))
        session.commit()
    except Exception:
        session.rollback()
        if hidden is not None:
            storage.move_package_back(root, package_id, hidden)
        raise
    if hidden is not None:
        storage.discard_package(hidden)


# --- room compositions (room-composition) ---------------------------------------------


def composition_by_scope(session: Session, scope: str, name: str) -> Composition | None:
    return session.scalar(select(Composition).where(Composition.scope == scope, Composition.name == name))


def composition_by_slug(session: Session, slug: str) -> Composition | None:
    return session.scalar(select(Composition).where(Composition.slug == slug))


def composition_version_row(
    session: Session, composition_id: UUID, version: int
) -> CompositionVersion | None:
    return session.get(CompositionVersion, (composition_id, version))


def approved_composition_version_of(session: Session, composition_id: UUID) -> int | None:
    """The composition's approved version number, or `None` when none is approved."""
    return session.scalar(
        select(CompositionVersion.version).where(
            CompositionVersion.composition_id == composition_id,
            CompositionVersion.approved_at.is_not(None),
        )
    )


def _composition_document(root: Path, slug: str, version: int) -> dict[str, Any]:
    folder = storage.composition_version_dir(root, slug, version)
    try:
        return json.loads((folder / storage.INPUT_FILE).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _unapproved_placed_pieces(session: Session, root: Path, slug: str, version: int) -> list[str]:
    """Piece versions in that composition version that are not currently approved."""
    found = []
    for item in _composition_document(root, slug, version).get("items", []):
        if item.get("type") != "piece":
            continue
        package_id, number = str(item.get("package_id")), item.get("version")
        if approved_version_of(session, package_id) != number:
            found.append(f"{package_id} v{number}")
    return found


def _approved_rooms_placing(session: Session, root: Path, package_id: str, version: int) -> list[str]:
    """Approved composition versions that place this piece version, as '<name> version <n>'."""
    found = []
    for composition in session.scalars(select(Composition).order_by(Composition.name)):
        approved = approved_composition_version_of(session, composition.id)
        if approved is None:
            continue
        items = _composition_document(root, composition.slug, approved).get("items", [])
        if any(
            i.get("type") == "piece" and i.get("package_id") == package_id and i.get("version") == version
            for i in items
        ):
            found.append(f"{composition.name} version {approved}")
    return found


def approve_composition_version(
    session: Session, root: Path, slug: str, version: int
) -> CompositionVersion:
    """Approve one composition version, clearing any other approval of it.

    Refused when the version is not recorded, or when a placed piece is not currently approved.
    Approving an approved version changes nothing.
    """
    composition = composition_by_slug(session, slug)
    if composition is None:
        raise HouseFileError(f"composition {slug!r} is not recorded in the house file")
    row = composition_version_row(session, composition.id, version)
    if row is None:
        raise HouseFileError(
            f"version {version} of {composition.name!r} is not recorded in the house file"
        )
    if row.approved_at is not None:
        return row
    stale = _unapproved_placed_pieces(session, root, slug, version)
    if stale:
        named = ", ".join(stale)
        verb = "is" if len(stale) == 1 else "are"
        raise HouseFileError(
            f"{composition.name} version {version} places {named}, which {verb} not approved; "
            "approve those piece versions first"
        )
    session.execute(
        update(CompositionVersion)
        .where(
            CompositionVersion.composition_id == composition.id,
            CompositionVersion.approved_at.is_not(None),
        )
        .values(approved_at=None)
    )
    row.approved_at = _now()
    session.flush()
    return row


def unapprove_composition_version(session: Session, slug: str, version: int) -> CompositionVersion:
    """Clear a composition version's approval; unapproving an unapproved version changes nothing."""
    composition = composition_by_slug(session, slug)
    if composition is None:
        raise HouseFileError(f"composition {slug!r} is not recorded in the house file")
    row = composition_version_row(session, composition.id, version)
    if row is None:
        raise HouseFileError(
            f"version {version} of {composition.name!r} is not recorded in the house file"
        )
    if row.approved_at is not None:
        row.approved_at = None
        session.flush()
    return row


def _composition_version_refusal(
    session: Session, root: Path, composition: Composition, version: int
) -> str | None:
    """Why the composition version cannot be deleted now, in plain words, or `None`."""
    row = composition_version_row(session, composition.id, version)
    if row is not None and row.approved_at is not None:
        return (
            f"{composition.name} version {version} is approved; unapprove version {version} first"
        )
    folder = storage.composition_version_dir(root, composition.slug, version)
    state = storage.read_status(folder) or {}
    if state.get("status") in _BUSY:
        return (
            f"{composition.name} version {version} is still building; "
            "delete it once the build has finished"
        )
    rendering = any(
        (entry or {}).get("status") in _BUSY for entry in (state.get("renders") or {}).values()
    )
    if rendering:
        return (
            f"{composition.name} version {version} is still rendering; "
            "delete it once the render has finished"
        )
    return None


def delete_composition_version(session: Session, root: Path, slug: str, version: int) -> bool:
    """Delete one composition version with its folder; whether the composition went too.

    Refuses with `HouseFileError` when the version is approved or still building or
    rendering, and with `VersionMissing` when it has neither a folder nor a record.
    The last version also removes the composition; the measured room stays. Commits
    like `delete_version`: the folder is moved aside first.
    """
    try:
        folder = storage.composition_version_dir(root, slug, version)
    except (storage.InvalidPackageId, ValueError) as error:
        raise VersionMissing(f"{slug} has no version {version}") from error
    composition = composition_by_slug(session, slug)
    recorded = {
        row.version
        for row in (
            composition_version_rows(session, composition) if composition is not None else []
        )
    }
    on_disk = set(storage.composition_versions(root, slug))
    if version not in recorded and version not in on_disk:
        raise VersionMissing(f"{slug} has no version {version}")
    if composition is not None:
        reason = _composition_version_refusal(session, root, composition, version)
        if reason is not None:
            raise HouseFileError(reason)

    last = not ((recorded | on_disk) - {version})
    hidden = storage.move_composition_version_aside(root, slug, version) if folder.is_dir() else None
    try:
        if composition is not None:
            session.execute(
                delete(CompositionVersion).where(
                    CompositionVersion.composition_id == composition.id,
                    CompositionVersion.version == version,
                )
            )
            if last:
                session.execute(delete(Composition).where(Composition.id == composition.id))
        session.commit()
    except Exception:
        session.rollback()
        if hidden is not None:
            storage.move_composition_version_back(root, slug, version, hidden)
        raise
    if hidden is not None:
        storage.discard_composition_version(root, slug, hidden)
    return last


def _refuse_folder_in_use(session: Session, model: type[Apartment | Composition], slug: str, name: str) -> None:
    """Folders on disk are named from the name and shared by every account, so a name
    whose folder another account already uses is refused rather than mixed with it."""
    every_account = {account_scope.ALL_ACCOUNTS: True}
    others = model.owner_id.is_distinct_from(account_scope.current())
    if model is Composition:
        slugs = session.scalars(select(Composition.slug).where(others).execution_options(**every_account))
        used = slug in set(slugs)
    else:
        names = session.scalars(select(Apartment.name).where(others).execution_options(**every_account))
        used = any(storage.apartment_slug(other) == slug for other in names)
    if used:
        raise HouseFileError(f"the name {name!r} is already used by another account; choose another name")


def record_composition(session: Session, scope: str, name: str) -> Composition:
    """The composition for a scope, created on first use. Flushes; the caller commits."""
    found = composition_by_scope(session, scope, name)
    if found is not None:
        return found
    slug = storage.composition_slug(scope, name)
    _refuse_folder_in_use(session, Composition, slug, name)
    row = Composition(scope=scope, name=name, slug=slug)
    session.add(row)
    session.flush()
    return row


def record_composition_version(
    session: Session, composition: Composition, version: int, revised_from: int | None, changes: list[str]
) -> CompositionVersion:
    row = CompositionVersion(
        composition_id=composition.id, version=version, revised_from=revised_from, changes=changes
    )
    session.add(row)
    session.flush()
    return row


def composition_version_rows(session: Session, composition: Composition) -> list[CompositionVersion]:
    return list(
        session.scalars(
            select(CompositionVersion)
            .where(CompositionVersion.composition_id == composition.id)
            .order_by(CompositionVersion.version)
        )
    )


def placed_items(session: Session, document: dict[str, Any]) -> list[dict[str, Any]]:
    """The document's items as the owner reads them; a piece carries its current approval.

    A placed piece version that is no longer approved stays and is marked, never dropped.
    An item the document's resolved placement covers also carries its `size_mm`, `centre_mm`
    and `rotation_deg` (room-change-goes-to-designer).
    """
    resolved_section = document.get("resolved")
    resolved_items = resolved_section.get("items", []) if isinstance(resolved_section, dict) else []
    resolved = {r.get("id"): r for r in resolved_items if isinstance(r, dict)}
    listed = []
    for item in document.get("items", []):
        entry: dict[str, Any] = {"id": item.get("id"), "type": item.get("type")}
        if item.get("type") == "piece":
            approved = approved_version_of(session, str(item.get("package_id"))) == item.get("version")
            entry.update(
                name=f"{item.get('package_id')} v{item.get('version')}",
                package_id=item.get("package_id"), version=item.get("version"),
                approved=approved, no_longer_approved=not approved,
            )
        else:
            entry["name"] = item.get("name")
        for key in ("room", "placement", "layer"):
            if key in item:
                entry[key] = item[key]
        if item.get("type") in ("model", "stand-in"):
            for key in ("width_mm", "depth_mm", "height_mm"):
                if key in item:
                    entry[key] = item[key]
        placed = resolved.get(item.get("id"))
        if placed is not None:
            for key in ("size_mm", "centre_mm", "rotation_deg"):
                if key in placed:
                    entry[key] = placed[key]
        listed.append(entry)
    return listed


def _version_items(session: Session, folder: Path) -> list[dict[str, Any]]:
    """The placed items of one composition version folder; none when its file is unreadable."""
    try:
        document = json.loads((folder / storage.INPUT_FILE).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        document = {}
    return placed_items(session, document)


def compositions(session: Session, root: Path) -> list[dict[str, Any]]:
    """Every recorded composition with its latest version, build status and placed items, and
    the approved version's items (`approved_items`) when a version is approved."""
    listing = []
    for row in session.scalars(select(Composition).order_by(Composition.scope, Composition.name)):
        versions = composition_version_rows(session, row)
        latest = versions[-1].version if versions else None
        approved = next((v.version for v in versions if v.approved_at is not None), None)
        status = None
        items: list[dict[str, Any]] = []
        if latest is not None:
            folder = storage.composition_version_dir(root, row.slug, latest)
            status = (storage.read_status(folder) or {}).get("status")
            items = _version_items(session, folder)
        entry: dict[str, Any] = {
            "scope": row.scope, "name": row.name, "slug": row.slug, "latest_version": latest,
            "status": status, "items": items, "versions": [v.version for v in versions],
            "approved_version": approved,
        }
        if approved is not None:
            entry["approved_items"] = (
                items if approved == latest
                else _version_items(session, storage.composition_version_dir(root, row.slug, approved))
            )
        listing.append(entry)
    return listing


# --- the Rooms page (rooms-page) -----------------------------------------------------

_BUSY = ("queued", "running")


def room_summaries(session: Session, render_root: Path) -> list[dict[str, Any]]:
    """Every measured room with what the Rooms page shows and what deleting it would touch."""
    apartment_names = {a.id: a.name for a in apartments(session)}
    pieces_by_room: dict[UUID, list[dict[str, str]]] = {}
    for piece in session.scalars(select(Piece).where(Piece.room_id.is_not(None)).order_by(Piece.package_id)):
        pieces_by_room.setdefault(piece.room_id, []).append({"package_id": piece.package_id, "name": piece.name})
    listing = []
    for room in rooms(session):
        xs = [point[0] for point in room.corners_mm]
        ys = [point[1] for point in room.corners_mm]
        composition = composition_by_scope(session, "room", room.name)
        conversations = session.scalar(
            select(func.count()).select_from(Thread).where(Thread.room_id == room.id)
        )
        listing.append(
            {
                "name": room.name,
                "width_mm": _whole(max(xs) - min(xs)),
                "depth_mm": _whole(max(ys) - min(ys)),
                "corners": len(room.corners_mm),
                "height_mm": room.height_mm,
                "openings": len(room.openings or []),
                "apartment": apartment_names.get(room.apartment_id),
                "pieces": pieces_by_room.get(room.id, []),
                "conversations": int(conversations or 0),
                "composition": (
                    {
                        "slug": composition.slug,
                        "versions": [v.version for v in composition_version_rows(session, composition)],
                    }
                    if composition is not None
                    else None
                ),
            }
        )
    return listing


def _composition_busy(render_root: Path, composition: Composition) -> bool:
    for number in storage.composition_versions(render_root, composition.slug):
        state = storage.read_status(storage.composition_version_dir(render_root, composition.slug, number)) or {}
        if state.get("status") in _BUSY:
            return True
        if any((entry or {}).get("status") in _BUSY for entry in (state.get("renders") or {}).values()):
            return True
    return False


def delete_room(session: Session, render_root: Path, name: str) -> bool:
    """Delete a measured room and its room composition; whether the room existed.

    Its pieces become unassigned and conversations that confirmed it lose it (their keys
    are `ON DELETE SET NULL`). A room in an apartment, or one whose composition is still
    building or rendering, is refused with `HouseFileError`. Unlike the writers above,
    this commits: the composition's folder is moved aside first and moved back if the
    commit fails, so the database and the folders agree either way.
    """
    room = room_by_name(session, name)
    if room is None:
        return False
    if room.apartment_id is not None:
        apartment = session.get(Apartment, room.apartment_id)
        raise HouseFileError(
            f"{room.name} belongs to the apartment {apartment.name if apartment else ''}; "
            "it cannot be deleted on its own yet"
        )
    composition = composition_by_scope(session, "room", room.name)
    if composition is not None and _composition_busy(render_root, composition):
        raise HouseFileError(
            f"the composition of {room.name} is building or rendering; delete it once that has finished"
        )
    _settle_removal(session, _remove_rooms(session, render_root, [room]))
    return True


def _remove_rooms(session: Session, render_root: Path, doomed: Sequence[Room]) -> list[tuple[Path, str, Path]]:
    """Delete each room and its room composition, its folder moved aside; the hidden folders.

    Pieces become unassigned and conversations lose the room through their `ON DELETE SET
    NULL` keys. Does not commit: `_settle_removal` commits, then drops the hidden folders.
    """
    hidden: list[tuple[Path, str, Path]] = []
    try:
        for room in doomed:
            composition = composition_by_scope(session, "room", room.name)
            if composition is not None:
                hidden.append(
                    (render_root, composition.slug, storage.move_composition_aside(render_root, composition.slug))
                )
                session.execute(delete(CompositionVersion).where(CompositionVersion.composition_id == composition.id))
                session.execute(delete(Composition).where(Composition.id == composition.id))
            session.execute(delete(Room).where(Room.id == room.id))
    except Exception:
        session.rollback()
        _restore(hidden)
        raise
    return hidden


def _restore(hidden: list[tuple[Path, str, Path]]) -> None:
    for render_root, slug, folder in hidden:
        storage.move_composition_back(render_root, slug, folder)


def _settle_removal(session: Session, hidden: list[tuple[Path, str, Path]]) -> None:
    """Commit a removal; on failure the rows are rolled back and the folders moved back."""
    try:
        session.commit()
    except Exception:
        session.rollback()
        _restore(hidden)
        raise
    for _root, _slug, folder in hidden:
        shutil.rmtree(folder, ignore_errors=True)


# --- generator-extension requests ----------------------------------------------


def record_extension_request(
    session: Session,
    field: str,
    request: str,
    package_id: str | None = None,
    thread_id: UUID | None = None,
) -> GeneratorExtensionRequest:
    row = GeneratorExtensionRequest(
        field=field[:200], request=request, package_id=package_id, thread_id=thread_id
    )
    session.add(row)
    session.flush()
    return row


def open_extension_requests(
    session: Session,
    package_ids: Sequence[str] | None = None,
    thread_id: UUID | None = None,
) -> list[GeneratorExtensionRequest]:
    """Every open request, or with `package_ids` / `thread_id` only those whose piece is
    one of the packages or that were recorded in the conversation (either matches)."""
    query = select(GeneratorExtensionRequest).where(GeneratorExtensionRequest.status == "open")
    if package_ids is not None or thread_id is not None:
        matches = []
        if package_ids:
            matches.append(GeneratorExtensionRequest.package_id.in_(list(package_ids)))
        if thread_id is not None:
            matches.append(GeneratorExtensionRequest.thread_id == thread_id)
        if not matches:
            return []
        query = query.where(or_(*matches))
    return list(session.scalars(query.order_by(GeneratorExtensionRequest.created_at)))


# --- threads ---------------------------------------------------------------------


def create_thread(session: Session, title: str = "", package_id: str | None = None) -> Thread:
    if package_id is not None:
        package_id = storage.validate_package_id(package_id)
    now = _now()
    thread = Thread(title=title.strip()[:200], package_id=package_id, created_at=now, last_turn_at=now)
    session.add(thread)
    session.flush()
    # One piece per conversation: the start bind also seeds the summary row.
    if package_id is not None:
        add_build(session, thread.id, package_id)
    return thread


def thread_id_for_piece(session: Session, package_id: str) -> UUID | None:
    """The conversation bound to a piece (`Thread.package_id`), newest activity first when
    legacy duplicates exist; `None` when none is bound."""
    package_id = storage.validate_package_id(package_id)
    return session.scalars(
        select(Thread.id)
        .where(Thread.package_id == package_id)
        .order_by(Thread.last_turn_at.desc(), Thread.created_at.desc())
        .limit(1)
    ).first()


def thread_ids_for_pieces(session: Session, package_ids: Sequence[str]) -> dict[str, UUID]:
    """Each piece's bound conversation id, when one exists. Newest activity wins on duplicates."""
    if not package_ids:
        return {}
    wanted = {storage.validate_package_id(pid) for pid in package_ids}
    rows = session.execute(
        select(Thread.package_id, Thread.id)
        .where(Thread.package_id.in_(wanted))
        .order_by(Thread.last_turn_at.desc(), Thread.created_at.desc())
    ).all()
    found: dict[str, UUID] = {}
    for package_id, thread_id in rows:
        if package_id is not None and package_id not in found:
            found[package_id] = thread_id
    return found


def delete_thread(session: Session, thread_id: UUID) -> bool:
    """Remove a thread's index entry; its upload records and tool settings go with it
    (foreign keys cascade). Pieces, versions, rooms and reviews are keyed by piece or
    room and stay. Whether a row was deleted."""
    deleted = session.execute(delete(Thread).where(Thread.id == thread_id))
    session.flush()
    return bool(deleted.rowcount)


def add_notice(
    session: Session,
    thread_id: UUID,
    *,
    after_messages: int,
    outcome: str,
    tier: str | None,
    text: str,
    package_id: str | None = None,
    version: int | None = None,
    kind: str = "render",
    composition_slug: str | None = None,
    render_key: str | None = None,
) -> ThreadNotice | None:
    """Record a render or build notice in a conversation; nothing when the thread is gone."""
    if session.get(Thread, thread_id) is None:
        return None
    notice = ThreadNotice(
        thread_id=thread_id,
        after_messages=after_messages,
        outcome=outcome,
        kind=kind,
        tier=tier,
        text=text,
        package_id=package_id,
        version=version,
        composition_slug=composition_slug,
        render_key=render_key,
    )
    session.add(notice)
    session.flush()
    return notice


def follow_room_render(session: Session, thread_id: UUID, slug: str, version: int, render_key: str) -> None:
    """Record a composition render the conversation is following; nothing when the thread is gone."""
    if session.get(Thread, thread_id) is None:
        return
    if session.get(ThreadRoomRender, (thread_id, slug, version, render_key)) is None:
        session.add(ThreadRoomRender(thread_id=thread_id, composition_slug=slug, version=version, render_key=render_key))
    session.flush()


def stop_following_room_render(session: Session, thread_id: UUID, slug: str, version: int, render_key: str) -> None:
    row = session.get(ThreadRoomRender, (thread_id, slug, version, render_key))
    if row is not None:
        session.delete(row)
        session.flush()


def followed_room_renders(session: Session, thread_id: UUID) -> list[ThreadRoomRender]:
    return list(session.scalars(select(ThreadRoomRender).where(ThreadRoomRender.thread_id == thread_id)))


def notices_for(session: Session, thread_id: UUID) -> list[ThreadNotice]:
    """A conversation's notices, in the order history shows them."""
    return list(
        session.scalars(
            select(ThreadNotice)
            .where(ThreadNotice.thread_id == thread_id)
            .order_by(ThreadNotice.after_messages, ThreadNotice.created_at)
        )
    )


def get_thread(session: Session, thread_id: UUID) -> Thread | None:
    return session.get(Thread, thread_id)


def list_threads(session: Session) -> list[Thread]:
    return list(session.scalars(select(Thread).order_by(Thread.last_turn_at.desc())))


def set_title(session: Session, thread_id: UUID, title: str) -> bool:
    """The owner's title for a thread. Whether the thread exists."""
    renamed = session.execute(update(Thread).where(Thread.id == thread_id).values(title=title.strip()[:200]))
    session.flush()
    return bool(renamed.rowcount)


def set_title_if_empty(session: Session, thread_id: UUID, title: str) -> bool:
    """A generated title, written only while the thread has none, so an owner's
    rename that lands first is kept. Whether it was written."""
    written = session.execute(
        update(Thread).where(Thread.id == thread_id, Thread.title == "").values(title=title.strip()[:200])
    )
    session.flush()
    return bool(written.rowcount)


def read_summary(
    session: Session, thread_id: UUID, package_id: str | None = None
) -> tuple[str | None, str | None]:
    """The summary of earlier exchanges and the id of the last message it covers: the
    build's when `package_id` is given, else the one for exchanges with no active build."""
    if package_id:
        build = session.get(ThreadPiece, (thread_id, package_id))
        return (build.summary, build.summary_through) if build is not None else (None, None)
    thread = session.get(Thread, thread_id)
    if thread is None:
        return None, None
    return thread.summary, thread.summary_through


def write_summary(
    session: Session,
    thread_id: UUID,
    summary: str,
    through: str,
    package_id: str | None = None,
    *,
    owner_edited: bool = False,
) -> None:
    """Store a refreshed summary; a deleted thread is left alone. `owner_edited` keeps it marked
    as the owner's (conversation-memory-settings)."""
    values = {"summary": summary, "summary_through": through[:64], "summary_owner_edited": owner_edited}
    if package_id:
        session.execute(
            update(ThreadPiece)
            .where(ThreadPiece.thread_id == thread_id, ThreadPiece.package_id == package_id)
            .values(**values)
        )
    else:
        session.execute(update(Thread).where(Thread.id == thread_id).values(**values))
    session.flush()


def summary_owner_edited(session: Session, thread_id: UUID, package_id: str | None = None) -> bool:
    """Whether the active note was last saved by the owner."""
    if package_id:
        build = session.get(ThreadPiece, (thread_id, package_id))
        return bool(build is not None and build.summary_owner_edited)
    thread = session.get(Thread, thread_id)
    return bool(thread is not None and thread.summary_owner_edited)


def write_owner_summary(session: Session, thread_id: UUID, summary: str, package_id: str | None = None) -> bool:
    """Store the owner's own text as the active note, keeping what it covers; `False` when there is
    no such thread or build."""
    if package_id:
        target = session.get(ThreadPiece, (thread_id, package_id))
    else:
        target = session.get(Thread, thread_id)
    if target is None:
        return False
    target.summary = summary
    target.summary_owner_edited = True
    session.flush()
    return True


# --- a conversation's room and builds (conversation-projects) -----------------------


def decline_room(session: Session, thread_id: UUID) -> bool:
    """Record that the conversation declined a room (optional-room-question); a room
    confirmed later does not clear it. Whether the thread exists."""
    thread = session.get(Thread, thread_id)
    if thread is None:
        return False
    thread.room_declined = True
    session.flush()
    return True


def set_thread_room(session: Session, thread_id: UUID, room: Room) -> None:
    """The room the owner confirmed in this conversation; clears an apartment scope."""
    session.execute(
        update(Thread).where(Thread.id == thread_id).values(room_id=room.id, apartment_id=None)
    )
    session.flush()


def set_thread_apartment(session: Session, thread_id: UUID, apartment: Apartment) -> None:
    """The apartment the owner confirmed in this conversation; clears a room scope."""
    session.execute(
        update(Thread)
        .where(Thread.id == thread_id)
        .values(apartment_id=apartment.id, room_id=None)
    )
    session.flush()


def thread_scope(session: Session, thread_id: UUID) -> tuple[Room | None, Apartment | None]:
    """The conversation's confirmed room or apartment (at most one is set)."""
    thread = session.get(Thread, thread_id)
    if thread is None:
        return None, None
    room = session.get(Room, thread.room_id) if thread.room_id else None
    apartment = session.get(Apartment, thread.apartment_id) if thread.apartment_id else None
    return room, apartment


def add_build(session: Session, thread_id: UUID, package_id: str) -> None:
    """List a piece among the conversation's builds, once."""
    package_id = storage.validate_package_id(package_id)
    if session.get(Thread, thread_id) is None:
        return
    if session.get(ThreadPiece, (thread_id, package_id)) is None:
        session.add(ThreadPiece(thread_id=thread_id, package_id=package_id))
        session.flush()


def builds_of(session: Session, thread_id: UUID) -> list[ThreadPiece]:
    """The conversation's builds, oldest first."""
    return list(
        session.scalars(
            select(ThreadPiece)
            .where(ThreadPiece.thread_id == thread_id)
            .order_by(ThreadPiece.added_at, ThreadPiece.package_id)
        )
    )


def set_active_build(session: Session, thread_id: UUID, package_id: str) -> None:
    """Bind an unbound conversation to a piece. A conversation already bound to a
    different piece is left unchanged (one piece per conversation)."""
    package_id = storage.validate_package_id(package_id)
    thread = session.get(Thread, thread_id)
    if thread is None:
        return
    if thread.package_id is not None and thread.package_id != package_id:
        return
    add_build(session, thread_id, package_id)
    thread.package_id = package_id
    session.flush()


def piece_room_name(session: Session, package_id: str) -> str | None:
    """The name of the room a piece is in, or `None` while it is unassigned."""
    piece = session.get(Piece, package_id)
    if piece is None or piece.room_id is None:
        return None
    room = session.get(Room, piece.room_id)
    return room.name if room is not None else None


def piece_room_names(session: Session) -> dict[str, str | None]:
    """The room name of every recorded piece; `None` for an unassigned one."""
    rows = session.execute(
        select(Piece.package_id, Room.name).outerjoin(Room, Room.id == Piece.room_id)
    )
    return {package_id: name for package_id, name in rows}


def set_piece_room(session: Session, package_id: str, room: Room | None) -> bool:
    """Attach a piece to a room, or clear it. Nothing else about the piece changes.
    Whether the piece is recorded."""
    piece = session.get(Piece, package_id)
    if piece is None:
        return False
    piece.room_id = room.id if room is not None else None
    session.flush()
    return True


def record_review(
    session: Session,
    package_id: str,
    version: int,
    renders: list[str],
    items: list[dict[str, Any]],
) -> Review:
    """Store a completed review and its items, all `open`."""
    review = Review(package_id=package_id, version=version, renders=list(renders))
    session.add(review)
    session.flush()
    for ordinal, item in enumerate(items, start=1):
        session.add(
            ReviewItem(
                review_id=review.id,
                ordinal=ordinal,
                aspect=item["aspect"],
                expected=item["expected"],
                expected_source=item["expected_source"],
                rule_id=item.get("rule_id"),
                observed=item["observed"],
                image=item["image"],
                severity=item["severity"],
                suggestion=item.get("suggestion"),
                status="open",
            )
        )
    session.flush()
    return review


def reviews_for(session: Session, package_id: str, version: int) -> list[Review]:
    return list(
        session.scalars(
            select(Review)
            .where(Review.package_id == package_id, Review.version == version)
            .order_by(Review.created_at.desc())
        )
    )


def items_of(session: Session, review_id: UUID) -> list[ReviewItem]:
    return list(
        session.scalars(
            select(ReviewItem)
            .where(ReviewItem.review_id == review_id)
            .order_by(ReviewItem.ordinal)
        )
    )


def latest_open_items(session: Session, package_id: str, version: int | None = None) -> list[dict[str, Any]]:
    """Open items of the newest review of `package_id`, for the Designer's note; of the newest review
    of `version` when one is given (review-items-follow-approved-version), each item naming it."""
    query = select(Review).where(Review.package_id == package_id)
    if version is not None:
        query = query.where(Review.version == version)
    review = session.scalars(query.order_by(Review.created_at.desc()).limit(1)).first()
    if review is None:
        return []
    return [
        {
            "id": item.id,
            "version": review.version,
            "aspect": item.aspect,
            "expected": item.expected,
            "observed": item.observed,
            "severity": item.severity,
            "suggestion": item.suggestion,
        }
        for item in items_of(session, review.id)
        if item.status == "open"
    ]


def set_item_status(session: Session, item_id: UUID, status: str) -> ReviewItem | None:
    item = session.get(ReviewItem, item_id)
    if item is None:
        return None
    item.status = status
    item.status_at = _now()
    session.flush()
    return item


def get_review(session: Session, review_id: UUID) -> Review | None:
    return session.get(Review, review_id)


def get_item(session: Session, item_id: UUID) -> ReviewItem | None:
    return session.get(ReviewItem, item_id)


def touch_thread(session: Session, thread_id: UUID, package_id: str | None = None) -> None:
    thread = session.get(Thread, thread_id)
    if thread is None:
        return
    thread.last_turn_at = _now()
    if package_id:
        set_active_build(session, thread_id, package_id)
    session.flush()
