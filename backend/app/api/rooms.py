"""The measured rooms of the house file (conversation-projects, rooms-page). Owner-gated.

The list carries what the Rooms page shows and what deleting a room would touch, so
the page can warn before it deletes. A room's measurements are changed through a
conversation (Intake), never here.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Request, Response, status
from sqlalchemy.orm import Session

from app.agent import house_file
from app.agent.house_file import HouseFileError
from app.api.gate import require_owner
from app.api.packages import not_found, refused

router = APIRouter(prefix="/rooms", tags=["rooms"], dependencies=[Depends(require_owner)])


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
