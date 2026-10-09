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
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.blender.custom_build.derive import (
    FLAP_HINGE_ID,
    FLAP_STAY_ID,
    HINGE_ID,
    PUSH_LATCH_ID,
    derive,
    emitted_spec,
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
