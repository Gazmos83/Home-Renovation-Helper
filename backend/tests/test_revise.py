"""design-agents: applying stated changes to a stored document (ported `revise_spec`)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.agent.revise import ReviseError, revise_spec
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
