"""hardware-drilling: the shelf-pin calculation lists cited hole columns and heights, or names what is missing."""

from __future__ import annotations

from app.blender.custom_build.derive import drilling
from tests.drill_helpers import SOURCE, build, exact, inputs, module, ranged, sheet

PIN = {
    "hole_diameter_mm": exact(5), "hole_depth_mm": exact(10), "pitch_mm": exact(32), "first_hole_mm": exact(50),
    "last_hole_mm": exact(50), "front_setback_mm": exact(37), "rear_setback_mm": exact(37), "pins_per_shelf": 4,
}


def _run(values: dict | None, **fields) -> dict:
    spec = build(modules=[module(adjustable_shelves=2, **fields)])
    return drilling(spec, inputs({"shelf-pin": sheet("shelf_pin", values)} if values is not None else {}))


def _entry(result: dict) -> dict:
    (entry,) = result["entries"]
    return entry


def test_holes_and_setbacks_for_a_720_mm_module_with_each_value_sourced() -> None:
    result = _run(PIN)
    entry = _entry(result)
    assert entry["part"] == "m-side"
    heights = [p["position"]["mm"] for p in entry["positions"] if p["label"].startswith("hole")]
    # from the bottom panel's top face (18) + 50 to 720 - 18 - 50, every 32 mm
    assert heights[0] == 68 and heights[1] == 100 and heights[-1] <= 652 and len(heights) == 19
    columns = {p["label"]: p["position"] for p in entry["positions"] if "column" in p["label"]}
    assert columns == {"front column": {"mm": 37}, "rear column": {"mm": 37}}
    assert all(value["source"] == SOURCE for value in entry["values"])
    assert {v["name"]: v["form"] for v in entry["values"]}["hole diameter"] == {"mm": 5}
    assert result["complete"] and result["warnings"] == []
    assert result["counts"]["shelf_pin_holes"] == 2 * 2 * 19


def test_a_missing_pitch_blanks_the_holes_and_warns_by_name() -> None:
    values = {k: v for k, v in PIN.items() if k != "pitch_mm"}
    result = _run(values)
    entry = _entry(result)
    assert not [p for p in entry["positions"] if p["label"].startswith("hole")]
    assert [p["label"] for p in entry["positions"]] == ["front column", "rear column"]
    assert result["warnings"][0].startswith("drilling positions missing: pitch")
    assert not result["complete"] and result["counts"]["shelf_pin_holes"] is None


def test_no_data_sheet_names_the_pin_and_lists_no_holes() -> None:
    result = _run(None)
    entry = _entry(result)
    assert entry["positions"] == [] and entry["missing"] == ["no data sheet for shelf-pin"]
    assert "no data sheet for shelf-pin" in result["warnings"][0]


def test_a_ranged_front_setback_is_listed_as_its_range() -> None:
    entry = _entry(_run(PIN | {"front_setback_mm": ranged(37, 40)}))
    front = next(p for p in entry["positions"] if p["label"] == "front column")
    assert front["position"] == {"min_mm": 37, "max_mm": 40}
    assert "37–40 mm from the front edge" in entry["text"]


def test_a_ranged_first_hole_gives_the_heights_in_words_with_no_count_and_no_warning() -> None:
    result = _run(PIN | {"first_hole_mm": ranged(50, 60)})
    entry = _entry(result)
    (holes,) = [p for p in entry["positions"] if p["label"] == "holes"]
    words = holes["position"]["rule"]
    assert "50–60 mm" in words and "32 mm" in words
    assert not [p for p in entry["positions"] if p["label"].startswith("hole ")]
    assert result["counts"]["shelf_pin_holes"] is None
    assert result["warnings"] == [] and result["complete"]


def test_the_same_inputs_give_the_same_list() -> None:
    assert _run(PIN) == _run(PIN)


def test_a_module_without_adjustable_shelves_has_no_entry() -> None:
    assert drilling(build(modules=[module()]), inputs())["entries"] == []
