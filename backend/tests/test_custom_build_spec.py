"""custom-build-packages: the `custom_build` contract and its rule-table derivation.

No database and no Blender: validation is `CustomBuildSpec`, derivation is the
standard-library `app.blender.custom_build.derive` the Phase 3 generator will
share. The fold-down desk's expected shop data is checked in beside this file,
so a rule change shows up as a reviewed diff of those two CSVs.
"""

from __future__ import annotations

import copy
import csv
import io
import json
from itertools import pairwise
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.blender.custom_build.derive import (
    FLAP_HINGE_ID,
    FLAP_STAY_ID,
    HINGE_ID,
    PUSH_LATCH_ID,
    derive,
    drilling,
    emitted_spec,
    end_cut_edges,
    extra_piece_corners,
    extra_piece_faces,
    handle_layout,
    overall,
    slat_handle_warnings,
    slat_layout,
)
from app.blender.schemas import CustomBuildSpec
from app.blender.schemas import describe_validation_error as _describe_validation_error
from app.blender.shop_csv import CUTLIST_FIELDS, HARDWARE_FIELDS, write_csv

BACKEND_ROOT = Path(__file__).resolve().parents[1]
TEMPLATES = BACKEND_ROOT / "fixtures/packages/templates"
EXPECTED = Path(__file__).parent / "fixtures/custom_build"


@pytest.fixture
def desk() -> dict:
    return json.loads((TEMPLATES / "fold-down-desk.json").read_text(encoding="utf-8"))


def _refusal(document: dict) -> str:
    with pytest.raises(ValidationError) as caught:
        CustomBuildSpec.model_validate(document)
    return _describe_validation_error(caught.value)


def _csv_text(rows: list[dict], fields: list[str], tmp_path: Path, name: str) -> str:
    path = tmp_path / name
    write_csv(path, rows, fields)
    return path.read_text(encoding="utf-8")


def _module(**overrides) -> dict:
    module = {
        "id": "m",
        "name": "Module",
        "x": 0,
        "y": 0,
        "z": 0,
        "width": 600,
        "height": 800,
        "depth": 400,
        "carcass": "carcass",
        "back": "back",
    }
    module.update(overrides)
    return module


# --- the contract --------------------------------------------------------------------


def test_the_fold_down_desk_template_is_valid_as_shipped(desk: dict) -> None:
    spec = CustomBuildSpec.model_validate(desk)

    assert spec.context.overall == {"w": 1000, "h": 700, "d": 300}
    parts, hardware, assembly = derive(spec.model_dump(mode="json"))
    assert parts and hardware and assembly


def test_the_blank_build_template_is_valid_and_derives_nothing() -> None:
    blank = json.loads((TEMPLATES / "blank-build.json").read_text(encoding="utf-8"))
    spec = CustomBuildSpec.model_validate(blank)

    assert spec.context.overall == {"w": 1000, "h": 2000, "d": 600}
    parts, hardware, _assembly = derive(spec.model_dump(mode="json"))
    assert parts == [] and hardware == []


def test_the_custom_build_starter_is_valid_and_shows_a_cabinet() -> None:
    starter = json.loads((TEMPLATES / "custom-build.json").read_text(encoding="utf-8"))
    spec = CustomBuildSpec.model_validate(starter)

    assert starter["template"] == "custom-build"
    assert len(starter["modules"]) == 1
    cabinet = starter["modules"][0]
    assert cabinet["carcass"] and cabinet["back"] and cabinet["shelves"] >= 1
    assert cabinet["fronts"] == [{"type": "door", "count": 2, "opening": "hinge"}]
    assert spec.context.overall == {"w": 800, "h": 1800, "d": 400}
    parts, hardware, assembly = derive(spec.model_dump(mode="json"))
    assert parts and hardware and assembly


def test_an_unknown_field_is_refused_naming_it(desk: dict) -> None:
    desk["modules"][0]["script"] = "__import__('os').system('true')"

    message = _refusal(desk)

    assert "modules.0.script" in message
    assert "Extra inputs are not permitted" in message


@pytest.mark.parametrize("value", [0, -1, 10_001])
def test_a_template_edited_out_of_range_is_refused_naming_the_width(desk: dict, value: int) -> None:
    desk["modules"][0]["width"] = value

    assert "modules.0.width" in _refusal(desk)


def test_a_float_dimension_is_refused(desk: dict) -> None:
    desk["modules"][0]["height"] = 700.5

    assert "modules.0.height" in _refusal(desk)


def test_a_duplicate_module_id_is_refused(desk: dict) -> None:
    desk["modules"].append({**copy.deepcopy(desk["modules"][0]), "x": 1000})

    assert "duplicate module id 'cabinet'" in _refusal(desk)


def test_an_undefined_material_slot_is_refused(desk: dict) -> None:
    desk["modules"][0]["back"] = "plywood"

    assert "modules[0].back: undefined material slot 'plywood'" in _refusal(desk)


def test_an_extra_part_with_an_undefined_slot_is_refused(desk: dict) -> None:
    desk["extra_parts"] = [
        {"id": "top", "name": "Top", "qty": 1, "length": 1000, "width": 300, "material": "oak"}
    ]

    assert "extra_parts[0].material: undefined material slot 'oak'" in _refusal(desk)


def test_a_material_the_price_list_cannot_read_is_accepted_for_review(desk: dict) -> None:
    """material-review-on-import: the wording is reviewed, not refused."""
    desk["materials"]["carcass"]["material"] = "Kiln-dried solid European oak"

    spec = CustomBuildSpec.model_validate(desk)

    assert spec.materials["carcass"].material == "Kiln-dried solid European oak"


def test_an_override_material_the_price_list_cannot_read_is_accepted(desk: dict) -> None:
    desk["part_overrides"] = [{"id": "cabinet-back", "material": "Solid hardwood"}]

    assert CustomBuildSpec.model_validate(desk).part_overrides[0].material == "Solid hardwood"


def test_a_slot_thickness_that_contradicts_its_material_is_refused(desk: dict) -> None:
    desk["materials"]["carcass"]["thickness_mm"] = 19

    assert "materials.carcass.thickness_mm" in _refusal(desk)


def test_overlapping_modules_are_refused_naming_both(desk: dict) -> None:
    desk["modules"].append({**copy.deepcopy(desk["modules"][0]), "id": "second", "x": 990})

    message = _refusal(desk)

    assert "'cabinet'" in message and "'second'" in message
    assert "overlap" in message


def test_touching_modules_are_accepted(desk: dict) -> None:
    desk["modules"].append({**copy.deepcopy(desk["modules"][0]), "id": "second", "x": 1000})

    CustomBuildSpec.model_validate(desk)


def test_too_many_doors_for_the_opening_are_refused(desk: dict) -> None:
    desk["modules"][0]["width"] = 300
    desk["modules"][0]["fronts"] = [{"type": "door", "count": 4, "opening": "hinge"}]

    message = _refusal(desk)

    assert "modules[0].fronts[0]" in message
    assert "'cabinet'" in message


def test_stated_front_heights_beyond_the_module_are_refused(desk: dict) -> None:
    desk["modules"][0]["fronts"] = [
        {"type": "drawer", "count": 1, "height": 500},
        {"type": "door", "count": 1, "opening": "hinge"},
        {"type": "door", "count": 1, "opening": "hinge", "height": 300},
    ]

    assert "modules[0].fronts" in _refusal(desk)


def test_a_module_narrower_than_twice_its_carcass_is_refused(desk: dict) -> None:
    desk["modules"][0]["width"] = 36
    desk["modules"][0]["fronts"] = []

    assert "modules[0].width" in _refusal(desk)


def test_a_blank_build_without_an_envelope_is_refused_naming_it() -> None:
    blank = json.loads((TEMPLATES / "blank-build.json").read_text(encoding="utf-8"))
    del blank["envelope"]

    assert "envelope" in _refusal(blank)


def test_a_module_outside_its_envelope_is_refused(desk: dict) -> None:
    desk["envelope"] = {"width": 900, "height": 2000, "depth": 600}

    assert "outside the envelope" in _refusal(desk)


def test_more_than_twenty_modules_are_refused(desk: dict) -> None:
    template = desk["modules"][0]
    desk["modules"] = [
        {**copy.deepcopy(template), "id": f"m{i}", "x": i * 1000 % 10_000, "y": (i // 10) * 300}
        for i in range(21)
    ]

    assert "modules" in _refusal(desk)


def test_more_than_two_hundred_derived_rows_are_refused(desk: dict) -> None:
    fronts = [{"type": "drawer", "count": 1, "height": 110} for _ in range(10)]
    desk["modules"] = [
        _module(id=f"m{i}", x=(i % 10) * 600, y=(i // 10) * 400, height=1100, fronts=fronts)
        for i in range(20)
    ]

    assert "at most 200" in _refusal(desk)


def test_an_extra_part_id_that_collides_with_a_derived_row_is_refused(desk: dict) -> None:
    desk["extra_parts"] = [
        {
            "id": "cabinet-side",
            "name": "Clash",
            "qty": 1,
            "length": 100,
            "width": 100,
            "material": "carcass",
        }
    ]

    assert "'cabinet-side' is used twice" in _refusal(desk)


# --- the rule table ------------------------------------------------------------------


def test_the_fold_down_desk_derives_the_checked_in_shop_data(desk: dict, tmp_path: Path) -> None:
    parts, hardware, _assembly = derive(CustomBuildSpec.model_validate(desk).model_dump(mode="json"))

    assert _csv_text(parts, CUTLIST_FIELDS, tmp_path, "c.csv") == (
        EXPECTED / "fold-down-desk.cutlist.csv"
    ).read_text(encoding="utf-8")
    assert _csv_text(hardware, HARDWARE_FIELDS, tmp_path, "h.csv") == (
        EXPECTED / "fold-down-desk.hardware.csv"
    ).read_text(encoding="utf-8")


def test_a_carcass_yields_its_panels_sized_by_the_rules(desk: dict) -> None:
    desk["modules"][0]["fronts"] = []
    parts, _hardware, _assembly = derive(CustomBuildSpec.model_validate(desk).model_dump(mode="json"))
    rows = {row["id"]: row for row in parts}

    assert set(rows) == {"cabinet-side", "cabinet-top-bottom", "cabinet-back", "cabinet-shelf"}
    assert (rows["cabinet-side"]["qty"], rows["cabinet-side"]["l"], rows["cabinet-side"]["w"]) == (2, 700, 288)
    assert (rows["cabinet-top-bottom"]["qty"], rows["cabinet-top-bottom"]["l"]) == (2, 964)
    assert (rows["cabinet-back"]["l"], rows["cabinet-back"]["w"], rows["cabinet-back"]["t"]) == (700, 1000, 12)
    assert (rows["cabinet-shelf"]["qty"], rows["cabinet-shelf"]["l"], rows["cabinet-shelf"]["w"]) == (2, 964, 288)
    assert all(row["module"] == "cabinet" for row in parts)
    assert rows["cabinet-back"]["material"] == "12 mm birch plywood"
    assert rows["cabinet-side"]["material"] == "18 mm oak-veneered birch"


def test_a_flap_brings_its_hinges_and_a_pair_of_stays(desk: dict) -> None:
    _parts, hardware, _assembly = derive(CustomBuildSpec.model_validate(desk).model_dump(mode="json"))
    lines = {line["id"]: line["qty"] for line in hardware}

    assert lines[FLAP_HINGE_ID] == 2
    assert lines[FLAP_STAY_ID] == 2


@pytest.mark.parametrize(("height", "hinges"), [(800, 2), (1500, 3), (2000, 4)])
def test_door_hinges_follow_the_door_height(desk: dict, height: int, hinges: int) -> None:
    desk["modules"] = [
        _module(height=height, fronts=[{"type": "door", "count": 2, "opening": "hinge"}])
    ]
    parts, hardware, _assembly = derive(CustomBuildSpec.model_validate(desk).model_dump(mode="json"))
    door = next(row for row in parts if row["id"] == "m-door-1")

    assert (door["qty"], door["l"], door["w"]) == (2, height - 3, (600 - 6) // 2)
    assert {line["id"]: line["qty"] for line in hardware}[HINGE_ID] == 2 * hinges
    assert "handle" in door["notes"]


def test_a_push_latch_door_gets_a_latch_and_no_handle_note(desk: dict) -> None:
    desk["modules"] = [_module(fronts=[{"type": "door", "count": 1, "opening": "push_latch"}])]
    parts, hardware, _assembly = derive(CustomBuildSpec.model_validate(desk).model_dump(mode="json"))
    door = next(row for row in parts if row["id"] == "m-door-1")

    assert {line["id"]: line["qty"] for line in hardware}[PUSH_LATCH_ID] == 1
    assert "no handle" in door["notes"]


def test_drawers_get_a_box_and_one_runner_pair_each(desk: dict) -> None:
    desk["modules"] = [_module(fronts=[{"type": "drawer", "count": 2}])]
    parts, hardware, _assembly = derive(CustomBuildSpec.model_validate(desk).model_dump(mode="json"))
    rows = {row["id"]: row for row in parts}

    assert rows["m-drawer-1-front"]["qty"] == 2
    assert rows["m-drawer-1-side"]["qty"] == 4
    assert rows["m-drawer-1-back"]["qty"] == 2
    assert rows["m-drawer-1-bottom"]["qty"] == 2
    # 400 deep less a 12 mm back leaves 388; the longest runner leaving 10 mm is 350.
    assert rows["m-drawer-1-side"]["l"] == 350
    assert {line["id"]: line["qty"] for line in hardware}["drawer-runner-350"] == 2


def test_extra_parts_and_free_hardware_are_added_as_given(desk: dict) -> None:
    desk["extra_parts"] = [
        {
            "id": "desk-leg",
            "name": "Folding leg",
            "qty": 2,
            "length": 700,
            "width": 60,
            "material": "carcass",
            "hardware": [{"id": "leg-hinge", "item": "Leg hinge", "qty": 2}],
        }
    ]
    desk["hardware"] = [{"id": "confirmat-7x50", "item": "Confirmat screw 7×50 mm", "qty": 4}]
    parts, hardware, _assembly = derive(CustomBuildSpec.model_validate(desk).model_dump(mode="json"))
    lines = {line["id"]: line["qty"] for line in hardware}

    assert parts[-1]["id"] == "desk-leg" and parts[-1]["module"] == "extras"
    assert parts[-1]["t"] == 18
    assert lines["leg-hinge"] == 2
    assert lines["confirmat-7x50"] == 16 + 4


def test_derivation_is_reproducible(desk: dict) -> None:
    normalised = CustomBuildSpec.model_validate(desk).model_dump(mode="json")

    assert derive(normalised) == derive(copy.deepcopy(normalised))
    assert emitted_spec(normalised) == emitted_spec(copy.deepcopy(normalised))


def test_the_emitted_spec_carries_the_studios_fields(desk: dict) -> None:
    normalised = CustomBuildSpec.model_validate(desk).model_dump(mode="json")
    emitted = emitted_spec(normalised)

    assert emitted["kind"] == "custom_build"
    assert emitted["overall"] == {"w": 1000, "h": 700, "d": 300}
    assert emitted["modules"]["cabinet"] == {"x": 0, "y": 0, "z": 750, "w": 1000, "h": 700, "d": 300, "shelves": 2}
    assert [front["type"] for front in emitted["fronts"]] == ["flap"]
    assert emitted["fronts"][0]["z"] == 751.5
    assert emitted["layers"] == {}
    assert emitted["input"] == normalised


def test_the_derived_csv_rows_have_positive_dimensions(desk: dict) -> None:
    parts, _hardware, _assembly = derive(CustomBuildSpec.model_validate(desk).model_dump(mode="json"))
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=CUTLIST_FIELDS)
    writer.writeheader()
    writer.writerows(parts)
    rows = list(csv.DictReader(io.StringIO(buffer.getvalue())))

    assert all(int(row["l"]) > 0 and int(row["w"]) > 0 and int(row["t"]) > 0 for row in rows)


# --- part overrides (design-iteration-workflow) ----------------------------------------------


def test_a_part_override_is_accepted_and_kept(desk: dict) -> None:
    desk["part_overrides"] = [{"id": "cabinet-back", "supply": "Personal_Supply"}]
    spec = CustomBuildSpec.model_validate(desk).model_dump(mode="json")
    assert spec["part_overrides"][0]["supply"] == "Personal_Supply"


def test_an_override_naming_no_derived_row_is_refused(desk: dict) -> None:
    desk["part_overrides"] = [{"id": "cabinet-drawer-1", "qty": 2}]
    message = _refusal(desk)
    assert "part_overrides[0].id" in message and "cabinet-drawer-1" in message


def test_a_row_overridden_twice_is_refused(desk: dict) -> None:
    desk["part_overrides"] = [{"id": "cabinet-side", "qty": 3}, {"id": "cabinet-side", "qty": 4}]
    assert "overridden twice" in _refusal(desk)


def test_an_override_with_an_unknown_field_is_refused(desk: dict) -> None:
    desk["part_overrides"] = [{"id": "cabinet-side", "colour": "red"}]
    assert "colour" in _refusal(desk)


def test_an_override_changes_one_row_and_nothing_else(desk: dict) -> None:
    plain, plain_hardware, _ = derive(CustomBuildSpec.model_validate(copy.deepcopy(desk)).model_dump(mode="json"))
    desk["part_overrides"] = [{"id": "cabinet-side", "length": 720, "notes": "scribe allowance"}]
    parts, hardware, _ = derive(CustomBuildSpec.model_validate(desk).model_dump(mode="json"))

    side = next(part for part in parts if part["id"] == "cabinet-side")
    assert side["l"] == 720
    assert side["notes"] == "scribe allowance [overridden: length, notes]"
    assert side["module"] == "cabinet"
    assert [part for part in parts if part["id"] != "cabinet-side"] == [
        part for part in plain if part["id"] != "cabinet-side"
    ]
    assert hardware == plain_hardware


def test_a_personal_supply_mark_is_carried_in_the_notes(desk: dict) -> None:
    desk["part_overrides"] = [{"id": "cabinet-back", "supply": "Personal_Supply"}]
    parts, _, _ = derive(CustomBuildSpec.model_validate(desk).model_dump(mode="json"))
    back = next(part for part in parts if part["id"] == "cabinet-back")
    assert back["notes"].endswith("[supply: Personal_Supply]")
    assert "[overridden:" not in back["notes"]


def test_an_extra_part_can_be_personal_supply(desk: dict) -> None:
    desk["extra_parts"] = [
        {"id": "desk-lip", "name": "Desk lip", "qty": 1, "length": 900, "width": 40, "material": "carcass",
         "supply": "Personal_Supply"}
    ]
    parts, _, _ = derive(CustomBuildSpec.model_validate(desk).model_dump(mode="json"))
    assert next(part for part in parts if part["id"] == "desk-lip")["notes"].endswith("[supply: Personal_Supply]")


def test_derivation_with_overrides_is_reproducible(desk: dict) -> None:
    desk["part_overrides"] = [{"id": "cabinet-shelf", "qty": 3, "banding": "none"}]
    spec = CustomBuildSpec.model_validate(desk).model_dump(mode="json")
    assert derive(spec) == derive(copy.deepcopy(spec))


# --- a slot resolved by the material review is marked (material-review-on-import) --------

_ORIGIN = {"material": "Birch plywood", "thickness_mm": 12, "lane": "auto",
           "accepted_by": "studio@example.de", "accepted_at": "2026-09-26"}


def _three_backs() -> dict:
    return {
        "kind": "custom_build", "schema_version": 1, "units": "mm", "name": "Three cabinets",
        "materials": {
            "carcass": {"material": "18 mm oak-veneered birch", "thickness_mm": 18},
            "back": {"material": "12 mm Multiplex birch", "thickness_mm": 12, "resolved_from": dict(_ORIGIN)},
        },
        "modules": [_module(id="a", x=0), _module(id="b", x=600), _module(id="c", x=1200)],
    }


def test_a_resolved_slot_carries_its_origin() -> None:
    spec = CustomBuildSpec.model_validate(_three_backs()).model_dump(mode="json")

    assert spec["materials"]["back"]["resolved_from"] == _ORIGIN
    assert "resolved_from" not in spec["materials"]["carcass"]


def test_every_row_of_a_resolved_slot_is_marked() -> None:
    parts = derive(CustomBuildSpec.model_validate(_three_backs()).model_dump(mode="json"))[0]

    backs = [p for p in parts if p["material"] == "12 mm Multiplex birch"]
    assert len(backs) == 3
    for row in backs:
        assert (
            "[material substituted: Birch plywood → 12 mm Multiplex birch; "
            "pre-approved by rule, accepted by studio@example.de on 2026-09-26]"
        ) in row["notes"]
    assert not any("material substituted" in p["notes"] for p in parts if p not in backs)


def test_a_thickness_change_is_stated() -> None:
    document = _three_backs()
    document["materials"]["back"]["resolved_from"]["thickness_mm"] = 10

    parts = derive(CustomBuildSpec.model_validate(document).model_dump(mode="json"))[0]

    back = next(p for p in parts if p["material"] == "12 mm Multiplex birch")
    assert "Birch plywood (10 mm) → 12 mm Multiplex birch" in back["notes"] and back["t"] == 12


def test_an_override_of_another_field_keeps_the_mark() -> None:
    document = _three_backs()
    parts = derive(CustomBuildSpec.model_validate(document).model_dump(mode="json"))[0]
    back_id = next(p["id"] for p in parts if p["material"] == "12 mm Multiplex birch")
    document["part_overrides"] = [{"id": back_id, "qty": 2}]

    row = next(p for p in derive(CustomBuildSpec.model_validate(document).model_dump(mode="json"))[0]
               if p["id"] == back_id)

    assert "material substituted" in row["notes"] and "[overridden: qty]" in row["notes"]


def test_a_plain_slot_derives_no_mark(desk: dict) -> None:
    parts = derive(CustomBuildSpec.model_validate(desk).model_dump(mode="json"))[0]

    assert not any("material substituted" in p["notes"] for p in parts)


def test_the_published_cutlist_carries_the_mark(tmp_path: Path) -> None:
    parts = derive(CustomBuildSpec.model_validate(_three_backs()).model_dump(mode="json"))[0]

    rows = list(csv.DictReader(io.StringIO(_csv_text(parts, CUTLIST_FIELDS, tmp_path, "cutlist.csv"))))

    assert sum("material substituted: Birch plywood" in row["notes"] for row in rows) == 3


def test_a_resolution_record_with_an_unknown_lane_is_refused() -> None:
    document = _three_backs()
    document["materials"]["back"]["resolved_from"]["lane"] = "model"

    assert "materials.back.resolved_from.lane" in _refusal(document)


# --- room scene schema: the tier owns frames and resolution -----------------------------------


@pytest.mark.parametrize(
    "output", [{"kind": "turntable", "frames": 36}, {"kind": "still", "resolution": "draft"}]
)
def test_the_room_schema_refuses_tier_owned_output_fields_by_name(output: dict) -> None:
    from app.blender.schemas import RoomSceneSpec, describe_validation_error

    document = json.loads((BACKEND_ROOT / "fixtures/packages/room-scene-rectangle.json").read_text())
    document["output"] = output
    with pytest.raises(ValidationError) as caught:
        RoomSceneSpec.model_validate(document)
    assert next(k for k in output if k != "kind") in describe_validation_error(caught.value)


# --- adjustable shelves, hinge keys and wall shelves (cabinet-hardware-calculator) ------------


def _shelf_build(**shelf) -> dict:
    entry = {
        "id": "wall-shelf-1", "name": "Wall shelf", "x": 100, "z": 1400, "length": 1200, "depth": 250,
        "material": "carcass", "bracket": "bracket-white",
    }
    entry.update(shelf)
    return {
        "kind": "custom_build", "schema_version": 1, "units": "mm", "name": "Shelf",
        "materials": {"carcass": {"material": "Eiche 18 mm", "thickness_mm": 18}},
        "envelope": {"width": 2000, "height": 2000, "depth": 400},
        "wall_shelves": [entry],
    }


def test_adjustable_shelves_and_the_hinge_key_are_accepted(desk: dict) -> None:
    desk["modules"][0]["adjustable_shelves"] = 2
    desk["modules"][0]["shelf_pin"] = "shelf-pin-5mm"
    spec = CustomBuildSpec.model_validate(desk)
    assert spec.modules[0].adjustable_shelves == 2 and spec.modules[0].shelf_pin == "shelf-pin-5mm"


def test_a_door_defaults_to_the_concealed_hinge_and_can_name_another() -> None:
    starter = json.loads((TEMPLATES / "custom-build.json").read_text(encoding="utf-8"))
    assert CustomBuildSpec.model_validate(starter).modules[0].fronts[0].hinge == "hinge-concealed-110"
    starter["modules"][0]["fronts"][0]["hinge"] = "hinge-blum-clip-110"
    assert CustomBuildSpec.model_validate(starter).modules[0].fronts[0].hinge == "hinge-blum-clip-110"


@pytest.mark.parametrize("positions", [None, [150, 600, 1050]])
def test_a_wall_shelf_is_accepted_with_and_without_positions(positions: list[int] | None) -> None:
    document = _shelf_build(bracket_positions_mm=positions) if positions else _shelf_build()
    spec = CustomBuildSpec.model_validate(document)
    assert spec.wall_shelves[0].bracket_positions_mm == positions


def test_a_bracket_outside_the_board_is_refused_naming_the_field() -> None:
    message = _refusal(_shelf_build(length=900, bracket_positions_mm=[100, 950]))
    assert "wall_shelves[0].bracket_positions_mm" in message and "900" in message


def test_positions_out_of_order_are_refused() -> None:
    message = _refusal(_shelf_build(bracket_positions_mm=[600, 150, 1050]))
    assert "wall_shelves[0].bracket_positions_mm" in message and "strictly increasing" in message


@pytest.mark.parametrize("positions", [[], list(range(10, 220, 10))])
def test_an_empty_or_long_position_list_is_refused(positions: list[int]) -> None:
    assert "wall_shelves.0.bracket_positions_mm" in _refusal(_shelf_build(bracket_positions_mm=positions))


def test_a_wall_shelf_id_must_be_unique_across_modules_and_parts(desk: dict) -> None:
    document = _shelf_build(id=desk["modules"][0]["id"])
    document["modules"] = [desk["modules"][0]]
    document["materials"] = desk["materials"]
    message = _refusal(document)
    assert "wall_shelves[0].id" in message


def test_a_wall_shelf_outside_the_envelope_or_without_a_slot_is_refused() -> None:
    assert "outside the envelope" in _refusal(_shelf_build(x=1000))
    assert "undefined material slot" in _refusal(_shelf_build(material="nope"))


@pytest.mark.parametrize("field", ["load_kg", "pin_pitch_mm"])
def test_unknown_shelf_and_module_fields_are_refused_by_name(desk: dict, field: str) -> None:
    assert f"wall_shelves.0.{field}" in _refusal(_shelf_build(**{field: 5}))
    desk["modules"][0][field] = 5
    assert f"modules.0.{field}" in _refusal(desk)


# --- shelf spacing, shelf positions and dividers (shelf-spacing-and-dividers) ---------------


def _interior_build(**module) -> dict:
    entry = {
        "id": "cabinet", "name": "Cabinet", "x": 0, "y": 0, "z": 0, "width": 1000, "height": 1600,
        "depth": 400, "carcass": "carcass", "shelves": 4,
    }
    entry.update(module)
    return {
        "kind": "custom_build", "schema_version": 1, "units": "mm", "name": "Cabinet",
        "materials": {"carcass": {"material": "Eiche 18 mm", "thickness_mm": 18}},
        "modules": [entry],
    }


def test_shelves_355_mm_apart_are_placed_from_the_bottom_panel() -> None:
    from app.blender.custom_build.derive import shelf_undersides

    spec = CustomBuildSpec.model_validate(_interior_build(shelf_spacing_mm=355))
    module = spec.model_dump(mode="json")["modules"][0]
    assert shelf_undersides(module, 18) == [355, 728, 1101, 1474]


def test_a_spacing_that_does_not_fit_is_refused_naming_the_inner_height() -> None:
    message = _refusal(_interior_build(height=1200, shelf_spacing_mm=355))
    assert "modules[0].shelf_spacing_mm" in message and "1164 mm" in message


def test_uneven_positions_are_accepted() -> None:
    from app.blender.custom_build.derive import shelf_undersides

    spec = CustomBuildSpec.model_validate(_interior_build(shelves=3, shelf_positions_mm=[300, 700, 1300]))
    assert shelf_undersides(spec.model_dump(mode="json")["modules"][0], 18) == [300, 700, 1300]


def test_the_wrong_number_of_positions_is_refused() -> None:
    message = _refusal(_interior_build(shelves=3, shelf_positions_mm=[300, 700]))
    assert "modules[0].shelf_positions_mm" in message and "3 shelves expected" in message


def test_overlapping_positions_are_refused() -> None:
    message = _refusal(_interior_build(shelves=2, shelf_positions_mm=[300, 310]))
    assert "modules[0].shelf_positions_mm" in message and "18 mm" in message


def test_spacing_and_positions_together_are_refused_naming_both() -> None:
    message = _refusal(_interior_build(shelf_spacing_mm=355, shelf_positions_mm=[1, 100, 200, 300]))
    assert "shelf_spacing_mm" in message and "shelf_positions_mm" in message


def test_a_spacing_without_shelves_is_refused() -> None:
    assert "no shelves" in _refusal(_interior_build(shelves=0, shelf_spacing_mm=355))


def test_a_module_without_the_new_fields_serialises_as_before(desk: dict) -> None:
    module = CustomBuildSpec.model_validate(desk).model_dump(mode="json")["modules"][0]
    assert not {"shelf_spacing_mm", "shelf_positions_mm", "dividers", "divider_positions_mm"} & module.keys()


def test_dividers_with_and_without_positions_are_accepted() -> None:
    assert CustomBuildSpec.model_validate(_interior_build(dividers=2)).modules[0].dividers == 2
    spec = CustomBuildSpec.model_validate(_interior_build(dividers=1, divider_positions_mm=[400]))
    assert spec.modules[0].divider_positions_mm == [400]


def test_a_divider_outside_the_inner_width_is_refused() -> None:
    message = _refusal(_interior_build(dividers=1, divider_positions_mm=[960]))
    assert "modules[0].divider_positions_mm" in message and "964 mm" in message


@pytest.mark.parametrize(
    ("dividers", "positions", "expected"),
    [(0, [400], "0 dividers expected"), (2, [400], "2 dividers expected"), (2, [400, 410], "more than")],
)
def test_divider_positions_must_match_and_increase(dividers: int, positions: list[int], expected: str) -> None:
    message = _refusal(_interior_build(dividers=dividers, divider_positions_mm=positions))
    assert "modules[0].divider_positions_mm" in message and expected in message


def test_too_many_dividers_for_the_width_are_refused() -> None:
    assert "modules[0].dividers" in _refusal(_interior_build(width=200, dividers=10))


def test_an_unknown_divider_field_is_refused_by_name() -> None:
    assert "modules.0.divider_material" in _refusal(_interior_build(divider_material="oak"))


def test_a_change_can_set_spacing_and_refuses_an_unknown_field() -> None:
    from app.blender.schemas import PackageChanges

    changes = PackageChanges.model_validate({"modules": {"cabinet": {"shelf_spacing_mm": 355}}})
    assert changes.modules["cabinet"].shelf_spacing_mm == 355
    with pytest.raises(ValidationError) as caught:
        PackageChanges.model_validate({"modules": {"cabinet": {"divider_material": "oak"}}})
    assert "divider_material" in _describe_validation_error(caught.value)


# --- extra-part placement (extra-part-placement) --------------------------------------


def _extra(**overrides) -> dict:
    part = {"id": "brace", "name": "Brace", "qty": 1, "length": 1000, "width": 60, "material": "carcass"}
    part.update(overrides)
    return part


def _at(x: int = 0, y: int = 0, z: int = 0, length_along: str = "x", width_along: str = "y", **turns) -> dict:
    return {"x": x, "y": y, "z": z, "length_along": length_along, "width_along": width_along, **turns}


def _rounded(corners) -> list[tuple[float, float, float]]:
    return [tuple(round(value, 1) for value in corner) for corner in corners]


def test_a_square_on_piece_sits_at_its_corner_along_its_axes() -> None:
    corners = extra_piece_corners(_extra(length=1200), _at(0, 0, 900), 18)

    assert min(c[0] for c in corners) == 0 and max(c[0] for c in corners) == 1200
    assert max(c[1] for c in corners) == 60
    assert min(c[2] for c in corners) == 900 and max(c[2] for c in corners) == 918


def test_an_upright_piece_stands_on_its_length() -> None:
    corners = extra_piece_corners(_extra(length=900, width=45), _at(length_along="z", width_along="y"), 18)

    assert max(c[2] for c in corners) == 900 and max(c[1] for c in corners) == 45 and max(c[0] for c in corners) == 18


def test_a_tilt_turns_the_length_towards_the_named_axis() -> None:
    corners = _rounded(extra_piece_corners(_extra(), _at(100, tilt={"towards": "z", "angle_deg": 30}), 18))

    assert corners[0] == (100.0, 0.0, 0.0)
    assert corners[1] == (966.0, 0.0, 500.0)
    assert {c[1] for c in corners} == {0.0, 60.0}


def test_a_roll_turns_the_width_about_the_length() -> None:
    corners = _rounded(extra_piece_corners(_extra(length=1200, width=40), _at(roll_deg=45), 18))

    assert corners[3] == (0.0, 28.3, 28.3)
    assert {c[0] for c in corners} == {0.0, 1200.0}


def test_roll_then_tilt_keeps_the_piece_rigid() -> None:
    corners = extra_piece_corners(_extra(), _at(roll_deg=20, tilt={"towards": "y", "angle_deg": -40}), 18)

    def distance(a: int, b: int) -> float:
        return sum((p - q) ** 2 for p, q in zip(corners[a], corners[b], strict=True)) ** 0.5

    assert round(distance(0, 1), 6) == 1000 and round(distance(0, 3), 6) == 60 and round(distance(0, 4), 6) == 18


def test_opposite_end_cuts_give_a_parallelogram_with_plumb_ends_on_a_tilted_brace() -> None:
    brace = _extra(end_cuts={"across": "width", "start_deg": 30, "end_deg": -30})
    corners = extra_piece_corners(brace, _at(width_along="z", tilt={"towards": "z", "angle_deg": 30}), 18)

    assert round(corners[0][0], 6) == round(corners[3][0], 6)
    assert round(corners[1][0], 6) == round(corners[2][0], 6)
    assert end_cut_edges(brace, 18) == (pytest.approx(1000 - 60 * 0.57735, abs=0.01), pytest.approx(1000 - 60 * 0.57735, abs=0.01))


def test_matching_end_cuts_give_a_mitred_trapezoid() -> None:
    stile = _extra(length=600, width=50, end_cuts={"across": "width", "start_deg": 45, "end_deg": 45})

    assert end_cut_edges(stile, 18) == (600, pytest.approx(500))


def test_a_piece_on_a_left_handed_choice_of_axes_has_its_faces_reversed() -> None:
    right = extra_piece_faces(_at(length_along="x", width_along="y"))
    left = extra_piece_faces(_at(length_along="x", width_along="z"))

    assert left == tuple(tuple(reversed(face)) for face in right)


def test_placements_disagreeing_with_qty_are_refused(desk: dict) -> None:
    desk["extra_parts"] = [_extra(id="slat", qty=4, placements=[_at(z=100 * n) for n in range(3)])]

    refusal = _refusal(desk)
    assert "extra_parts[0].placements" in refusal and "4 are needed" in refusal


@pytest.mark.parametrize(
    ("placement", "field"),
    [
        (_at(width_along="x"), "width_along"),
        (_at(tilt={"towards": "x", "angle_deg": 30}), "tilt.towards"),
        (_at(tilt={"towards": "z", "angle_deg": 0}), "angle_deg"),
        (_at(roll_deg=0), "roll_deg"),
        (_at(roll_deg=90), "roll_deg"),
    ],
)
def test_an_impossible_placement_is_refused_naming_the_field(desk: dict, placement: dict, field: str) -> None:
    desk["extra_parts"] = [_extra(placements=[placement])]

    assert field in _refusal(desk)


def test_end_cuts_that_leave_no_length_are_refused(desk: dict) -> None:
    desk["extra_parts"] = [_extra(id="stub", length=80, end_cuts={"across": "width", "start_deg": 45, "end_deg": 45})]

    refusal = _refusal(desk)
    assert "stub" in refusal and "leave no length" in refusal


def test_a_placed_piece_outside_the_envelope_is_refused(desk: dict) -> None:
    desk["envelope"] = {"width": 1200, "height": 2000, "depth": 600}
    desk["extra_parts"] = [_extra(id="rail", placements=[_at(300, 0, 100)])]

    assert "part 'rail' lies outside the envelope" in _refusal(desk)


def test_a_tilted_piece_leaving_the_envelope_is_refused(desk: dict) -> None:
    desk["envelope"] = {"width": 1200, "height": 1000, "depth": 600}
    desk["modules"][0]["z"] = 0
    desk["extra_parts"] = [_extra(length=1200, placements=[_at(tilt={"towards": "z", "angle_deg": 60})])]

    assert "part 'brace' lies outside the envelope" in _refusal(desk)


def test_a_placed_piece_inside_the_envelope_is_accepted_and_kept(desk: dict) -> None:
    desk["envelope"] = {"width": 1200, "height": 2000, "depth": 600}
    desk["extra_parts"] = [_extra(placements=[_at(100, tilt={"towards": "z", "angle_deg": 30})])]

    stored = CustomBuildSpec.model_validate(desk).model_dump(mode="json")
    assert stored["extra_parts"][0]["placements"] == [_at(100, tilt={"towards": "z", "angle_deg": 30})]


def test_an_unplaced_extra_part_serialises_as_before(desk: dict) -> None:
    desk["extra_parts"] = [_extra()]

    stored = CustomBuildSpec.model_validate(desk).model_dump(mode="json")
    assert "placements" not in stored["extra_parts"][0] and "end_cuts" not in stored["extra_parts"][0]


def test_placed_pieces_count_toward_the_overall_size_and_unplaced_do_not(desk: dict) -> None:
    unplaced = copy.deepcopy(desk)
    unplaced["extra_parts"] = [_extra()]
    desk["extra_parts"] = [_extra(length=2000, placements=[_at(0, 0, 750, tilt={"towards": "z", "angle_deg": 30})])]

    assert overall(unplaced) == overall({k: v for k, v in desk.items() if k != "extra_parts"})
    # The far end rises 1000 mm and the board's thickness, turned with it, adds 18 × cos 30°
    # above it and 18 × sin 30° behind the corner on x.
    assert overall(desk)["h"] == round(1000 + 18 * 0.8660254)
    assert overall(desk)["w"] == round(2000 * 0.8660254 + 9)


def test_placement_leaves_the_shop_data_unchanged(desk: dict) -> None:
    unplaced = copy.deepcopy(desk)
    unplaced["extra_parts"] = [_extra(qty=2)]
    desk["extra_parts"] = [_extra(qty=2, placements=[_at(z=750), _at(z=1300, roll_deg=10)])]

    first = derive(CustomBuildSpec.model_validate(unplaced).model_dump(mode="json"))
    second = derive(CustomBuildSpec.model_validate(desk).model_dump(mode="json"))
    assert first == second
    assert drilling(unplaced, {}) == drilling(desk, {})


def test_end_cuts_are_noted_on_the_row_and_keep_its_size(desk: dict) -> None:
    desk["extra_parts"] = [_extra(end_cuts={"across": "width", "start_deg": 30, "end_deg": -30})]

    parts, _hardware, _assembly = derive(CustomBuildSpec.model_validate(desk).model_dump(mode="json"))
    row = parts[-1]
    assert "ends cut 30° / −30° across width" in row["notes"]
    assert (row["qty"], row["l"], row["w"], row["t"]) == (1, 1000, 60, 18)


# --- front handles (front-handles) -----------------------------------------------------


BAR = {"kind": "bar", "length": 160}


@pytest.mark.parametrize(
    ("front", "named"),
    [
        ({"type": "door", "count": 1, "opening": "hinge", "handle": {"kind": "bar"}}, "handle.length"),
        ({"type": "door", "count": 1, "opening": "hinge", "handle": {"kind": "knob", "length": 30}}, "handle.length"),
        (
            {"type": "door", "count": 1, "opening": "hinge", "handle": {"kind": "knob", "orientation": "vertical"}},
            "handle.orientation",
        ),
        ({"type": "drawer", "count": 1, "handle": {**BAR, "edge": "left"}}, "handle.edge"),
        ({"type": "flap", "hinged": "bottom", "handle": {**BAR, "edge": "right"}}, "handle.edge"),
        ({"type": "door", "count": 3, "opening": "hinge", "handle": {**BAR, "edge": "meeting"}}, "handle.edge"),
        ({"type": "door", "count": 1, "opening": "hinge", "handle": {**BAR, "grip": "round"}}, "grip"),
    ],
)
def test_a_handle_that_breaks_its_rules_is_refused_naming_the_field(desk: dict, front: dict, named: str) -> None:
    desk["modules"] = [_module(width=900, fronts=[front])]

    message = _refusal(desk)

    assert "modules.0.fronts.0" in message
    assert named in message


def test_a_handle_on_a_push_latch_door_is_refused(desk: dict) -> None:
    desk["modules"] = [_module(fronts=[{"type": "door", "count": 1, "opening": "push_latch", "handle": BAR}])]

    message = _refusal(desk)

    assert "handle" in message
    assert "push-latch door takes no handle" in message


def test_a_front_without_a_handle_serialises_as_before(desk: dict) -> None:
    desk["modules"] = [_module(fronts=[{"type": "door", "count": 1, "opening": "hinge"}, {"type": "drawer", "count": 1}])]

    dumped = CustomBuildSpec.model_validate(desk).model_dump(mode="json")

    assert all("handle" not in front for front in dumped["modules"][0]["fronts"])


def test_a_handle_keeps_only_its_stated_fields(desk: dict) -> None:
    desk["modules"] = [_module(fronts=[{"type": "door", "count": 2, "opening": "hinge", "handle": BAR}])]

    dumped = CustomBuildSpec.model_validate(desk).model_dump(mode="json")

    assert dumped["modules"][0]["fronts"][0]["handle"] == {"kind": "bar", "length": 160, "finish": "black"}


def _laid_out(desk: dict, **module) -> list[dict]:
    desk["modules"] = [_module(**module)]
    spec = CustomBuildSpec.model_validate(desk).model_dump(mode="json")
    t = spec["materials"]["carcass"]["thickness_mm"]
    return handle_layout(spec["modules"][0], t, spec["materials"]["back"]["thickness_mm"])


def test_bar_handles_on_a_pair_of_doors_sit_on_the_meeting_edges(desk: dict) -> None:
    door = {"type": "door", "count": 2, "opening": "hinge", "handle": {"kind": "bar", "length": 900}}

    records = _laid_out(desk, width=900, height=2034, fronts=[door])

    assert [(r["row"], r["leaf"]) for r in records] == [("m-door-1", 0), ("m-door-1", 1)]
    # Leaves are 447 wide from 1.5 and 451.5: the meeting edges are at 448.5 and 451.5.
    assert [r["x"] for r in records] == [408.5, 491.5]
    assert [r["z"] for r in records] == [1017.0, 1017.0]
    assert {(r["key"], r["orientation"], r["w"], r["h"]) for r in records} == {("handle-bar-900-black", "vertical", 12, 900)}


def test_drawer_handles_are_centred_across_and_inset_from_the_top(desk: dict) -> None:
    drawers = {"type": "drawer", "count": 5, "handle": {"kind": "bar", "length": 160, "inset_mm": 30}}

    records = _laid_out(desk, width=900, height=900, fronts=[drawers])

    assert len(records) == 5
    assert {r["row"] for r in records} == {"m-drawer-1-front"}
    assert {r["x"] for r in records} == {450.0}
    # Drawer fronts are 177 high; the top one runs from 721.5 to 898.5.
    assert records[0]["z"] == 898.5 - 30
    assert {(r["orientation"], r["w"], r["h"]) for r in records} == {("horizontal", 160, 12)}


def test_handle_defaults_follow_the_front_type(desk: dict) -> None:
    fronts = [
        {"type": "flap", "hinged": "bottom", "height": 300, "handle": {"kind": "knob", "finish": "brass"}},
        {"type": "door", "count": 1, "opening": "hinge", "handle": {"kind": "bar", "length": 200, "edge": "left", "at_mm": 150}},
    ]

    flap, door = _laid_out(desk, width=600, height=800, fronts=fronts)

    assert (flap["key"], flap["item"], flap["w"]) == ("handle-knob-brass", "Knob, brass", 30)
    assert flap["z"] == 798.5 - 40  # opposite the bottom hinge: 40 mm below the flap's top edge
    assert flap["x"] == 300.0
    assert door["x"] == 1.5 + 40  # the left edge
    assert door["z"] == 1.5 + 150


def test_a_handle_too_long_for_its_leaf_is_refused_naming_the_leaf(desk: dict) -> None:
    drawers = {"type": "drawer", "count": 1, "handle": {"kind": "bar", "length": 500}}
    desk["modules"] = [_module(width=450, fronts=[drawers])]

    message = _refusal(desk)

    assert "modules[0].fronts[0].handle" in message
    assert "447 × 797 mm" in message


def test_a_handle_on_a_folded_module_is_refused(desk: dict) -> None:
    door = {"type": "door", "count": 1, "opening": "hinge", "handle": {"kind": "knob"}}
    fold = {"side": "left", "from_mm": 400, "along": "height", "angle_deg": 10, "towards": "inside"}
    desk["modules"] = [_module(fronts=[door], side_folds=[fold])]

    message = _refusal(desk)

    assert "modules[0].fronts[0].handle" in message
    assert "handles on a folded module are not supported" in message


def test_handles_add_one_hardware_line_per_key_and_name_it_on_the_door_row(desk: dict) -> None:
    fronts = [
        {"type": "door", "count": 2, "opening": "hinge", "handle": {"kind": "bar", "length": 160}},
        {"type": "drawer", "count": 3, "handle": {"kind": "bar", "length": 160}},
    ]
    desk["modules"] = [_module(width=900, height=1600, fronts=fronts)]

    parts, hardware, _assembly = derive(CustomBuildSpec.model_validate(desk).model_dump(mode="json"))
    lines = {line["id"]: line for line in hardware}
    door = next(row for row in parts if row["id"] == "m-door-1")

    assert lines["handle-bar-160-black"] == {
        "id": "handle-bar-160-black",
        "item": "Bar handle 160 mm, black",
        "qty": 5,
        "notes": "Rule: one handle per leaf",
    }
    assert door["notes"].endswith("; handle handle-bar-160-black")
    assert not any("handle" in row["id"] for row in parts)


def test_a_hand_written_handle_line_is_kept_beside_a_modelled_one(desk: dict) -> None:
    door = {"type": "door", "count": 1, "opening": "hinge", "handle": {"kind": "knob", "key": "knob-oak"}}
    hand = {"id": "bar-handle", "item": "Bar handle", "qty": 1}
    desk["modules"] = [_module(fronts=[door], hardware=[hand])]

    _parts, hardware, _assembly = derive(CustomBuildSpec.model_validate(desk).model_dump(mode="json"))
    lines = {line["id"]: line["qty"] for line in hardware}

    assert lines["bar-handle"] == 1
    assert lines["knob-oak"] == 1


def test_a_door_without_a_handle_keeps_its_note(desk: dict) -> None:
    desk["modules"] = [_module(fronts=[{"type": "door", "count": 1, "opening": "hinge"}])]

    parts, hardware, _assembly = derive(CustomBuildSpec.model_validate(desk).model_dump(mode="json"))

    assert next(row for row in parts if row["id"] == "m-door-1")["notes"].endswith("; handle as specified")
    assert not any(line["id"].startswith("handle-") for line in hardware)


# --- door slats (door-slats) -------------------------------------------------------------


SLAT_SLOT = {"material": "12 mm oak-veneered MDF", "thickness_mm": 12}


def _slat_door(**slats) -> dict:
    return {
        "type": "door",
        "count": 2,
        "opening": "hinge",
        "slats": {"count": 8, "width": 30, "material": "slats", **slats},
    }


def _kommode(desk: dict, *fronts: dict, **module) -> dict:
    """The Höffner dresser: 800 mm wide, two doors of 397 × 747 mm."""
    desk["materials"]["slats"] = dict(SLAT_SLOT)
    desk["modules"] = [_module(id="kommode", width=800, height=750, fronts=list(fronts), **module)]
    return desk


def _slat_rows(desk: dict) -> tuple[dict, list[dict]]:
    spec = CustomBuildSpec.model_validate(desk).model_dump(mode="json")
    parts, _hardware, _assembly = derive(spec)
    return spec, parts


def _slats_of(spec: dict) -> list[dict]:
    module = spec["modules"][0]
    return slat_layout(module, spec["materials"], 18, spec["materials"]["back"]["thickness_mm"])


def test_vertical_slats_on_the_right_door_only(desk: dict) -> None:
    spec, parts = _slat_rows(_kommode(desk, _slat_door(leaves=[2])))

    row = next(row for row in parts if row["id"] == "kommode-door-1-slat")
    assert (row["name"], row["qty"], row["l"], row["w"], row["t"]) == ("Door slat", 8, 747, 30, 12)
    assert row["material"] == "12 mm oak-veneered MDF"
    assert row["grain"] == "length (vertical)"
    assert row["notes"] == "Rule: 8 vertical slats per door, 22.4 mm gap, glued to the door face"
    slats = _slats_of(spec)
    assert {record["leaf"] for record in slats} == {1}
    # The right door runs from 401.5 to 798.5: the outer slats lie flush with its edges.
    assert slats[0]["x"] - 15 == 401.5
    assert slats[-1]["x"] + 15 == 798.5
    assert [record["x"] for record in slats] == sorted(record["x"] for record in slats)


def test_horizontal_slats_run_across_the_door_top_to_bottom(desk: dict) -> None:
    spec, parts = _slat_rows(_kommode(desk, _slat_door(count=10, width=40, orientation="horizontal", leaves=[2])))

    row = next(row for row in parts if row["id"] == "kommode-door-1-slat")
    assert (row["qty"], row["l"], row["w"], row["t"]) == (10, 397, 40, 12)
    assert row["grain"] == "length (left-right)"
    assert "10 horizontal slats per door" in row["notes"]
    slats = _slats_of(spec)
    # The door runs from z 1.5 to 748.5; the first slat sits on its top edge, the last on its bottom.
    assert slats[0]["z"] + 20 == 748.5
    assert slats[-1]["z"] - 20 == 1.5
    assert [record["z"] for record in slats] == sorted((record["z"] for record in slats), reverse=True)
    assert {(record["w"], record["h"]) for record in slats} == {(397, 40)}


def test_slats_go_on_every_door_by_default(desk: dict) -> None:
    spec, parts = _slat_rows(_kommode(desk, _slat_door(count=6, width=40)))

    assert next(row for row in parts if row["id"] == "kommode-door-1-slat")["qty"] == 12
    assert [record["leaf"] for record in _slats_of(spec)] == [0] * 6 + [1] * 6


def test_fewer_slats_are_re_spaced(desk: dict) -> None:
    spec, parts = _slat_rows(_kommode(desk, _slat_door(count=5, leaves=[2])))

    assert next(row for row in parts if row["id"] == "kommode-door-1-slat")["qty"] == 5
    slats = _slats_of(spec)
    gaps = {round(later["x"] - earlier["x"] - 30, 6) for earlier, later in pairwise(slats)}
    assert gaps == {round((397 - 150) / 4, 6)}


def test_slats_follow_a_resized_door(desk: dict) -> None:
    _spec, parts = _slat_rows(_kommode(desk, _slat_door(leaves=[2])))
    desk["modules"][0]["width"] = 900
    wider, wider_parts = _slat_rows(desk)

    before = next(row for row in parts if row["id"] == "kommode-door-1-slat")
    after = next(row for row in wider_parts if row["id"] == "kommode-door-1-slat")
    assert (after["qty"], after["l"]) == (before["qty"], before["l"])
    slats = _slats_of(wider)
    # Doors are 447 wide: the right door runs from 451.5 to 898.5.
    assert (slats[0]["x"] - 15, slats[-1]["x"] + 15) == (451.5, 898.5)


def test_a_margin_shortens_and_insets_the_slats(desk: dict) -> None:
    spec, parts = _slat_rows(_kommode(desk, _slat_door(margin_mm=20, leaves=[2])))

    assert next(row for row in parts if row["id"] == "kommode-door-1-slat")["l"] == 707
    slats = _slats_of(spec)
    assert (slats[0]["x"] - 15, slats[-1]["x"] + 15) == (421.5, 778.5)


def test_a_single_slat_is_centred(desk: dict) -> None:
    spec, parts = _slat_rows(_kommode(desk, _slat_door(count=1, width=60, leaves=[1])))

    (slat,) = _slats_of(spec)
    assert slat["x"] == 1.5 + 397 / 2
    assert "1 vertical slat per door, centred" in next(row for row in parts if row["id"] == "kommode-door-1-slat")["notes"]


def test_too_many_slats_are_refused_with_the_count_that_fits(desk: dict) -> None:
    message = _refusal(_kommode(desk, _slat_door(count=13)))

    assert "fronts[0].slats" in message
    assert "397 mm wide" in message
    assert "at most 12 such slats fit" in message


def test_a_margin_without_room_is_refused(desk: dict) -> None:
    message = _refusal(_kommode(desk, _slat_door(count=2, margin_mm=200)))

    assert "slats.margin_mm" in message
    assert "397 × 747 mm" in message


@pytest.mark.parametrize(
    ("slats", "named", "says"),
    [
        ({"leaves": [3]}, "slats.leaves", "the entry has 2 doors"),
        ({"leaves": [2, 2]}, "slats.leaves", "each door may be named once"),
        ({"material": "veneer"}, "slats.material", "undefined material slot 'veneer'"),
        ({"pattern": "fluted"}, "pattern", "Extra inputs are not permitted"),
    ],
)
def test_bad_slats_are_refused_naming_the_field(desk: dict, slats: dict, named: str, says: str) -> None:
    message = _refusal(_kommode(desk, _slat_door(**slats)))

    assert named in message
    assert says in message


def test_slats_on_a_drawer_are_an_unknown_field(desk: dict) -> None:
    drawer = {"type": "drawer", "count": 1, "slats": {"count": 4, "width": 30, "material": "slats"}}

    message = _refusal(_kommode(desk, drawer))

    assert "slats" in message
    assert "Extra inputs are not permitted" in message


def test_slats_on_a_folded_module_are_refused(desk: dict) -> None:
    fold = {"side": "left", "from_mm": 500, "along": "height", "angle_deg": 10, "towards": "inside"}

    message = _refusal(_kommode(desk, _slat_door(count=4), side_folds=[fold]))

    assert "fronts[0].slats" in message
    assert "slats on a folded module are not supported" in message


def test_slats_keep_only_their_stated_fields(desk: dict) -> None:
    spec, _parts = _slat_rows(_kommode(desk, _slat_door(), {"type": "door", "count": 1, "opening": "hinge"}))

    fronts = spec["modules"][0]["fronts"]
    assert fronts[0]["slats"] == {"count": 8, "width": 30, "material": "slats"}
    assert "slats" not in fronts[1]


def test_slats_change_nothing_else(desk: dict) -> None:
    plain = copy.deepcopy(_kommode(desk, {"type": "door", "count": 2, "opening": "hinge", "handle": {"kind": "knob"}}))
    slatted = copy.deepcopy(plain)
    slatted["modules"][0]["fronts"][0]["slats"] = {"count": 8, "width": 30, "material": "slats", "leaves": [2]}

    plain_spec, plain_parts = _slat_rows(plain)
    slatted_spec, slatted_parts = _slat_rows(slatted)

    assert [row for row in slatted_parts if not row["id"].endswith("-slat")] == plain_parts
    assert derive(slatted_spec)[1] == derive(plain_spec)[1]
    assert overall(slatted_spec) == overall(plain_spec)
    assert drilling(slatted_spec, {}) == drilling(plain_spec, {})


def test_a_handle_on_slats_is_warned_about_in_the_cut_list(desk: dict) -> None:
    door = _slat_door(leaves=[2])
    door["handle"] = {"kind": "knob"}

    spec, parts = _slat_rows(_kommode(desk, door))

    warning = (
        "the handle on door 2 of kommode-door-1 is mounted over the slats, so its screws pass through a slat "
        "into the door and its posts may land on a slat or in a gap; check the screw length and the handle's "
        "position before drilling"
    )
    assert slat_handle_warnings(spec) == [warning]
    notes = next(row for row in parts if row["id"] == "kommode-door-1-slat")["notes"]
    assert notes.endswith(f"glued to the door face. Warning: {warning}.")
    assert "Warning" not in next(row for row in parts if row["id"] == "kommode-door-1")["notes"]


def test_slats_without_a_handle_carry_no_warning(desk: dict) -> None:
    spec, parts = _slat_rows(_kommode(desk, _slat_door()))

    assert slat_handle_warnings(spec) == []
    assert "Warning" not in next(row for row in parts if row["id"] == "kommode-door-1-slat")["notes"]


def test_the_shipped_templates_derive_no_slats() -> None:
    for name in ("custom-build.json", "fold-down-desk.json", "blank-build.json"):
        document = json.loads((TEMPLATES / name).read_text(encoding="utf-8"))
        parts, _hardware, _assembly = derive(CustomBuildSpec.model_validate(document).model_dump(mode="json"))
        assert not any(row["id"].endswith("-slat") for row in parts)


# --- mounting ------------------------------------------------------------------------


def test_a_wall_mounting_is_accepted_and_kept(desk: dict) -> None:
    desk["modules"][0]["mounting"] = "wall"

    dumped = CustomBuildSpec.model_validate(desk).model_dump(mode="json")

    assert dumped["modules"][0]["mounting"] == "wall"


def test_an_unknown_mounting_is_refused_naming_the_allowed_values(desk: dict) -> None:
    desk["modules"][0]["mounting"] = "ceiling"

    message = _refusal(desk)

    assert "modules.0.mounting" in message
    assert "'floor'" in message and "'wall'" in message


def test_a_document_without_mounting_normalises_as_before(desk: dict) -> None:
    dumped = CustomBuildSpec.model_validate(desk).model_dump(mode="json")

    assert all("mounting" not in module for module in dumped["modules"])


def test_mounting_changes_no_derived_output(desk: dict) -> None:
    from app.blender.custom_build.derive import hardware_layout
    from tests.drill_helpers import inputs

    plain = CustomBuildSpec.model_validate(desk).model_dump(mode="json")
    marked_document = copy.deepcopy(desk)
    for module in marked_document["modules"]:
        module["mounting"] = "wall"
    marked = CustomBuildSpec.model_validate(marked_document).model_dump(mode="json")

    assert derive(marked) == derive(plain)
    assert drilling(marked, inputs()) == drilling(plain, inputs())
    assert hardware_layout(marked, inputs()) == hardware_layout(plain, inputs())


# --- door leaf materials (door-leaf-materials) ----------------------------------------------


BLACK_SLOT = {"material": "18 mm black painted MDF", "thickness_mm": 18}


def _black_right(desk: dict, door: dict | None = None, **module) -> dict:
    door = door or {"type": "door", "count": 2, "opening": "hinge"}
    door["leaf_materials"] = {"2": "black_paint"}
    desk["materials"]["black_paint"] = dict(BLACK_SLOT)
    return _kommode(desk, door, **module)


def _hinges(hardware: list[dict]) -> dict[str, int]:
    return {line["id"]: line["qty"] for line in hardware if "hinge" in line["id"]}


def test_a_black_right_door_beside_an_oak_one_splits_the_row(desk: dict) -> None:
    pair = _kommode(copy.deepcopy(desk), {"type": "door", "count": 2, "opening": "hinge"})
    _parts, pair_hardware, _assembly = derive(CustomBuildSpec.model_validate(pair).model_dump(mode="json"))
    spec, parts = _slat_rows(_black_right(desk))
    doors = {row["id"]: row for row in parts if row["name"] == "Door"}
    assert list(doors) == ["kommode-door-1-1", "kommode-door-1-2"]
    assert doors["kommode-door-1-1"]["material"] == "18 mm oak-veneered birch"
    assert doors["kommode-door-1-2"]["material"] == "18 mm black painted MDF"
    assert {(row["qty"], row["l"], row["w"], row["t"]) for row in doors.values()} == {(1, 747, 397, 18)}
    _parts, hardware, _assembly = derive(spec)
    assert _hinges(hardware) == _hinges(pair_hardware)


def test_slats_on_the_black_door_follow_its_row(desk: dict) -> None:
    spec, parts = _slat_rows(_black_right(desk, _slat_door(leaves=[2])))
    slat = next(row for row in parts if row["id"] == "kommode-door-1-2-slat")
    assert slat["qty"] == 8
    assert not any(row["id"] == "kommode-door-1-slat" for row in parts)
    assert {record["row"] for record in _slats_of(spec)} == {"kommode-door-1-2"}


def test_a_handle_on_a_split_door_sits_on_its_own_row(desk: dict) -> None:
    door = _slat_door(leaves=[2])
    door["handle"] = {"kind": "knob"}
    spec = CustomBuildSpec.model_validate(_black_right(desk, door)).model_dump(mode="json")
    rows = [record["row"] for record in handle_layout(spec["modules"][0], 18, 12)]
    assert rows == ["kommode-door-1-1", "kommode-door-1-2"]
    warning = (
        "the handle on door 2 of kommode-door-1-2 is mounted over the slats, so its screws pass through a slat "
        "into the door and its posts may land on a slat or in a gap; check the screw length and the handle's "
        "position before drilling"
    )
    assert slat_handle_warnings(spec) == [warning]


@pytest.mark.parametrize("named", [None, {"1": "carcass", "2": "carcass"}])
def test_doors_in_one_material_keep_one_row(desk: dict, named) -> None:
    door = {"type": "door", "count": 2, "opening": "hinge"}
    if named:
        door["leaf_materials"] = named
    _spec, parts = _slat_rows(_kommode(desk, door))
    assert [(row["id"], row["qty"]) for row in parts if row["name"] == "Door"] == [("kommode-door-1", 2)]


def test_a_spec_without_leaf_materials_serialises_unchanged(desk: dict) -> None:
    spec = CustomBuildSpec.model_validate(_kommode(desk, {"type": "door", "count": 2, "opening": "hinge"})).model_dump(mode="json")
    assert "leaf_materials" not in spec["modules"][0]["fronts"][0]


def test_a_door_outside_the_count_is_refused(desk: dict) -> None:
    document = _black_right(desk)
    document["modules"][0]["fronts"][0]["leaf_materials"] = {"3": "black_paint"}
    message = _refusal(document)
    assert "leaf_materials" in message and "the entry has 2 doors" in message


def test_an_unknown_leaf_slot_is_refused(desk: dict) -> None:
    document = _black_right(desk)
    document["modules"][0]["fronts"][0]["leaf_materials"] = {"2": "walnut"}
    message = _refusal(document)
    assert "fronts[0].leaf_materials" in message and "undefined material slot 'walnut'" in message


def test_a_leaf_slot_of_another_thickness_is_refused(desk: dict) -> None:
    document = _black_right(desk)
    document["materials"]["black_paint"] = {"material": "12 mm black painted MDF", "thickness_mm": 12}
    message = _refusal(document)
    assert "fronts[0].leaf_materials" in message and "12 mm but the carcass is 18 mm" in message


def test_leaf_materials_on_a_folded_module_are_refused(desk: dict) -> None:
    fold = {"side": "left", "from_mm": 500, "along": "height", "angle_deg": 10, "towards": "inside"}
    message = _refusal(_black_right(desk, side_folds=[fold]))
    assert "per-door materials on a folded module are not supported" in message


def test_leaf_materials_on_a_drawer_are_an_unknown_field(desk: dict) -> None:
    desk["materials"]["black_paint"] = dict(BLACK_SLOT)
    message = _refusal(_kommode(desk, {"type": "drawer", "count": 1, "leaf_materials": {"1": "black_paint"}}))
    assert "leaf_materials" in message


def test_an_override_of_the_former_pair_row_is_refused(desk: dict) -> None:
    document = _black_right(desk)
    document["part_overrides"] = [{"id": "kommode-door-1", "qty": 2}]
    message = _refusal(document)
    assert "no derived cut-list row is named 'kommode-door-1'" in message


def test_the_drilling_list_names_each_split_door(desk: dict) -> None:
    spec = CustomBuildSpec.model_validate(_black_right(desk)).model_dump(mode="json")
    pair = CustomBuildSpec.model_validate(
        _kommode(copy.deepcopy(desk), {"type": "door", "count": 2, "opening": "hinge"})
    ).model_dump(mode="json")
    result = drilling(spec, {})
    hinge_parts = [entry["part"] for entry in result["entries"] if entry["calculation"] == "hinges"]
    assert hinge_parts == ["kommode-door-1-1", "kommode-door-1-2"]
    assert result["counts"]["hinge_cup_borings"] == drilling(pair, {})["counts"]["hinge_cup_borings"]
