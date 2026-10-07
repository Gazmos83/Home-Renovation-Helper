"""Starting stills and turntables, and approving a `final` (render-guard). Owner-gated.

Every render passes the guard: the tier is required, raw frame/resolution/engine
fields are refused by name, the estimate is returned in human terms before the
run, and a `final` answers 409 with the estimate and a token until the owner
confirms with "yes".
"""

from __future__ import annotations

import json
import logging
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
from pydantic import ValidationError

from app.api.gate import require_owner
from app.api.packages import (
    existing_version,
    launcher,
    refused,
    require_generation,
)
from app.blender import runner, storage
from app.blender.room_contract import SpecValidationError as RoomSpecError
from app.blender.schemas import RoomSceneSpec, describe_validation_error
from app.feedback import runs as feedback_runs
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
from app.render.offload import jobs as offload_jobs
from app.render.offload.runtime import (
    confirm_server_sync,
    remote_benchmark_for,
    target_for,
)

logger = logging.getLogger("app")

router = APIRouter(
    prefix="/packages/{package_id}/versions/{version}/renders",
    tags=["renders"],
    dependencies=[Depends(require_owner)],
)

ALLOWED_FIELDS: Final = frozenset({"kind", "tier", "room"})
_STATUS_FOR: Final = {
    "benchmark_missing": status.HTTP_409_CONFLICT,
    "declined": status.HTTP_409_CONFLICT,
    "offload_unreachable": status.HTTP_503_SERVICE_UNAVAILABLE,
    "offload_version": status.HTTP_503_SERVICE_UNAVAILABLE,
    "offload_not_configured": status.HTTP_503_SERVICE_UNAVAILABLE,
}


def _refusal(error: RenderRefused) -> HTTPException:
    code = _STATUS_FOR.get(error.failure_class, 422)
    extra = {"field": error.field} if error.field else {}
    return refused(code, error.failure_class, error.reason, **extra)


def _require_built(folder: Path) -> None:
    state = storage.read_status(folder) or {}
    if state.get("status") != "succeeded" or not (folder / "model.blend").is_file():
        raise refused(
            status.HTTP_409_CONFLICT, "not_built",
            "this version has not been built successfully yet, so it cannot be rendered",
        )


def _room_document(folder: Path, kind: str, room: Any) -> dict[str, Any]:
    """The normalised room-scene document, or a 422 naming what is wrong."""
    if not isinstance(room, dict):
        raise refused(422, "invalid_room", "room must be a room-scene document")
    try:
        spec = RoomSceneSpec.model_validate(room)
    except ValidationError as error:
        raise refused(422, "invalid_room", describe_validation_error(error)) from None
    if spec.output.kind != kind:
        raise refused(422, "invalid_room", f"room.output.kind must be {kind!r} to match the request")
    try:
        overall = json.loads((folder / "spec.json").read_text(encoding="utf-8"))["overall"]
        spec.context({key: float(value) for key, value in overall.items()})
    except RoomSpecError as error:
        raise refused(422, "invalid_room", str(error)) from None
    except (OSError, KeyError, ValueError, TypeError):
        raise refused(409, "not_built", "this version has no readable spec.json to place in a room") from None
    return spec.model_dump(mode="json")


def _start(
    request: Request, background: BackgroundTasks, folder: Path, ticket: RenderTicket,
    scene_document: dict[str, Any] | None,
) -> dict[str, Any]:
    settings = request.app.state.settings
    engine = request.app.state.engine
    runner.mark_render_queued(folder, ticket)
    run_id = feedback_runs.record_run(engine, ticket.quote)
    background.add_task(
        runner.run_render,
        ticket,
        root=settings.render_root,
        blender_bin=settings.blender_bin,
        timeout=settings.blender_timeout_seconds,
        semaphore=request.app.state.blender_semaphore,
        launch=launcher(request),
        scene_document=scene_document,
        tracing=getattr(request.app.state, "tracing", None),
        on_finished=lambda quote, actual: calibrate_after_render(engine, quote, actual),
        on_outcome=lambda outcome: feedback_runs.finish_run(engine, run_id, outcome),
        offload=getattr(request.app.state, "offload", None),
        on_remote_job=lambda record: offload_jobs.record_job(engine, record),
    )
    quote = ticket.quote
    return {
        "package_id": quote.package_id,
        "version": quote.version,
        "kind": quote.kind,
        "room": quote.room,
        "tier": quote.tier.name,
        "frames": quote.frames,
        "estimate_seconds": round(quote.estimate_seconds, 1),
        "estimate": quote.estimate_text,
        "status": "queued",
    }


def _price_args(
    request: Request, *, package_id: str, version: int, kind: str, tier: Any, room: bool,
    raw_fields: list[str],
) -> dict[str, Any]:
    engine = request.app.state.engine
    return {
        "package_id": package_id, "version": version, "kind": kind, "tier": tier,
        "tiers": request.app.state.tiers,
        "benchmark": benchmark_store.read_benchmark(engine),
        "cycles_multiplier": benchmark_store.read_cycles_multiplier(engine),
        "room": room, "raw_fields": raw_fields,
    }


def _with_target(request: Request, args: dict[str, Any]) -> dict[str, Any]:
    """Add where the render runs. A final the developer sent to the render server needs a
    usable server (refused, never moved to the laptop) and the server's own benchmark."""
    engine = request.app.state.engine
    where = target_for(engine, args["tier"])
    if where == "remote":
        confirm_server_sync(
            getattr(request.app.state, "loop", None),
            getattr(request.app.state, "offload", None),
            launcher(request),
        )
    return {**args, "target": where, "remote_benchmark": remote_benchmark_for(engine, where)}


@router.post("", status_code=status.HTTP_202_ACCEPTED)
def start_render(
    package_id: str, version: int, request: Request, background: BackgroundTasks,
    body: Annotated[dict[str, Any], Body()],
):
    folder = existing_version(request, package_id, version)
    require_generation(request)

    raw_fields = list(body)
    unknown = sorted(set(raw_fields) - ALLOWED_FIELDS - set(FORBIDDEN_FIELDS))
    if unknown:
        raise refused(422, "refused", f"unknown field {unknown[0]!r}; a render takes kind, tier and room")
    kind = str(body.get("kind"))
    room_given = body.get("room") is not None
    args = _price_args(
        request, package_id=package_id, version=version, kind=kind, tier=body.get("tier"),
        room=room_given, raw_fields=raw_fields,
    )
    try:
        # Validates the tier, raw knobs, kind and benchmark; approves nothing.
        args = _with_target(request, args)
        priced = quote(**args)
    except RenderRefused as error:
        raise _refusal(error) from None

    _require_built(folder)
    scene_document = _room_document(folder, kind, body["room"]) if room_given else None

    if priced.tier.name == "final":
        token = request.app.state.render_approvals.issue(
            package_id=package_id, version=version, kind=kind, tier=priced.tier.name,
            room=room_given, scene_document=scene_document,
        )
        raise refused(
            status.HTTP_409_CONFLICT, "approval_required",
            f"a final render needs your approval: {priced.summary}",
            tier=priced.tier.name,
            estimate_seconds=round(priced.estimate_seconds, 1),
            estimate=priced.estimate_text,
            summary=priced.summary,
            approval_token=token,
        )
    try:
        ticket = authorise(**args)
    except RenderRefused as error:
        raise _refusal(error) from None
    return _start(request, background, folder, ticket, scene_document)


@router.post("/approve", status_code=status.HTTP_202_ACCEPTED)
def approve_render(
    package_id: str, version: int, request: Request, background: BackgroundTasks,
    body: Annotated[dict[str, Any], Body()],
):
    folder = existing_version(request, package_id, version)
    require_generation(request)
    token = body.get("approval_token")
    if not isinstance(token, str):
        raise refused(422, "refused", "an approval_token is required")
    try:
        pending = request.app.state.render_approvals.take(
            token, package_id=package_id, version=version
        )
    except ApprovalError as error:
        raise refused(status.HTTP_409_CONFLICT, "approval_invalid", error.reason) from None
    _require_built(folder)
    args = _price_args(
        request, package_id=package_id, version=version, kind=pending.kind, tier=pending.tier,
        room=pending.room, raw_fields=[],
    )
    try:
        # The token is spent by `take`: a declined or failed approval is over.
        args = _with_target(request, args)
        ticket = authorise(**args, approval=body.get("confirm"))
    except RenderRefused as error:
        raise _refusal(error) from None
    return _start(request, background, folder, ticket, pending.scene_document)
