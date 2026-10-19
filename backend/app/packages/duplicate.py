"""Duplicating a piece version into a new piece (duplicate-piece), shared by the package route
and the Designer's `duplicate_piece` tool.

The chosen version's design and frozen hardware inputs become version 1 of the new piece with
only the name replaced. The new piece takes the source's room and brief and gets its own
conversation. Nothing else is copied, and the source is never changed. Every refusal is checked
before anything is written.
"""

from __future__ import annotations

import json
import re
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from uuid import UUID

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agent import house_file
from app.blender import storage
from app.blender.schemas import CustomBuildSpec, describe_validation_error
from app.blender.spec_contract import SpecValidationError
from app.db.models import Piece
from app.packages import service


class DuplicateRefused(ValueError):
    """A duplicate that cannot be made; `code` names the kind, the message says why."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class Plan:
    """A checked duplicate, ready to create."""

    source_id: str
    version: int
    name: str
    package_id: str
    spec: dict[str, Any]
    inputs: dict[str, Any] | None
    room_id: UUID | None
    brief: dict[str, Any]


def change_line(source_id: str, version: int) -> str:
    return f"duplicated from {source_id} v{version}"


def _taken(session: Session, root: Path, package_id: str) -> bool:
    return bool(storage.versions(root, package_id)) or session.get(Piece, package_id) is not None


def name_taken(session: Session, name: str) -> bool:
    """Whether a piece already has this name, ignoring case."""
    wanted = name.strip().casefold()
    return any(str(found).casefold() == wanted for found in session.scalars(select(Piece.name)))


def default_id(session: Session, root: Path, name: str) -> str:
    """The name made into an id, with `-2`, `-3`… appended while that id is taken."""
    try:
        base = storage.apartment_slug(name)
    except storage.InvalidPackageId as error:
        raise DuplicateRefused("invalid_package_id", str(error)) from None
    candidate, n = base, 1
    while _taken(session, root, candidate):
        n += 1
        suffix = f"-{n}"
        candidate = re.sub(r"-+$", "", base[: 64 - len(suffix)]) + suffix
    return candidate


def plan(
    session: Session,
    root: Path,
    source_id: str,
    version: int | None,
    name: str,
    package_id: str | None,
) -> Plan:
    """Check a duplicate and return what it would create; raises `DuplicateRefused`."""
    try:
        source_id = storage.validate_package_id(source_id)
    except storage.InvalidPackageId:
        raise DuplicateRefused("not_found", f"there is no piece {source_id!r}") from None
    found = storage.versions(root, source_id)
    if not found or not house_file.piece_visible(session, source_id):
        raise DuplicateRefused("not_found", f"there is no piece {source_id!r}")
    chosen = found[-1] if version is None else version
    if chosen not in found:
        raise DuplicateRefused("not_found", f"{source_id} has no version {chosen}")
    folder = storage.version_dir(root, source_id, chosen)
    try:
        document = json.loads((folder / storage.INPUT_FILE).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        raise DuplicateRefused("no_design", f"{source_id} version {chosen} has no design to copy") from None
    name = name.strip()
    if not name:
        raise DuplicateRefused("invalid_name", "the copy needs a name")
    if name_taken(session, name):
        raise DuplicateRefused("name_taken", f"a piece is already named {name!r}; choose another name")
    if package_id is None:
        package_id = default_id(session, root, name)
    else:
        try:
            package_id = storage.validate_package_id(package_id)
        except storage.InvalidPackageId as error:
            raise DuplicateRefused("invalid_package_id", str(error)) from None
        if _taken(session, root, package_id):
            raise DuplicateRefused(
                "package_exists", f"the package id {package_id!r} is already in use; choose another id"
            )
    if not isinstance(document, dict):
        raise DuplicateRefused("no_design", f"{source_id} version {chosen} has no design to copy")
    try:
        spec = CustomBuildSpec.model_validate({**document, "name": name}).model_dump(mode="json")
    except ValidationError as error:
        raise DuplicateRefused("invalid_spec", describe_validation_error(error)) from None
    except SpecValidationError as error:
        raise DuplicateRefused("invalid_spec", str(error)) from None
    piece = session.get(Piece, source_id)
    return Plan(
        source_id=source_id,
        version=chosen,
        name=name,
        package_id=package_id,
        spec=spec,
        inputs=storage.read_hardware_inputs(folder),
        room_id=piece.room_id if piece is not None else None,
        brief=dict(piece.brief) if piece is not None else {},
    )


def create(
    session: Session,
    root: Path,
    checked: Plan,
    start: Callable[[UUID, int], None],
    *,
    slot: str | None = None,
    model: str | None = None,
) -> dict[str, Any]:
    """Create the new piece's conversation, version 1 (its build handed to `start` with the
    conversation id) and its records, then commit."""
    thread = house_file.create_thread(session, checked.name, package_id=checked.package_id)
    created = service.create_version(
        root,
        checked.package_id,
        checked.spec,
        lambda version: start(thread.id, version),
        inputs=checked.inputs,
    )
    house_file.record_piece(
        session, checked.package_id, checked.name, brief=checked.brief, room_id=checked.room_id
    )
    house_file.record_version(
        session,
        checked.package_id,
        created["version"],
        changes=[change_line(checked.source_id, checked.version)],
        slot=slot,
        model=model,
    )
    session.commit()
    return {**created, "thread_id": str(thread.id)}
