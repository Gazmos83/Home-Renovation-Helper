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
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.blender import storage
from app.blender.room_contract import normalise_room_shell
from app.blender.shell_contract import ShellContext, normalise_shell
from app.blender.spec_contract import SpecValidationError
from app.db.models import (
    Apartment,
    Composition,
    CompositionVersion,
    GeneratorExtensionRequest,
    Piece,
    PieceVersion,
    Preference,
    Review,
    ReviewItem,
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


def upsert_apartment(
    session: Session,
    name: str,
    ceiling_height_mm: Any,
    wall_thickness_mm: Any,
    rooms: list[dict[str, Any]],
    notes: str = "",
) -> Apartment:
    """Store an apartment and its rooms in one plan frame; rooms of the same name are replaced.

    Rooms already in the apartment that are not named here stay and are checked
    for overlap with the new ones. Flushes; the caller commits.
    """
    name = (name or "").strip()
    apartment = apartment_by_name(session, name)
    kept = []
    if apartment is not None:
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


def unapprove_version(session: Session, package_id: str, version: int) -> PieceVersion:
    """Clear a version's approval; unapproving an unapproved version changes nothing."""
    row = version_row(session, package_id, version)
    if row is None:
        raise HouseFileError(f"version {version} of {package_id!r} is not recorded in the house file")
    if row.approved_at is not None:
        row.approved_at = None
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


# --- room compositions (room-composition) ---------------------------------------------


def composition_by_scope(session: Session, scope: str, name: str) -> Composition | None:
    return session.scalar(select(Composition).where(Composition.scope == scope, Composition.name == name))


def record_composition(session: Session, scope: str, name: str) -> Composition:
    """The composition for a scope, created on first use. Flushes; the caller commits."""
    found = composition_by_scope(session, scope, name)
    if found is not None:
        return found
    row = Composition(scope=scope, name=name, slug=storage.composition_slug(scope, name))
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
    """
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
        listed.append(entry)
    return listed


def compositions(session: Session, root: Path) -> list[dict[str, Any]]:
    """Every recorded composition with its latest version, build status and placed items."""
    listing = []
    for row in session.scalars(select(Composition).order_by(Composition.scope, Composition.name)):
        versions = composition_version_rows(session, row)
        latest = versions[-1].version if versions else None
        status = None
        items: list[dict[str, Any]] = []
        if latest is not None:
            folder = storage.composition_version_dir(root, row.slug, latest)
            status = (storage.read_status(folder) or {}).get("status")
            try:
                document = json.loads((folder / storage.INPUT_FILE).read_text(encoding="utf-8"))
            except (OSError, ValueError):
                document = {}
            items = placed_items(session, document)
        listing.append(
            {
                "scope": row.scope, "name": row.name, "slug": row.slug, "latest_version": latest,
                "status": status, "items": items, "versions": [v.version for v in versions],
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


def latest_open_items(session: Session, package_id: str) -> list[dict[str, Any]]:
    """Open items of the newest review of `package_id`, for the Designer's note."""
    review = session.scalars(
        select(Review)
        .where(Review.package_id == package_id)
        .order_by(Review.created_at.desc())
        .limit(1)
    ).first()
    if review is None:
        return []
    return [
        {
            "id": item.id,
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
        thread.package_id = package_id
    session.flush()
