"""Apartments and their shells (apartment-shell). Owner-gated.

An apartment lives in the house file; its shell is a versioned folder under
`<render root>/shells/<slug>/v<N>/` built headless from the stored rooms. A
build is not a render; a still or turntable of a shell passes the render guard
exactly like a furniture version: a required tier, raw knobs refused by name, the
estimate before the run, a `final` only after the owner's yes.
"""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Annotated, Any, Final

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Body,
    Depends,
    HTTPException,
    Request,
    status,
)
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.agent import house_file
from app.api.gate import require_owner
from app.api.packages import (
    _frame_count,
    frame_index,
    launcher,
    not_found,
    refused,
    require_generation,
)
from app.blender import runner, storage
from app.packages import service
from app.render import benchmark_store
from app.render.approvals import ApprovalError
from app.render.calibration import calibrate_after_render
from app.render.guard import (
    FORBIDDEN_FIELDS,
    RenderRefused,
    RenderTicket,
    authorise,
    quote,
)

logger = logging.getLogger("app")

router = APIRouter(
    prefix="/apartments", tags=["apartments"], dependencies=[Depends(require_owner)]
)

ALLOWED_FIELDS: Final = frozenset({"kind", "tier"})
_FRAME: Final = re.compile(r"^frames/(?:(\d{1,4})|frame_(\d{3,4})\.png)$")  # as packages
_EXTRA_FILES: Final[dict[str, str]] = {
    "still.png": "image/png",
    "viewer.html": "text/html",
    "scene.json": "application/json",
    storage.STATUS_FILE: "application/json",
}
_STATUS_FOR: Final = {"benchmark_missing": status.HTTP_409_CONFLICT, "declined": status.HTTP_409_CONFLICT}


def _root(request: Request) -> Path:
    return request.app.state.settings.render_root


def _find(session: Session, slug: str):
    """The stored apartment whose name makes `slug`, or a 404."""
    for apartment in house_file.apartments(session):
        try:
            if storage.apartment_slug(apartment.name) == slug:
                return apartment
        except storage.InvalidPackageId:
            continue
    raise not_found()


def _shell_folder(request: Request, slug: str, version: int) -> Path:
    try:
        folder = storage.shell_version_dir(_root(request), slug, version)
    except (storage.InvalidPackageId, ValueError):
        raise not_found() from None
    if not folder.is_dir():
        raise not_found()
    return folder


def _describe(root: Path, slug: str, version: int) -> dict[str, Any]:
    folder = storage.shell_version_dir(root, slug, version)
    state = storage.read_status(folder) or {}
    served = {**storage.SHELL_FILES, **_EXTRA_FILES}
    return {
        "apartment": slug,
        "version": version,
        "status": state.get("status"),
        "started_at": state.get("started_at"),
        "finished_at": state.get("finished_at"),
        "error": state.get("error"),
        "files": sorted(name for name in served if (folder / name).is_file()),
        "renders": {"still": (folder / "still.png").is_file(), "turntable_frames": _frame_count(folder)},
        "jobs": state.get("renders") or {},
    }


def _out(session: Session, request: Request, apartment) -> dict[str, Any]:
    slug = storage.apartment_slug(apartment.name)
    rooms = house_file.rooms_of(session, apartment)
    return {
        "apartment": slug,
        "name": apartment.name,
        "ceiling_height_mm": apartment.ceiling_height_mm,
        "wall_thickness_mm": apartment.wall_thickness_mm,
        "rooms": [room.name for room in rooms],
        "shell_versions": sorted(storage.shell_versions(_root(request), slug), reverse=True),
    }


@router.get("")
def list_apartments(request: Request) -> list[dict[str, Any]]:
    with Session(request.app.state.engine) as session:
        return [_out(session, request, a) for a in house_file.apartments(session)]


@router.get("/{slug}")
def read_apartment(slug: str, request: Request) -> dict[str, Any]:
    with Session(request.app.state.engine) as session:
        apartment = _find(session, slug)
        detail = _out(session, request, apartment)
        detail["rooms"] = [room["name"] for room in house_file.describe_apartment(session, apartment)["rooms"]]
        return detail


def shell_document(session: Session, apartment) -> dict[str, Any]:
    """The normalised shell document for a stored apartment, or a stated refusal."""
    try:
        return house_file.apartment_shell_document(session, apartment)
    except house_file.HouseFileError as error:
        if not house_file.rooms_of(session, apartment):
            raise refused(status.HTTP_409_CONFLICT, "no_rooms", str(error)) from None
        raise refused(422, "invalid_apartment", str(error)) from None


def _start_build(request: Request, background: BackgroundTasks, slug: str, version: int) -> None:
    settings = request.app.state.settings
    background.add_task(
        runner.run_build,
        root=settings.render_root,
        blender_bin=settings.blender_bin,
        timeout=settings.blender_timeout_seconds,
        package_id=slug,
        version=version,
        semaphore=request.app.state.blender_semaphore,
        launch=launcher(request),
        record="shell",
    )


@router.post("/{slug}/shell", status_code=status.HTTP_202_ACCEPTED)
def build_shell(slug: str, request: Request, background: BackgroundTasks) -> dict[str, Any]:
    with Session(request.app.state.engine) as session:
        document = shell_document(session, _find(session, slug))
    require_generation(request)
    return service.create_shell_version(
        _root(request), slug, document, lambda version: _start_build(request, background, slug, version)
    )


@router.get("/{slug}/shell/versions/{version}")
def read_shell_version(slug: str, version: int, request: Request) -> dict[str, Any]:
    _shell_folder(request, slug, version)
    return _describe(_root(request), slug, version)


@router.get("/{slug}/shell/versions/{version}/files/{name:path}", response_class=FileResponse)
def read_shell_file(slug: str, version: int, name: str, request: Request):
    """One file by exact name from a closed set; anything else is not found."""
    folder = _shell_folder(request, slug, version)
    served = {**storage.SHELL_FILES, **_EXTRA_FILES}
    if name in served:
        path, media_type = folder / name, served[name]
    elif (frame := _FRAME.match(name)) is not None:
        path, media_type = folder / "frames" / f"frame_{frame_index(frame):03d}.png", "image/png"
    else:
        raise not_found()
    root = _root(request).resolve()
    try:
        resolved = path.resolve()
        resolved.relative_to(root)
    except (OSError, ValueError):
        raise not_found() from None
    if not resolved.is_file():
        raise not_found()
    return FileResponse(resolved, media_type=media_type)


# --- renders: the same guard as a furniture version --------------------------------------------


def _refusal(error: RenderRefused) -> HTTPException:
    extra = {"field": error.field} if error.field else {}
    return refused(_STATUS_FOR.get(error.failure_class, 422), error.failure_class, error.reason, **extra)


def _price_args(
    request: Request, *, slug: str, version: int, kind: str, tier: Any, raw_fields: list[str]
) -> dict[str, Any]:
    return {
        "package_id": slug, "version": version, "kind": kind, "tier": tier,
        **benchmark_store.quote_inputs(request.app.state.engine, request.app.state.tiers),
        "room": False, "raw_fields": raw_fields, "record": "shell",
    }


def _require_built(folder: Path) -> None:
    state = storage.read_status(folder) or {}
    if state.get("status") != "succeeded" or not (folder / "model.blend").is_file():
        raise refused(
            status.HTTP_409_CONFLICT, "not_built",
            "this shell version has not been built successfully yet, so it cannot be rendered",
        )


def _start_render(request: Request, background: BackgroundTasks, folder: Path, ticket: RenderTicket) -> dict[str, Any]:
    settings = request.app.state.settings
    engine = request.app.state.engine
    runner.mark_render_queued(folder, ticket)
    background.add_task(
        runner.run_render,
        ticket,
        root=settings.render_root,
        blender_bin=settings.blender_bin,
        timeout=settings.blender_timeout_seconds,
        semaphore=request.app.state.blender_semaphore,
        launch=launcher(request),
        scene_document=None,
        tracing=getattr(request.app.state, "tracing", None),
        on_finished=lambda finished, actual: calibrate_after_render(engine, finished, actual),
    )
    priced = ticket.quote
    return {
        "apartment": priced.package_id, "version": priced.version, "kind": priced.kind,
        "tier": priced.tier.name, "frames": priced.frames,
        "estimate_seconds": round(priced.estimate_seconds, 1), "estimate": priced.estimate_text,
        "status": "queued",
    }


@router.post("/{slug}/shell/versions/{version}/renders", status_code=status.HTTP_202_ACCEPTED)
def start_shell_render(
    slug: str, version: int, request: Request, background: BackgroundTasks,
    body: Annotated[dict[str, Any], Body()],
):
    folder = _shell_folder(request, slug, version)
    require_generation(request)
    raw_fields = list(body)
    unknown = sorted(set(raw_fields) - ALLOWED_FIELDS - set(FORBIDDEN_FIELDS))
    if unknown:
        raise refused(422, "refused", f"unknown field {unknown[0]!r}; a render takes kind and tier")
    kind = str(body.get("kind"))
    args = _price_args(request, slug=slug, version=version, kind=kind, tier=body.get("tier"), raw_fields=raw_fields)
    try:
        priced = quote(**args)
    except RenderRefused as error:
        raise _refusal(error) from None
    _require_built(folder)
    if priced.tier.name == "final":
        token = request.app.state.render_approvals.issue(
            package_id=slug, version=version, kind=kind, tier=priced.tier.name,
            room=False, scene_document=None, record="shell",
            target=priced.target, estimate_seconds=priced.estimate_seconds,
        )
        raise refused(
            status.HTTP_409_CONFLICT, "approval_required",
            " ".join(filter(None, [f"a final render needs your approval: {priced.summary}.", priced.warning])),
            tier=priced.tier.name, estimate_seconds=round(priced.estimate_seconds, 1),
            estimate=priced.estimate_text, summary=priced.summary, warning=priced.warning,
            approval_token=token,
        )
    try:
        ticket = authorise(**args)
    except RenderRefused as error:
        raise _refusal(error) from None
    return _start_render(request, background, folder, ticket)


@router.post("/{slug}/shell/versions/{version}/renders/approve", status_code=status.HTTP_202_ACCEPTED)
def approve_shell_render(
    slug: str, version: int, request: Request, background: BackgroundTasks,
    body: Annotated[dict[str, Any], Body()],
):
    folder = _shell_folder(request, slug, version)
    require_generation(request)
    token = body.get("approval_token")
    if not isinstance(token, str):
        raise refused(422, "refused", "an approval_token is required")
    try:
        pending = request.app.state.render_approvals.take(token, package_id=slug, version=version, record="shell")
    except ApprovalError as error:
        raise refused(status.HTTP_409_CONFLICT, "approval_invalid", error.reason) from None
    _require_built(folder)
    args = _price_args(request, slug=slug, version=version, kind=pending.kind, tier=pending.tier, raw_fields=[])
    try:
        priced = quote(**args)
        pending.refuse_if_changed(priced.target, priced.estimate_seconds)
        ticket = authorise(**args, approval=body.get("confirm"))
    except RenderRefused as error:
        raise _refusal(error) from None
    except ApprovalError as error:
        raise refused(status.HTTP_409_CONFLICT, "approval_changed", error.reason) from None
    return _start_render(request, background, folder, ticket)
