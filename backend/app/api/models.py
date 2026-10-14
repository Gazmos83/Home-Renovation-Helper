"""The owner's model library (model-assets). Owner-gated.

Upload one model with its real size; list, read, fetch files by exact relative
name, and delete. After an upload the model is imported once in headless Blender
to measure it; until then it reads `checking`.
"""

from __future__ import annotations

from typing import Annotated, Any
from uuid import UUID

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    File,
    Form,
    HTTPException,
    Request,
    UploadFile,
    status,
)
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app import compositions
from app.api.gate import require_owner
from app.assets import models as library
from app.blender import runner
from app.blender.launch import subprocess_launch

router = APIRouter(prefix="/models", tags=["models"], dependencies=[Depends(require_owner)])

MAX_DIMENSION_MM = 10_000


class ModelOut(BaseModel):
    model_id: UUID
    name: str
    kind: str
    width_mm: int
    depth_mm: int
    height_mm: int
    state: str
    reason: str | None
    measured_mm: dict[str, float] | None
    triangles: int | None
    files: list[str]
    entry: str
    has_thumbnail: bool


def _out(request: Request, model: Any) -> ModelOut:
    root = request.app.state.settings.upload_root
    folder = library.model_dir(root, model.id)
    files = sorted(
        p.relative_to(folder).as_posix() for p in folder.rglob("*") if p.is_file() and p.name != "check.json"
    ) if folder.is_dir() else []
    return ModelOut(
        model_id=model.id, name=model.name, kind=model.kind, width_mm=model.width_mm, depth_mm=model.depth_mm,
        height_mm=model.height_mm, state=model.state, reason=model.reason, measured_mm=model.measured_mm,
        triangles=model.triangles, files=files, entry=model.entry,
        has_thumbnail=library.thumbnail_path(root, model.id).is_file(),
    )


def _refusal(error: library.ModelRefused) -> HTTPException:
    failure_class = {413: "too_large", 415: "unsupported_type", 409: "in_use"}.get(error.status, "refused")
    return HTTPException(error.status, detail={"failure_class": failure_class, "reason": error.reason})


def _not_found() -> HTTPException:
    return HTTPException(status.HTTP_404_NOT_FOUND, detail="Not Found")


def _start_check(request: Request, background: BackgroundTasks, model: Any) -> None:
    settings = request.app.state.settings
    engine = request.app.state.engine
    model_id = model.id

    def record(report: dict | None, error: str | None) -> None:
        with Session(engine) as session:
            row = library.get_model(session, model_id)
            if row is None:
                return
            library.record_check(session, row, report, max_triangles=settings.model_max_triangles, error=error)
            session.commit()

    background.add_task(
        runner.run_model_check,
        model_folder=library.model_dir(settings.upload_root, model_id),
        entry=model.entry,
        kind=model.kind,
        blender_bin=settings.blender_bin,
        timeout=settings.blender_timeout_seconds,
        semaphore=request.app.state.blender_semaphore,
        on_done=record,
        launch=request.app.state.blender_launch or subprocess_launch,
    )


def _dimension(value: int, field: str) -> int:
    if not 1 <= value <= MAX_DIMENSION_MM:
        raise HTTPException(
            422, detail={"failure_class": "invalid_size", "field": field,
                         "reason": f"{field} must be a whole millimetre from 1 to {MAX_DIMENSION_MM}"},
        )
    return value


@router.post("", status_code=status.HTTP_201_CREATED)
def upload_model(
    request: Request,
    background: BackgroundTasks,
    file: Annotated[UploadFile, File()],
    name: Annotated[str, Form(min_length=1, max_length=120)],
    width_mm: Annotated[int, Form()],
    depth_mm: Annotated[int, Form()],
    height_mm: Annotated[int, Form()],
) -> ModelOut:
    settings = request.app.state.settings
    if not settings.generation_enabled:
        raise HTTPException(
            503, detail={"failure_class": "blender_unavailable",
                         "reason": "Blender is not available on this host, so a model cannot be checked"},
        )
    for value, field in ((width_mm, "width_mm"), (depth_mm, "depth_mm"), (height_mm, "height_mm")):
        _dimension(value, field)
    declared = request.headers.get("content-length")
    if declared and declared.isdigit() and int(declared) > settings.model_max_bytes + 64 * 1024:
        raise _refusal(library.ModelRefused(413, "the model is too large"))
    limits = library.Limits(
        max_bytes=settings.model_max_bytes,
        max_entries=settings.model_zip_max_entries,
        max_unpacked_bytes=settings.model_zip_max_unpacked_bytes,
    )
    with Session(request.app.state.engine) as session:
        try:
            model = library.add_model(
                session, settings.upload_root, file.file, name=name, width_mm=width_mm, depth_mm=depth_mm,
                height_mm=height_mm, original_name=file.filename or "", limits=limits,
            )
        except library.ModelRefused as error:
            raise _refusal(error) from None
        out = _out(request, model)
        _start_check(request, background, model)
        return out


@router.get("")
def list_models(request: Request) -> list[ModelOut]:
    with Session(request.app.state.engine) as session:
        return [_out(request, model) for model in library.list_models(session)]


@router.get("/{model_id}")
def read_model(model_id: UUID, request: Request) -> ModelOut:
    with Session(request.app.state.engine) as session:
        model = library.get_model(session, model_id)
        if model is None:
            raise _not_found()
        return _out(request, model)


@router.get("/{model_id}/files/{name:path}", response_class=FileResponse)
def read_model_file(model_id: UUID, name: str, request: Request) -> FileResponse:
    with Session(request.app.state.engine) as session:
        model = library.get_model(session, model_id)
        if model is None:
            raise _not_found()
        found = library.stored_file(request.app.state.settings.upload_root, model, name)
    if found is None:
        raise _not_found()
    path, content_type = found
    return FileResponse(path, media_type=content_type, headers={"X-Content-Type-Options": "nosniff"})


@router.put("/{model_id}/thumbnail", status_code=status.HTTP_204_NO_CONTENT)
async def store_thumbnail(model_id: UUID, request: Request) -> None:
    """The model's preview picture, drawn by the owner's browser (studio-tile-grid)."""
    data = bytearray()
    async for chunk in request.stream():
        data.extend(chunk)
        if len(data) > library.THUMBNAIL_MAX_BYTES:
            raise _refusal(library.ModelRefused(413, f"the picture is larger than {library.THUMBNAIL_MAX_BYTES // 1024} KB"))

    def store() -> None:
        with Session(request.app.state.engine) as session:
            model = library.get_model(session, model_id)
            if model is None:
                raise _not_found()
            try:
                library.store_thumbnail(request.app.state.settings.upload_root, model, bytes(data))
            except library.ModelRefused as error:
                if error.status == 409:
                    raise HTTPException(409, detail={"failure_class": "not_ready", "reason": error.reason}) from None
                if error.status == 422:
                    raise HTTPException(422, detail={"failure_class": "invalid_size", "reason": error.reason}) from None
                raise _refusal(error) from None

    await run_in_threadpool(store)


@router.get("/{model_id}/thumbnail", response_class=FileResponse)
def read_thumbnail(model_id: UUID, request: Request) -> FileResponse:
    path = library.thumbnail_path(request.app.state.settings.upload_root, model_id)
    if not path.is_file():
        raise _not_found()
    return FileResponse(path, media_type="image/png", headers={"X-Content-Type-Options": "nosniff"})


@router.delete("/{model_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_model(model_id: UUID, request: Request) -> None:
    settings = request.app.state.settings
    with Session(request.app.state.engine) as session:
        model = library.get_model(session, model_id)
        if model is None:
            raise _not_found()
        used_by = compositions.placing_model(session, settings.render_root, model_id)
        try:
            library.delete_model(session, settings.upload_root, model, used_by)
        except library.ModelRefused as error:
            raise _refusal(error) from None
