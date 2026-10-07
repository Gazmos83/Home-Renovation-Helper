"""Files the owner attaches to a conversation (plan-uploads): images, design files and notes.

A design file is a UTF-8 JSON object whose `kind` is `custom_build` or
`package_import` (design-import); it is never sent to a model. A note is any other
UTF-8 text with no control character but tab, line feed and carriage return
(studio-chat-polish); text that opens like JSON must be a design file. The bytes live in a file under the upload root, named by the upload's id; the
database holds only metadata and conversation state holds only the id. The type
comes from the file's own bytes, never from its name or declared type.
"""

from __future__ import annotations

import codecs
import json
import logging
import os
import unicodedata
from pathlib import Path
from typing import BinaryIO, Final
from uuid import UUID, uuid4

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import Upload

logger = logging.getLogger("app")

CHUNK_BYTES: Final = 1024 * 1024
EXTENSIONS: Final = {"png": "png", "jpeg": "jpg", "design": "json", "text": "md"}
MEDIA_TYPES: Final = {
    "png": "image/png",
    "jpeg": "image/jpeg",
    "design": "application/json",
    "text": "text/plain; charset=utf-8",
}
IMAGE_KINDS: Final = ("png", "jpeg")
DESIGN_KINDS: Final = ("custom_build", "package_import")
UNSUPPORTED: Final = (
    "only PNG and JPEG images, design files (.json) and Markdown or plain-text notes are accepted"
)
_ALLOWED_CONTROLS: Final = frozenset("\t\n\r")


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


def _clean_text(text: str) -> bool:
    return not any(c not in _ALLOWED_CONTROLS and unicodedata.category(c) == "Cc" for c in text)


def is_text(data: bytes, *, complete: bool = True) -> bool:
    """Whether `data` is a note: strict UTF-8 with no control character but tab, LF and CR.
    With `complete=False`, `data` is a prefix and may end inside a character."""
    try:
        text = codecs.getincrementaldecoder("utf-8")().decode(data, final=complete)
    except UnicodeDecodeError:
        return False
    return _clean_text(text)


def classify(head: bytes, rest: bytes = b"") -> str | None:
    """The kind of a whole file from its bytes: `png`, `jpeg`, `design`, `text`, or `None`."""
    data = head + rest
    kind = sniff(data)
    if kind is not None:
        return kind
    if data.lstrip()[:1] in (b"{", b"["):
        return "design" if is_design(data) else None
    return "text" if is_text(data) else None


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
    max_note_bytes: int = 256 * 1024,
) -> tuple[str, int, Path]:
    """Copy `stream` to its file; returns `(kind, size, path)`.

    An image is copied in chunks up to `max_bytes`. Anything else is read whole,
    up to the larger of the design and note caps, and kept only if it is a design
    file or a note within its own cap. No file is left behind on any refusal.
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

    too_large_design = UploadRefused(413, f"the design file is larger than {max_design_bytes // 1024} KiB")
    too_large_note = UploadRefused(413, f"the note is larger than {max_note_bytes // 1024} KiB")
    limit = max(max_design_bytes, max_note_bytes)
    data = head
    while len(data) <= limit:
        chunk = stream.read(CHUNK_BYTES)
        if not chunk:
            break
        data += chunk
    opening = data.lstrip()[:1]
    if len(data) > limit:
        # Too long to check whole: a JSON object is a design file over its cap, clean
        # text a note over its cap, and anything else is refused.
        if opening == b"{":
            raise too_large_design
        if opening != b"[" and is_text(data[: limit + 1], complete=False):
            raise too_large_note
        raise UploadRefused(415, UNSUPPORTED)
    kind = classify(data)
    if kind is None:
        raise UploadRefused(415, UNSUPPORTED)
    if kind == "design" and len(data) > max_design_bytes:
        raise too_large_design
    if kind == "text" and len(data) > max_note_bytes:
        raise too_large_note
    path = upload_path(root, thread_id, upload_id, kind)
    return kind, _write_atomically(path, [data]), path


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
    max_note_bytes: int = 256 * 1024,
) -> Upload:
    """Store one image, design file or note for a thread and record it; commits."""
    count = session.scalar(select(func.count()).select_from(Upload).where(Upload.thread_id == thread_id))
    if (count or 0) >= max_per_thread:
        raise UploadRefused(409, f"a conversation holds at most {max_per_thread} uploads")
    upload_id = uuid4()
    kind, size, path = write_upload(
        root,
        thread_id,
        upload_id,
        stream,
        max_bytes=max_bytes,
        max_design_bytes=max_design_bytes,
        max_note_bytes=max_note_bytes,
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
