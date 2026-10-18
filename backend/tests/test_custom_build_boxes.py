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


def test_a_folded_module_places_one_box_per_cut_list_row(generator) -> None:
    from app.blender.custom_build.derive import derive
    from app.blender.schemas import CustomBuildSpec
    from tests.test_side_folds import folded_cabinet

    spec = CustomBuildSpec.model_validate(folded_cabinet()).model_dump(mode="json")
    parts, _hardware, _assembly = derive(spec)
    placed = generator._folded_module_pieces(spec["modules"][0], spec["materials"])
    for row in parts:
        assert row["id"] in placed
        assert len(placed[row["id"]][1]) == row["qty"]
    upper = placed["cabinet-side-left-upper"][1][0]
    assert upper.rotation_deg[1] == pytest.approx(26)


def test_a_folded_cabinet_with_two_doors_places_an_n_gon_left_and_a_box_right(generator) -> None:
    from app.blender.custom_build.derive import derive
    from app.blender.schemas import CustomBuildSpec
    from tests.test_side_folds import folded_cabinet

    spec = CustomBuildSpec.model_validate(
        folded_cabinet(shelves=4, fronts=[{"type": "door", "count": 2, "opening": "hinge"}])
    ).model_dump(mode="json")
    parts, _hardware, _assembly = derive(spec)
    placed = generator._folded_module_pieces(spec["modules"][0], spec["materials"])
    for row in parts:
        assert row["id"] in placed
        assert len(placed[row["id"]][1]) == row["qty"]
    left = placed["cabinet-door-1-1"][1][0]
    right = placed["cabinet-door-1-2"][1][0]
    assert left.verts is not None and right.verts is None
    assert placed["cabinet-door-1-1"][0] == placed["cabinet-door-1-2"][0] == "fronts"


def test_shelves_355_mm_apart_and_two_dividers_are_laid_out_per_bay(generator) -> None:
    spec = build(modules=[module(width=1000, height=1600, shelves=4, shelf_spacing_mm=355, dividers=2)])
    pieces = generator._module_boxes(spec["modules"][0], spec["materials"])
    layer, dividers = pieces["m-divider"]
    assert layer == "carcass" and len(dividers) == 2
    # left faces at 18 + 309 and 18 + 327 + 309 from the module's left face
    assert [box[1][0] for box in dividers] == [18 + 309 + 9, 18 + 327 + 309 + 9]
    assert all(box[0] == (18, 397, 1600 - 36) for box in dividers)
    boards = pieces["m-shelf"][1]
    assert len(boards) == 12
    undersides = sorted({box[1][2] - 9 - 18 for box in boards})
    assert undersides == [355, 728, 1101, 1474]


@pytest.mark.parametrize(
    "fields",
    [
        {"shelves": 3, "dividers": 2},
        {"shelves": 2, "adjustable_shelves": 1, "dividers": 1, "divider_positions_mm": [400]},
        {"shelves": 3, "shelf_positions_mm": [300, 700, 1300]},
    ],
)
def test_every_shelf_and_divider_row_has_one_box_per_piece(generator, fields: dict) -> None:
    from app.blender.custom_build.derive import derive

    spec = build(modules=[module(width=1000, height=1600, **fields)])
    parts, _hardware, _assembly = derive(spec)
    placed = generator._module_boxes(spec["modules"][0], spec["materials"])
    for row in parts:
        if "shelf" in row["id"] or "divider" in row["id"]:
            assert len(placed[row["id"]][1]) == row["qty"]
            assert all(box[0][0] in (row["l"], row["w"]) or box[0][2] == row["l"] for box in placed[row["id"]][1])


def _black_right_spec(slats: bool = True) -> dict:
    """The Höffner dresser: an oak left door and a black right door carrying slats (door-leaf-materials)."""
    from app.blender.schemas import CustomBuildSpec

    door = {"type": "door", "count": 2, "opening": "hinge", "leaf_materials": {"2": "black_paint"}}
    if slats:
        door["slats"] = {"count": 8, "width": 30, "material": "slats", "leaves": [2]}
    document = {
        "kind": "custom_build", "schema_version": 1, "units": "mm", "name": "Kommode",
        "materials": {
            "carcass": {"material": "16 mm oak Möbelbauplatte", "thickness_mm": 16},
            "back": {"material": "3 mm mdf", "thickness_mm": 3},
            "black_paint": {"material": "16 mm black painted MDF", "thickness_mm": 16},
            "slats": {"material": "12 mm oak-veneered MDF", "thickness_mm": 12},
        },
        "modules": [
            {"id": "kommode", "name": "Kommode", "x": 0, "y": 20, "z": 100, "width": 800, "height": 750,
             "depth": 400, "carcass": "carcass", "back": "back", "fronts": [door]},
        ],
    }
    return CustomBuildSpec.model_validate(document).model_dump(mode="json")


def test_split_doors_are_a_box_each_where_the_pair_was(generator) -> None:
    from app.blender.custom_build.derive import derive

    spec = _black_right_spec()
    pieces = generator._module_boxes(spec["modules"][0], spec["materials"])
    plain = dict(spec, modules=[dict(spec["modules"][0], fronts=[{"type": "door", "count": 2, "opening": "hinge"}])])
    pair = generator._module_boxes(plain["modules"][0], plain["materials"])["kommode-door-1"][1]
    assert "kommode-door-1" not in pieces
    assert [pieces["kommode-door-1-1"][1][0], pieces["kommode-door-1-2"][1][0]] == pair
    assert len(pieces["kommode-door-1-2-slat"][1]) == 8
    parts, _hardware, _assembly = derive(spec)
    for row in parts:
        assert len(pieces[row["id"]][1]) == int(row["qty"]), row["id"]


def test_doors_without_leaf_materials_are_laid_out_as_before(generator) -> None:
    spec = _black_right_spec(slats=False)
    del spec["modules"][0]["fronts"][0]["leaf_materials"]
    pieces = generator._module_boxes(spec["modules"][0], spec["materials"])
    assert len(pieces["kommode-door-1"][1]) == 2
    assert not any(name.startswith("kommode-door-1-") for name in pieces)
