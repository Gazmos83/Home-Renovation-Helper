"""guideline-hardware-counts: pin and hinge counts from the data sheet, else the cited count rule, else as before."""

from __future__ import annotations

from typing import Any

from app.blender.custom_build.derive import derive, drilling
from tests.drill_helpers import build, inputs, module, sheet

NOTE_SOURCE = {"publication": "owner:7cf8c9ef-e98f-4d3d-af6c-f0384a17ffdd", "section": "Shelf Pin Count", "quote": "q"}
HINGE_SOURCE = {"publication": "owner:a8147011-0f73-4e5e-a5f2-e3a9f8fd9852", "section": "Hinges", "quote": "q"}
PIN_RULE = {
    "rule_id": "shelf-pin-count", "params": {"table": [{"max_width_mm": 914, "pins": 4}], "beyond": 5},
    "source": NOTE_SOURCE,
}
HINGE_RULE = {
    "rule_id": "hinge-count",
    "params": {
        "table": [
            {"max_height_mm": 1016, "hinges": 2}, {"max_height_mm": 1524, "hinges": 3},
            {"max_height_mm": 2032, "hinges": 4},
        ],
        "beyond": 5,
    },
    "source": HINGE_SOURCE,
}
COUNT_RULES = {"shelf_pin_count_for_width": PIN_RULE, "hinge_count_for_height": HINGE_RULE}


def _line(spec: dict, frozen: dict | None, key: str) -> dict[str, Any]:
    _parts, hardware, _ = derive(spec, frozen)
    return next(line for line in hardware if line["id"] == key)


def _kommode(**fields: Any) -> dict:
    return build(modules=[module(width=800, height=750, adjustable_shelves=2, **fields)])


# --- shelf pins ---------------------------------------------------------------------------------


def test_pin_count_from_the_rule() -> None:
    spec = _kommode()
    parts, _hardware, _ = derive(spec, inputs(rule_set=COUNT_RULES))
    assert next(p for p in parts if p["id"] == "m-adjustable-shelf")["l"] == 762
    line = _line(spec, inputs(rule_set=COUNT_RULES), "shelf-pin")
    assert line["qty"] == 8
    assert "shelf-pin-count" in line["notes"] and NOTE_SOURCE["publication"] in line["notes"]
    assert "4 per shelf up to 914 mm wide, 5 beyond" in line["notes"]


def test_a_wide_shelf_takes_the_beyond_count() -> None:
    spec = build(modules=[module(width=1200, adjustable_shelves=1)])
    assert _line(spec, inputs(rule_set=COUNT_RULES), "shelf-pin")["qty"] == 5


def test_the_data_sheet_wins_over_the_pin_rule() -> None:
    frozen = inputs({"shelf-pin": sheet("shelf_pin", {"pins_per_shelf": 6})}, COUNT_RULES)
    line = _line(_kommode(), frozen, "shelf-pin")
    assert line["qty"] == 12 and line["notes"] == "Rule: pins per shelf × adjustable shelves"


def test_a_sheet_without_pins_per_shelf_falls_back_to_the_rule() -> None:
    frozen = inputs({"shelf-pin": sheet("shelf_pin", {"pitch_mm": {"value": 32}})}, COUNT_RULES)
    assert _line(_kommode(), frozen, "shelf-pin")["qty"] == 8


def test_no_sheet_and_no_rule_leaves_the_quantity_blank() -> None:
    line = _line(_kommode(), inputs(), "shelf-pin")
    assert line["qty"] == "" and line["notes"] == "No quantity: no data sheet"
    assert _line(_kommode(), None, "shelf-pin")["qty"] == ""


def test_bays_of_different_widths_count_per_board() -> None:
    # 1600 mm wide, 18 mm sides and divider: bays 1000 and 546 mm, each less 1.5 mm clearance
    spec = build(modules=[module(width=1600, adjustable_shelves=1, dividers=1, divider_positions_mm=[1000])])
    assert _line(spec, inputs(rule_set=COUNT_RULES), "shelf-pin")["qty"] == 5 + 4


# --- hinges -------------------------------------------------------------------------------------


def _doors(height: int, count: int = 1) -> dict:
    return build(modules=[module(height=height, fronts=[{"type": "door", "count": count, "opening": "hinge"}])])


def _hinge_entry(result: dict) -> dict:
    return next(e for e in result["entries"] if e["calculation"] == "hinges" and e["part"].startswith("m-door"))


def test_the_rule_decides_a_1000_mm_door() -> None:
    spec = _doors(1003, count=2)  # leaves 1000 mm tall after the 3 mm gap
    frozen = inputs(rule_set=COUNT_RULES)
    result = drilling(spec, frozen)
    assert result["counts"]["hinge_cup_borings"] == 4
    entry = _hinge_entry(result)
    assert "2 hinges per door" in entry["text"] and "hinge-count" in entry["text"]
    line = _line(spec, frozen, "hinge-concealed-110")
    assert line["qty"] == 4 and "hinge-count" in line["notes"] and HINGE_SOURCE["publication"] in line["notes"]


def test_the_sheet_count_table_wins_over_the_rule() -> None:
    table = [{"max_height_mm": 1100, "hinges": 3}]
    frozen = inputs({"hinge-concealed-110": sheet("hinge", {"count_table": table})}, COUNT_RULES)
    spec = _doors(1003)
    assert drilling(spec, frozen)["counts"]["hinge_cup_borings"] == 3
    line = _line(spec, frozen, "hinge-concealed-110")
    assert line["qty"] == 3 and line["notes"] == "Rule: per the item's data sheet count table"


def test_without_the_rule_the_fallback_is_kept() -> None:
    spec = _doors(1003)
    assert drilling(spec, inputs())["counts"]["hinge_cup_borings"] == 3
    line = _line(spec, inputs(), "hinge-concealed-110")
    assert line["qty"] == 3 and line["notes"] == "Rule: 2/3/4 per door up to 900/1600 mm tall/above"
    assert "built-in" not in _hinge_entry(drilling(spec, inputs()))["text"]
    assert "2/3/4 per door" in _hinge_entry(drilling(spec, inputs()))["text"]


def test_hinge_count_from_the_rule_for_tall_doors() -> None:
    spec = _doors(1553, count=2)  # 1550 mm leaves
    frozen = inputs(rule_set=COUNT_RULES)
    assert _line(spec, frozen, "hinge-concealed-110")["qty"] == 8
    assert _line(spec, inputs(), "hinge-concealed-110")["qty"] == 6


def test_a_door_beyond_the_table_takes_the_beyond_count() -> None:
    spec = build(modules=[module(height=2203, fronts=[{"type": "door", "count": 1, "opening": "hinge"}])])
    assert _line(spec, inputs(rule_set=COUNT_RULES), "hinge-concealed-110")["qty"] == 5
