"""Writing a page's text into the corpus (chunked, embedded, attributed)."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.db.chunk_store import IncomingChunk, replace_page_chunks
from app.embedding import embed
from app.ingestion.extract import chunk_text


def index_page(
    session: Session,
    url: str,
    title: str,
    text: str,
    *,
    source_site: str = "toom",
    category: str = "product",
    section: str | None = None,
    scraped_at: datetime | None = None,
) -> int:
    """(Re)write the chunks of one page; returns how many it now has. Flushes only."""
    pieces = chunk_text(text) if text.strip() else []
    vectors = embed(pieces) if pieces else []
    when = scraped_at or datetime.now(UTC)
    incoming = [
        IncomingChunk(
            content=piece, embedding=vector, source_site=source_site, url=url, category=category,
            chunk_index=index, scraped_at=when, title=title[:300] or None, section=section,
        )
        for index, (piece, vector) in enumerate(zip(pieces, vectors, strict=True))
    ]
    replace_page_chunks(session, url, incoming, page_length=len(incoming))
    return len(incoming)
