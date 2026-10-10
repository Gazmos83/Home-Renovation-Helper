"""carcass-side-folds: SideFoldIn, fold_profile, cut-list rows and overall bounds."""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.agent.revise import revise_spec
from app.blender.custom_build.derive import (
    derive,
    fold_profile,
    inset_mm,
    module_bounds,
    overall,
    slope_mm,
)
from app.blender.schemas import CustomBuildSpec, PackageChanges
from app.blender.schemas import describe_validation_error as _describe_validation_error

TEMPLATES = Path(__file__).resolve().parents[1] / "fixtures/packages/templates"

FOLD = {"side": "left", "from_mm": 1100, "along": "height", "angle_deg": 26, "towards": "inside"}


def folded_cabinet(**module_overrides) -> dict:
    module = {
        "id": "cabinet",
        "name": "Cabinet",
        "x": 0,
        "y": 0,
        "z": 0,
        "width": 800,
        "height": 2000,
        "depth": 400,
        "carcass": "carcass",
        "back": "back",
        "side_folds": [dict(FOLD)],
    }
    module.update(module_overrides)
    return {
        "kind": "custom_build",
        "schema_version": 1,
        "units": "mm",
        "name": "Folded cabinet",
        "materials": {
            "carcass": {"material": "18 mm oak-veneered birch", "thickness_mm": 18},
            "back": {"material": "12 mm birch plywood", "thickness_mm": 12},
        },
        "modules": [module],
    }


def _refusal(document: dict) -> str:
    with pytest.raises(ValidationError) as caught:
        CustomBuildSpec.model_validate(document)
    return _describe_validation_error(caught.value)


def _by_id(rows: list[dict]) -> dict[str, dict]:
    return {row["id"]: row for row in rows}


def test_900_mm_at_26_degrees_insets_439_and_slopes_1001() -> None:
    assert inset_mm(900, 26) == 439
    assert slope_mm(900, 26) == 1001


def test_an_inside_left_height_fold_keeps_overall_width() -> None:
    spec = CustomBuildSpec.model_validate(folded_cabinet()).model_dump(mode="json")
    assert overall(spec) == {"w": 800, "h": 2000, "d": 400}
    assert module_bounds(spec["modules"][0], 18, 12) == (0, 0, 0, 800, 400, 2000)
    profile = fold_profile(spec["modules"][0], 18, 12)
    assert profile.fold_on("left").inset_mm == 439
    assert profile.fold_on("left").slope_mm == 1001


def test_an_outside_left_height_fold_grows_overall_width() -> None:
    document = folded_cabinet(side_folds=[{**FOLD, "towards": "outside"}])
    spec = CustomBuildSpec.model_validate(document).model_dump(mode="json")
    assert overall(spec)["w"] == 1239
    assert module_bounds(spec["modules"][0], 18, 12)[0] == -439


def test_the_26_degree_cabinet_is_accepted_and_omits_empty_folds_on_other_modules() -> None:
    spec = CustomBuildSpec.model_validate(folded_cabinet())
    dumped = spec.model_dump(mode="json")
    assert dumped["modules"][0]["side_folds"] == [FOLD]
    desk = json.loads((TEMPLATES / "fold-down-desk.json").read_text(encoding="utf-8"))
    plain = CustomBuildSpec.model_validate(desk).model_dump(mode="json")
    assert "side_folds" not in plain["modules"][0]


def test_two_folds_on_the_same_side_are_refused() -> None:
    document = folded_cabinet(side_folds=[FOLD, {**FOLD, "from_mm": 1200}])
    assert "modules[0].side_folds" in _refusal(document)


def test_from_mm_inside_the_carcass_thickness_is_refused() -> None:
    document = folded_cabinet(side_folds=[{**FOLD, "from_mm": 10}])
    message = _refusal(document)
    assert "modules[0].side_folds" in message
    assert "10" in message


def test_a_zero_mm_inset_is_refused() -> None:
    document = folded_cabinet(height=800, side_folds=[{**FOLD, "from_mm": 780, "angle_deg": 1}])
    message = _refusal(document)
    assert "modules[0].side_folds" in message
    assert "0 mm" in message


def test_a_fold_that_pinches_the_opening_is_refused_naming_the_inner_width() -> None:
    document = folded_cabinet(
        width=400, height=800, side_folds=[{**FOLD, "from_mm": 100, "angle_deg": 45}]
    )
    message = _refusal(document)
    assert "modules[0].side_folds" in message
    assert "remaining inner width" in message
    assert "-336" in message


def test_two_doors_on_the_26_degree_cabinet_are_accepted() -> None:
    document = folded_cabinet(fronts=[{"type": "door", "count": 2, "opening": "hinge"}])
    spec = CustomBuildSpec.model_validate(document).model_dump(mode="json")
    parts, _hardware, _assembly = derive(spec)
    rows = _by_id(parts)
    assert "cabinet-door-1-1" in rows and "cabinet-door-1-2" in rows
    assert "cabinet-door-1" not in rows
    left, right = rows["cabinet-door-1-1"], rows["cabinet-door-1-2"]
    assert left["qty"] == right["qty"] == 1
    assert right["l"] == 1997 and right["w"] == 397
    assert "net" in left["notes"] and "26" in left["notes"]
    assert left["w"] == 397
    assert left["l"] < right["l"]


def test_dividers_on_a_folded_module_are_accepted_when_they_fit() -> None:
    # partial-and-folded-dividers lifted the v1 refusal; the divider must fit the folded opening.
    document = folded_cabinet(dividers=1)
    CustomBuildSpec.model_validate(document)
    assert "cabinet-divider" in _by_id(derive(CustomBuildSpec.model_validate(document).model_dump(mode="json"))[0])


def test_a_front_pinched_below_100_mm_is_refused_naming_fronts() -> None:
    document = folded_cabinet(
        width=400,
        height=800,
        side_folds=[{**FOLD, "from_mm": 100, "angle_deg": 24}],
        fronts=[{"type": "door", "count": 1, "opening": "hinge"}],
    )
    message = _refusal(document)
    assert "modules[0].fronts" in message
    assert "100" in message


def test_an_adjustable_shelf_above_the_kink_uses_the_pinched_width() -> None:
    import math

    from app.blender.custom_build.derive import (
        ADJUSTABLE_SHELF_CLEARANCE_MM,
        fold_profile,
        min_inner_width,
        shelf_centres,
    )

    document = folded_cabinet(
        adjustable_shelves=1,
        shelf_positions_mm=[1100],
        fronts=[{"type": "door", "count": 2, "opening": "hinge"}],
    )
    spec = CustomBuildSpec.model_validate(document).model_dump(mode="json")
    module = spec["modules"][0]
    profile = fold_profile(module, 18, 12)
    centre = shelf_centres(module, 18)[0]
    inner = min_inner_width(profile, 0, profile.inner_d, centre - 9, centre + 9)
    parts, _hardware, _assembly = derive(spec)
    row = _by_id(parts)["cabinet-adjustable-shelf"]
    assert row["qty"] == 1
    assert row["l"] == math.floor(inner - ADJUSTABLE_SHELF_CLEARANCE_MM)
    assert row["w"] == 388
    assert row["l"] < 800 - 36


def test_a_drawer_box_on_a_fold_uses_the_pinched_inner_width() -> None:
    import math

    from app.blender.custom_build.derive import (
        DRAWER_SIDE_CLEARANCE_MM,
        fold_profile,
        front_layout,
        min_inner_width,
    )

    document = folded_cabinet(fronts=[{"type": "drawer", "count": 1, "height": 200}])
    spec = CustomBuildSpec.model_validate(document).model_dump(mode="json")
    module = spec["modules"][0]
    profile = fold_profile(module, 18, 12)
    rect = front_layout(module, 18, 12)[0]
    inner = min_inner_width(profile, 0, profile.inner_d, rect["z"], rect["z"] + rect["h"])
    parts, _hardware, _assembly = derive(spec)
    back = _by_id(parts)["cabinet-drawer-1-back"]
    assert back["l"] == math.floor(inner - 2 * DRAWER_SIDE_CLEARANCE_MM) - 36


def test_an_unfolder_module_still_derives_door_qty_two_and_one_adjustable_row() -> None:
    document = json.loads((TEMPLATES / "custom-build.json").read_text(encoding="utf-8"))
    document["modules"][0]["adjustable_shelves"] = 2
    spec = CustomBuildSpec.model_validate(document).model_dump(mode="json")
    parts, _hardware, _assembly = derive(spec)
    rows = _by_id(parts)
    assert rows["cabinet-door-1"]["qty"] == 2
    assert rows["cabinet-adjustable-shelf"]["qty"] == 2
    assert "cabinet-door-1-1" not in rows


def test_package_changes_accept_side_folds_and_refuse_bevel_mm() -> None:
    change = PackageChanges.model_validate({"modules": {"cabinet": {"side_folds": [FOLD]}}})
    assert change.modules["cabinet"].side_folds[0].angle_deg == 26
    with pytest.raises(ValidationError, match="bevel_mm"):
        PackageChanges.model_validate({"modules": {"cabinet": {"bevel_mm": 3}}})


def test_an_outside_fold_that_leaves_the_envelope_is_refused_naming_the_module() -> None:
    document = folded_cabinet(side_folds=[{**FOLD, "towards": "outside"}])
    document["envelope"] = {"width": 800, "height": 2000, "depth": 400}
    message = _refusal(document)
    assert "outside the envelope" in message
    assert "'cabinet'" in message


def test_left_side_26_degrees_from_1100_mm_cut_list() -> None:
    spec = CustomBuildSpec.model_validate(folded_cabinet()).model_dump(mode="json")
    parts, hardware, assembly = derive(spec)
    rows = _by_id(parts)
    assert (rows["cabinet-side-left-lower"]["l"], rows["cabinet-side-left-lower"]["w"]) == (1100, 388)
    assert (rows["cabinet-side-left-upper"]["l"], rows["cabinet-side-left-upper"]["w"]) == (1001, 388)
    assert "26" in rows["cabinet-side-left-upper"]["notes"] and "mitre" in rows["cabinet-side-left-upper"]["notes"]
    assert (rows["cabinet-side-right"]["l"], rows["cabinet-side-right"]["w"], rows["cabinet-side-right"]["qty"]) == (
        2000, 388, 1,
    )
    assert "cabinet-top" in rows and "cabinet-bottom" in rows
    assert "cabinet-side" not in rows and "cabinet-top-bottom" not in rows
    confirmat = _by_id(hardware)["confirmat-7x50"]
    assert confirmat["qty"] == 12
    body = next(step["body"] for step in assembly if step["title"].startswith("Carcass"))
    assert "left" in body and "26" in body and "1100" in body


def test_clearing_folds_restores_the_quantity_two_side_row() -> None:
    spec = CustomBuildSpec.model_validate(folded_cabinet()).model_dump(mode="json")
    revised, lines = revise_spec(spec, PackageChanges.model_validate({"modules": {"cabinet": {"side_folds": []}}}))
    assert "side_folds" not in revised["modules"][0]
    assert any("1100" in line and "not set" in line for line in lines)
    assert any("left" in line and "26" in line for line in lines)
    parts, _hardware, _assembly = derive(CustomBuildSpec.model_validate(revised).model_dump(mode="json"))
    side = _by_id(parts)["cabinet-side"]
    assert side["qty"] == 2 and side["l"] == 2000 and side["w"] == 388


def test_shipped_templates_still_derive_the_unfolder_side_row() -> None:
    for name in ("fold-down-desk.json", "custom-build.json"):
        document = json.loads((TEMPLATES / name).read_text(encoding="utf-8"))
        spec = CustomBuildSpec.model_validate(document).model_dump(mode="json")
        parts, _hardware, _assembly = derive(spec)
        sides = [row for row in parts if row["id"].endswith("-side")]
        assert sides and all(row["qty"] == 2 for row in sides)


def test_a_document_without_side_folds_matches_its_copy() -> None:
    desk = json.loads((TEMPLATES / "fold-down-desk.json").read_text(encoding="utf-8"))
    spec = CustomBuildSpec.model_validate(desk).model_dump(mode="json")
    again = CustomBuildSpec.model_validate(copy.deepcopy(spec)).model_dump(mode="json")
    assert derive(spec) == derive(again)
    assert "side_folds" not in spec["modules"][0]
