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
