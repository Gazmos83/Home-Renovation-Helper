"""Uploading blueprints, photos and design files to a conversation (plan-uploads). Owner-gated.

One file per request: a PNG or JPEG image, or a design file (design-import),
identified from its bytes, size- and count-capped. Files are served back only by upload id with a fixed content type.
"""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile, status
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.agent import house_file, uploads
from app.api.gate import require_owner

router = APIRouter(tags=["uploads"], dependencies=[Depends(require_owner)])


class UploadOut(BaseModel):
    upload_id: UUID
    kind: str
    size_bytes: int
    original_name: str


def _out(upload) -> UploadOut:
    return UploadOut(
        upload_id=upload.id, kind=upload.kind, size_bytes=upload.size_bytes, original_name=upload.original_name
    )


def _refusal(error: uploads.UploadRefused) -> HTTPException:
    failure_class = {413: "too_large", 415: "unsupported_type", 409: "too_many"}.get(error.status, "refused")
    return HTTPException(error.status, detail={"failure_class": failure_class, "reason": error.reason})


def _require_thread(session: Session, thread_id: UUID) -> None:
    if house_file.get_thread(session, thread_id) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Not Found")


@router.post("/chat/threads/{thread_id}/uploads", status_code=status.HTTP_201_CREATED)
def upload_image(
    thread_id: UUID, request: Request, file: Annotated[UploadFile, File()]
) -> UploadOut:
    settings = request.app.state.settings
    declared = request.headers.get("content-length")
    # The whole multipart body is at least as large as the file: refuse early.
    if declared and declared.isdigit() and int(declared) > settings.upload_max_bytes + 64 * 1024:
        raise _refusal(uploads.UploadRefused(413, "the image is too large"))
    with Session(request.app.state.engine) as session:
        _require_thread(session, thread_id)
        try:
            upload = uploads.add_upload(
                session,
                settings.upload_root,
                thread_id,
                file.file,
                original_name=file.filename or "",
                max_bytes=settings.upload_max_bytes,
                max_per_thread=settings.upload_max_per_thread,
                max_design_bytes=settings.upload_max_design_bytes,
            )
        except uploads.UploadRefused as error:
            raise _refusal(error) from None
        return _out(upload)


@router.get("/chat/threads/{thread_id}/uploads")
def list_thread_uploads(thread_id: UUID, request: Request) -> list[UploadOut]:
    with Session(request.app.state.engine) as session:
        _require_thread(session, thread_id)
        return [_out(upload) for upload in uploads.list_uploads(session, thread_id)]


@router.get("/uploads/{upload_id}", response_class=FileResponse)
def read_upload(upload_id: UUID, request: Request) -> FileResponse:
    with Session(request.app.state.engine) as session:
        upload = uploads.get_upload(session, upload_id)
        if upload is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Not Found")
        path = uploads.upload_path(
            request.app.state.settings.upload_root, upload.thread_id, upload.id, upload.kind
        )
        media_type = uploads.MEDIA_TYPES[upload.kind]
    if not path.is_file():
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Not Found")
    return FileResponse(path, media_type=media_type, headers={"X-Content-Type-Options": "nosniff"})
