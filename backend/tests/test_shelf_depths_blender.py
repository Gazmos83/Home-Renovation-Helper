"""per-shelf-depth: one deeper back-flush shelf, built in the pinned Blender (--blender)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.blender.custom_build import derive as rules
from app.blender.schemas import CustomBuildSpec
from tests.test_custom_build_generator import _build, _inspect

pytestmark = pytest.mark.blender

SPEC = {
    "kind": "custom_build",
    "schema_version": 1,
    "units": "mm",
    "name": "Mixed shelf depths",
    "materials": {
        "carcass": {"material": "Spanplatte 18 mm", "thickness_mm": 18},
        "back": {"material": "HDF 12 mm", "thickness_mm": 12},
    },
    "modules": [
        {
            "id": "cabinet",
            "name": "Cabinet",
            "x": 0,
            "y": 0,
            "z": 0,
            "width": 800,
            "height": 1600,
            "depth": 400,
            "carcass": "carcass",
            "back": "back",
            "shelves": 4,
            "shelf_depths_mm": [None, 500, None, None],
            "shelf_depth_align": "back",
        }
    ],
}


@pytest.fixture(scope="module")
def built(blender_bin: Path, tmp_path_factory: pytest.TempPathFactory):
    tmp = tmp_path_factory.mktemp("shelf-depths")
    spec = CustomBuildSpec.model_validate(SPEC).model_dump(mode="json")
    result, out = _build(blender_bin, spec, tmp)
    assert result.returncode == 0, result.stderr
    return spec, out


def test_deeper_shelf_is_placed_back_flush(built, blender_bin: Path) -> None:
    spec, out = built
    module = spec["modules"][0]
    boards = rules.shelf_boards(module, 18, 12)
    deeper = next(board for board in boards if board.depth == 500)
    default = next(board for board in boards if board.depth == 388)
    # Scene is centred on overall AABB (including the protruding shelf).
    _x0, y0, _z0, _w, d, _h = rules.module_bounds(module, 18, 12)
    shift_y = y0 + d / 2
    objects = {o["name"]: o for o in _inspect(blender_bin, out / "model.blend")["objects"]}
    shelf_names = [name for name in objects if name.split("#")[0].startswith("cabinet-shelf")]
    assert len(shelf_names) == 4
    expected_deeper_y = deeper.y0 + deeper.depth / 2 - shift_y
    deeper_objects = [
        objects[name]
        for name in shelf_names
        if abs(objects[name]["location"][1] * 1000 - expected_deeper_y) < 0.5
    ]
    assert len(deeper_objects) == 1
    ys = [corner[1] for corner in deeper_objects[0]["bound_box"]]
    assert (max(ys) - min(ys)) * 1000 == pytest.approx(500, abs=0.1)
    assert min(ys) * 1000 == pytest.approx(deeper.y0 - shift_y, abs=0.1)
    default_ys = [
        (max(c[1] for c in objects[name]["bound_box"]) - min(c[1] for c in objects[name]["bound_box"])) * 1000
        for name in shelf_names
        if abs(objects[name]["location"][1] * 1000 - (default.y0 + default.depth / 2 - shift_y)) < 0.5
    ]
    assert default_ys and all(depth == pytest.approx(388, abs=0.1) for depth in default_ys)


def test_layers_list_the_mixed_depth_shelves(built) -> None:
    _spec, out = built
    emitted = json.loads((out / "spec.json").read_text(encoding="utf-8"))
    shelves = [name for name in emitted["layers"]["shelves"] if name.startswith("cabinet-shelf")]
    assert len(shelves) == 4


FOLDED = json.loads(json.dumps(SPEC))
FOLDED["name"] = "Folded cabinet, protruding shelf"
FOLDED["modules"][0].update(
    y=162,
    shelves=3,
    shelf_depths_mm=[None, None, 550],
    side_folds=[{"side": "left", "from_mm": 1100, "along": "height", "angle_deg": 26, "towards": "inside"}],
)
FOLDED["envelope"] = {"width": 800, "height": 1600, "depth": 562}


def test_a_protruding_shelf_on_a_folded_cabinet_is_drawn_where_derived(blender_bin: Path, tmp_path: Path) -> None:
    spec = CustomBuildSpec.model_validate(FOLDED).model_dump(mode="json")
    result, out = _build(blender_bin, spec, tmp_path)
    assert result.returncode == 0, result.stderr
    module = spec["modules"][0]
    deeper = next(board for board in rules.shelf_boards(module, 18, 12) if board.depth == 550)
    # The scene is centred on the build's overall AABB: the envelope here.
    shift_y = 562 / 2 - module["y"]
    objects = {o["name"]: o for o in _inspect(blender_bin, out / "model.blend")["objects"]}
    found = [
        o for name, o in objects.items()
        if name.split("#")[0].startswith("cabinet-shelf")
        and abs(o["location"][1] * 1000 - (deeper.y0 + deeper.depth / 2 - shift_y)) < 0.5
    ]
    assert len(found) == 1
    ys = [corner[1] for corner in found[0]["bound_box"]]
    xs = [corner[0] for corner in found[0]["bound_box"]]
    assert (max(ys) - min(ys)) * 1000 == pytest.approx(550, abs=0.1)
    assert (max(xs) - min(xs)) * 1000 == pytest.approx(deeper.width, abs=0.1)
