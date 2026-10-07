"""Files the owner attaches to a conversation (plan-uploads): images and design files.

A design file is a UTF-8 JSON object whose `kind` is `custom_build` or
`package_import` (design-import); it is never sent to a model. The bytes live in a file under the upload root, named by the upload's id; the
database holds only metadata and conversation state holds only the id. The type
comes from the file's own bytes, never from its name or declared type.
"""

from __future__ import annotations

import json
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
EXTENSIONS: Final = {"png": "png", "jpeg": "jpg", "design": "json"}
MEDIA_TYPES: Final = {"png": "image/png", "jpeg": "image/jpeg", "design": "application/json"}
IMAGE_KINDS: Final = ("png", "jpeg")
DESIGN_KINDS: Final = ("custom_build", "package_import")
UNSUPPORTED: Final = "only PNG and JPEG images and design files (.json) are accepted"


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


def is_design(data: bytes) -> bool:
    """Whether `data` is a design file: strict UTF-8, one JSON object of a design kind."""
    try:
        document = json.loads(data.decode("utf-8"))
    except (UnicodeDecodeError, ValueError):
        return False
    return isinstance(document, dict) and document.get("kind") in DESIGN_KINDS


def upload_path(root: Path, thread_id: UUID, upload_id: UUID, kind: str) -> Path:
    return root / str(thread_id) / f"{upload_id}.{EXTENSIONS[kind]}"


def _write_atomically(path: Path, chunks) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    partial = path.with_suffix(path.suffix + ".part")
    size = 0
    try:
        with partial.open("wb") as handle:
            for chunk in chunks:
                size += len(chunk)
                handle.write(chunk)
        os.replace(partial, path)
    except BaseException:
        partial.unlink(missing_ok=True)
        raise
    return size


def write_upload(
    root: Path,
    thread_id: UUID,
    upload_id: UUID,
    stream: BinaryIO,
    *,
    max_bytes: int,
    max_design_bytes: int,
) -> tuple[str, int, Path]:
    """Copy `stream` to its file; returns `(kind, size, path)`.

    An image is copied in chunks up to `max_bytes`. Anything else is read up to
    `max_design_bytes` and kept only if it is a design file. No file is left
    behind on any refusal.
    """
    head = stream.read(CHUNK_BYTES)
    kind = sniff(head)
    if kind is not None:

        def chunks():
            chunk, size = head, 0
            while chunk:
                size += len(chunk)
                if size > max_bytes:
                    raise UploadRefused(413, f"the image is larger than {max_bytes // (1024 * 1024)} MiB")
                yield chunk
                chunk = stream.read(CHUNK_BYTES)

        path = upload_path(root, thread_id, upload_id, kind)
        return kind, _write_atomically(path, chunks()), path

    data = head
    while len(data) <= max_design_bytes:
        chunk = stream.read(CHUNK_BYTES)
        if not chunk:
            break
        data += chunk
    if len(data) > max_design_bytes:
        # Too long to check whole: a JSON object is a design file over its cap, anything else is refused.
        if data.lstrip()[:1] != b"{":
            raise UploadRefused(415, UNSUPPORTED)
        raise UploadRefused(413, f"the design file is larger than {max_design_bytes // 1024} KiB")
    if not is_design(data):
        raise UploadRefused(415, UNSUPPORTED)
    path = upload_path(root, thread_id, upload_id, "design")
    return "design", _write_atomically(path, [data]), path


def add_upload(
    session: Session,
    root: Path,
    thread_id: UUID,
    stream: BinaryIO,
    *,
    original_name: str,
    max_bytes: int,
    max_per_thread: int,
    max_design_bytes: int = 256 * 1024,
) -> Upload:
    """Store one image or design file for a thread and record it; commits."""
    count = session.scalar(select(func.count()).select_from(Upload).where(Upload.thread_id == thread_id))
    if (count or 0) >= max_per_thread:
        raise UploadRefused(409, f"a conversation holds at most {max_per_thread} uploads")
    upload_id = uuid4()
    kind, size, path = write_upload(
        root, thread_id, upload_id, stream, max_bytes=max_bytes, max_design_bytes=max_design_bytes
    )
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
