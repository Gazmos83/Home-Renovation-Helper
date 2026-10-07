"""Packages and their versions (furniture-packages). Owner-gated.

A package is `<render root>/<package-id>/v<N>/`; nothing here touches the
database. A spec is validated before anything is written; a field the schema
does not define is refused by name. Building and rendering are background jobs
run by `app.blender.runner` behind the render guard.
"""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Any, Final

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, status
from fastapi.responses import FileResponse
from pydantic import BaseModel, ValidationError

from app.api.gate import require_owner
from app.blender import runner, storage
from app.blender.launch import subprocess_launch
from app.blender.schemas import CustomBuildSpec, describe_validation_error
from app.blender.spec_contract import SpecValidationError
from app.packages import service

logger = logging.getLogger("app")

router = APIRouter(
    prefix="/packages", tags=["packages"], dependencies=[Depends(require_owner)]
)

# `frames/<index>` and `room/...` are matched exactly; no other path is served.
_FRAME: Final = re.compile(r"^frames/(\d{1,4})$")
_ROOM_FILES: Final[dict[str, str]] = {
    "still.png": "image/png",
    "viewer.html": "text/html",
    "scene.json": "application/json",
}
_ROOM_FRAME: Final = re.compile(r"^room/frames/(\d{1,4})$")
# The detail pass's outputs; never `detail.blend` or the log (photoreal-detail).
_DETAIL_FRAME: Final = re.compile(r"^detail/frames/(\d{1,4})$")
_DETAIL_SCREEN: Final = re.compile(r"^detail/screens/(\d{1,4})$")


class PackageIn(BaseModel):
    package_id: str
    spec: dict[str, Any]


class SpecIn(BaseModel):
    spec: dict[str, Any]


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


def describe_version(root: Path, package_id: str, version: int) -> dict[str, Any]:
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
    return service.create_version(
        render_root(request),
        package_id,
        spec,
        lambda version: _start_build(request, background, package_id, version),
    )


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
    return [
        {"package_id": package_id, "versions": sorted(found, reverse=True)}
        for package_id, found in storage.list_packages(render_root(request))
    ]


@router.get("/{package_id}")
def read_package(package_id: str, request: Request):
    try:
        found = storage.versions(render_root(request), package_id)
    except storage.InvalidPackageId:
        raise not_found() from None
    if not found:
        raise not_found()
    return {
        "package_id": package_id,
        "versions": [
            describe_version(render_root(request), package_id, number)
            for number in sorted(found, reverse=True)
        ],
    }


@router.get("/{package_id}/versions/{version}")
def read_version(package_id: str, version: int, request: Request):
    existing_version(request, package_id, version)
    return describe_version(render_root(request), package_id, version)


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


def _file_for(folder: Path, name: str) -> tuple[Path, str] | None:
    """The path and media type for an exactly-named file, or `None`."""
    if name in storage.SERVED_FILES:
        return folder / name, storage.SERVED_FILES[name]
    frame = _FRAME.match(name)
    if frame:
        return folder / "frames" / f"frame_{int(frame.group(1)):03d}.png", "image/png"
    if name.startswith("room/"):
        room_name = name[len("room/") :]
        if room_name in _ROOM_FILES:
            return folder / "room" / room_name, _ROOM_FILES[room_name]
        room_frame = _ROOM_FRAME.match(name)
        if room_frame:
            return (
                folder / "room" / "frames" / f"frame_{int(room_frame.group(1)):03d}.png",
                "image/png",
            )
    if name.startswith("detail/"):
        detail_name = name[len("detail/") :]
        if detail_name in _ROOM_FILES:
            return storage.detail_dir(folder) / detail_name, _ROOM_FILES[detail_name]
        detail_frame = _DETAIL_FRAME.match(name)
        if detail_frame:
            return (
                storage.detail_dir(folder) / "frames" / f"frame_{int(detail_frame.group(1)):03d}.png",
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
