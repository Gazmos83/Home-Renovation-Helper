"""cabinet-hardware-calculator: adjustable shelves, item-keyed hardware and wall-shelf boards in `derive`."""

from __future__ import annotations

import json
from pathlib import Path

from app.blender.custom_build.derive import (
    ADJUSTABLE_SHELF_CLEARANCE_MM,
    derive,
    overall,
)
from app.blender.schemas import CustomBuildSpec
from tests.drill_helpers import build, exact, inputs, module, rules, sheet, wall_shelf

TEMPLATES = Path(__file__).resolve().parents[1] / "fixtures" / "packages" / "templates"


def _by_id(rows: list[dict]) -> dict[str, dict]:
    return {row["id"]: row for row in rows}


def test_the_clearance_is_one_and_a_half_mm() -> None:
    assert ADJUSTABLE_SHELF_CLEARANCE_MM == 1.5


def test_the_desk_derives_the_same_with_no_inputs_and_with_empty_inputs() -> None:
    desk = CustomBuildSpec.model_validate(
        json.loads((TEMPLATES / "fold-down-desk.json").read_text(encoding="utf-8"))
    ).model_dump(mode="json")
    plain = derive(desk)
    assert derive(desk, None) == plain
    assert derive(desk, inputs()) == plain


def test_a_module_without_new_fields_has_no_adjustable_row_or_pin_line() -> None:
    parts, hardware, _ = derive(build(modules=[module(shelves=1)]))
    assert not any("adjustable" in row["id"] for row in parts)
    assert [line["id"] for line in hardware] == ["confirmat-7x50"]


def test_two_adjustable_shelves_give_a_row_of_two_and_eight_pins() -> None:
    spec = build(modules=[module(adjustable_shelves=2)])
    data = inputs({"shelf-pin": sheet("shelf_pin", {"pins_per_shelf": 4})})
    parts, hardware, _ = derive(spec, data)
    row = _by_id(parts)["m-adjustable-shelf"]
    # inner width 600 - 2 x 18 = 564, less 1.5 mm rounded down; back-reduced depth 400 - 3
    assert (row["qty"], row["l"], row["w"], row["t"]) == (2, 562, 397, 18)
    pin = _by_id(hardware)["shelf-pin"]
    assert pin["qty"] == 8 and pin["item"] == "Maker M1"


def test_a_pin_line_has_no_quantity_and_a_note_when_pins_per_shelf_is_missing() -> None:
    spec = build(modules=[module(adjustable_shelves=2)])
    for data in (inputs(), inputs({"shelf-pin": sheet("shelf_pin", {"pitch_mm": exact(32)})}), None):
        pin = _by_id(derive(spec, data)[1])["shelf-pin"]
        assert pin["qty"] == ""
        assert "No quantity" in pin["notes"]
    assert "pins per shelf" in _by_id(derive(spec, inputs({"shelf-pin": sheet("shelf_pin", {})}))[1])["shelf-pin"]["notes"]


def test_a_named_hinge_is_listed_under_its_item_and_the_default_line_is_absent() -> None:
    spec = build(modules=[module(fronts=[{"type": "door", "count": 2, "opening": "hinge", "hinge": "hinge-blum-clip-110"}])])
    hardware = _by_id(derive(spec)[1])
    assert hardware["hinge-blum-clip-110"]["qty"] == 4
    assert "hinge-concealed-110" not in hardware


def test_a_count_table_replaces_the_height_rule_and_a_plate_line_follows_the_hinge() -> None:
    spec = build(modules=[module(height=1200, fronts=[{"type": "door", "count": 1, "opening": "hinge"}])])
    table = [{"max_height_mm": 1500, "hinges": 4}]
    data = inputs({"hinge-concealed-110": sheet("hinge", {"count_table": table, "plate_item": "plate-110"})})
    hardware = _by_id(derive(spec, data)[1])
    assert hardware["hinge-concealed-110"]["qty"] == 4  # the height rule would give 3
    assert hardware["plate-110"]["qty"] == 4
    assert _by_id(derive(spec)[1])["hinge-concealed-110"]["qty"] == 3


def test_a_wall_shelf_is_one_board_row_and_the_owners_brackets_are_counted() -> None:
    spec = build(wall_shelves=[wall_shelf(bracket_positions_mm=[150, 600, 1050])])
    parts, hardware, assembly = derive(spec)
    row = _by_id(parts)["wall-shelf-1"]
    assert (row["l"], row["w"], row["t"], row["material"], row["module"]) == (1200, 250, 18, "Eiche 18 mm", "wall-shelf-1")
    assert _by_id(hardware)["bracket-white"]["qty"] == 3
    assert any(step["title"] == "Wall shelves" for step in assembly)


def test_calculated_brackets_come_from_the_count_rule_and_need_both_rules() -> None:
    spec = build(wall_shelves=[wall_shelf()])
    full = inputs(rule_set=rules(end={"min": 100, "max": 200}))
    assert _by_id(derive(spec, full)[1])["bracket-white"]["qty"] == 2
    for partial in (None, inputs(), inputs(rule_set=rules(count=False, end={"min": 100, "max": 200})), inputs(rule_set=rules())):
        line = _by_id(derive(spec, partial)[1])["bracket-white"]
        assert line["qty"] == "" and "No quantity" in line["notes"]


def test_overall_includes_wall_shelves_without_an_envelope() -> None:
    spec = build(modules=[module()], wall_shelves=[wall_shelf(x=700, z=1000, length=900, depth=250)])
    spec["envelope"] = None
    assert overall(spec) == {"w": 1600, "h": 1018, "d": 400}
