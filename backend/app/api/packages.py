"""Packages and their versions (furniture-packages). Owner-gated.

A package is `<render root>/<package-id>/v<N>/`; only a version's approval
(the owner's acceptance of a built version) is read from and written to the
house file. A spec is validated before anything is written; a field the schema
does not define is refused by name. Building and rendering are background jobs
run by `app.blender.runner` behind the render guard.
"""

from __future__ import annotations

import json
import logging
import re
import tempfile
import zipfile
from pathlib import Path
from typing import Any, Final

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, status
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from pydantic import BaseModel, ValidationError
from sqlalchemy.orm import Session

from app.agent import house_file
from app.api.gate import require_owner
from app.blender import runner, storage
from app.blender.launch import subprocess_launch
from app.blender.schemas import CustomBuildSpec, describe_validation_error
from app.blender.spec_contract import SpecValidationError
from app.db.models import Piece
from app.design_import import export_document
from app.guidelines.hardware_inputs import freeze_inputs
from app.packages import service

logger = logging.getLogger("app")

router = APIRouter(
    prefix="/packages", tags=["packages"], dependencies=[Depends(require_owner)]
)

# `frames/<index>` and `room/...` are matched exactly; no other path is served. A frame is
# also served by its file name (`frames/frame_000.png`), the name `viewer.html` loads.
_FRAME: Final = re.compile(r"^frames/(?:(\d{1,4})|frame_(\d{3,4})\.png)$")
_ROOM_FILES: Final[dict[str, str]] = {
    "still.png": "image/png",
    "viewer.html": "text/html",
    "scene.json": "application/json",
}
_ROOM_FRAME: Final = re.compile(r"^room/frames/(?:(\d{1,4})|frame_(\d{3,4})\.png)$")
# The detail pass's outputs; never `detail.blend` or the log (photoreal-detail).
_DETAIL_FRAME: Final = re.compile(r"^detail/frames/(?:(\d{1,4})|frame_(\d{3,4})\.png)$")
_DETAIL_SCREEN: Final = re.compile(r"^detail/screens/(\d{1,4})$")


class PackageIn(BaseModel):
    package_id: str
    spec: dict[str, Any]


class SpecIn(BaseModel):
    spec: dict[str, Any]


class RoomIn(BaseModel):
    room: str | None = None


def not_found() -> HTTPException:
    return HTTPException(status.HTTP_404_NOT_FOUND, detail="Not Found")


def refused(
    status_code: int, failure_class: str, reason: str, **extra: Any
) -> HTTPException:
    return HTTPException(
        status_code, detail={"failure_class": failure_class, "reason": reason, **extra}
    )


def render_root(request: Request) -> Path:
    return request.app.state.settings.render_root


def require_generation(request: Request) -> None:
    """Starting a Blender process needs the binary; listing and files do not."""
    settings = request.app.state.settings
    if not settings.generation_enabled:
        raise refused(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "blender_unavailable",
            "Blender is not available on this host; builds and renders cannot start",
        )


def launcher(request: Request):
    return request.app.state.blender_launch or subprocess_launch


def validated_spec(document: dict[str, Any]) -> dict[str, Any]:
    """The normalised custom-build document, or a 422 naming what is wrong."""
    try:
        return CustomBuildSpec.model_validate(document).model_dump(mode="json")
    except ValidationError as error:
        raise refused(422, "invalid_spec", describe_validation_error(error)) from None
    except SpecValidationError as error:
        raise refused(422, "invalid_spec", str(error)) from None


def checked_id(package_id: str) -> str:
    try:
        return storage.validate_package_id(package_id)
    except storage.InvalidPackageId as error:
        raise refused(422, "invalid_package_id", str(error)) from None


def existing_version(request: Request, package_id: str, version: int) -> Path:
    try:
        folder = storage.version_dir(render_root(request), package_id, version)
    except (storage.InvalidPackageId, ValueError):
        raise not_found() from None
    if not folder.is_dir():
        raise not_found()
    return folder


def _frame_count(folder: Path) -> int:
    frames = folder / "frames"
    return len(list(frames.glob("frame_*.png"))) if frames.is_dir() else 0


def describe_version(
    root: Path, package_id: str, version: int, approved_at: str | None = None
) -> dict[str, Any]:
    folder = storage.version_dir(root, package_id, version)
    state = storage.read_status(folder) or {}
    files = sorted(name for name in storage.SERVED_FILES if (folder / name).is_file())
    room = folder / "room"
    return {
        "package_id": package_id,
        "version": version,
        "status": state.get("status"),
        "started_at": state.get("started_at"),
        "finished_at": state.get("finished_at"),
        "error": state.get("error"),
        "approved_at": approved_at,
        "files": files,
        "renders": {
            "still": (folder / "still.png").is_file(),
            "turntable_frames": _frame_count(folder),
            "room_still": (room / "still.png").is_file(),
            "room_turntable_frames": _frame_count(room),
            "detail_still": (storage.detail_dir(folder) / "still.png").is_file(),
            "detail_turntable_frames": _frame_count(storage.detail_dir(folder)),
        },
        "jobs": state.get("renders") or {},
    }


def _approvals(request: Request, package_id: str) -> dict[int, str]:
    """When each approved version of the piece was approved (at most one entry)."""
    with Session(request.app.state.engine) as session:
        number = house_file.approved_version_of(session, package_id)
        if number is None:
            return {}
        row = house_file.version_row(session, package_id, number)
        return {number: row.approved_at.isoformat()}


def _start_build(
    request: Request, background: BackgroundTasks, package_id: str, version: int
) -> None:
    settings = request.app.state.settings
    background.add_task(
        runner.run_build,
        root=settings.render_root,
        blender_bin=settings.blender_bin,
        timeout=settings.blender_timeout_seconds,
        package_id=package_id,
        version=version,
        semaphore=request.app.state.blender_semaphore,
        launch=launcher(request),
    )


def _create_version(
    request: Request, background: BackgroundTasks, package_id: str, spec: dict[str, Any]
) -> dict[str, Any]:
    with Session(request.app.state.engine) as session:
        inputs = freeze_inputs(session, request.app.state.design_rules, spec)
    try:
        return service.create_version(
            render_root(request),
            package_id,
            spec,
            lambda version: _start_build(request, background, package_id, version),
            inputs=inputs,
        )
    except service.VersionLimitReached as error:
        raise refused(status.HTTP_409_CONFLICT, "version_limit", str(error)) from None


@router.post("", status_code=status.HTTP_202_ACCEPTED)
def create_package(body: PackageIn, request: Request, background: BackgroundTasks):
    package_id = checked_id(body.package_id)
    spec = validated_spec(body.spec)
    if storage.versions(render_root(request), package_id):
        raise refused(
            status.HTTP_409_CONFLICT,
            "package_exists",
            f"package {package_id!r} already exists; edit its spec to make a new version",
        )
    require_generation(request)
    return _create_version(request, background, package_id, spec)


@router.get("")
def list_packages(request: Request):
    with Session(request.app.state.engine) as session:
        rooms = house_file.piece_room_names(session)
    return [
        {
            "package_id": package_id,
            "versions": sorted(found, reverse=True),
            "room": rooms.get(package_id),
        }
        for package_id, found in storage.list_packages(render_root(request))
    ]


@router.put("/{package_id}/room")
def set_room(package_id: str, body: RoomIn, request: Request):
    """Attach a piece to a room of the house file, or clear it (`null`). Nothing else about
    the piece changes, and no conversation's confirmed room does."""
    package_id = checked_id(package_id)
    with Session(request.app.state.engine) as session:
        recorded = session.get(Piece, package_id) is not None
        if not recorded and not storage.versions(render_root(request), package_id):
            raise not_found()
        name = (body.room or "").strip()
        room = None
        if name:
            room = house_file.room_by_name(session, name)
            if room is None:
                raise refused(
                    422, "unknown_room", f"there is no room {name!r} in the house file", room=name
                )
        if not recorded:
            house_file.record_piece(session, package_id, package_id)
        house_file.set_piece_room(session, package_id, room)
        room_name = room.name if room is not None else None
        session.commit()
    return {"package_id": package_id, "room": room_name}


@router.get("/{package_id}")
def read_package(package_id: str, request: Request):
    try:
        found = storage.versions(render_root(request), package_id)
    except storage.InvalidPackageId:
        raise not_found() from None
    if not found:
        raise not_found()
    approvals = _approvals(request, package_id)
    return {
        "package_id": package_id,
        "versions": [
            describe_version(render_root(request), package_id, number, approvals.get(number))
            for number in sorted(found, reverse=True)
        ],
    }


@router.get("/{package_id}/versions/{version}")
def read_version(package_id: str, version: int, request: Request):
    existing_version(request, package_id, version)
    approved_at = _approvals(request, package_id).get(version)
    return describe_version(render_root(request), package_id, version, approved_at)


@router.put("/{package_id}/versions/{version}/approval")
def approve_version(package_id: str, version: int, request: Request):
    folder = existing_version(request, package_id, version)
    if (storage.read_status(folder) or {}).get("status") != "succeeded":
        raise refused(
            409, "not_built", f"version {version} must be built before it can be approved"
        )
    with Session(request.app.state.engine) as session:
        if house_file.version_row(session, package_id, version) is None:
            raise refused(
                409,
                "not_recorded",
                f"version {version} of {package_id!r} is not in the house file; "
                "only versions made in a conversation can be approved",
            )
        row = house_file.approve_version(session, package_id, version)
        session.commit()
        approved_at = row.approved_at.isoformat()
    return describe_version(render_root(request), package_id, version, approved_at)


@router.delete("/{package_id}/versions/{version}/approval")
def unapprove_version(package_id: str, version: int, request: Request):
    existing_version(request, package_id, version)
    with Session(request.app.state.engine) as session:
        if house_file.version_row(session, package_id, version) is not None:
            house_file.unapprove_version(session, package_id, version)
            session.commit()
    return describe_version(render_root(request), package_id, version)


@router.delete("/{package_id}/versions/{version}", status_code=status.HTTP_204_NO_CONTENT)
def delete_version(package_id: str, version: int, request: Request) -> None:
    """Delete one version with its folder and records; the last one deletes the piece.
    Refused (nothing changed) with the reason when it is approved, placed in a room
    composition, or still building or rendering (version-cleanup-and-inspection)."""
    try:
        storage.version_dir(render_root(request), package_id, version)
    except (storage.InvalidPackageId, ValueError):
        raise not_found() from None
    with Session(request.app.state.engine) as session:
        try:
            house_file.delete_version(session, render_root(request), package_id, version)
        except house_file.VersionMissing:
            raise not_found() from None
        except house_file.HouseFileError as error:
            raise refused(status.HTTP_409_CONFLICT, "version_in_use", str(error)) from None


@router.put("/{package_id}/spec", status_code=status.HTTP_202_ACCEPTED)
def edit_spec(package_id: str, body: SpecIn, request: Request, background: BackgroundTasks):
    try:
        found = storage.versions(render_root(request), package_id)
    except storage.InvalidPackageId:
        raise not_found() from None
    if not found:
        raise not_found()
    spec = validated_spec(body.spec)
    require_generation(request)
    return _create_version(request, background, package_id, spec)


def frame_index(match: re.Match[str]) -> int:
    """The frame number of a `frames/<n>` or `frames/frame_<nnn>.png` match."""
    return int(match.group(1) or match.group(2))


def _file_for(folder: Path, name: str) -> tuple[Path, str] | None:
    """The path and media type for an exactly-named file, or `None`."""
    if name in storage.SERVED_FILES:
        return folder / name, storage.SERVED_FILES[name]
    frame = _FRAME.match(name)
    if frame:
        return folder / "frames" / f"frame_{frame_index(frame):03d}.png", "image/png"
    if name.startswith("room/"):
        room_name = name[len("room/") :]
        if room_name in _ROOM_FILES:
            return folder / "room" / room_name, _ROOM_FILES[room_name]
        room_frame = _ROOM_FRAME.match(name)
        if room_frame:
            return (
                folder / "room" / "frames" / f"frame_{frame_index(room_frame):03d}.png",
                "image/png",
            )
    if name.startswith("detail/"):
        detail_name = name[len("detail/") :]
        if detail_name in _ROOM_FILES:
            return storage.detail_dir(folder) / detail_name, _ROOM_FILES[detail_name]
        detail_frame = _DETAIL_FRAME.match(name)
        if detail_frame:
            return (
                storage.detail_dir(folder) / "frames" / f"frame_{frame_index(detail_frame):03d}.png",
                "image/png",
            )
        detail_screen = _DETAIL_SCREEN.match(name)
        if detail_screen:
            return (
                storage.detail_dir(folder)
                / storage.DETAIL_SCREENS_DIRNAME
                / f"screen_{int(detail_screen.group(1)):03d}.png",
                "image/png",
            )
    return None


@router.get("/{package_id}/versions/{version}/files/{name:path}", response_class=FileResponse)
def read_file(package_id: str, version: int, name: str, request: Request):
    """One file by exact name from a closed set; anything else is not found."""
    chosen = _file_for(existing_version(request, package_id, version), name)
    if chosen is None:
        raise not_found()
    path, media_type = chosen
    root = render_root(request).resolve()
    try:
        # A symlink inside a version folder must not lead outside the root.
        resolved = path.resolve()
        resolved.relative_to(root)
    except (OSError, ValueError):
        raise not_found() from None
    if not resolved.is_file():
        raise not_found()
    return FileResponse(resolved, media_type=media_type)


# --- export (design-import) -----------------------------------------------------------------

# The bundle's members besides the design file, by fixed name; `still.png` only when rendered.
BUNDLE_FILES: Final = ("cutlist.csv", "hardware.csv", "model.glb", "screenshot.png")


def _design_document(folder: Path) -> dict[str, Any]:
    try:
        design = json.loads((folder / storage.INPUT_FILE).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        raise not_found() from None
    return export_document(design)


@router.get("/{package_id}/versions/{version}/design")
def export_design(package_id: str, version: int, request: Request) -> JSONResponse:
    """The version's design as an import document that re-imports unchanged."""
    folder = existing_version(request, package_id, version)
    return JSONResponse(
        _design_document(folder),
        headers={"Content-Disposition": f'attachment; filename="{package_id}-v{version}.json"'},
    )


@router.get("/{package_id}/versions/{version}/bundle")
def export_bundle(package_id: str, version: int, request: Request) -> StreamingResponse:
    """A zip of the design file, the shop files, the model and the pictures of a built version."""
    folder = existing_version(request, package_id, version)
    if (storage.read_status(folder) or {}).get("status") != "succeeded":
        raise refused(409, "not_built", f"version {version} must be built before its bundle can be downloaded")
    design_name = f"{package_id}-v{version}.json"
    spool = tempfile.SpooledTemporaryFile(max_size=8 * 1024 * 1024)  # noqa: SIM115 - closed by the stream
    with zipfile.ZipFile(spool, "w", compression=zipfile.ZIP_DEFLATED) as bundle:
        bundle.writestr(design_name, json.dumps(_design_document(folder), indent=2, ensure_ascii=False))
        for name in (*BUNDLE_FILES, "still.png"):
            path = folder / name
            if path.is_file():
                bundle.write(path, arcname=name)
    spool.seek(0)

    def chunks():
        try:
            while chunk := spool.read(1024 * 1024):
                yield chunk
        finally:
            spool.close()

    return StreamingResponse(
        chunks(),
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{package_id}-v{version}.zip"'},
    )
