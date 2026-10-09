"""The generator's box layout for adjustable shelves and wall shelves, checked without Blender.

The generator imports `bpy` at the top, so the import runs against empty stand-in modules; only its
pure layout functions are called.
"""

from __future__ import annotations

import importlib
import sys
import types

import pytest

from tests.drill_helpers import build, module, wall_shelf


@pytest.fixture
def generator(monkeypatch: pytest.MonkeyPatch):
    for name in ("bpy", "mathutils"):
        stand_in = types.ModuleType(name)
        stand_in.types = types.SimpleNamespace(Material=object, Object=object, Collection=object)
        stand_in.Vector = object
        monkeypatch.setitem(sys.modules, name, stand_in)
    sys.modules.pop("app.blender.generators.build_custom_build", None)
    sys.modules.pop("app.blender.generators._scene", None)
    try:
        yield importlib.import_module("app.blender.generators.build_custom_build")
    finally:
        sys.modules.pop("app.blender.generators.build_custom_build", None)
        sys.modules.pop("app.blender.generators._scene", None)


def test_fixed_and_adjustable_shelves_are_spaced_evenly_together(generator) -> None:
    spec = build(modules=[module(shelves=1, adjustable_shelves=2)])
    pieces = generator._module_boxes(spec["modules"][0], spec["materials"])
    heights = [pieces["m-shelf"][1][0][1][2]] + [box[1][2] for box in pieces["m-adjustable-shelf"][1]]
    step = (720 - 36) / 4
    assert heights == [18 + step, 18 + 2 * step, 18 + 3 * step]
    assert pieces["m-adjustable-shelf"][0] == "shelves"
    size = pieces["m-adjustable-shelf"][1][0][0]
    assert size == (562, 397, 18)


def test_a_module_with_no_adjustable_shelves_is_laid_out_as_before(generator) -> None:
    spec = build(modules=[module(shelves=2)])
    pieces = generator._module_boxes(spec["modules"][0], spec["materials"])
    assert "m-adjustable-shelf" not in pieces
    assert [box[1][2] for box in pieces["m-shelf"][1]] == [18 + 228, 18 + 456]


def test_a_wall_shelf_is_one_board_at_its_position(generator) -> None:
    spec = build(wall_shelves=[wall_shelf(x=100, y=0, z=1400, length=1200, depth=250)])
    pieces = generator._wall_shelf_boxes(spec)
    assert pieces == {"wall-shelf-1": ("shelves", [((1200, 250, 18), (700, 125, 1409))])}


def test_every_cut_list_row_of_the_new_boards_has_a_box(generator) -> None:
    from app.blender.custom_build.derive import derive

    spec = build(modules=[module(adjustable_shelves=2)], wall_shelves=[wall_shelf()])
    parts, _hardware, _assembly = derive(spec)
    placed = dict(generator._module_boxes(spec["modules"][0], spec["materials"])) | generator._wall_shelf_boxes(spec)
    for row in parts:
        if row["id"] in ("m-adjustable-shelf", "wall-shelf-1"):
            assert len(placed[row["id"]][1]) == row["qty"]
