"""partial-and-folded-dividers: partial dividers, split shelves and shelf kinds in the pinned Blender (--blender)."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.blender.schemas import CustomBuildSpec
from tests.test_custom_build_generator import _build, _inspect
from tests.test_divider_spans import FOLD, TOP_SPAN, cabinet

pytestmark = pytest.mark.blender

FOURTH_SHELF_TOP = 1.5982  # centre 1589.2 mm + 9 mm
TOP_UNDERSIDE = 1.982


def _objects(blender_bin: Path, document: dict, tmp: Path) -> dict[str, dict]:
    spec = CustomBuildSpec.model_validate(document).model_dump(mode="json")
    result, out = _build(blender_bin, spec, tmp)
    assert result.returncode == 0, result.stderr[-800:]
    return {o["name"]: o for o in _inspect(blender_bin, out / "model.blend")["objects"]}


def _z(found: dict) -> tuple[float, float]:
    zs = [corner[2] for corner in found["bound_box"]]
    return min(zs), max(zs)


def _x(found: dict) -> tuple[float, float]:
    xs = [corner[0] for corner in found["bound_box"]]
    return min(xs), max(xs)


def test_a_divider_from_the_fourth_shelf_reaches_the_top_panel(blender_bin: Path, tmp_path: Path) -> None:
    objects = _objects(blender_bin, cabinet(dividers=1, divider_spans=TOP_SPAN), tmp_path)
    bottom, top = _z(objects["cabinet-divider"])
    assert bottom == pytest.approx(FOURTH_SHELF_TOP, abs=0.0001)
    # 383.8 mm clear gap, cut to 383 mm: within 1 mm of the top panel's underside
    assert top == pytest.approx(TOP_UNDERSIDE, abs=0.001)
    shelves = [name for name in objects if name.split("#")[0] == "cabinet-shelf"]
    assert len(shelves) == 4


def test_a_divider_on_the_folded_cabinet_stays_clear_of_the_upper_side(blender_bin: Path, tmp_path: Path) -> None:
    objects = _objects(blender_bin, cabinet(dividers=1, divider_spans=TOP_SPAN, side_folds=[dict(FOLD)]), tmp_path)
    divider = objects["cabinet-divider"]
    assert _z(divider)[0] == pytest.approx(FOURTH_SHELF_TOP, abs=0.0001)
    # the build is centred on the origin; measure from the module's left face
    left_face = _x(objects["cabinet-side-left-lower"])[0]
    assert _x(divider)[0] - left_face == pytest.approx(0.606, abs=0.0001)
    assert _x(divider)[0] > _x(objects["cabinet-side-left-upper"])[1]


def test_the_top_shelf_is_drawn_as_the_fixed_board(blender_bin: Path, tmp_path: Path) -> None:
    objects = _objects(
        blender_bin,
        cabinet(shelves=1, adjustable_shelves=3, shelf_kinds=["adjustable", "adjustable", "adjustable", "fixed"]),
        tmp_path,
    )
    low, high = _z(objects["cabinet-shelf"])
    assert (low + high) / 2 == pytest.approx(1.5892, abs=0.0001)
    adjustable = [o for name, o in objects.items() if name.split("#")[0] == "cabinet-adjustable-shelf"]
    assert len(adjustable) == 3 and all(_z(o)[1] < low for o in adjustable)
