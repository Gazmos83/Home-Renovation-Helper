"""Composed rooms for the Studio's Rooms page (room-composition). Owner-gated.

Compositions are created only by a confirmed `compose_room`; here they are listed,
each with its latest version, build status and items (a placed piece version that is
no longer approved is marked), its 3D model and surface map when the latest version has
them, a version's files are served by exact name, and a version can be approved,
unapproved or deleted (room-version-approval).
"""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Body,
    Depends,
    HTTPException,
    Query,
    Request,
    Response,
    status,
)
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app import compositions
from app.agent import house_file, progress
from app.agent.house_file import HouseFileError, VersionMissing
from app.api.gate import require_owner
from app.api.packages import (
    _file_for,
    _frame_count,
    _render_job,
    describe_variants,
    refused,
    require_generation,
)
from app.api.renders import _price_args, _refusal, _start, _with_target
from app.blender import storage
from app.render.guard import FORBIDDEN_FIELDS, RenderRefused, authorise, quote

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


# --- the room inspector's Renders tab (render-now-blueprints-verdict-note) --------------------

_ROOM_RENDERS = (
    # (key, label, preview file, frames folder)
    ("turntable", "Turntable", "frames/0", "frames"),
    ("still", "Still", "still.png", None),
)


def _room_built(folder) -> None:
    state = storage.read_status(folder) or {}
    if state.get("status") != "succeeded" or not (folder / "model.blend").is_file():
        raise refused(
            status.HTTP_409_CONFLICT, "not_built",
            "this room version has not been built successfully yet, so it cannot be rendered",
        )


@router.get("/{slug}/versions/{version}/renders")
def list_room_renders(slug: str, version: int, request: Request) -> dict[str, Any]:
    """A room version's published still and turntable, newest first, and the render that is
    queued or running (`render_job`), so the Renders tab can follow it."""
    folder = _existing_version(request.app.state.settings.render_root, slug, version)
    jobs = (storage.read_status(folder) or {}).get("renders") or {}
    base = f"/compositions/{slug}/versions/{version}/files/"
    renders = []
    for key, label, preview, frames_folder in _ROOM_RENDERS:
        frames = _frame_count(folder) if frames_folder else 0
        if (frames_folder and frames == 0) or (not frames_folder and not (folder / preview).is_file()):
            continue
        job = jobs.get(key) or {}
        renders.append({
            "render": key, "label": label, "tier": job.get("tier"), "finished_at": job.get("finished_at"),
            "frames": frames, "preview": base + preview,
            "viewer": base + "viewer.html" if frames_folder and (folder / "viewer.html").is_file() else None,
        })
    renders.sort(key=lambda item: item["finished_at"] or "", reverse=True)
    return {"renders": renders, "render_job": _render_job(jobs).get("render_job")}


def _room_price(request: Request, slug: str, version: int, kind: str, tier: Any, raw_fields: list[str]):
    args = _price_args(
        request, package_id=slug, version=version, kind=kind, tier=tier, room=False, raw_fields=raw_fields,
        record="room",
    )
    try:
        args = _with_target(request, args)
        return args, quote(**args)
    except RenderRefused as error:
        raise _refusal(error) from None


@router.get("/{slug}/versions/{version}/render-estimate")
def room_render_estimate(
    slug: str, version: int, request: Request,
    kind: Annotated[str, Query()] = "turntable", tier: Annotated[str | None, Query()] = None,
) -> dict[str, Any]:
    """The guard's estimate in human terms for a built room version; starts, queues,
    approves and records nothing. Refused exactly as a render request is (render-guard)."""
    folder = _existing_version(request.app.state.settings.render_root, slug, version)
    raw_fields = list(request.query_params)
    unknown = sorted(set(raw_fields) - {"kind", "tier"} - set(FORBIDDEN_FIELDS))
    if unknown:
        raise refused(422, "refused", f"unknown field {unknown[0]!r}; an estimate takes kind and tier")
    _args, priced = _room_price(request, slug, version, kind, tier, raw_fields)
    _room_built(folder)
    return {
        "tier": priced.tier.name, "kind": priced.kind, "estimate": priced.estimate_text,
        "estimate_seconds": round(priced.estimate_seconds, 1), "warning": priced.warning,
    }


@router.post("/{slug}/versions/{version}/renders", status_code=status.HTTP_202_ACCEPTED)
def start_room_render(
    slug: str, version: int, request: Request, background: BackgroundTasks,
    body: Annotated[dict[str, Any], Body()],
) -> dict[str, Any]:
    """"Render version N now": a draft of a built room version through the guard. A final is
    asked for in a conversation, where the owner approves it."""
    settings = request.app.state.settings
    folder = _existing_version(settings.render_root, slug, version)
    require_generation(request)
    raw_fields = list(body)
    unknown = sorted(set(raw_fields) - {"kind", "tier"} - set(FORBIDDEN_FIELDS))
    if unknown:
        raise refused(422, "refused", f"unknown field {unknown[0]!r}; a render takes kind and tier")
    args, priced = _room_price(request, slug, version, str(body.get("kind")), body.get("tier"), raw_fields)
    if priced.tier.name != "draft":
        raise refused(
            status.HTTP_409_CONFLICT, "final_in_conversation",
            "a final render of a room is asked for in a conversation, where you approve it",
        )
    _room_built(folder)
    try:
        ticket = authorise(**args)
    except RenderRefused as error:
        raise _refusal(error) from None
    return _start(request, background, folder, ticket, None, models_root=settings.upload_root / "models")
