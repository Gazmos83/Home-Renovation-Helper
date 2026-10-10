"""Composed rooms for the Studio's Rooms page (room-composition). Owner-gated, read-only.

Compositions are created only by a confirmed `compose_room`; here they are listed,
each with its latest version, build status and items (a placed piece version that is
no longer approved is marked), its 3D model and surface map when the latest version has
them, and a version's files are served by exact name.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app import compositions
from app.agent import house_file, progress
from app.api.gate import require_owner
from app.api.packages import _file_for
from app.blender import storage

router = APIRouter(prefix="/compositions", tags=["compositions"], dependencies=[Depends(require_owner)])


def _not_found() -> HTTPException:
    return HTTPException(status.HTTP_404_NOT_FOUND, detail="Not Found")


@router.get("")
def list_compositions(request: Request) -> list[dict[str, Any]]:
    root = request.app.state.settings.render_root
    with Session(request.app.state.engine) as session:
        listed = house_file.compositions(session, root)
        for composition in listed:
            # The newest versions for the dropdown, newest first (project-room-inspection).
            views = progress.composition_version_views(session, root, composition["slug"], composition["versions"])
            composition["version_views"] = views
            # The latest version's files; a version built before the model was published has no 3D view.
            latest = views[0] if views else {}
            for key in ("picture", "viewer", "model", "surfaces"):
                composition[key] = latest.get(key)
    return listed


@router.get("/{slug}/versions/{version}/dimensions")
def read_composition_dimensions(slug: str, version: int, request: Request) -> dict[str, Any]:
    """The version's wall lengths and ceiling heights (project-room-inspection)."""
    root = request.app.state.settings.render_root
    try:
        folder = storage.composition_version_dir(root, slug, version)
    except (storage.InvalidPackageId, ValueError):
        raise _not_found() from None
    document = compositions.read_document(folder) if folder.is_dir() else None
    found = compositions.room_dimensions(document) if document is not None else None
    if found is None:
        raise _not_found()
    return found


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
