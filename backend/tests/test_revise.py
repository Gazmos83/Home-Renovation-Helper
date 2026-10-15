"""design-agents: applying stated changes to a stored document (ported `revise_spec`)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.agent.revise import ReviseError, revise_spec
from app.blender.custom_build.derive import overall
from app.blender.schemas import CustomBuildSpec, PackageChanges

TEMPLATES = Path(__file__).resolve().parents[1] / "fixtures" / "packages" / "templates"


@pytest.fixture
def desk() -> dict:
    return CustomBuildSpec.model_validate(
        json.loads((TEMPLATES / "fold-down-desk.json").read_text(encoding="utf-8"))
    ).model_dump(mode="json")


def test_a_module_field_change_reads_before_and_after(desk: dict) -> None:
    before = desk["modules"][0]["shelves"]
    revised, lines = revise_spec(desk, PackageChanges(modules={"cabinet": {"shelves": before + 1}}))
    assert lines == [f"cabinet: shelves {before} → {before + 1}"]
    assert revised["modules"][0]["shelves"] == before + 1
    # The stored document is untouched.
    assert desk["modules"][0]["shelves"] == before


def test_the_name_and_a_material_change_have_lines(desk: dict) -> None:
    revised, lines = revise_spec(
        desk,
        PackageChanges(
            name="Desk v2",
            materials={"carcass": {"material": "18 mm white melamine", "thickness_mm": 18}},
        ),
    )
    assert lines[0].endswith("→ Desk v2")
    assert lines[1].startswith("materials.carcass:")
    assert revised["materials"]["carcass"]["material"] == "18 mm white melamine"


def test_an_unknown_module_is_refused_naming_it_and_listing_the_known_ones(desk: dict) -> None:
    with pytest.raises(ReviseError) as error:
        revise_spec(desk, PackageChanges(modules={"drawers": {"shelves": 1}}))
    assert "'drawers'" in str(error.value)
    assert "cabinet" in str(error.value)


def test_an_unknown_extra_part_is_refused(desk: dict) -> None:
    with pytest.raises(ReviseError, match="extra part 'ghost'"):
        revise_spec(desk, PackageChanges(remove_extra_parts=["ghost"]))


def test_removing_a_module_and_adding_one(desk: dict) -> None:
    module = {
        "id": "shelf-unit", "name": "Shelf unit", "x": 0, "y": 0, "z": 1500, "width": 600,
        "height": 300, "depth": 300, "carcass": "carcass", "shelves": 1,
    }
    revised, lines = revise_spec(
        desk, PackageChanges(add_modules=[module], remove_modules=["cabinet"])
    )
    assert lines[0] == "cabinet: module removed"
    assert lines[1].startswith("shelf-unit: module added (600×300×300 mm)")
    assert [m["id"] for m in revised["modules"]] == ["shelf-unit"]


def test_a_part_override_is_added_or_replaced(desk: dict) -> None:
    changes = PackageChanges(part_overrides=[{"id": "cabinet-left", "qty": 2}])
    revised, lines = revise_spec(desk, changes)
    assert lines == ["part_overrides.cabinet-left: added"]
    _, again = revise_spec(revised, changes)
    assert again == ["part_overrides.cabinet-left: replaced"]


def test_changes_must_state_something_and_unknown_fields_are_refused() -> None:
    with pytest.raises(ValidationError, match="at least one change"):
        PackageChanges()
    with pytest.raises(ValidationError, match="bevel_mm"):
        PackageChanges.model_validate({"modules": {"cabinet": {"bevel_mm": 3}}})


# --- wall shelves, adjustable shelves and hinge keys (cabinet-hardware-calculator) ------------

WALL_SHELF = {
    "id": "wall-shelf-1", "name": "Wall shelf", "x": 100, "y": 0, "z": 1400, "length": 1200, "depth": 250,
    "material": "carcass", "bracket": "bracket-white",
}


@pytest.fixture
def shelved(desk: dict) -> dict:
    desk["materials"].setdefault("carcass", {"material": "Eiche 18 mm", "thickness_mm": 18})
    desk["envelope"] = {"width": 2000, "height": 2000, "depth": 400}
    desk["wall_shelves"] = [dict(WALL_SHELF)]
    return desk


def _revise(document: dict, **changes) -> tuple[dict, list[str]]:
    return revise_spec(document, PackageChanges.model_validate(changes))


def test_a_wall_shelf_is_added_and_removed(desk: dict, shelved: dict) -> None:
    second = WALL_SHELF | {"id": "wall-shelf-2", "z": 1700}
    revised, lines = _revise(shelved, add_wall_shelves=[second], remove_wall_shelves=["wall-shelf-1"])
    assert [shelf["id"] for shelf in revised["wall_shelves"]] == ["wall-shelf-2"]
    assert "wall-shelf-1: wall shelf removed" in lines
    assert any(line.startswith("wall-shelf-2: wall shelf added") for line in lines)


def test_bracket_positions_are_set_and_cleared_with_old_and_new_in_the_line(shelved: dict) -> None:
    revised, lines = _revise(shelved, wall_shelves={"wall-shelf-1": {"bracket_positions_mm": [150, 600, 1050]}})
    assert revised["wall_shelves"][0]["bracket_positions_mm"] == [150, 600, 1050]
    assert lines == ["wall-shelf-1: bracket positions calculated → [150, 600, 1050]"]
    CustomBuildSpec.model_validate(revised)

    cleared, lines = _revise(revised, wall_shelves={"wall-shelf-1": {"bracket_positions_mm": []}})
    assert "bracket_positions_mm" not in cleared["wall_shelves"][0]
    assert lines == ["wall-shelf-1: bracket positions [150, 600, 1050] → calculated"]
    CustomBuildSpec.model_validate(cleared)


def test_an_unknown_wall_shelf_is_refused_naming_the_shelves_present(shelved: dict) -> None:
    with pytest.raises(ReviseError, match="wall-shelf-1"):
        _revise(shelved, wall_shelves={"nope": {"length": 900}})
    with pytest.raises(ReviseError, match="wall-shelf-1"):
        _revise(shelved, remove_wall_shelves=["nope"])


def test_adjustable_shelves_and_the_pin_key_are_changed_on_a_module(desk: dict) -> None:
    module_id = desk["modules"][0]["id"]
    revised, lines = _revise(desk, modules={module_id: {"adjustable_shelves": 2, "shelf_pin": "shelf-pin-5mm"}})
    assert revised["modules"][0]["adjustable_shelves"] == 2
    assert f"{module_id}: adjustable_shelves 0 → 2" in lines


def test_a_hinge_item_is_set_on_the_hinged_doors() -> None:
    starter = json.loads((TEMPLATES / "custom-build.json").read_text(encoding="utf-8"))
    module_id = starter["modules"][0]["id"]
    revised, lines = _revise(starter, modules={module_id: {"hinge": "hinge-blum-clip-110"}})
    assert revised["modules"][0]["fronts"][0]["hinge"] == "hinge-blum-clip-110"
    assert lines == [f"{module_id}: hinge hinge-concealed-110 → hinge-blum-clip-110"]
    assert "hinge" not in revised["modules"][0]
    with pytest.raises(ReviseError, match="no hinged door"):
        _revise(revised | {"modules": [revised["modules"][0] | {"fronts": []}]}, modules={module_id: {"hinge": "x"}})


DOORS = [{"type": "door", "count": 2, "opening": "hinge"}]


def _with_fronts(desk: dict, fronts: list[dict], hardware: list[dict] | None = None) -> dict:
    module = desk["modules"][0] | {"fronts": fronts}
    if hardware is not None:
        module["hardware"] = hardware
    return desk | {"modules": [module]}


def test_a_fronts_change_is_described_before_and_after(desk: dict) -> None:
    doors = _with_fronts(desk, DOORS)
    _revised, lines = _revise(
        doors,
        modules={"cabinet": {"fronts": [
            {"type": "door", "count": 1, "opening": "hinge"},
            {"type": "drawer", "count": 1, "height": 200},
        ]}},
    )
    assert lines == ["cabinet: fronts 2 doors (hinge) → 1 door (hinge), 1 drawer 200 mm"]


def test_a_non_default_hinge_is_named_and_an_empty_list_reads_none(desk: dict) -> None:
    doors = _with_fronts(desk, DOORS)
    _revised, lines = _revise(
        doors, modules={"cabinet": {"fronts": [{"type": "door", "count": 2, "opening": "hinge", "hinge": "hinge-blum-155"}]}}
    )
    assert lines == ["cabinet: fronts 2 doors (hinge) → 2 doors (hinge, hinge-blum-155)"]
    _revised, lines = _revise(doors, modules={"cabinet": {"fronts": []}})
    assert lines == ["cabinet: fronts 2 doors (hinge) → none"]


def test_a_hardware_change_names_id_item_and_quantity(desk: dict) -> None:
    handled = _with_fronts(desk, DOORS, [{"id": "handle", "item": "Bar handle", "qty": 2, "notes": ""}])
    _revised, lines = _revise(
        handled, modules={"cabinet": {"hardware": [{"id": "handle", "item": "Bar handle", "qty": 4}]}}
    )
    assert lines == ['cabinet: hardware handle "Bar handle" ×2 → handle "Bar handle" ×4']
    assert not any("entries" in line for line in lines)


def test_a_value_the_module_already_has_gives_no_line(desk: dict) -> None:
    height = desk["modules"][0]["height"]
    shelves = desk["modules"][0]["shelves"]
    _revised, lines = _revise(desk, modules={"cabinet": {"height": height, "shelves": shelves + 1}})
    assert lines == [f"cabinet: shelves {shelves} → {shelves + 1}"]


def test_unchanged_name_envelope_material_fronts_and_shelf_values_give_no_line(desk: dict, shelved: dict) -> None:
    module = shelved["modules"][0]
    _revised, lines = _revise(
        shelved,
        name=shelved["name"],
        envelope=shelved["envelope"],
        materials={"carcass": shelved["materials"]["carcass"]},
        modules={"cabinet": {"fronts": module["fronts"], "hardware": module["hardware"]}},
        wall_shelves={"wall-shelf-1": {"length": WALL_SHELF["length"], "bracket_positions_mm": []}},
    )
    assert lines == []


def test_a_hinge_every_hinged_door_already_has_gives_no_line() -> None:
    starter = json.loads((TEMPLATES / "custom-build.json").read_text(encoding="utf-8"))
    module_id = starter["modules"][0]["id"]
    _revised, lines = _revise(starter, modules={module_id: {"hinge": "hinge-concealed-110"}})
    assert lines == []


def test_adds_removes_and_overrides_always_give_lines(desk: dict, shelved: dict) -> None:
    _revised, lines = _revise(shelved, add_wall_shelves=[WALL_SHELF | {"id": "wall-shelf-2", "z": 1700}])
    assert lines and lines[0].startswith("wall-shelf-2: wall shelf added")
    _revised, lines = _revise(shelved, remove_wall_shelves=["wall-shelf-1"])
    assert lines == ["wall-shelf-1: wall shelf removed"]


# --- shelf spacing and dividers (shelf-spacing-and-dividers) ---------------------------------


def test_setting_a_spacing_replaces_stated_positions_and_names_both(desk: dict) -> None:
    placed, lines = _revise(desk, modules={"cabinet": {"shelf_positions_mm": [200, 400]}})
    assert lines == ["cabinet: shelf_positions_mm not set → [200, 400]"]
    spaced, lines = _revise(placed, modules={"cabinet": {"shelf_spacing_mm": 150}})
    assert lines == [
        "cabinet: shelf_spacing_mm not set → 150",
        "cabinet: shelf_positions_mm [200, 400] → not set (replaced by shelf_spacing_mm)",
    ]
    module = spaced["modules"][0]
    assert module["shelf_spacing_mm"] == 150 and "shelf_positions_mm" not in module
    CustomBuildSpec.model_validate(spaced)


def test_zero_or_an_empty_list_clears_back_to_even_spacing_and_equal_bays(desk: dict) -> None:
    spaced, _ = _revise(desk, modules={"cabinet": {"shelf_spacing_mm": 150, "dividers": 1, "divider_positions_mm": [400]}})
    cleared, lines = _revise(spaced, modules={"cabinet": {"shelf_spacing_mm": 0, "divider_positions_mm": []}})
    assert lines == ["cabinet: shelf_spacing_mm 150 → not set", "cabinet: divider_positions_mm [400] → not set"]
    assert not {"shelf_spacing_mm", "divider_positions_mm"} & cleared["modules"][0].keys()
    assert _revise(cleared, modules={"cabinet": {"shelf_spacing_mm": 0, "dividers": 1}})[1] == []


def test_side_folds_are_set_and_cleared_with_each_fold_named(desk: dict) -> None:
    desk["modules"][0]["fronts"] = []
    desk["modules"][0]["z"] = 0
    desk["modules"][0]["height"] = 2000
    desk["envelope"] = {"width": 2000, "height": 2200, "depth": 400}
    fold = {"side": "left", "from_mm": 1100, "along": "height", "angle_deg": 26, "towards": "inside"}
    folded, lines = _revise(desk, modules={"cabinet": {"side_folds": [fold]}})
    assert folded["modules"][0]["side_folds"] == [fold]
    assert "left from 1100 mm along height, 26°, inside" in lines[0]
    cleared, lines = _revise(folded, modules={"cabinet": {"side_folds": []}})
    assert "side_folds" not in cleared["modules"][0]
    assert "left from 1100 mm along height, 26°, inside" in lines[0] and "not set" in lines[0]
    CustomBuildSpec.model_validate(cleared)


def test_removing_the_dividers_drops_their_positions(desk: dict) -> None:
    divided, _ = _revise(desk, modules={"cabinet": {"dividers": 1, "divider_positions_mm": [400]}})
    plain, lines = _revise(divided, modules={"cabinet": {"dividers": 0}})
    assert lines == ["cabinet: divider_positions_mm [400] → not set", "cabinet: dividers 1 → 0"]
    CustomBuildSpec.model_validate(plain)


# --- auto-fit-protruding-shelves ---------------------------------------------------------------

DEEPER = {"cabinet": {"shelf_depths_mm": [None, 400], "shelf_depth_align": "back"}}


@pytest.fixture
def boxed(desk: dict) -> dict:
    desk["envelope"] = {"width": 1000, "height": 1450, "depth": 300}
    return CustomBuildSpec.model_validate(desk).model_dump(mode="json")


def test_a_shelf_past_the_front_moves_the_build_back_and_grows_the_envelope(boxed: dict) -> None:
    revised, lines = revise_spec(boxed, PackageChanges(modules=DEEPER))
    # 400 mm shelf, back-flush on a 300 mm module with a 12 mm back: 288 − 400 = −112 mm
    assert revised["modules"][0]["y"] == 112
    assert revised["envelope"]["depth"] == 412
    assert "fit: cabinet: y 0 → 112 mm" in lines and "fit: envelope depth 300 → 412 mm" in lines
    CustomBuildSpec.model_validate(revised)
    # room_fit places the piece by its overall size, which follows the grown envelope
    assert overall(revised) == {"w": 1000, "h": 1450, "d": 412}


def test_without_the_fit_the_same_change_is_refused(boxed: dict) -> None:
    unfitted = json.loads(json.dumps(boxed))
    unfitted["modules"][0].update(shelf_depths_mm=[None, 400], shelf_depth_align="back")
    with pytest.raises(Exception, match="lies outside the envelope"):
        CustomBuildSpec.model_validate(unfitted)


def test_the_whole_build_moves_together(boxed: dict) -> None:
    second = {**boxed["modules"][0], "id": "second", "x": 1000}
    boxed["modules"].append(second)
    boxed["envelope"]["width"] = 2000
    boxed["wall_shelves"] = [
        {"id": "ledge", "name": "Ledge", "x": 0, "y": 0, "z": 1500, "length": 500, "depth": 150, "material": "carcass"}
    ]
    boxed["envelope"]["height"] = 1700
    revised, _ = revise_spec(boxed, PackageChanges(modules=DEEPER))
    assert [module["y"] for module in revised["modules"]] == [112, 112]
    assert revised["wall_shelves"][0]["y"] == 112
    assert revised["envelope"]["depth"] == 412


def test_a_build_already_clear_of_the_front_is_fitted_only_for_the_shortfall(boxed: dict) -> None:
    boxed["modules"][0]["y"] = 100
    boxed["envelope"]["depth"] = 400
    revised, _ = revise_spec(boxed, PackageChanges(modules=DEEPER))
    assert revised["modules"][0]["y"] == 112 and revised["envelope"]["depth"] == 412


def test_no_protrusion_changes_no_position(boxed: dict) -> None:
    revised, lines = revise_spec(boxed, PackageChanges(modules={"cabinet": {"shelves": 3}}))
    assert revised["modules"][0]["y"] == 0 and revised["envelope"]["depth"] == 300
    assert not any(line.startswith("fit: ") for line in lines)


def test_a_build_without_an_envelope_moves_but_gains_none(desk: dict) -> None:
    revised, _ = revise_spec(desk, PackageChanges(modules=DEEPER))
    assert revised["modules"][0]["y"] == 112 and revised.get("envelope") is None


def test_other_overflow_is_still_refused(boxed: dict) -> None:
    revised, _ = revise_spec(boxed, PackageChanges(modules={"cabinet": {"width": 1200}}))
    with pytest.raises(Exception, match="lies outside the envelope"):
        CustomBuildSpec.model_validate(revised)


# --- extra-part placement (extra-part-placement) --------------------------------------


def _with_extra(desk: dict, **part) -> dict:
    desk["extra_parts"] = [{"id": "top-frame", "name": "Top frame", "qty": 1, "length": 1000, "width": 60,
                            "material": "carcass", **part}]
    return desk


_AT = {"x": 0, "y": 0, "z": 1450, "length_along": "x", "width_along": "y"}


def test_an_extra_part_is_placed_with_a_before_and_after_line(desk: dict) -> None:
    revised, lines = revise_spec(_with_extra(desk), PackageChanges(extra_parts={"top-frame": {"placements": [_AT]}}))

    assert lines == ["top-frame: placements beside the build → x0 y0 z1450, length along x, width along y"]
    assert revised["extra_parts"][0]["placements"] == [_AT]


def test_an_empty_placement_list_lays_the_part_beside_the_build_again(desk: dict) -> None:
    revised, lines = revise_spec(
        _with_extra(desk, placements=[_AT]), PackageChanges(extra_parts={"top-frame": {"placements": []}})
    )

    assert lines == ["top-frame: placements x0 y0 z1450, length along x, width along y → beside the build"]
    assert "placements" not in revised["extra_parts"][0]


def test_a_placement_count_that_disagrees_with_the_quantity_is_refused(desk: dict) -> None:
    with pytest.raises(ReviseError, match=r"'top-frame' needs 2 placements, one per piece; 1 were given"):
        revise_spec(_with_extra(desk, qty=2), PackageChanges(extra_parts={"top-frame": {"placements": [_AT]}}))


def test_placing_an_unknown_extra_part_is_refused_listing_the_known_ones(desk: dict) -> None:
    with pytest.raises(ReviseError) as error:
        revise_spec(_with_extra(desk), PackageChanges(extra_parts={"rail": {"placements": [_AT]}}))
    assert "extra part 'rail'" in str(error.value) and "top-frame" in str(error.value)


def test_a_tilted_and_cut_brace_reads_its_turn_and_its_cuts(desk: dict) -> None:
    tilted = _AT | {"z": 0, "width_along": "z", "tilt": {"towards": "z", "angle_deg": 30}}
    _revised, lines = revise_spec(
        _with_extra(desk),
        PackageChanges(extra_parts={"top-frame": {
            "placements": [tilted], "end_cuts": {"across": "width", "start_deg": 30, "end_deg": -30},
        }}),
    )

    assert "tilt 30° towards z" in lines[0]
    assert lines[1] == "top-frame: end cuts square → 30° / −30° across width"


def test_an_unchanged_placement_gives_no_change_line(desk: dict) -> None:
    _revised, lines = revise_spec(
        _with_extra(desk, placements=[_AT]), PackageChanges(extra_parts={"top-frame": {"placements": [_AT]}})
    )

    assert lines == []


def test_an_extra_part_change_must_state_a_field() -> None:
    with pytest.raises(ValidationError, match="state placements or end_cuts"):
        PackageChanges.model_validate({"extra_parts": {"top-frame": {}}})


def test_a_protruding_shelf_fit_moves_placed_pieces_with_the_build(desk: dict) -> None:
    desk = _with_extra(desk, placements=[_AT])
    depth = desk["modules"][0]["depth"]
    revised, lines = revise_spec(
        desk,
        PackageChanges(modules={"cabinet": {"shelves": 1, "shelf_depths_mm": [depth + 100]}}),
    )

    shift = revised["modules"][0]["y"]
    assert shift > 0
    assert revised["extra_parts"][0]["placements"][0]["y"] == shift
    assert f"fit: top-frame: extra part pieces move back {shift} mm" in lines
