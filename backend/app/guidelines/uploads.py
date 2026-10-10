"""Guideline PDFs uploaded from the developer panel (dev-panel-insights).

The checked-in source list stays the list; an uploaded PDF is recorded in
`guideline_uploads` and becomes one more file source (`upload-<sha12>`, stored as
`pdf/upload-<sha12>.pdf` under the gitignored guidelines folder), so the CLI and the
panel ingest the same set. An upload is refused, naming the problem, when it is not
a PDF by its content, is over the cap, has no readable text, or repeats a source.
Ingesting it makes no network request.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Final

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.chunk_store import delete_page_chunks
from app.db.models import GuidelineUpload
from app.guidelines.ingest import ingest_guidelines, pdf_text
from app.guidelines.sources import GuidelineSource

PDF_MAGIC: Final = b"%PDF-"
UPLOAD_PREFIX: Final = "upload-"


class UploadRefused(ValueError):
    """An upload that cannot become a source; `field` names what is wrong."""

    def __init__(self, field: str, reason: str) -> None:
        super().__init__(reason)
        self.field = field
        self.reason = reason


@dataclass(frozen=True)
class UploadIn:
    title: str
    jurisdiction: str
    published_on: date
    licence: str


def source_of(upload: GuidelineUpload) -> GuidelineSource:
    """The uploaded file as a file source of the corpus."""
    return GuidelineSource(
        id=upload.id, title=upload.title, jurisdiction=upload.jurisdiction, path=upload.file_name,
        format="pdf", published_on=upload.published_on, licence=upload.licence,
    )


def uploaded_sources(session: Session) -> list[GuidelineSource]:
    return [source_of(upload) for upload in session.scalars(select(GuidelineUpload).order_by(GuidelineUpload.created_at))]


def accept_upload(
    session: Session, root: Path, content: bytes, meta: UploadIn, *, max_bytes: int, known_ids: frozenset[str]
) -> GuidelineUpload:
    """Check, store and record an upload; the caller ingests it. Raises `UploadRefused`."""
    if not content.startswith(PDF_MAGIC):
        raise UploadRefused("file", "the file is not a PDF")
    if len(content) > max_bytes:
        raise UploadRefused("file", f"the file is larger than {max_bytes} bytes")
    for field, value in (("title", meta.title), ("jurisdiction", meta.jurisdiction), ("licence", meta.licence)):
        if not value.strip():
            raise UploadRefused(field, f"{field} is required")
    digest = hashlib.sha256(content).hexdigest()
    existing = session.scalars(select(GuidelineUpload).where(GuidelineUpload.sha256 == digest)).first()
    if existing is not None:
        raise UploadRefused("file", f"the same file is already the source {existing.id!r} ({existing.title})")
    upload_id = f"{UPLOAD_PREFIX}{digest[:12]}"
    if upload_id in known_ids:
        raise UploadRefused("file", f"a source with the id {upload_id!r} is already listed")
    try:
        text = pdf_text(content)
    except Exception:  # noqa: BLE001 - any parser failure is an unreadable upload
        raise UploadRefused("file", "the PDF cannot be read") from None
    if not text.strip():
        raise UploadRefused("file", "the PDF has no readable text")
    file_name = f"pdf/{upload_id}.pdf"
    target = root / file_name
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(content)
    upload = GuidelineUpload(
        id=upload_id, title=meta.title.strip(), jurisdiction=meta.jurisdiction.strip(),
        published_on=meta.published_on, licence=meta.licence.strip(), file_name=file_name, sha256=digest,
        size_bytes=len(content),
    )
    session.add(upload)
    session.flush()
    return upload


def ingest_upload(session: Session, root: Path, upload: GuidelineUpload) -> None:
    """Ingest one uploaded source and record the outcome on its row; never raises."""
    report = ingest_guidelines(session, None, [source_of(upload)], root=root)
    if upload.id in report.ingested:
        upload.ingested_at, upload.error = datetime.now(UTC), None
    else:
        upload.ingested_at = None
        upload.error = "; ".join(report.failures) or "not ingested"
    session.add(upload)
    session.commit()


def delete_upload(session: Session, root: Path, upload: GuidelineUpload) -> None:
    """Remove an uploaded source: its passages, its file and its row."""
    delete_page_chunks(session, source_of(upload).location)
    (root / upload.file_name).unlink(missing_ok=True)
    session.delete(upload)
    session.commit()
