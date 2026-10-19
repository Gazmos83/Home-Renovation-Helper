"""The measured rooms of the house file (conversation-projects, rooms-page). Owner-gated.

The list carries what the Rooms page shows and what deleting a room would touch, so
the page can warn before it deletes. A room's measurements are changed through a
conversation (Intake), never here.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, Request, Response, status
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app import rooms_duplicate
from app.agent import house_file, uploads
from app.agent.house_file import HouseFileError
from app.api.gate import require_owner
from app.api.packages import launcher, not_found, refused, require_generation
from app.blender import runner
from app.db.models import Blueprint

router = APIRouter(prefix="/rooms", tags=["rooms"], dependencies=[Depends(require_owner)])
# A kept blueprint's download (render-now-blueprints-verdict-note).
blueprints_router = APIRouter(prefix="/blueprints", tags=["rooms"], dependencies=[Depends(require_owner)])


@router.get("")
def list_rooms(request: Request) -> list[dict[str, Any]]:
    with Session(request.app.state.engine) as session:
        return house_file.room_summaries(session, request.app.state.settings.render_root)


@router.delete("/{name}", status_code=status.HTTP_204_NO_CONTENT)
def delete_room(name: str, request: Request) -> Response:
    """Delete a room and its room composition; its pieces become unassigned."""
    with Session(request.app.state.engine) as session:
        try:
            deleted = house_file.delete_room(session, request.app.state.settings.render_root, name)
        except HouseFileError as error:
            raise refused(status.HTTP_409_CONFLICT, "room_in_use", str(error)) from None
    if not deleted:
        raise not_found()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


class DuplicateRoomIn(BaseModel):
    name: str
    version: int | None = None


@router.post("/{name}/duplicate", status_code=status.HTTP_201_CREATED)
def duplicate_room(name: str, body: DuplicateRoomIn, request: Request, background: BackgroundTasks) -> dict[str, Any]:
    """Copy a room under a new name, with one layout version when `version` is given (duplicate-room).
    Nothing of the source changes; nothing is written when it is refused."""
    state = request.app.state
    settings = state.settings
    if body.version is not None:
        require_generation(request)
    with Session(state.engine) as session:
        try:
            checked = rooms_duplicate.plan(
                session, settings.render_root, name, body.name, body.version,
                max_items=settings.composition_max_items, rules=state.design_rules, lighting=state.lighting,
            )
        except rooms_duplicate.RoomDuplicateRefused as error:
            if error.code == "not_found":
                raise not_found() from None
            invalid = error.code in ("invalid_name", "invalid_room")
            raise refused(422 if invalid else status.HTTP_409_CONFLICT, error.code, str(error)) from None
        return rooms_duplicate.create(
            session,
            settings.render_root,
            checked,
            lambda slug, version: background.add_task(
                runner.run_build,
                root=settings.render_root,
                blender_bin=settings.blender_bin,
                timeout=settings.blender_timeout_seconds,
                package_id=slug,
                version=version,
                semaphore=state.blender_semaphore,
                launch=launcher(request),
                record="room",
                models_root=settings.upload_root / "models",
            ),
        )


@router.get("/{name}/blueprints")
def list_room_blueprints(name: str, request: Request) -> list[dict[str, Any]]:
    """The blueprints of the room's apartment, newest first; none for a room with no apartment."""
    with Session(request.app.state.engine) as session:
        room = house_file.room_by_name(session, name)
        if room is None:
            raise not_found()
        if room.apartment_id is None:
            return []
        return [
            {
                "id": str(blueprint.id),
                "original_name": blueprint.original_name,
                "kind": blueprint.kind,
                "created_at": blueprint.created_at.isoformat(),
                "href": f"/blueprints/{blueprint.id}",
            }
            for blueprint in uploads.apartment_blueprints(session, room.apartment_id)
        ]


@blueprints_router.get("/{blueprint_id}", response_class=FileResponse)
def read_blueprint(blueprint_id: UUID, request: Request) -> FileResponse:
    """The stored file as an attachment, in its original type and `nosniff`."""
    with Session(request.app.state.engine) as session:
        blueprint = session.get(Blueprint, blueprint_id)
        if blueprint is None:
            raise not_found()
        path = uploads.blueprint_path(request.app.state.settings.upload_root, blueprint.id, blueprint.kind)
        media_type = uploads.MEDIA_TYPES[blueprint.kind]
        filename = blueprint.original_name or f"blueprint.{uploads.EXTENSIONS[blueprint.kind]}"
    if not path.is_file():
        raise not_found()
    return FileResponse(
        path, media_type=media_type, filename=filename, headers={"X-Content-Type-Options": "nosniff"},
    )
