"""Composed rooms for the Studio's Rooms page (room-composition). Owner-gated.

Compositions are created only by a confirmed `compose_room`; here they are listed,
each with its latest version, build status and items (a placed piece version that is
no longer approved is marked), its 3D model and surface map when the latest version has
them, a version's files are served by exact name, and a version can be approved,
unapproved or deleted (room-version-approval).
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app import compositions
from app.agent import house_file, progress
from app.agent.house_file import HouseFileError, VersionMissing
from app.api.gate import require_owner
from app.api.packages import _file_for, describe_variants, refused
from app.blender import storage

router = APIRouter(prefix="/compositions", tags=["compositions"], dependencies=[Depends(require_owner)])


def _not_found() -> HTTPException:
    return HTTPException(status.HTTP_404_NOT_FOUND, detail="Not Found")


def _existing_version(root, slug: str, version: int):
    try:
        folder = storage.composition_version_dir(root, slug, version)
    except (storage.InvalidPackageId, ValueError):
        raise _not_found() from None
    if not folder.is_dir():
        raise _not_found()
    return folder


def describe_composition_version(
    root, slug: str, version: int, approved_at: str | None = None
) -> dict[str, Any]:
    folder = storage.composition_version_dir(root, slug, version)
    return {
        "slug": slug,
        "version": version,
        "status": (storage.read_status(folder) or {}).get("status"),
        "approved_at": approved_at,
    }


@router.get("")
def list_compositions(request: Request) -> list[dict[str, Any]]:
    root = request.app.state.settings.render_root
    with Session(request.app.state.engine) as session:
        listed = house_file.compositions(session, root)
        for composition in listed:
            row = house_file.composition_by_slug(session, composition["slug"])
            approved_at = {}
            if row is not None:
                approved_at = {
                    v.version: v.approved_at.isoformat()
                    for v in house_file.composition_version_rows(session, row)
                    if v.approved_at is not None
                }
            # The newest versions for the dropdown, newest first (project-room-inspection).
            views = progress.composition_version_views(
                session, root, composition["slug"], composition["versions"], approved_at=approved_at
            )
            composition["version_views"] = views
            # The latest version's files; a version built before the model was published has no 3D view.
            latest = views[0] if views else {}
            for key in ("picture", "viewer", "model", "surfaces"):
                composition[key] = latest.get(key)
    return listed


@router.put("/{slug}/versions/{version}/approval")
def approve_composition_version(slug: str, version: int, request: Request) -> dict[str, Any]:
    root = request.app.state.settings.render_root
    folder = _existing_version(root, slug, version)
    if (storage.read_status(folder) or {}).get("status") != "succeeded":
        raise refused(
            409, "not_built", f"version {version} must be built before it can be approved"
        )
    with Session(request.app.state.engine) as session:
        try:
            row = house_file.approve_composition_version(session, root, slug, version)
        except HouseFileError as error:
            reason = str(error)
            klass = "unapproved_pieces" if "not approved" in reason else "not_recorded"
            raise refused(409, klass, reason) from None
        session.commit()
        approved_at = row.approved_at.isoformat() if row.approved_at else None
    return describe_composition_version(root, slug, version, approved_at)


@router.delete("/{slug}/versions/{version}/approval")
def unapprove_composition_version(slug: str, version: int, request: Request) -> dict[str, Any]:
    root = request.app.state.settings.render_root
    _existing_version(root, slug, version)
    with Session(request.app.state.engine) as session:
        try:
            house_file.unapprove_composition_version(session, slug, version)
        except HouseFileError as error:
            raise refused(409, "not_recorded", str(error)) from None
        session.commit()
    return describe_composition_version(root, slug, version)


@router.delete("/{slug}/versions/{version}", status_code=status.HTTP_204_NO_CONTENT)
def delete_composition_version(slug: str, version: int, request: Request) -> Response:
    """Delete one composition version; the last one deletes the composition."""
    root = request.app.state.settings.render_root
    try:
        storage.composition_version_dir(root, slug, version)
    except (storage.InvalidPackageId, ValueError):
        raise _not_found() from None
    with Session(request.app.state.engine) as session:
        try:
            house_file.delete_composition_version(session, root, slug, version)
        except VersionMissing:
            raise _not_found() from None
        except HouseFileError as error:
            raise refused(status.HTTP_409_CONFLICT, "version_in_use", str(error)) from None
    return Response(status_code=status.HTTP_204_NO_CONTENT)


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


@router.get("/{slug}/versions/{version}/variants")
def list_composition_variants(slug: str, version: int, request: Request) -> list[dict[str, Any]]:
    folder = _existing_version(request.app.state.settings.render_root, slug, version)
    return describe_variants(f"/compositions/{slug}/versions/{version}", folder)


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
