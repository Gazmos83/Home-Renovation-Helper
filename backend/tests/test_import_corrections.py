"""Correcting an imported design's hand-written hardware against the rules (hardware-catalog, design-import)."""

from __future__ import annotations

from app.blender.custom_build.derive import derive
from app.blender.hardware_catalog import default_catalog
from app.blender.import_corrections import correct, rule_lines
from app.blender.schemas import CustomBuildSpec


def _design(*, doors: bool = True, handle: dict | None = None, module_hardware=(), build_hardware=()) -> dict:
    fronts = [{"type": "door", "count": 2, "opening": "hinge", **({"handle": handle} if handle else {})}] if doors else []
    document = {
        "kind": "custom_build", "schema_version": 1, "units": "mm", "name": "Import",
        "materials": {"carcass": {"material": "18 mm Spanplatte", "thickness_mm": 18}},
        "modules": [{
            "id": "cabinet", "name": "Cabinet", "x": 0, "y": 0, "z": 0, "width": 800, "height": 2000,
            "depth": 500, "carcass": "carcass", "fronts": fronts, "hardware": list(module_hardware),
        }],
        "hardware": list(build_hardware),
    }
    return CustomBuildSpec.model_validate(document).model_dump(mode="json")


def _corrected(design: dict):
    return correct(design, rule_lines(design, None), default_catalog())


def test_a_hinge_line_under_another_id_is_removed_in_favour_of_the_rule() -> None:
    """Scenario: Duplicate hinges removed."""
    line = {"id": "cabinet-hinges", "item": "110 degree soft-close concealed cabinet hinges", "qty": 8, "notes": ""}
    found = _corrected(_design(build_hardware=[line]))
    assert found.design["hardware"] == []
    assert len(found.removals) == 1
    assert "`cabinet-hinges`" in found.removals[0] and "`hinge-concealed-110` ×8" in found.removals[0]


def test_a_hand_written_line_with_a_rule_id_is_not_added_twice() -> None:
    """Scenario: Same id not added twice."""
    line = {"id": "hinge-concealed-110", "item": "Concealed hinge", "qty": 8, "notes": ""}
    found = _corrected(_design(module_hardware=[line]))
    assert found.design["modules"][0]["hardware"] == []
    assert "the rules already count `hinge-concealed-110` ×8" in found.removals[0]
    _parts, hardware, _assembly = derive(found.design)
    assert next(h for h in hardware if h["id"] == "hinge-concealed-110")["qty"] == 8


def test_a_knob_line_is_kept_with_a_handle_warning() -> None:
    """Scenario: Knob line warned, not converted."""
    line = {"id": "cabinet-knobs", "item": "Antique brass cabinet knobs", "qty": 2, "notes": ""}
    found = _corrected(_design(module_hardware=[line]))
    assert found.design["modules"][0]["hardware"] == [line]
    assert found.removals == []
    assert found.warnings == [(
        "Kept `cabinet-knobs` 'Antique brass cabinet knobs' ×2: it is not drawn; it can be written as a "
        "front's `handle` with kind `knob` and finish `brass`"
    )]


def test_a_knob_line_is_removed_when_the_fronts_carry_knobs() -> None:
    line = {"id": "cabinet-knobs", "item": "Antique brass cabinet knobs", "qty": 2, "notes": ""}
    found = _corrected(_design(handle={"kind": "knob", "finish": "brass"}, module_hardware=[line]))
    assert found.design["modules"][0]["hardware"] == []
    assert "`handle-knob-brass` ×2" in found.removals[0]


def test_an_unknown_item_is_kept_without_a_note() -> None:
    """Scenario: Unknown item kept."""
    line = {"id": "murphy-mechanism", "item": "Vertical Murphy bed mechanism", "qty": 1, "notes": ""}
    found = _corrected(_design(build_hardware=[line]))
    assert found.design["hardware"] == [line]
    assert found.lines() == []


def test_a_hinge_line_on_a_design_without_doors_is_kept_with_a_warning() -> None:
    line = {"id": "cabinet-hinges", "item": "Concealed cabinet hinges", "qty": 4, "notes": ""}
    found = _corrected(_design(doors=False, build_hardware=[line]))
    assert found.design["hardware"] == [line]
    assert found.warnings == ["Kept `cabinet-hinges` 'Concealed cabinet hinges' ×4: nothing in the design uses it"]


def test_the_same_line_in_several_modules_is_reported_once() -> None:
    line = {"id": "cabinet-knobs", "item": "Brass knobs", "qty": 2, "notes": ""}
    design = _design(module_hardware=[line], build_hardware=[{**line, "qty": 4}])
    found = _corrected(design)
    assert len(found.warnings) == 1 and "×6 in 2 places" in found.warnings[0]


def test_a_section_connector_is_not_taken_for_a_confirmat_screw() -> None:
    line = {"id": "section-connector", "item": "Cabinet connector screw", "qty": 8, "notes": ""}
    found = _corrected(_design(build_hardware=[line]))
    assert found.design["hardware"] == [line]
    assert found.lines() == []


def test_correcting_leaves_the_input_design_unchanged() -> None:
    line = {"id": "cabinet-hinges", "item": "Concealed cabinet hinges", "qty": 8, "notes": ""}
    design = _design(build_hardware=[line])
    _corrected(design)
    assert design["hardware"] == [line]
