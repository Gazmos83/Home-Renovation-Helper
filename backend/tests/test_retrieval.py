"""catalog-knowledge-store: combined search, cross-language retrieval, thresholds.

The combined-search and threshold tests use fixed vectors so they are fast and
deterministic. The cross-language tests are marked `slow`: they embed real
questions with the real model, because "an English question reaches a German
answer" cannot be demonstrated with synthetic vectors.
"""

from __future__ import annotations

import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.db.chunk_store import (
    IncomingChunk,
    search_hybrid,
    upsert_chunks,
)
from conftest import embedding

pytestmark = pytest.mark.usefixtures("clean_chunks")

URL = "https://toom.de/c/bauen-renovieren/holz/moebelbauplatten"


def chunk(content: str, *, seed: int, index: int) -> IncomingChunk:
    return IncomingChunk(
        content=content,
        embedding=embedding(seed),
        source_site="toom",
        url=URL,
        category="catalog",
        chunk_index=index,
    )


@pytest.fixture
def corpus(db_session: Session) -> Session:
    upsert_chunks(
        db_session,
        [
            chunk("Möbelbauplatte beschichtet 2630 x 400 x 19 mm", seed=1, index=0),
            chunk("Siebdruckplatte Art. SDP1250 beschichtet", seed=2, index=1),
            chunk("Paketversand ab 5,95 Euro, ab 59 Euro kostenfrei", seed=3, index=2),
        ],
    )
    db_session.commit()
    return db_session


# --- combined search --------------------------------------------------------


def test_a_combined_search_returns_one_ranked_set(corpus: Session) -> None:
    hits = search_hybrid(corpus, embedding(1), "Möbelbauplatte beschichtet", limit=5)

    assert hits, "a query matching on both bases must return results"
    scores = [hit.similarity for hit in hits]
    assert scores == sorted(scores, reverse=True), "one set, ranked"


def test_a_chunk_matching_only_on_keywords_is_eligible(corpus: Session) -> None:
    """An exact article number must surface even from a distant vector."""
    hits = search_hybrid(corpus, embedding(999), "SDP1250", limit=5)

    assert any("SDP1250" in hit.content for hit in hits)


def test_a_chunk_matching_only_on_meaning_is_eligible(corpus: Session) -> None:
    """No shared term, but the nearest vector still qualifies."""
    hits = search_hybrid(corpus, embedding(1), "xyzzy-nonexistent-term", limit=5)

    assert hits, "absence of keyword matches is not an error"
    assert hits[0].url == URL


def test_a_combined_search_matching_nothing_returns_empty(db_session: Session) -> None:
    hits = search_hybrid(db_session, embedding(1), "Schokoladenkuchen", limit=5)

    assert hits == []


def test_combined_results_carry_provenance(corpus: Session) -> None:
    hits = search_hybrid(corpus, embedding(1), "Möbelbauplatte", limit=1)

    hit = hits[0]
    assert hit.source_site == "toom"
    assert hit.url == URL
    assert hit.category == "catalog"
    assert hit.scraped_at is not None


def test_source_scoping_applies_to_combined_search(corpus: Session) -> None:
    assert search_hybrid(
        corpus, embedding(1), "Möbelbauplatte", sources=["obi"]
    ) == []


# --- against the real ingested corpus ---------------------------------------


def real_corpus_size(session: Session) -> int:
    return int(
        session.execute(
            text("SELECT count(*) FROM chunks WHERE source_site = 'toom'")
        ).scalar_one()
    )


@pytest.fixture
def ingested(migrated_database: str):
    """A session over the *dev* corpus, skipped when ingestion has not run."""
    import os

    from sqlalchemy.orm import Session as SessionType

    from app.db.session import make_engine

    url = os.environ.get(
        "DATABASE_URL", "postgresql://postgres:postgres@127.0.0.1:5432/interior_design"
    )
    engine = make_engine(url)
    with SessionType(engine) as session:
        if real_corpus_size(session) < 20:
            pytest.skip("no ingested corpus; run `python -m app.ingestion toom` first")
        yield session
    engine.dispose()


@pytest.mark.slow
def test_a_german_question_retrieves_attributed_toom_chunks(ingested: Session) -> None:
    from app.retrieval import search_knowledge

    hits = search_knowledge(ingested, "Was kostet die Lieferung nach Hause?", limit=5)

    assert hits, "the corpus covers delivery"
    scores = [hit.similarity for hit in hits]
    assert scores == sorted(scores, reverse=True)
    for hit in hits:
        assert hit.source_site == "toom"
        assert hit.url.startswith("https://")
        assert hit.scraped_at is not None


@pytest.mark.slow
def test_an_english_question_retrieves_german_content(ingested: Session) -> None:
    """The capability bge-m3 was chosen for, on scraped text.

    The question and the answering page share no vocabulary — keyword search
    cannot make this match.
    """
    from app.retrieval import search_knowledge

    hits = search_knowledge(ingested, "how much does delivery cost", limit=3)

    assert hits, "an English question must reach the German delivery pages"
    assert any(
        term in hit.content for hit in hits for term in ("Versand", "Liefer", "€")
    )


@pytest.mark.slow
def test_a_question_the_corpus_cannot_answer_returns_nothing(
    ingested: Session,
) -> None:
    """The threshold must hold the line, or the agent will invent an answer."""
    from app.retrieval import search_knowledge

    assert search_knowledge(ingested, "Rezept für Schokoladenkuchen") == []
    assert search_knowledge(ingested, "how do I center a div in CSS") == []


@pytest.mark.slow
def test_an_empty_question_retrieves_nothing_without_embedding(
    ingested: Session,
) -> None:
    from app.retrieval import search_knowledge

    assert search_knowledge(ingested, "   ") == []


# --- index usage at the new width -------------------------------------------
#
# `enable_seqscan = off` for the same reason day 1 used it: at a few hundred
# rows Postgres rightly prefers a sequential scan on cost, which says nothing
# about whether the index is usable. The question here is narrower and is the
# one the width migration puts at risk — after rebuilding HNSW at 1024
# dimensions, can the planner still use it for the distance operator the store
# orders by?


def plan_for(session: Session, statement: object) -> str:
    compiled = statement.compile(  # type: ignore[attr-defined]
        session.get_bind(), compile_kwargs={"literal_binds": True}
    )
    session.execute(text("SET LOCAL enable_seqscan = off"))
    return "\n".join(session.execute(text(f"EXPLAIN {compiled}")).scalars().all())


@pytest.mark.slow
def test_similarity_over_the_real_corpus_can_use_the_rebuilt_hnsw_index(
    ingested: Session,
) -> None:
    from app.db.chunk_store import similar_statement
    from app.embedding import embed_one

    plan = plan_for(ingested, similar_statement(embed_one("Möbelbauplatte"), limit=5))

    assert "ix_chunks_embedding_hnsw" in plan, plan


@pytest.mark.slow
def test_keyword_over_the_real_corpus_uses_the_full_text_index(
    ingested: Session,
) -> None:
    from app.db.chunk_store import keyword_statement

    plan = plan_for(ingested, keyword_statement("Versandkosten", limit=5))

    assert "ix_chunks_search_vector" in plan, plan
