"""Drawn hardware, `shown` and hanging rails, derived without Blender (hardware-catalog, furniture-packages)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.blender.custom_build.derive import derive, emitted_spec, hardware_layout
from app.blender.hardware_catalog import default_catalog
from app.blender.schemas import CustomBuildSpec
from app.blender.spec_contract import SpecValidationError

TEMPLATES = Path(__file__).resolve().parents[1] / "fixtures/packages/templates"


def _sheet(kind: str, values: dict) -> dict:
    return {"kind": kind, "maker": "Test", "model": "T1", "values": values, "source": "test sheet",
            "source_kind": "manual", "updated_at": "2026-10-16T00:00:00"}


EXACT_HINGE = _sheet("hinge", {
    "cup_diameter_mm": {"value": 35}, "cup_depth_mm": {"value": 13},
    "cup_edge_distance_mm": {"value": 4}, "end_distance_mm": {"value": 100},
})
EXACT_PIN = _sheet("shelf_pin", {"front_setback_mm": {"value": 37}, "rear_setback_mm": {"value": 37}, "pins_per_shelf": 4})


def _inputs(sheets: dict | None = None, rules: dict | None = None) -> dict:
    return {"data_sheets": sheets or {}, "rules": rules or {}, "hardware_catalog": default_catalog().frozen()}


def _spec(**module: object) -> dict:
    document = {
        "kind": "custom_build", "schema_version": 1, "units": "mm", "name": "Hardware",
        "materials": {"carcass": {"material": "18 mm Spanplatte", "thickness_mm": 18},
                      "back": {"material": "3 mm HDF", "thickness_mm": 3}},
        "modules": [{"id": "cabinet", "name": "Cabinet", "x": 0, "y": 0, "z": 0, "width": 932, "height": 2000,
                     "depth": 600, "carcass": "carcass", "back": "back", **module}],
    }
    return CustomBuildSpec.model_validate(document).model_dump(mode="json")


def _shown(spec: dict, inputs: dict | None) -> dict[str, tuple[object, int]]:
    return {line["id"]: (line["qty"], line["shown"]) for line in emitted_spec(spec, inputs)["hardware"]}


def test_hinges_are_drawn_at_the_exact_cup_positions() -> None:
    """Scenario: Hinges drawn."""
    spec = _spec(height=700, fronts=[{"type": "door", "count": 2, "opening": "hinge"}])
    inputs = _inputs({"hinge-concealed-110": EXACT_HINGE})
    hinges = [p for p in hardware_layout(spec, inputs) if p["shape"] == "hinge_concealed"]
    assert len(hinges) == 4
    # Door bottom 1.5 mm + 100 mm end distance; the outer edge of each door; cup 4 + 17.5 mm in.
    assert sorted(round(p["cup"][2], 1) for p in hinges) == [101.5, 101.5, 598.5, 598.5]
    left = next(p for p in hinges if p["side"] == "left")
    assert left["cup"][0] == pytest.approx(1.5 + 21.5) and left["plate_x"] == 18 and left["cup"][1] == 0
    assert _shown(spec, inputs)["hinge-concealed-110"] == (4, 4)


def test_a_ranged_hinge_end_distance_draws_no_hinge() -> None:
    ranged = _sheet("hinge", {**EXACT_HINGE["values"], "end_distance_mm": {"min": 80, "max": 120}})
    spec = _spec(height=700, fronts=[{"type": "door", "count": 1, "opening": "hinge"}])
    assert _shown(spec, _inputs({"hinge-concealed-110": ranged}))["hinge-concealed-110"] == (2, 0)


def test_pins_are_drawn_under_each_adjustable_shelf_at_the_exact_setbacks() -> None:
    """Scenario: Pins drawn at exact holes."""
    spec = _spec(height=900, depth=500, width=600, adjustable_shelves=2)
    inputs = _inputs({"shelf-pin": EXACT_PIN})
    pins = [p for p in hardware_layout(spec, inputs) if p["shape"] == "shelf_pin"]
    assert len(pins) == 8
    assert {round(p["at"][1], 1) for p in pins} == {37, 497 - 37}
    assert _shown(spec, inputs)["shelf-pin"] == (8, 8)


def test_calculated_brackets_have_ranged_ends_and_are_not_drawn() -> None:
    """Scenario: Ranged position not drawn."""
    document = _spec(height=900)
    document["wall_shelves"] = [{"id": "wall-shelf-1", "name": "Shelf", "x": 0, "y": 0, "z": 1500, "length": 1200,
                                 "depth": 250, "material": "carcass", "bracket": "bracket-white"}]
    spec = CustomBuildSpec.model_validate(document).model_dump(mode="json")
    assert not [p for p in hardware_layout(spec, _inputs()) if p["shape"] == "shelf_bracket"]
    stated = json.loads(json.dumps(document))
    stated["wall_shelves"][0]["bracket_positions_mm"] = [150, 1050]
    spec = CustomBuildSpec.model_validate(stated).model_dump(mode="json")
    assert _shown(spec, _inputs())["bracket-white"] == (2, 2)


def test_a_hand_written_line_is_never_drawn() -> None:
    """Scenario: Free line not drawn."""
    spec = _spec(hardware=[{"id": "wall-anchors", "item": "Wall anchors", "qty": 10, "notes": ""}])
    assert _shown(spec, _inputs())["wall-anchors"] == (10, 0)


def test_confirmat_screws_are_never_drawn() -> None:
    """Scenario: Confirmat never drawn."""
    shown = _shown(_spec(shelves=2), _inputs())
    assert shown["confirmat-7x50"][1] == 0


def test_drawer_runners_are_drawn_as_one_pair_per_drawer() -> None:
    spec = _spec(height=900, depth=500, fronts=[{"type": "drawer", "count": 3}])
    runners = [p for p in hardware_layout(spec, _inputs()) if p["shape"] == "drawer_runner"]
    assert len(runners) == 3 and {p["length"] for p in runners} == {450}
    assert _shown(spec, _inputs())["drawer-runner-450"] == (3, 3)


def test_nothing_is_drawn_without_the_frozen_catalog() -> None:
    spec = _spec(height=900, depth=500, fronts=[{"type": "drawer", "count": 1}])
    assert hardware_layout(spec, None) == []
    assert _shown(spec, None)["drawer-runner-450"] == (1, 0)


@pytest.mark.parametrize("template", sorted(TEMPLATES.glob("*.json")), ids=lambda path: path.stem)
def test_templates_derive_the_same_hardware_apart_from_shown(template: Path) -> None:
    document = json.loads(template.read_text(encoding="utf-8"))
    spec = CustomBuildSpec.model_validate(document.get("build", document)).model_dump(mode="json")
    _parts, hardware, _assembly = derive(spec)
    emitted = emitted_spec(spec, _inputs())["hardware"]
    assert [{k: v for k, v in line.items() if k != "shown"} for line in emitted] == hardware


# --- hanging rails -----------------------------------------------------------------------------


def test_a_rail_in_a_wardrobe_bay_is_cut_listed_and_drawn() -> None:
    """Scenario: Rail in a wardrobe bay."""
    spec = _spec(shelves=1, shelf_positions_mm=[1800], hanging_rails=[{"z": 1650}])
    shown = _shown(spec, _inputs())
    assert shown["rail-oval-30x15-894"] == (1, 1)
    assert shown["rail-support-oval"] == (2, 2)
    _parts, hardware, _assembly = derive(spec)
    rail = next(line for line in hardware if line["id"] == "rail-oval-30x15-894")
    assert rail["item"] == "Wardrobe rail oval 30×15 mm, cut to 894 mm"
    support = next(line for line in hardware if line["id"] == "rail-support-oval")
    assert "no centre-support rule" in support["notes"]


def test_the_rail_support_rule_gives_the_support_count() -> None:
    """Scenario: Supports from the rule."""
    rule = {"rule_id": "rail-supports", "params": {"table": [{"max_length_mm": 1000, "supports": 2}], "beyond": 3},
            "source": {"publication": "owner:00000000-0000-0000-0000-000000000000", "section": "s", "quote": "q"}}
    spec = _spec(width=1232, hanging_rails=[{"z": 1650}])
    _parts, hardware, _assembly = derive(spec, {"rules": {"rail_support_count_for_length": rule}})
    support = next(line for line in hardware if line["id"] == "rail-support-oval")
    assert support["qty"] == 3 and "rail-supports" in support["notes"]
    inputs = _inputs(rules={"rail_support_count_for_length": rule})
    assert _shown(spec, inputs)["rail-support-oval"] == (3, 3)


@pytest.mark.parametrize(
    ("rail", "field", "reason"),
    [
        ({"z": 1770}, "z", "below the board above"),
        ({"z": 1805}, "z", "crosses shelf 1"),
        ({"bay": 2, "z": 1000}, "bay", "bay 2 does not exist"),
    ],
)
def test_a_rail_that_cannot_hang_is_refused_by_field(rail: dict, field: str, reason: str) -> None:
    """Scenario: Rail through a shelf refused."""
    with pytest.raises((SpecValidationError, ValueError), match=rf"modules\[0\]\.hanging_rails\[0\]\.{field}: .*{reason}"):
        _spec(shelves=1, shelf_positions_mm=[1800], hanging_rails=[rail])


def test_a_rail_without_a_height_is_refused() -> None:
    """Scenario: Missing height refused."""
    with pytest.raises(ValueError, match="hanging_rails.0.z"):
        _spec(hanging_rails=[{}])


def test_a_module_without_rails_serialises_as_before() -> None:
    assert "hanging_rails" not in _spec()["modules"][0]
