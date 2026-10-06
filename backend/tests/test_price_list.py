"""price-list: entries, provenance, override, refresh, deletion."""

from __future__ import annotations

import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.db.models import CutListPricing, CutListPricingEntry
from app.pricing import capture, price_list
from app.pricing.errors import NotFound, Refused
from tests.pricing_helpers import clean_pricing, fixture, make_fetcher

PRODUCT = "/p/hartschaumplatte-eps-040-50-x-100-cm/3150333"
URL = f"https://toom.de{PRODUCT}"


@pytest.fixture
def session(migrated_database: str):
    from app.db.session import make_engine

    engine = make_engine(migrated_database)
    clean_pricing(engine)
    with Session(engine) as s:
        yield s
        s.rollback()
    clean_pricing(engine)
    engine.dispose()


def panel(session, key="panel:birch-18", **over):
    values = {
        "key": key, "label": "Birch plywood 18 mm", "category": "panel", "unit": "per_piece",
        "base_cents": 5990, "sheet_length_mm": 2500, "sheet_width_mm": 1250, "thickness_mm": 18,
    }
    values.update(over)
    return price_list.create_entry(session, **values)


def test_a_manual_entry_is_made_with_its_provenance(session) -> None:
    entry = price_list.create_entry(
        session, key="band:oak-22", label="Oak edge band 22 mm", category="edge_band", unit="per_metre",
        base_cents=120, bundle_length_mm=25_000,
    )
    assert entry.provenance == "manual" and entry.captured_at is None
    assert entry.effective_cents == 120 and entry.bundle_length_mm == 25_000


def test_a_panel_without_a_sheet_size_is_refused_naming_the_missing_dimension(session) -> None:
    with pytest.raises(Refused, match="sheet length, thickness"):
        price_list.create_entry(
            session, key="panel:x", label="x", category="panel", unit="per_piece", sheet_width_mm=1250
        )


@pytest.mark.parametrize(
    ("fields", "message"),
    [
        ({"key": " "}, "needs a key"),
        ({"label": ""}, "needs a label"),
        ({"category": "timber"}, "unknown category"),
        ({"unit": "per_pound"}, "unknown unit"),
        ({"base_cents": -1}, "euro cents"),
        ({"key": "Personal_Supply"}, "reserved"),
    ],
)
def test_bad_entries_are_refused(session, fields, message) -> None:
    values = {"key": "hw:hinge", "label": "Hinge", "category": "hardware", "unit": "per_piece", "base_cents": 250}
    values.update(fields)
    with pytest.raises(Refused, match=message):
        price_list.create_entry(session, **values)


def test_a_duplicate_key_is_refused(session) -> None:
    panel(session)
    with pytest.raises(Refused, match="already exists"):
        panel(session)


def test_an_override_shows_beside_the_base_price_and_clears(session) -> None:
    entry = panel(session)
    price_list.set_override(session, entry.key, cents=3500, note="my own price")
    described = price_list.describe(entry)
    assert (described["base_cents"], described["override_cents"], described["effective_cents"]) == (5990, 3500, 3500)
    assert described["override_note"] == "my own price" and described["provenance"] == "manual"
    price_list.clear_override(session, entry.key)
    assert price_list.describe(entry)["effective_cents"] == 5990


def test_listing_filters_by_category_and_refuses_an_unknown_one(session) -> None:
    panel(session)
    price_list.create_entry(session, key="hw:hinge", label="Hinge", category="hardware", unit="per_piece", base_cents=250)
    keys = [e.key for e in price_list.list_entries(session, category="hardware")]
    assert "hw:hinge" in keys and "panel:birch-18" not in keys
    with pytest.raises(Refused):
        price_list.list_entries(session, category="timber")


def test_revising_never_changes_the_key_category_or_provenance(session) -> None:
    entry = panel(session)
    price_list.revise_entry(session, entry.key, label="Birch ply 18", base_cents=6200, bundle_length_mm=None)
    assert (entry.label, entry.base_cents) == ("Birch ply 18", 6200)
    for field in ("key", "category", "provenance"):
        with pytest.raises(Refused, match="cannot be changed"):
            price_list.revise_entry(session, entry.key, **{field: "x"})
    with pytest.raises(Refused, match="only change its label"):
        price_list.revise_entry(session, "Personal_Supply", base_cents=5)


def test_refresh_changes_only_the_captured_price_and_never_the_override(session) -> None:
    fetcher, _ = make_fetcher({PRODUCT: (200, fixture("toom_product_3150333.html"))})
    with fetcher:
        entry = price_list.create_entry(
            session, key="foam:50x100", label="Foam board", category="finish", unit="per_piece", base_cents=3000,
            provenance="captured", source_url=URL,
        )
        price_list.set_override(session, entry.key, cents=2800)
        result = capture.refresh(session, fetcher, entry.key)
    assert result.outcome == "ok"
    assert (entry.base_cents, entry.override_cents, entry.effective_cents) == (3649, 2800, 2800)
    assert entry.captured_at is not None


def test_refreshing_a_manual_or_snapshot_entry_is_refused_as_having_no_source(session) -> None:
    entry = panel(session)
    fetcher, seen = make_fetcher({})
    with fetcher:
        result = capture.refresh(session, fetcher, entry.key)
    assert result.outcome == "no_source" and "no page to read" in result.reason
    assert seen == []


def test_a_refused_refresh_is_reported_and_leaves_the_price(session) -> None:
    fetcher, _ = make_fetcher({PRODUCT: (403, "denied")})
    with fetcher:
        entry = price_list.create_entry(
            session, key="foam:x", label="Foam", category="finish", unit="per_piece", base_cents=3000,
            provenance="captured", source_url=URL,
        )
        result = capture.refresh(session, fetcher, entry.key)
    assert result.outcome == "refused" and "403" in result.reason
    assert entry.base_cents == 3000


def test_an_entry_used_by_a_pricing_cannot_be_deleted_and_the_refusal_names_it(session) -> None:
    used = panel(session)
    spare = panel(session, key="panel:spare")
    session.execute(text(
        "INSERT INTO stores (store_key, source_site, name, url) VALUES ('s','toom','S','https://toom.de') "
        "ON CONFLICT DO NOTHING"
    ))
    pricing = CutListPricing(
        package_id="hall-bench", version=1, store_key="s", materials_cents=0, cut_service_cents=0,
        total_cents=0, complete=True, result={},
    )
    session.add(pricing)
    session.flush()
    session.add(CutListPricingEntry(pricing_id=pricing.id, entry_id=used.id, cents_used=5990))
    session.flush()
    with pytest.raises(Refused, match="hall-bench version 1"):
        price_list.delete_entry(session, used.key)
    price_list.delete_entry(session, spare.key)
    with pytest.raises(NotFound):
        price_list.get_entry(session, spare.key)


def test_the_seeded_planning_rows_are_unconfirmed_and_the_reserved_entry_is_free(session) -> None:
    straight = price_list.get_entry(session, "cut_service:gerader_zuschnitt")
    assert (straight.unconfirmed, straight.base_cents, straight.provenance) == (True, 0, "manual")
    assert price_list.get_entry(session, "delivery:10km").base_cents == 5499
    supply = price_list.get_entry(session, "Personal_Supply")
    assert supply.effective_cents == 0
    with pytest.raises(Refused, match="reserved"):
        price_list.delete_entry(session, "Personal_Supply")
