"""price-list: manual snapshots — recorded, searchable, optionally prefilling an entry."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

import pytest
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.db.chunk_store import count_chunks
from app.pricing import price_list, snapshots
from app.pricing.errors import Refused
from app.pricing.snapshots import Prefill, SnapshotConflict, SnapshotIn
from app.retrieval import search_knowledge
from tests.pricing_helpers import clean_pricing

URL = "https://www.bauhaus.info/p/siebdruckplatte-15mm/123"


def today() -> date:
    """The UTC date the module itself judges a snapshot's date against."""
    return datetime.now(UTC).date()


@pytest.fixture
def session(migrated_database: str, fake_embedder):
    from app.db.session import make_engine

    engine = make_engine(migrated_database)
    clean_pricing(engine)
    with Session(engine) as s:
        yield s
        s.rollback()
    clean_pricing(engine)
    engine.dispose()


def data(**over) -> SnapshotIn:
    values = {
        "retailer": "bauhaus", "url": URL, "product_name": "Siebdruckplatte 15 mm", "price": Decimal("49.90"),
        "currency": "EUR", "availability": "im Markt", "specification": "2500 x 1250 x 15 mm, Birke",
        "captured_on": today() - timedelta(days=1),
    }
    values.update(over)
    return SnapshotIn(**values)


def test_a_snapshot_is_recorded_and_searchable_as_a_dated_passage(session) -> None:
    row = snapshots.record_snapshot(session, data(), recorded_by=None)
    session.commit()
    assert row.retailer == "bauhaus" and row.price == Decimal("49.90")
    hits = search_knowledge(session, "Siebdruckplatte 15 mm Birke", min_relevance=0.0, categories=["manual_snapshot"])
    assert hits and hits[0].url == URL and hits[0].source_site == "bauhaus"
    assert "captured on" in hits[0].content


def test_a_snapshot_never_enables_crawling_for_its_retailer() -> None:
    from app.config import Settings

    settings = Settings(
        database_url="postgresql://u:p@h/d", openrouter_api_key="k", cors_origins="http://x",
        owner_email="o@example.com", owner_password="an-initial-owner-password", _env_file=None,
    )
    assert not settings.source_enabled("bauhaus")


def test_a_snapshot_can_prefill_a_snapshot_entry(session) -> None:
    row = snapshots.record_snapshot(
        session, data(), recorded_by=None,
        prefill=Prefill(key="panel:sieb-15", category="panel", unit="per_piece",
                        sheet_length_mm=2500, sheet_width_mm=1250, thickness_mm=15),
    )
    session.commit()
    entry = price_list.get_entry(session, "panel:sieb-15")
    assert (entry.provenance, entry.base_cents, entry.snapshot_id) == ("snapshot", 4990, row.id)
    assert entry.source_url == URL


def test_a_refused_prefill_leaves_no_snapshot_behind(session) -> None:
    with pytest.raises(Refused, match="sheet length"):
        snapshots.record_snapshot(
            session, data(), recorded_by=None,
            prefill=Prefill(key="panel:bad", category="panel", unit="per_piece"),
        )
    session.rollback()
    assert snapshots.list_snapshots(session) == []
    assert count_chunks(session, url=URL) == 0


def test_a_prefill_needs_a_price(session) -> None:
    with pytest.raises(Refused, match="needs a price"):
        snapshots.record_snapshot(
            session, data(price=None), recorded_by=None,
            prefill=Prefill(key="hw:x", category="hardware", unit="per_piece"),
        )


def test_a_future_date_is_refused() -> None:
    with pytest.raises(ValidationError, match="must not be in the future"):
        data(captured_on=today() + timedelta(days=1))


@pytest.mark.parametrize(
    ("field", "value"),
    [("retailer", "Bad Slug"), ("url", "ftp://x/y"), ("product_name", " "), ("price", Decimal(-1)), ("currency", "eur")],
)
def test_a_bad_field_is_refused_by_name(field, value) -> None:
    with pytest.raises(ValidationError) as caught:
        data(**{field: value})
    assert field in str(caught.value)


def test_a_url_holding_crawled_content_cannot_be_overwritten(session) -> None:
    from app.db.chunk_store import IncomingChunk, upsert_chunks
    from app.embedding import embed_one

    upsert_chunks(session, [IncomingChunk(
        content="crawled", embedding=embed_one("crawled"), source_site="toom", url=URL, category="product",
        chunk_index=0,
    )])
    with pytest.raises(SnapshotConflict):
        snapshots.record_snapshot(session, data(), recorded_by=None)


def test_re_recording_replaces_the_chunks_but_keeps_both_rows_and_deleting_the_newer_restores_the_older(session) -> None:
    older = snapshots.record_snapshot(session, data(specification="Birke 15 mm alt"), recorded_by=None)
    newer = snapshots.record_snapshot(session, data(specification="Birke 15 mm neu", captured_on=today()), recorded_by=None)
    session.commit()
    assert len(snapshots.list_snapshots(session)) == 2
    hit = search_knowledge(session, "Birke neu", min_relevance=0.0, categories=["manual_snapshot"])[0]
    assert "neu" in hit.content
    snapshots.delete_snapshot(session, newer.id)
    session.commit()
    assert [s.id for s in snapshots.list_snapshots(session)] == [older.id]
    hit = search_knowledge(session, "Birke alt", min_relevance=0.0, categories=["manual_snapshot"])[0]
    assert "alt" in hit.content


def test_deleting_the_only_snapshot_drops_its_chunks(session) -> None:
    row = snapshots.record_snapshot(session, data(), recorded_by=None)
    snapshots.delete_snapshot(session, row.id)
    session.commit()
    assert count_chunks(session, url=URL) == 0


def test_a_snapshot_an_entry_was_made_from_cannot_be_deleted(session) -> None:
    row = snapshots.record_snapshot(
        session, data(), recorded_by=None, prefill=Prefill(key="hw:snap", category="hardware", unit="per_piece"),
    )
    session.commit()
    with pytest.raises(Refused, match="'hw:snap' was made from this snapshot"):
        snapshots.delete_snapshot(session, row.id)
