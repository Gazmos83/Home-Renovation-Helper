"""partial-and-folded-dividers: divider spans, shelf kinds, dividers on a fold, and the Designer's questions."""

from __future__ import annotations

import copy

import pytest
from pydantic import ValidationError

from app.agent.divider_questions import fix_shelf_question, position_question
from app.agent.revise import derived_changes, revise_spec
from app.blender.custom_build.derive import (
    derive,
    divider_places,
    drilling,
    shelf_kinds_of,
)
from app.blender.schemas import CustomBuildSpec, PackageChanges
from app.blender.schemas import describe_validation_error as _describe_validation_error
from app.guidelines.checks import ShelfSpan, shelf_span
from app.guidelines.rules import Rule, RuleSource
from tests.drill_helpers import build, exact, inputs, module, sheet

FOLD = {"side": "left", "from_mm": 1100, "along": "height", "angle_deg": 26, "towards": "inside"}
TOP_SPAN = [{"from_board": 4, "to_board": "top"}]


def cabinet(**overrides) -> dict:
    """The starter-like 800 × 2000 × 400 mm cabinet: 18 mm carcass, 12 mm back, 4 fixed shelves."""
    found = {
        "id": "cabinet", "name": "Cabinet", "x": 0, "y": 0, "z": 0, "width": 800, "height": 2000, "depth": 400,
        "carcass": "carcass", "back": "back", "shelves": 4,
    }
    found.update(overrides)
    return {
        "kind": "custom_build", "schema_version": 1, "units": "mm", "name": "Cabinet",
        "materials": {
            "carcass": {"material": "18 mm oak-veneered birch", "thickness_mm": 18},
            "back": {"material": "12 mm birch plywood", "thickness_mm": 12},
        },
        "modules": [found],
    }


def wide(**overrides) -> dict:
    """A 1000 × 1200 mm module with 3 fixed shelves (309, 600 and 891 mm centres)."""
    found = {"width": 1000, "height": 1200, "shelves": 3}
    found.update(overrides)
    return cabinet(**found)


def _valid(document: dict) -> dict:
    return CustomBuildSpec.model_validate(document).model_dump(mode="json")


def _refusal(document: dict) -> str:
    with pytest.raises(ValidationError) as caught:
        CustomBuildSpec.model_validate(document)
    return _describe_validation_error(caught.value)


def _rows(document: dict) -> dict[str, dict]:
    parts, _hardware, _assembly = derive(_valid(document))
    return {row["id"]: row for row in parts}


def _hardware(document: dict) -> dict[str, object]:
    _parts, hardware, _assembly = derive(_valid(document))
    return {line["id"]: line["qty"] for line in hardware}


# --- schema -------------------------------------------------------------------------------------


def test_a_divider_from_the_top_shelf_to_the_top_is_accepted() -> None:
    _valid(cabinet(dividers=1, divider_spans=TOP_SPAN))


def test_a_span_on_a_missing_shelf_is_refused() -> None:
    message = _refusal(cabinet(shelves=2, dividers=1, divider_spans=[{"from_board": 3, "to_board": "top"}]))
    assert "modules[0].divider_spans" in message and "2 shelves" in message


def test_a_span_on_an_adjustable_shelf_is_refused_naming_the_shelf() -> None:
    message = _refusal(cabinet(shelves=0, adjustable_shelves=4, dividers=1, divider_spans=TOP_SPAN))
    assert "modules[0].divider_spans" in message and "shelf 4" in message
    assert "only a fixed shelf can hold a divider" in message


@pytest.mark.parametrize(
    ("dividers", "spans", "words"),
    [
        (2, TOP_SPAN, "1 spans given, 2 dividers expected"),
        (0, TOP_SPAN, "has no dividers"),
        (1, [{"from_board": 3, "to_board": 2}], "must stand on a board below"),
    ],
)
def test_bad_spans_are_refused_naming_the_field(dividers: int, spans: list, words: str) -> None:
    message = _refusal(cabinet(dividers=dividers, divider_spans=spans))
    assert "modules[0].divider_spans" in message and words in message


def test_an_unknown_divider_field_is_still_refused_by_name() -> None:
    assert "divider_material" in _refusal(cabinet(dividers=1, divider_material="oak"))


def test_shelf_kinds_must_agree_with_the_counts() -> None:
    message = _refusal(
        cabinet(shelves=1, adjustable_shelves=3, shelf_kinds=["fixed", "fixed", "adjustable", "adjustable"])
    )
    assert "modules[0].shelf_kinds" in message


def test_a_document_without_the_new_fields_serialises_as_before() -> None:
    dumped = _valid(cabinet(dividers=1))["modules"][0]
    assert "divider_spans" not in dumped and "shelf_kinds" not in dumped


# --- derivation ---------------------------------------------------------------------------------


def test_divider_from_the_top_shelf_to_the_top() -> None:
    rows = _rows(cabinet(dividers=1, divider_spans=TOP_SPAN))
    assert (rows["cabinet-divider"]["l"], rows["cabinet-divider"]["w"], rows["cabinet-divider"]["qty"]) == (383, 388, 1)
    assert (rows["cabinet-shelf"]["l"], rows["cabinet-shelf"]["qty"]) == (764, 4)
    assert _hardware(cabinet(dividers=1, divider_spans=TOP_SPAN))["confirmat-7x50"] == 8 + 4 * 4 + 4


def test_a_divider_crosses_only_the_shelf_below_it() -> None:
    document = wide(dividers=1, divider_positions_mm=[400], divider_spans=[{"from_board": "bottom", "to_board": 2}])
    rows = _rows(document)
    assert rows["cabinet-divider"]["l"] == 573
    assert [(rows[f"cabinet-shelf-{n}"]["l"], rows[f"cabinet-shelf-{n}"]["qty"]) for n in (1, 2, 3)] == [
        (400, 1), (546, 1), (964, 2),
    ]
    assert "shelf 1 bay 1" in rows["cabinet-shelf-1"]["notes"]
    assert _hardware(document)["confirmat-7x50"] == 8 + 4 * 4 + 4


def test_a_divider_on_a_folded_module_splits_the_narrowest_opening() -> None:
    document = cabinet(dividers=1, divider_spans=TOP_SPAN, side_folds=[dict(FOLD)])
    (place,) = divider_places(_valid(document)["modules"][0], 18, 12)
    assert place.left == 606  # 588 mm from the unbent left inner face: 448 + 158
    rows = _rows(document)
    assert (rows["cabinet-divider"]["l"], rows["cabinet-divider"]["w"]) == (383, 388)
    assert _hardware(document)["confirmat-7x50"] == 8 + 4 + 4 * 4 + 4


def test_a_divider_cutting_into_a_folded_side_is_refused() -> None:
    message = _refusal(
        cabinet(dividers=1, divider_positions_mm=[100], divider_spans=TOP_SPAN, side_folds=[dict(FOLD)])
    )
    assert "modules[0].divider_positions_mm" in message and "folded left side" in message


def test_full_height_dividers_derive_as_before() -> None:
    rows = _rows(wide(width=1000, dividers=2))
    assert rows["cabinet-divider"]["qty"] == 2 and rows["cabinet-shelf"]["l"] == 309
    assert rows["cabinet-shelf"]["qty"] == 9
    rows = _rows(wide(shelves=2, dividers=1, divider_positions_mm=[400]))
    assert rows["cabinet-shelf-bay-1"]["l"] == 400 and rows["cabinet-shelf-bay-2"]["l"] == 546


def test_the_top_shelf_can_be_fixed_while_the_rest_stay_adjustable() -> None:
    before = cabinet(shelves=0, adjustable_shelves=4)
    after = cabinet(shelves=1, adjustable_shelves=3, shelf_kinds=["adjustable", "adjustable", "adjustable", "fixed"])
    rows = _rows(after)
    assert rows["cabinet-shelf"]["qty"] == 1 and rows["cabinet-adjustable-shelf"]["qty"] == 3
    assert _hardware(after)["confirmat-7x50"] == _hardware(before)["confirmat-7x50"] + 4
    assert shelf_kinds_of(_valid(after)["modules"][0])[-1] == "fixed"


def test_no_shelf_kinds_keeps_the_fixed_shelves_lowest() -> None:
    assert shelf_kinds_of(cabinet(shelves=1, adjustable_shelves=2)["modules"][0]) == ["fixed", "adjustable", "adjustable"]


def test_the_assembly_names_the_span() -> None:
    _parts, _hardware, steps = derive(_valid(cabinet(dividers=1, divider_spans=TOP_SPAN)))
    assert "divider 1 from shelf 4 to the top" in steps[1]["body"]


# --- drilling -----------------------------------------------------------------------------------

PIN = {
    "hole_diameter_mm": exact(5), "hole_depth_mm": exact(10), "pitch_mm": exact(32), "first_hole_mm": exact(50),
    "last_hole_mm": exact(50), "front_setback_mm": exact(37), "rear_setback_mm": exact(37), "pins_per_shelf": 4,
}


def _drill(**fields) -> dict:
    spec = build(modules=[module(**fields)])
    return drilling(spec, inputs({"shelf-pin": sheet("shelf_pin", PIN)}))


def test_a_partial_divider_drills_its_own_length_from_its_bottom_end() -> None:
    # 720 mm module: fixed shelf at 300 mm underside, adjustable shelves below and above it
    result = _drill(
        shelves=1, adjustable_shelves=2, shelf_positions_mm=[150, 300, 500],
        shelf_kinds=["adjustable", "fixed", "adjustable"],
        dividers=1, divider_spans=[{"from_board": 2, "to_board": "top"}],
    )
    divider = next(entry for entry in result["entries"] if entry["part"] == "m-divider")
    heights = [p["position"]["mm"] for p in divider["positions"] if p["label"].startswith("hole")]
    # the divider stands on the fixed shelf's top face (18 + 300 + 18 = 336) and reaches 702: 366 mm long
    assert heights[0] == 50 and heights[-1] <= 366 - 50 and len(heights) == 9
    assert divider["counts"]["shelf_pin_holes"] == 2 * 2 * 9


def test_a_divider_with_no_adjustable_shelf_in_its_span_has_no_entry() -> None:
    result = _drill(
        shelves=2, adjustable_shelves=1, shelf_positions_mm=[150, 300, 500],
        dividers=1, divider_spans=[{"from_board": 1, "to_board": 2}],
    )
    assert [entry["part"] for entry in result["entries"]] == ["m-side"]


def test_fixing_a_shelf_keeps_the_side_holes() -> None:
    before = _drill(adjustable_shelves=3)
    after = _drill(shelves=1, adjustable_shelves=2, shelf_kinds=["adjustable", "adjustable", "fixed"])
    assert before["entries"][0]["positions"] == after["entries"][0]["positions"]


# --- guidelines ---------------------------------------------------------------------------------


def test_a_partial_divider_leaves_a_whole_shelf_for_the_span_check() -> None:
    spec = _valid(wide(dividers=1, divider_positions_mm=[400], divider_spans=[{"from_board": "bottom", "to_board": 2}]))
    (found,) = shelf_span(spec, ShelfSpan(table=[{"thickness_mm": 18, "max_span_mm": 800}]))
    assert found.value == "964 mm" and "bay" not in found.what


def test_full_height_unequal_bays_still_name_bay_2() -> None:
    spec = _valid(wide(shelves=2, dividers=1, divider_positions_mm=[400]))
    (found,) = shelf_span(spec, ShelfSpan(table=[{"thickness_mm": 18, "max_span_mm": 800}]))
    assert found.value == "546 mm" and "bay 2" in found.what


# --- the Designer's questions -------------------------------------------------------------------


def _span_rule(limit: float) -> Rule:
    return Rule(
        id="shelf-span", applies_to="piece", check="shelf_span_mm_for_thickness",
        params=ShelfSpan(table=[{"thickness_mm": 18, "max_span_mm": limit}]), severity="warn",
        source=RuleSource(publication="owner:note", section="p. 12", quote="18 mm: 800 mm"),
    )


def test_a_new_divider_without_a_position_is_asked_with_no_limit_configured() -> None:
    before = _valid(cabinet())
    after = _valid(cabinet(dividers=1, divider_spans=TOP_SPAN))
    question = position_question(before, after, [])
    assert question is not None and "[373] mm from the left side's inner face" in question
    assert "373 mm and 373 mm" in question and "No shelf-span limit is configured" in question
    assert "search_guidelines" in question


def test_a_new_divider_is_asked_with_the_configured_limit_and_its_source() -> None:
    before = _valid(cabinet(width=1200, shelves=3))
    after = _valid(cabinet(width=1200, shelves=3, dividers=1))
    question = position_question(before, after, [_span_rule(800)])
    assert question is not None and "573 mm and 573 mm" in question
    assert "at most 800 mm" in question and "owner:note" in question and "every compartment is within it" in question


def test_a_positioned_or_unchanged_divider_is_not_asked() -> None:
    positioned = _valid(cabinet(dividers=1, divider_positions_mm=[200], divider_spans=TOP_SPAN))
    assert position_question(_valid(cabinet()), positioned, []) is None
    same = _valid(cabinet(dividers=1))
    assert position_question(same, same, []) is None


def test_an_adjustable_anchor_asks_to_fix_the_shelf_with_the_hardware_it_changes() -> None:
    document = cabinet(shelves=0, adjustable_shelves=4, dividers=1, divider_spans=TOP_SPAN)
    question = fix_shelf_question(document)
    assert question is not None and "shelf 4" in question and "Only a fixed shelf can hold a divider" in question
    assert "Confirmat screw 7×50 mm 8 → 12" in question
    assert "['adjustable', 'adjustable', 'adjustable', 'fixed']" in question


def test_a_fixed_anchor_asks_nothing() -> None:
    assert fix_shelf_question(cabinet(dividers=1, divider_spans=TOP_SPAN)) is None


def test_a_malformed_document_asks_nothing() -> None:
    assert fix_shelf_question({"modules": [{"id": "m", "divider_spans": "x"}]}) is None


# --- revisions and the preview ------------------------------------------------------------------


def test_spans_cleared_in_a_revision_go_back_to_full_height() -> None:
    document = _valid(cabinet(dividers=1, divider_positions_mm=[373], divider_spans=TOP_SPAN))
    revised, lines = revise_spec(
        copy.deepcopy(document), PackageChanges.model_validate({"modules": {"cabinet": {"divider_spans": []}}})
    )
    assert "divider_spans" not in revised["modules"][0]
    assert lines == ["cabinet: divider_spans divider 1 from shelf 4 to the top → full height"]


def test_no_dividers_clears_the_spans_too() -> None:
    document = _valid(cabinet(dividers=1, divider_positions_mm=[373], divider_spans=TOP_SPAN))
    revised, lines = revise_spec(
        copy.deepcopy(document), PackageChanges.model_validate({"modules": {"cabinet": {"dividers": 0}}})
    )
    assert "divider_spans" not in revised["modules"][0]
    assert any("divider_spans" in line and "full height" in line for line in lines)


def test_the_preview_lists_the_divider_row_and_the_confirmat_change() -> None:
    before = _valid(cabinet())
    after = _valid(cabinet(dividers=1, divider_positions_mm=[373], divider_spans=TOP_SPAN))
    effects = derived_changes(before, after)
    assert "Cut list: + cabinet-divider 383 × 388 mm ×1" in effects
    assert "Hardware: Confirmat screw 7×50 mm 24 → 28" in effects


def test_the_preview_lists_fixing_a_shelf() -> None:
    before = _valid(cabinet(shelves=0, adjustable_shelves=4))
    after = _valid(
        cabinet(shelves=1, adjustable_shelves=3, shelf_kinds=["adjustable", "adjustable", "adjustable", "fixed"])
    )
    effects = derived_changes(before, after)
    assert any(line.startswith("Cut list: + cabinet-shelf ") for line in effects)
    assert any("cabinet-adjustable-shelf" in line and "×4 →" in line and "×3" in line for line in effects)
    assert "Hardware: Confirmat screw 7×50 mm 8 → 12" in effects


def test_a_name_change_shows_no_derived_lines() -> None:
    before = _valid(cabinet())
    after = copy.deepcopy(before)
    after["modules"][0]["name"] = "Renamed"
    assert derived_changes(before, after) == []
