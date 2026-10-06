"""cut-list-pricing: pricing a version's derived cut list against the price list and the home store."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.blender import storage
from app.db.models import CutListPricing
from app.pricing import price_list, remnants
from app.pricing.errors import Refused
from app.pricing.pricing import describe_pricing, list_pricings, price_cut_list
from app.pricing.store import StoreCapture, UnknownStore, upsert_store
from tests.api_helpers import desk
from tests.pricing_helpers import clean_pricing

KEY = "berlin-friedrichshain"
BIRCH = "panel:oak-veneer-birch:18"
PLY = "panel:birch-ply:12"


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


@pytest.fixture
def settings(tool_state):
    return tool_state.settings


def write_version(root: Path, document: dict | None = None, package_id: str = "hall-desk", version: int = 1) -> None:
    folder = storage.version_dir(root, package_id, version)
    folder.mkdir(parents=True)
    (folder / "input.json").write_text(json.dumps(document or desk()), encoding="utf-8")


def home_store(session: Session, *, cut_desk: bool = True) -> None:
    upsert_store(
        session,
        StoreCapture(store_key=KEY, name="Berlin Friedrichshain", url="https://toom.de/m/x/", offers_cutting=cut_desk),
    )
    session.flush()


def sheet(session, key: str, cents: int, *, thickness: int, length: int = 2500, width: int = 1250, unit="per_piece"):
    return price_list.create_entry(
        session, key=key, label=key, category="panel", unit=unit, base_cents=cents,
        sheet_length_mm=length, sheet_width_mm=width, thickness_mm=thickness,
    )


def price_the_desk(session) -> None:
    sheet(session, BIRCH, 6000, thickness=18)
    sheet(session, PLY, 3000, thickness=12)
    for key, cents in (("confirmat-7x50", 10), ("hinge-flap", 250), ("flap-stay", 400), ("cabinet-hanger", 800)):
        price_list.create_entry(session, key=key, label=key, category="hardware", unit="per_piece", base_cents=cents)
    for key, cents in (("band:front-edge", 90), ("band:all-edges", 90)):
        price_list.create_entry(
            session, key=key, label=key, category="edge_band", unit="per_metre", base_cents=cents, bundle_length_mm=25_000
        )


def test_the_desk_is_priced_complete_with_every_line_from_the_price_list(session, settings) -> None:
    write_version(settings.render_root)
    home_store(session)
    price_the_desk(session)

    row = price_cut_list(session, settings.render_root, "hall-desk", 1, settings)
    result = row.result

    assert row.complete and row.unpriced_count == 0 and row.undetermined_count == 0
    birch = result["materials"][BIRCH]
    assert birch["sheet_count"] >= 1 and 0 < birch["utilisation_percent"] <= 100
    assert birch["cost_cents"] == 6000 * birch["sheet_count"]
    assert row.hardware_cents == 16 * 10 + 2 * 250 + 2 * 400 + 2 * 800
    assert row.banding_cents > 0 and row.cut_service_cents == 0 and row.delivery_cents == 0
    assert row.total_cents == (
        row.materials_cents + row.hardware_cents + row.banding_cents + row.cut_service_cents + row.delivery_cents
    )
    assert {e["key"] for e in result["entries_used"]} >= {BIRCH, PLY, "hinge-flap", "band:front-edge"}
    assert {e["origin"] for e in result["entries_used"]} == {"manual"}
    assert result["cut_charge_choice_open"] is True


def test_a_hardware_line_with_no_entry_makes_it_incomplete_and_is_listed_by_id(session, settings) -> None:
    write_version(settings.render_root)
    home_store(session)
    price_the_desk(session)
    price_list.delete_entry(session, "hinge-flap")

    row = price_cut_list(session, settings.render_root, "hall-desk", 1, settings)
    assert not row.complete and row.unpriced_count >= 1
    unpriced = [u for u in row.result["unpriced"] if u.get("kind") == "hardware"]
    assert [u["id"] for u in unpriced] == ["hinge-flap"]
    assert "no price-list entry" in unpriced[0]["reason"]


def test_an_unknown_material_phrase_is_unpriced_by_name_never_guessed(session, settings) -> None:
    document = desk()
    document["materials"]["carcass"]["material"] = "18 mm Recycled ocean plastic"
    write_version(settings.render_root, document)
    home_store(session)
    price_the_desk(session)
    row = price_cut_list(session, settings.render_root, "hall-desk", 1, settings)
    assert not row.complete
    assert any("is not recognised" in u["reason"] for u in row.result["unpriced"])


def test_a_part_too_large_for_any_sheet_is_listed_and_makes_it_incomplete(session, settings) -> None:
    write_version(settings.render_root)
    home_store(session)
    price_the_desk(session)
    price_list.revise_entry(session, BIRCH, sheet_length_mm=500, sheet_width_mm=300)
    row = price_cut_list(session, settings.render_root, "hall-desk", 1, settings)
    assert not row.complete and row.result["unfitting"]
    assert {u["material_key"] for u in row.result["unfitting"]} == {BIRCH}


def test_a_remnant_is_used_first_and_the_rack_is_unchanged(session, settings) -> None:
    write_version(settings.render_root)
    home_store(session)
    price_the_desk(session)
    without = price_cut_list(session, settings.render_root, "hall-desk", 1, settings)
    rack = remnants.add_remnant(session, material_key=BIRCH, length_mm=2500, width_mm=1250, grain_axis="length", quantity=1)
    with_rack = price_cut_list(session, settings.render_root, "hall-desk", 1, settings)

    assert with_rack.result["materials"][BIRCH]["sheet_count"] <= without.result["materials"][BIRCH]["sheet_count"]
    assert [r["remnant_id"] for r in with_rack.result["remnants_used"]] == [str(rack.id)]
    assert remnants.list_remnants(session)[0].quantity == 1


def test_repricing_after_an_override_makes_a_second_record_and_leaves_the_first(session, settings) -> None:
    write_version(settings.render_root)
    home_store(session)
    price_the_desk(session)
    first = price_cut_list(session, settings.render_root, "hall-desk", 1, settings)
    first_total, first_id = first.total_cents, first.id
    price_list.set_override(session, BIRCH, cents=5000, note="my supplier")
    second = price_cut_list(session, settings.render_root, "hall-desk", 1, settings)

    assert second.id != first_id and second.total_cents < first_total
    assert {e["key"]: e["origin"] for e in second.result["entries_used"]}[BIRCH] == "override"
    session.refresh(first)
    assert first.total_cents == first_total
    assert [p.id for p in list_pricings(session, "hall-desk", 1)] == [second.id, first_id]


def test_the_per_cut_charge_is_the_shared_cut_count_times_the_straight_cut_price(session, settings) -> None:
    write_version(settings.render_root)
    home_store(session)
    price_the_desk(session)
    session.execute(text("UPDATE store_services SET price_cents = 150 WHERE service = 'gerader_zuschnitt'"))
    shared = price_cut_list(session, settings.render_root, "hall-desk", 1, settings, cut_charge_mode="shared")
    per_cut = price_cut_list(session, settings.render_root, "hall-desk", 1, settings, cut_charge_mode="per_cut")
    cuts = per_cut.result["shared_cut_count"]
    assert shared.cut_service_cents == 0 and cuts > 0
    assert per_cut.cut_service_cents == cuts * 150 == per_cut.result["per_cut_fee_cents"]
    assert per_cut.result["cut_charge_choice_open"] is False
    with pytest.raises(Refused, match="unknown cut-charge mode"):
        price_cut_list(session, settings.render_root, "hall-desk", 1, settings, cut_charge_mode="weekly")


def test_a_delivery_option_adds_its_price(session, settings) -> None:
    write_version(settings.render_root)
    home_store(session)
    price_the_desk(session)
    row = price_cut_list(session, settings.render_root, "hall-desk", 1, settings, delivery_key="delivery:10km")
    assert row.delivery_cents == 5499 and row.result["delivery"]["key"] == "delivery:10km"
    with pytest.raises(Refused, match="no delivery option"):
        price_cut_list(session, settings.render_root, "hall-desk", 1, settings, delivery_key="panel:x")


def test_a_part_the_workshop_supplies_itself_is_priced_at_the_reserved_entry(session, settings) -> None:
    document = desk()
    document["extra_parts"] = [
        {"id": "owner-shelf", "name": "Owner's shelf", "qty": 1, "length": 800, "width": 250,
         "material": "carcass", "supply": "Personal_Supply"}
    ]
    from app.blender.schemas import CustomBuildSpec

    write_version(settings.render_root, CustomBuildSpec.model_validate(document).model_dump(mode="json"))
    home_store(session)
    price_the_desk(session)
    row = price_cut_list(session, settings.render_root, "hall-desk", 1, settings)
    assert [line["id"] for line in row.result["personal_supply"]] == ["owner-shelf"]
    assert row.result["personal_supply"][0]["cost_cents"] == 0


def test_a_missing_home_store_or_version_is_refused_by_name(session, settings) -> None:
    write_version(settings.render_root)
    with pytest.raises(UnknownStore, match="berlin-friedrichshain"):
        price_cut_list(session, settings.render_root, "hall-desk", 1, settings)
    home_store(session)
    with pytest.raises(Refused, match="no readable document"):
        price_cut_list(session, settings.render_root, "ghost", 1, settings)


def test_a_pricing_describes_itself_as_plain_data(session, settings) -> None:
    write_version(settings.render_root)
    home_store(session)
    price_the_desk(session)
    row = price_cut_list(session, settings.render_root, "hall-desk", 1, settings)
    described = describe_pricing(row)
    assert described["package_id"] == "hall-desk" and described["version"] == 1
    assert described["total_cents"] == row.total_cents and isinstance(described["result"], dict)
    assert session.get(CutListPricing, row.id) is row
