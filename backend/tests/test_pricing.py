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
from app.pricing.errors import NotApproved, Refused
from app.pricing.pricing import describe_pricing, list_pricings, price_cut_list
from app.pricing.store import StoreCapture, UnknownStore, upsert_store
from tests.api_helpers import desk
from tests.pricing_helpers import approve_version, clean_pricing

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


@pytest.fixture(autouse=True)
def approved_desk(settings, session: Session) -> None:
    """Pricing needs an approved version; the desk is approved unless a test says otherwise."""
    approve_version(session, "hall-desk", 1)
    session.flush()


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


def test_derived_mitre_notes_are_marked_for_review(session, settings) -> None:
    document = {
        "kind": "custom_build", "schema_version": 1, "units": "mm", "name": "Folded cabinet",
        "materials": {
            "carcass": {"material": "18 mm oak-veneered birch", "thickness_mm": 18},
            "back": {"material": "12 mm birch plywood", "thickness_mm": 12},
        },
        "modules": [{
            "id": "cabinet", "name": "Cabinet", "x": 0, "y": 0, "z": 0,
            "width": 800, "height": 2000, "depth": 400, "carcass": "carcass", "back": "back",
            "side_folds": [{"side": "left", "from_mm": 1100, "along": "height", "angle_deg": 26, "towards": "inside"}],
        }],
    }
    from app.blender.schemas import CustomBuildSpec

    write_version(settings.render_root, CustomBuildSpec.model_validate(document).model_dump(mode="json"), package_id="folded-cab")
    approve_version(session, "folded-cab", 1)
    session.flush()
    home_store(session)
    price_the_desk(session)
    row = price_cut_list(session, settings.render_root, "folded-cab", 1, settings)
    reviewed = {item["part_id"]: item["note"] for item in row.result["review"]}
    assert "cabinet-side-left-upper" in reviewed
    assert "26" in reviewed["cabinet-side-left-upper"] and "mitre" in reviewed["cabinet-side-left-upper"].casefold()


def test_a_pricing_describes_itself_as_plain_data(session, settings) -> None:
    write_version(settings.render_root)
    home_store(session)
    price_the_desk(session)
    row = price_cut_list(session, settings.render_root, "hall-desk", 1, settings)
    described = describe_pricing(session, row)
    assert described["package_id"] == "hall-desk" and described["version"] == 1
    assert described["total_cents"] == row.total_cents and isinstance(described["result"], dict)
    assert session.get(CutListPricing, row.id) is row


# --- only an approved version is priced -------------------------------------------------------


def test_an_unapproved_version_is_refused_and_no_record_is_written(session, settings) -> None:
    from app.agent import house_file

    write_version(settings.render_root)
    home_store(session)
    price_the_desk(session)
    house_file.unapprove_version(session, "hall-desk", 1)
    session.flush()

    with pytest.raises(NotApproved, match="approve it first in the version's inspector"):
        price_cut_list(session, settings.render_root, "hall-desk", 1, settings)

    assert list_pricings(session, "hall-desk", 1) == []


def test_a_version_with_no_house_file_record_is_not_priced(session, settings) -> None:
    write_version(settings.render_root, package_id="folder-only")
    home_store(session)
    price_the_desk(session)
    with pytest.raises(NotApproved):
        price_cut_list(session, settings.render_root, "folder-only", 1, settings)


def test_the_approved_version_is_priced_and_another_version_is_not(session, settings) -> None:
    from app.agent import house_file

    write_version(settings.render_root)
    write_version(settings.render_root, package_id="hall-desk", version=2)
    house_file.record_version(session, "hall-desk", 2, revised_from=1)
    home_store(session)
    price_the_desk(session)

    assert price_cut_list(session, settings.render_root, "hall-desk", 1, settings).complete
    with pytest.raises(NotApproved):
        price_cut_list(session, settings.render_root, "hall-desk", 2, settings)


def test_a_pricing_stays_readable_after_unapproval_and_reports_it(session, settings) -> None:
    from app.agent import house_file

    write_version(settings.render_root)
    home_store(session)
    price_the_desk(session)
    row = price_cut_list(session, settings.render_root, "hall-desk", 1, settings)
    total = row.total_cents
    assert describe_pricing(session, row)["version_approved"] is True

    house_file.unapprove_version(session, "hall-desk", 1)
    session.flush()
    described = describe_pricing(session, row)
    assert described["version_approved"] is False
    assert described["total_cents"] == total


def test_a_pricing_reports_the_approval_moving_to_another_version(session, settings) -> None:
    from app.agent import house_file

    write_version(settings.render_root)
    home_store(session)
    price_the_desk(session)
    row = price_cut_list(session, settings.render_root, "hall-desk", 1, settings)

    house_file.record_version(session, "hall-desk", 2, revised_from=1)
    house_file.approve_version(session, "hall-desk", 2)
    session.flush()

    assert describe_pricing(session, row)["version_approved"] is False
    assert describe_pricing(session, row)["total_cents"] == row.total_cents


# --- hinge cup borings and hardware with no quantity (cabinet-hardware-calculator) -------------


def door_document(*, adjustable: int = 0) -> dict:
    document = desk()
    module = document["modules"][0]
    module["height"] = 700
    module["fronts"] = [{"type": "door", "count": 4, "opening": "hinge"}]
    if adjustable:
        module["adjustable_shelves"] = adjustable
    return document


def write_frozen(root: Path, document: dict) -> None:
    write_version(root, document)
    folder = storage.version_dir(root, "hall-desk", 1)
    storage.write_hardware_inputs(folder, {"data_sheets": {}, "rules": {}})


def set_boring_price(session: Session, cents: int | None) -> None:
    session.execute(text("UPDATE store_services SET price_cents = :c WHERE service = 'topfband_bohrung'"), {"c": cents})


def test_hinge_borings_are_charged_per_cut_counted_when_shared_and_incomplete_without_a_price(
    session, settings
) -> None:
    write_frozen(settings.render_root, door_document())
    home_store(session)
    price_the_desk(session)
    set_boring_price(session, 299)

    per_cut = price_cut_list(session, settings.render_root, "hall-desk", 1, settings, cut_charge_mode="per_cut")
    assert per_cut.result["drilling"]["hinge_cup_borings"] == 8  # 2 hinges x 4 doors of 700 mm
    assert per_cut.result["drilling"]["hinge_boring_fee_cents"] == 8 * 299
    assert per_cut.cut_service_cents == per_cut.result["per_cut_fee_cents"] + 8 * 299

    shared = price_cut_list(session, settings.render_root, "hall-desk", 1, settings, cut_charge_mode="shared")
    assert shared.result["drilling"]["hinge_cup_borings"] == 8
    assert shared.result["drilling"]["hinge_boring_fee_cents"] is None and shared.cut_service_cents == 0

    set_boring_price(session, None)
    unpriced = price_cut_list(session, settings.render_root, "hall-desk", 1, settings, cut_charge_mode="per_cut")
    assert not unpriced.complete
    assert any("hinge-boring" in line.get("reason", "") for line in unpriced.result["unpriced"])


def test_a_pin_line_with_no_quantity_is_unpriced_and_holes_are_not_counted(session, settings) -> None:
    write_frozen(settings.render_root, door_document(adjustable=2))
    home_store(session)
    price_the_desk(session)
    price_list.create_entry(session, key="shelf-pin", label="Pin", category="hardware", unit="per_piece", base_cents=5)
    pricing = price_cut_list(session, settings.render_root, "hall-desk", 1, settings)
    line = next(item for item in pricing.result["hardware"] if item["id"] == "shelf-pin")
    assert line["cost_cents"] is None and line["qty"] == ""
    unpriced = next(item for item in pricing.result["unpriced"] if item.get("id") == "shelf-pin")
    assert unpriced["reason"].startswith("no quantity")
    assert not pricing.complete
    assert pricing.result["drilling"]["shelf_pin_holes"] is None


def test_a_version_without_frozen_inputs_is_priced_as_before(session, settings) -> None:
    write_version(settings.render_root, door_document())
    home_store(session)
    price_the_desk(session)
    assert "drilling" not in price_cut_list(session, settings.render_root, "hall-desk", 1, settings).result


# --- the priced lines in the chat (pricing-completion) ---------------------------------------


def _summary(session, row) -> str:
    from plugins.material_cost.tool import summarise

    return summarise(describe_pricing(session, row))


def _table(summary: str) -> list[list[str]]:
    rows = [line for line in summary.splitlines() if line.startswith("| ") and not line.startswith("| Line")]
    return [[cell.strip() for cell in line.strip("|").split("|")] for line in rows]


def test_a_complete_pricing_lists_every_line_and_the_total_in_one_table(session, settings) -> None:
    write_version(settings.render_root)
    home_store(session)
    price_the_desk(session)
    row = price_cut_list(session, settings.render_root, "hall-desk", 1, settings, delivery_key="delivery:10km")
    summary = _summary(session, row)
    assert "Every priced line (show this table as given):" in summary
    table = _table(summary)
    names = [cells[0] for cells in table]
    assert BIRCH in names and PLY in names
    for item in ("Confirmat screw 7×50 mm", "Flap hinge", "Flap stay", "Cabinet wall hanger"):
        assert item in names, item
    assert any(name.startswith("edge band") for name in names)
    assert "cut service" in names and "delivery delivery:10km" in names
    assert table[-1] == ["**Total**", "", f"**{row.total_cents // 100},{row.total_cents % 100:02d} EUR**"]
    assert "the pricing is complete" in summary


def test_an_unpriced_hardware_line_says_unpriced_and_why(session, settings) -> None:
    write_version(settings.render_root)
    home_store(session)
    sheet(session, BIRCH, 6000, thickness=18)
    sheet(session, PLY, 3000, thickness=12)
    for key, cents in (("confirmat-7x50", 10), ("flap-stay", 400), ("cabinet-hanger", 800)):
        price_list.create_entry(session, key=key, label=key, category="hardware", unit="per_piece", base_cents=cents)
    row = price_cut_list(session, settings.render_root, "hall-desk", 1, settings)
    summary = _summary(session, row)
    hinge = next(cells for cells in _table(summary) if "hinge" in cells[0].lower())
    assert hinge[2] == "unpriced"
    assert "the pricing is INCOMPLETE" in summary and "no price-list entry for this hardware item" in summary


def test_every_amount_in_the_table_is_in_the_stored_pricing(session, settings) -> None:
    import re

    write_version(settings.render_root)
    home_store(session)
    price_the_desk(session)
    row = price_cut_list(session, settings.render_root, "hall-desk", 1, settings, delivery_key="delivery:10km")
    result = row.result
    stored = {row.total_cents, row.cut_service_cents}
    stored |= {m.get("cost_cents") for m in result["materials"].values()}
    stored |= {line.get("cost_cents") for line in result["hardware"] + result["banding"]}
    stored.add(result["delivery"]["cents"])
    shown = {
        int(euros) * 100 + int(cents)
        for cells in _table(_summary(session, row))
        for euros, cents in re.findall(r"(\d+),(\d{2}) EUR", cells[2])
    }
    assert shown and shown <= stored
