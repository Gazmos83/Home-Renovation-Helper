"""Reads and writes for the catalog knowledge store.

All access to `chunks` goes through here. Nothing in this module accepts SQL
from a caller, and nothing interprets chunk content — content is data, never
instructions (CLAUDE.md §8).
"""

from __future__ import annotations

import hashlib
from collections.abc import Collection, Iterable, Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime
from typing import Final

from sqlalchemy import Select, delete, func, literal_column, select, text, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.db.models import EMBEDDING_DIMENSIONS, FTS_CONFIG, Chunk


class ChunkValidationError(ValueError):
    """An incoming chunk cannot be stored as given."""


@dataclass(frozen=True, slots=True)
class IncomingChunk:
    content: str
    embedding: Sequence[float]
    source_site: str
    url: str
    category: str
    chunk_index: int
    scraped_at: datetime | None = None
    # Where in a long document the passage sits (guidelines): title, section, date.
    title: str | None = None
    section: str | None = None
    published_on: date | None = None


@dataclass(frozen=True, slots=True)
class SearchHit:
    """A result detached from ORM identity, so callers cannot mutate stored rows."""

    id: int
    content: str
    source_site: str
    url: str
    category: str
    chunk_index: int
    scraped_at: datetime
    title: str | None
    section: str | None
    published_on: date | None
    similarity: float


_SELECTED = (
    Chunk.id,
    Chunk.content,
    Chunk.source_site,
    Chunk.url,
    Chunk.category,
    Chunk.chunk_index,
    Chunk.scraped_at,
    Chunk.title,
    Chunk.section,
    Chunk.published_on,
)


def _validate_width(embedding: Sequence[float]) -> None:
    if len(embedding) != EMBEDDING_DIMENSIONS:
        raise ChunkValidationError(
            f"embedding has {len(embedding)} dimensions, "
            f"expected {EMBEDDING_DIMENSIONS}"
        )


def _validate(chunk: IncomingChunk) -> None:
    """Validated before any row is written, so a bad chunk leaves nothing behind."""
    if not chunk.url or not chunk.url.strip():
        raise ChunkValidationError("url is required: retrieval must be able to cite it")
    if not chunk.source_site or not chunk.source_site.strip():
        raise ChunkValidationError("source_site is required")
    if not chunk.category or not chunk.category.strip():
        raise ChunkValidationError("category is required")
    if chunk.chunk_index < 0:
        raise ChunkValidationError("chunk_index must not be negative")
    _validate_width(chunk.embedding)


@dataclass(frozen=True)
class UpsertResult:
    """How many rows were new and how many refreshed an existing row.

    A run needs the split, not the total: it is the only way to tell a first
    ingestion from a re-run over unchanged pages without counting the table
    before and after.
    """

    created: int = 0
    updated: int = 0

    @property
    def total(self) -> int:
        return self.created + self.updated

    def __int__(self) -> int:
        return self.total

    def __eq__(self, other: object) -> bool:
        # Day-1 callers compare against a plain row count.
        if isinstance(other, int):
            return self.total == other
        return NotImplemented

    def __hash__(self) -> int:
        return hash((self.created, self.updated))


def upsert_chunks(session: Session, chunks: Iterable[IncomingChunk]) -> UpsertResult:
    """Insert or refresh chunks, keyed on (url, chunk_index).

    Re-ingesting a page updates its chunks in place rather than duplicating
    them, so running ingestion twice over unchanged content is a no-op.
    """
    incoming = list(chunks)
    for chunk in incoming:
        _validate(chunk)
    if not incoming:
        return UpsertResult()

    now = datetime.now(UTC)
    rows = [
        {
            "content": chunk.content,
            "embedding": list(chunk.embedding),
            "source_site": chunk.source_site,
            "url": chunk.url,
            "category": chunk.category,
            "chunk_index": chunk.chunk_index,
            "scraped_at": chunk.scraped_at or now,
            "title": chunk.title,
            "section": chunk.section,
            "published_on": chunk.published_on,
            "content_hash": content_hash(chunk.content),
        }
        for chunk in incoming
    ]

    statement = insert(Chunk).values(rows)
    statement = statement.on_conflict_do_update(
        constraint="uq_chunks_url_chunk_index",
        set_={
            "content": statement.excluded.content,
            "embedding": statement.excluded.embedding,
            "source_site": statement.excluded.source_site,
            "category": statement.excluded.category,
            "scraped_at": statement.excluded.scraped_at,
            "title": statement.excluded.title,
            "section": statement.excluded.section,
            "published_on": statement.excluded.published_on,
            "content_hash": statement.excluded.content_hash,
        },
    )
    # `xmax = 0` is true only for a row this statement inserted; an updated
    # row carries the transaction id that superseded it. It is the standard
    # way to split an upsert's outcome without a second query.
    statement = statement.returning(text("(xmax = 0) AS inserted"))
    outcomes = [bool(row[0]) for row in session.execute(statement)]
    created = sum(outcomes)
    return UpsertResult(created=created, updated=len(outcomes) - created)


def content_hash(content: str) -> str:
    """SHA-256 of a chunk's text: what a re-run compares, and a reportable corpus fact."""
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def stored_page_hashes(session: Session, url: str) -> dict[int, str | None]:
    rows = session.execute(select(Chunk.chunk_index, Chunk.content_hash).where(Chunk.url == url))
    return {int(index): value for index, value in rows}


def stored_page_contents(session: Session, url: str) -> dict[int, str]:
    """The text currently stored for `url`, by chunk index.

    What a refresh compares against before embedding anything: a chunk whose
    text is unchanged keeps its vector, so an unchanged page costs no model
    time and no index write.
    """
    rows = session.execute(
        select(Chunk.chunk_index, Chunk.content).where(Chunk.url == url)
    )
    return {int(index): content for index, content in rows}


def refresh_page_chunks(
    session: Session, url: str, chunk_indices: Collection[int], scraped_at: datetime
) -> int:
    """Record that these unchanged chunks were seen again, without rewriting them.

    Freshness is separate from content: `scraped_at` says when the page last
    said this, and must advance on a re-run even when nothing else does.
    Returns how many rows were refreshed.
    """
    indices = sorted(set(chunk_indices))
    if not indices:
        return 0
    result = session.execute(
        update(Chunk)
        .where(Chunk.url == url, Chunk.chunk_index.in_(indices))
        # A chunk stored before hashes existed gains one when seen unchanged.
        .values(
            scraped_at=scraped_at,
            content_hash=func.coalesce(
                Chunk.content_hash,
                func.encode(func.sha256(func.convert_to(Chunk.content, "UTF8")), "hex"),
            ),
        )
    )
    return int(result.rowcount or 0)


def replace_page_chunks(
    session: Session,
    url: str,
    chunks: Iterable[IncomingChunk],
    *,
    page_length: int | None = None,
) -> UpsertResult:
    """Write `chunks` for `url` and drop whatever lies past the page's end.

    Upserting alone is not enough. Chunks are keyed on (url, chunk_index), so
    if a page now yields four chunks where it once yielded six, indices four
    and five keep their old content forever — retrievable, attributed to a
    page that no longer says it. Anything past the new end is deleted in the
    same transaction.

    `page_length` is how many chunks the page has now. It defaults to the
    number supplied, which is right when every chunk is written; a caller
    that writes only the changed chunks must pass the full count, or the
    unchanged tail would be deleted as obsolete.
    """
    incoming = list(chunks)
    result = upsert_chunks(session, incoming)
    end = len(incoming) if page_length is None else page_length
    session.execute(delete(Chunk).where(Chunk.url == url, Chunk.chunk_index >= end))
    return result


def similar_statement(
    embedding: Sequence[float],
    *,
    limit: int = 5,
    sources: Collection[str] | None = None,
    min_similarity: float | None = None,
) -> Select:
    """The similarity query, ordered by the operator the HNSW index was built on.

    Exposed separately so a test can EXPLAIN the statement the store actually
    runs, rather than a hand-written imitation of it.
    """
    _validate_width(embedding)

    distance = Chunk.embedding.cosine_distance(embedding)
    statement = select(*_SELECTED, (1 - distance).label("similarity"))
    if sources is not None:
        statement = statement.where(Chunk.source_site.in_(list(sources)))
    if min_similarity is not None:
        statement = statement.where((1 - distance) >= min_similarity)
    return statement.order_by(distance).limit(limit)


def keyword_statement(
    query: str,
    *,
    limit: int = 5,
    sources: Collection[str] | None = None,
    categories: Collection[str] | None = None,
) -> Select:
    """The keyword query, using the configuration the stored column was built with.

    The configuration is inlined as a literal because it is a module constant,
    never caller input, and because a bound REGCONFIG parameter cannot be
    rendered for EXPLAIN. A different configuration here would silently bypass
    the GIN index.
    """
    tsquery = func.plainto_tsquery(literal_column(f"'{FTS_CONFIG}'"), query)
    rank = func.ts_rank(Chunk.search_vector, tsquery)

    statement = select(*_SELECTED, rank.label("similarity")).where(
        Chunk.search_vector.bool_op("@@")(tsquery)
    )
    if sources is not None:
        statement = statement.where(Chunk.source_site.in_(list(sources)))
    if categories is not None:
        statement = statement.where(Chunk.category.in_(list(categories)))
    return statement.order_by(rank.desc()).limit(limit)


# How much each basis contributes to a combined score. Vector similarity leads
# because the corpus is German and questions arrive in either language, where
# keyword matching contributes nothing; keyword matching earns its share on
# exact tokens — an article number, a dimension, an R-rating — that embeddings
# blur together.
VECTOR_WEIGHT: Final = 0.7
KEYWORD_WEIGHT: Final = 0.3


def hybrid_statement(
    embedding: Sequence[float],
    query: str,
    *,
    limit: int = 5,
    sources: Collection[str] | None = None,
    categories: Collection[str] | None = None,
    vector_weight: float = VECTOR_WEIGHT,
    keyword_weight: float = KEYWORD_WEIGHT,
) -> Select:
    """One statement scoring both bases, so the caller gets one ranked set.

    A chunk qualifies on either basis: semantically near the question, or
    carrying its exact terms. Merging two result sets in application code
    would put the ranking outside the store, where it could not be tested at
    this boundary.

    Deliberate trade-off: the OR across two different access paths means the
    planner may scan rather than use either index. On a corpus this size that
    costs milliseconds, and the separate similarity and keyword searches — the
    ones that must stay index-backed as the corpus grows — are unaffected.
    """
    _validate_width(embedding)

    tsquery = func.plainto_tsquery(literal_column(f"'{FTS_CONFIG}'"), query)
    similarity = 1 - Chunk.embedding.cosine_distance(embedding)
    rank = func.ts_rank(Chunk.search_vector, tsquery)
    score = (similarity * vector_weight) + (rank * keyword_weight)

    statement = select(*_SELECTED, score.label("similarity")).where(
        Chunk.search_vector.bool_op("@@")(tsquery) | (similarity > 0)
    )
    if sources is not None:
        statement = statement.where(Chunk.source_site.in_(list(sources)))
    if categories is not None:
        statement = statement.where(Chunk.category.in_(list(categories)))
    return statement.order_by(score.desc()).limit(limit)


def search_hybrid(
    session: Session,
    embedding: Sequence[float],
    query: str,
    *,
    limit: int = 5,
    sources: Collection[str] | None = None,
    categories: Collection[str] | None = None,
) -> list[SearchHit]:
    """Chunks matching by meaning or by exact term, in one ranked set."""
    statement = hybrid_statement(
        embedding, query, limit=limit, sources=sources, categories=categories
    )
    return [SearchHit(*row) for row in session.execute(statement)]


def search_similar(
    session: Session,
    embedding: Sequence[float],
    *,
    limit: int = 5,
    sources: Collection[str] | None = None,
    min_similarity: float | None = None,
) -> list[SearchHit]:
    """Nearest chunks by cosine similarity, most similar first.

    An empty result is a successful search that found nothing, not an error.
    """
    statement = similar_statement(
        embedding, limit=limit, sources=sources, min_similarity=min_similarity
    )
    return [SearchHit(*row) for row in session.execute(statement)]


def search_keyword(
    session: Session,
    query: str,
    *,
    limit: int = 5,
    sources: Collection[str] | None = None,
) -> list[SearchHit]:
    """Chunks matching `query` by keyword, best-ranked first."""
    statement = keyword_statement(query, limit=limit, sources=sources)
    return [SearchHit(*row) for row in session.execute(statement)]


def delete_page_chunks(session: Session, url: str) -> int:
    """Remove every chunk of one page (a deleted snapshot or note)."""
    result = session.execute(delete(Chunk).where(Chunk.url == url))
    return int(result.rowcount or 0)


def count_chunks(session: Session, *, url: str | None = None) -> int:
    statement = select(func.count()).select_from(Chunk)
    if url is not None:
        statement = statement.where(Chunk.url == url)
    return int(session.execute(statement).scalar_one())


def source_sites(session: Session) -> list[str]:
    """Every source that currently holds at least one chunk (index-backed)."""
    statement = select(Chunk.source_site).distinct()
    return [row[0] for row in session.execute(statement)]
