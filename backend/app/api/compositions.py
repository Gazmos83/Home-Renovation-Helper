"""Composed rooms for the Studio's Rooms page (room-composition). Owner-gated, read-only.

Compositions are created only by a confirmed `compose_room`; here they are listed,
each with its latest version, build status and items (a placed piece version that is
no longer approved is marked), and a version's files are served by exact name.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.agent import house_file
from app.api.gate import require_owner
from app.api.packages import _file_for
from app.blender import storage

router = APIRouter(prefix="/compositions", tags=["compositions"], dependencies=[Depends(require_owner)])


def _not_found() -> HTTPException:
    return HTTPException(status.HTTP_404_NOT_FOUND, detail="Not Found")


def _route(slug: str, version: int, name: str) -> str:
    return f"/compositions/{slug}/versions/{version}/files/{name}"


@router.get("")
def list_compositions(request: Request) -> list[dict[str, Any]]:
    root = request.app.state.settings.render_root
    with Session(request.app.state.engine) as session:
        listed = house_file.compositions(session, root)
    for composition in listed:
        latest = composition["latest_version"]
        picture = viewer = None
        if latest is not None:
            folder = storage.composition_version_dir(root, composition["slug"], latest)
            for name in ("still.png", "screenshot.png"):
                if (folder / name).is_file():
                    picture = _route(composition["slug"], latest, name)
                    break
            if (folder / "viewer.html").is_file():
                viewer = _route(composition["slug"], latest, "viewer.html")
        composition["picture"] = picture
        composition["viewer"] = viewer
    return listed


@router.get("/{slug}/versions/{version}/files/{name:path}", response_class=FileResponse)
def read_composition_file(slug: str, version: int, name: str, request: Request) -> FileResponse:
    root = request.app.state.settings.render_root
    try:
        folder = storage.composition_version_dir(root, slug, version)
    except (storage.InvalidPackageId, ValueError):
        raise _not_found() from None
    if not folder.is_dir():
        raise _not_found()
    chosen = (folder / "report.json", "application/json") if name == "report.json" else _file_for(folder, name)
    if chosen is None:
        raise _not_found()
    path, media_type = chosen
    try:
        resolved = path.resolve()
        resolved.relative_to(root.resolve())
    except (OSError, ValueError):
        raise _not_found() from None
    if not resolved.is_file():
        raise _not_found()
    return FileResponse(resolved, media_type=media_type, headers={"X-Content-Type-Options": "nosniff"})
