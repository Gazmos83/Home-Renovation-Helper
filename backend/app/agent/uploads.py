"""Images the owner attaches to a conversation (plan-uploads).

The bytes live in a file under the upload root, named by the upload's id; the
database holds only metadata and conversation state holds only the id. The type
comes from the file's own bytes, never from its name or declared type.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import BinaryIO, Final
from uuid import UUID, uuid4

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import Upload

logger = logging.getLogger("app")

CHUNK_BYTES: Final = 1024 * 1024
EXTENSIONS: Final = {"png": "png", "jpeg": "jpg"}
MEDIA_TYPES: Final = {"png": "image/png", "jpeg": "image/jpeg"}


class UploadRefused(Exception):
    """An upload refused, with the HTTP status and a reason safe to show."""

    def __init__(self, status: int, reason: str) -> None:
        super().__init__(reason)
        self.status = status
        self.reason = reason


def sniff(head: bytes) -> str | None:
    """`png` or `jpeg` from the first bytes of a file, else `None`."""
    if head.startswith(b"\x89PNG\r\n\x1a\n"):
        return "png"
    if head.startswith(b"\xff\xd8\xff"):
        return "jpeg"
    return None


def upload_path(root: Path, thread_id: UUID, upload_id: UUID, kind: str) -> Path:
    return root / str(thread_id) / f"{upload_id}.{EXTENSIONS[kind]}"


def write_image(
    root: Path, thread_id: UUID, upload_id: UUID, stream: BinaryIO, *, max_bytes: int
) -> tuple[str, int, Path]:
    """Copy `stream` to its file in chunks; returns `(kind, size, path)`.

    Stops reading past `max_bytes` and leaves no file behind on any refusal.
    """
    head = stream.read(CHUNK_BYTES)
    kind = sniff(head)
    if kind is None:
        raise UploadRefused(415, "only PNG and JPEG images are accepted")
    path = upload_path(root, thread_id, upload_id, kind)
    path.parent.mkdir(parents=True, exist_ok=True)
    partial = path.with_suffix(path.suffix + ".part")
    size = 0
    try:
        with partial.open("wb") as handle:
            chunk = head
            while chunk:
                size += len(chunk)
                if size > max_bytes:
                    raise UploadRefused(413, f"the image is larger than {max_bytes // (1024 * 1024)} MiB")
                handle.write(chunk)
                chunk = stream.read(CHUNK_BYTES)
        os.replace(partial, path)
    except BaseException:
        partial.unlink(missing_ok=True)
        raise
    return kind, size, path


def add_upload(
    session: Session,
    root: Path,
    thread_id: UUID,
    stream: BinaryIO,
    *,
    original_name: str,
    max_bytes: int,
    max_per_thread: int,
) -> Upload:
    """Store one image for a thread and record it; commits."""
    count = session.scalar(select(func.count()).select_from(Upload).where(Upload.thread_id == thread_id))
    if (count or 0) >= max_per_thread:
        raise UploadRefused(409, f"a conversation holds at most {max_per_thread} uploads")
    upload_id = uuid4()
    kind, size, path = write_image(root, thread_id, upload_id, stream, max_bytes=max_bytes)
    upload = Upload(
        id=upload_id, thread_id=thread_id, kind=kind, size_bytes=size, original_name=original_name[:512]
    )
    session.add(upload)
    try:
        session.commit()
    except BaseException:
        session.rollback()
        path.unlink(missing_ok=True)
        raise
    return upload


def list_uploads(session: Session, thread_id: UUID) -> list[Upload]:
    return list(
        session.scalars(select(Upload).where(Upload.thread_id == thread_id).order_by(Upload.created_at))
    )


def get_upload(session: Session, upload_id: UUID) -> Upload | None:
    return session.get(Upload, upload_id)
