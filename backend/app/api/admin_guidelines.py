"""Developer panel: guideline sources, with PDF upload, re-ingestion and deletion of uploads (dev-panel-insights)."""

from __future__ import annotations

from datetime import date
from typing import Annotated, Any

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Request,
    Response,
    UploadFile,
    status,
)
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.gate import require_dev
from app.db.models import Chunk, GuidelineUpload
from app.guidelines.sources import load_sources
from app.guidelines.uploads import (
    UploadIn,
    UploadRefused,
    accept_upload,
    delete_upload,
    ingest_upload,
)

router = APIRouter(prefix="/admin/guidelines", tags=["admin"], dependencies=[Depends(require_dev)])


def _passages(session: Session, location: str) -> int:
    return session.scalar(select(func.count()).select_from(Chunk).where(Chunk.url == location)) or 0


def _upload_out(session: Session, upload: GuidelineUpload) -> dict[str, Any]:
    return {
        "id": upload.id, "origin": "upload", "title": upload.title, "jurisdiction": upload.jurisdiction,
        "published_on": upload.published_on.isoformat(), "licence": upload.licence, "format": "pdf",
        "size_bytes": upload.size_bytes, "passages": _passages(session, f"file:{upload.file_name}"),
        "ingested_at": upload.ingested_at.isoformat() if upload.ingested_at else None, "error": upload.error,
        "deletable": True,
    }


@router.get("")
def list_sources(request: Request) -> list[dict[str, Any]]:
    root = request.app.state.settings.guideline_root
    with Session(request.app.state.engine) as session:
        listed = [
            {
                "id": source.id, "origin": "list", "title": source.title, "jurisdiction": source.jurisdiction,
                "published_on": source.published_on.isoformat(), "licence": source.licence, "format": source.format,
                "passages": _passages(session, source.location), "deletable": False,
            }
            for source in load_sources(root=root)
        ]
        uploaded = [
            _upload_out(session, upload)
            for upload in session.scalars(select(GuidelineUpload).order_by(GuidelineUpload.created_at))
        ]
    return [*listed, *uploaded]


@router.post("", status_code=status.HTTP_201_CREATED)
def upload_source(
    request: Request,
    file: Annotated[UploadFile, File()],
    title: Annotated[str, Form(max_length=200)],
    jurisdiction: Annotated[str, Form(max_length=200)],
    published_on: Annotated[date, Form()],
    licence: Annotated[str, Form(max_length=2000)],
) -> dict[str, Any]:
    settings = request.app.state.settings
    content = file.file.read(settings.guideline_upload_max_bytes + 1)
    known = frozenset(source.id for source in load_sources(root=settings.guideline_root))
    with Session(request.app.state.engine) as session:
        try:
            upload = accept_upload(
                session, settings.guideline_root, content,
                UploadIn(title=title, jurisdiction=jurisdiction, published_on=published_on, licence=licence),
                max_bytes=settings.guideline_upload_max_bytes, known_ids=known,
            )
            session.commit()
        except UploadRefused as error:
            session.rollback()
            raise HTTPException(
                422,
                detail={"failure_class": "upload_refused", "field": error.field, "reason": error.reason},
            ) from None
        ingest_upload(session, settings.guideline_root, upload)
        return _upload_out(session, upload)


def _upload(session: Session, source_id: str) -> GuidelineUpload:
    upload = session.get(GuidelineUpload, source_id)
    if upload is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Not Found")
    return upload


@router.post("/{source_id}/ingest")
def reingest_source(source_id: str, request: Request) -> dict[str, Any]:
    with Session(request.app.state.engine) as session:
        upload = _upload(session, source_id)
        ingest_upload(session, request.app.state.settings.guideline_root, upload)
        return _upload_out(session, upload)


@router.delete("/{source_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_source(source_id: str, request: Request) -> Response:
    root = request.app.state.settings.guideline_root
    if source_id in {source.id for source in load_sources(root=root)}:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            detail={"failure_class": "checked_in_source", "reason": "a source from the checked-in list cannot be deleted here"},
        )
    with Session(request.app.state.engine) as session:
        delete_upload(session, root, _upload(session, source_id))
    return Response(status_code=status.HTTP_204_NO_CONTENT)
