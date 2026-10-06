"""catalog-knowledge: title, section and date travel with a chunk; categories scope search."""

from __future__ import annotations

from datetime import date

import pytest
from sqlalchemy.orm import Session

from app import embedding
from app.db.chunk_store import (
    IncomingChunk,
    delete_page_chunks,
    search_hybrid,
    upsert_chunks,
)
from app.retrieval import search_knowledge

pytestmark = pytest.mark.usefixtures("clean_chunks")


def chunk(text: str, url: str, category: str, **kw) -> IncomingChunk:
    return IncomingChunk(
        content=text, embedding=embedding.embed_one(text), source_site=kw.pop("source_site", "toom"),
        url=url, category=category, chunk_index=kw.pop("index", 0), **kw,
    )


def test_a_guideline_chunk_keeps_its_title_section_and_date(db_session: Session, fake_embedder) -> None:
    upsert_chunks(db_session, [chunk(
        "Die lichte Raumhöhe von Aufenthaltsräumen muss mindestens 2,40 m betragen.",
        "https://example.invalid/bauo#43", "guideline", source_site="bauo-berlin",
        title="Bauordnung Berlin", section="§ 43 Aufenthaltsräume", published_on=date(2025, 1, 1),
    )])
    db_session.commit()
    hits = search_knowledge(
        db_session, "lichte Raumhöhe Aufenthaltsräume", categories=["guideline"], min_relevance=0.0
    )
    assert len(hits) == 1
    assert (hits[0].title, hits[0].section, hits[0].published_on) == (
        "Bauordnung Berlin", "§ 43 Aufenthaltsräume", date(2025, 1, 1),
    )


def test_categories_scope_a_search(db_session: Session, fake_embedder) -> None:
    upsert_chunks(db_session, [
        chunk("Siebdruckplatte 15 mm beschichtet", "https://toom.de/p/a/1", "product"),
        chunk("Siebdruckplatte Mindestbreite Durchgang 90 cm", "https://example.invalid/g", "guideline", index=0,
              source_site="owner"),
    ])
    db_session.commit()
    vector = embedding.embed_one("Siebdruckplatte")
    both = search_hybrid(db_session, vector, "Siebdruckplatte", limit=5)
    only = search_hybrid(db_session, vector, "Siebdruckplatte", limit=5, categories=["guideline"])
    assert {h.category for h in both} == {"product", "guideline"}
    assert {h.category for h in only} == {"guideline"}


def test_deleting_a_page_removes_every_chunk_of_it(db_session: Session, fake_embedder) -> None:
    url = "https://example.invalid/note"
    upsert_chunks(db_session, [chunk("one", url, "guideline", index=0), chunk("two", url, "guideline", index=1)])
    db_session.commit()
    assert delete_page_chunks(db_session, url) == 2


def test_the_fake_embedder_is_deterministic_and_normalised(fake_embedder) -> None:
    a, b = embedding.embed(["Möbelbauplatte beschichtet", "Möbelbauplatte beschichtet"])
    assert a == b
    assert sum(v * v for v in a) == pytest.approx(1.0)


def test_without_an_installed_embedder_the_real_model_is_what_would_load() -> None:
    assert embedding._override is None
