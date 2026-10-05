"""room-scene-rendering: the standard-library room contract.

Mirrors test_blender_spec.py's shape for the furniture contract: dependency-
free input, validated before any Blender work, with every relational check
proved against the traced apartment 4 fixture and a plain rectangle.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from app.blender.room_contract import SpecValidationError, normalise_room_scene

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "packages"
LISTENING_WALL_OVERALL = {"w": 2112.0, "h": 1508.0, "d": 372.0}


def _load(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


@pytest.fixture
def rectangle_doc() -> dict:
    return _load("room-scene-rectangle.json")


@pytest.fixture
def apt4_doc() -> dict:
    return _load("room-scene-apt4-living.json")


# --- valid documents ------------------------------------------------------------------


def test_the_rectangle_fixture_is_accepted(rectangle_doc: dict) -> None:
    ctx = normalise_room_scene(rectangle_doc, package_overall=LISTENING_WALL_OVERALL)
    assert len(ctx.corners) == 4
    assert len(ctx.walls) == 4
    assert ctx.walls[0].length_mm == pytest.approx(4000)
    assert ctx.walls[1].length_mm == pytest.approx(3500)


def test_the_apartment_4_quadrilateral_is_accepted(apt4_doc: dict) -> None:
    ctx = normalise_room_scene(apt4_doc, package_overall=LISTENING_WALL_OVERALL)
    assert len(ctx.corners) == 4
    # Shoelace area within 0.5% of the plan's printed 32.287 m^2.
    n = len(ctx.corners)
    area2 = sum(
        ctx.corners[i][0] * ctx.corners[(i + 1) % n][1]
        - ctx.corners[(i + 1) % n][0] * ctx.corners[i][1]
        for i in range(n)
    )
    area_m2 = abs(area2) / 2 / 1_000_000
    assert area_m2 == pytest.approx(32.287, rel=0.005)
    assert len(ctx.openings) == 3
    assert len(ctx.furnishings) == 6
    for furnishing in ctx.furnishings:
        for corner in furnishing["footprint"]:
            assert _inside(corner, ctx.corners)


def _inside(point, corners) -> bool:
    from app.blender.room_contract import _point_in_convex_polygon

    return _point_in_convex_polygon(point, corners)


def test_a_rectangle_is_the_four_corner_case(rectangle_doc: dict) -> None:
    """A client's three intake dimensions become exactly this shape."""
    corners = rectangle_doc["room"]["corners"]
    assert len(corners) == 4
    xs = sorted({c[0] for c in corners})
    ys = sorted({c[1] for c in corners})
    assert len(xs) == 2 and len(ys) == 2  # an axis-aligned rectangle


# --- package placement ------------------------------------------------------------


def test_package_overflow_names_the_wall_and_the_excess(rectangle_doc: dict) -> None:
    document = copy.deepcopy(rectangle_doc)
    document["placement"]["offset_mm"] = 3500  # 3500 + 2112 > 4000

    with pytest.raises(SpecValidationError, match=r"wall 0"):
        normalise_room_scene(document, package_overall=LISTENING_WALL_OVERALL)


def test_a_taller_package_than_the_ceiling_is_refused(rectangle_doc: dict) -> None:
    with pytest.raises(SpecValidationError, match="ceiling"):
        normalise_room_scene(
            rectangle_doc, package_overall={"w": 2112, "h": 3000, "d": 372}
        )


def test_a_package_footprint_leaving_the_room_is_refused() -> None:
    # A tiny triangle-adjacent room where the package cannot fit inward.
    document = {
        "kind": "room_scene",
        "schema_version": 1,
        "units": "mm",
        "room": {"corners": [[0, 0], [3000, 0], [3000, 300], [0, 300]], "height_mm": 2600},
        "openings": [],
        "placement": {"wall": 0, "offset_mm": 0},
        "furnishings": [],
        "output": {"kind": "still"},
    }
    with pytest.raises(SpecValidationError, match="leaves the room"):
        normalise_room_scene(document, package_overall=LISTENING_WALL_OVERALL)


# --- furnishings --------------------------------------------------------------------


def test_a_furnishing_outside_the_leaning_west_wall_is_refused(apt4_doc: dict) -> None:
    document = copy.deepcopy(apt4_doc)
    document["furnishings"] = [
        {
            "name": "misplaced_lamp",
            "width_mm": 400,
            "depth_mm": 400,
            "height_mm": 1600,
            "x_mm": 200,
            "y_mm": 4400,  # west of the leaning wall boundary at this y
            "rotation_deg": 0,
        }
    ]
    with pytest.raises(SpecValidationError, match=r"misplaced_lamp.*leaves the room"):
        normalise_room_scene(document, package_overall=LISTENING_WALL_OVERALL)


def test_a_furnishing_intersecting_the_package_is_refused(apt4_doc: dict) -> None:
    document = copy.deepcopy(apt4_doc)
    document["furnishings"] = [
        {
            "name": "on_top_of_package",
            "width_mm": 400,
            "depth_mm": 400,
            "height_mm": 900,
            "x_mm": 6100,
            "y_mm": 2664,  # inside the Listening Wall's own footprint
            "rotation_deg": 0,
        }
    ]
    with pytest.raises(SpecValidationError, match=r"on_top_of_package.*overlaps the package"):
        normalise_room_scene(document, package_overall=LISTENING_WALL_OVERALL)


def test_furnishings_may_overlap_each_other(rectangle_doc: dict) -> None:
    document = copy.deepcopy(rectangle_doc)
    document["furnishings"] = [
        {
            "name": "rug",
            "width_mm": 2000,
            "depth_mm": 2000,
            "height_mm": 10,
            "x_mm": 1500,
            "y_mm": 1500,
            "rotation_deg": 0,
        },
        {
            "name": "coffee_table",
            "width_mm": 800,
            "depth_mm": 800,
            "height_mm": 400,
            "x_mm": 1500,
            "y_mm": 1500,
            "rotation_deg": 0,
        },
    ]
    ctx = normalise_room_scene(document, package_overall=LISTENING_WALL_OVERALL)
    assert len(ctx.furnishings) == 2


def test_duplicate_furnishing_names_are_refused(rectangle_doc: dict) -> None:
    document = copy.deepcopy(rectangle_doc)
    document["furnishings"] = [
        {"name": "lamp", "width_mm": 300, "depth_mm": 300, "height_mm": 1500, "x_mm": 500, "y_mm": 500, "rotation_deg": 0},
        {"name": "lamp", "width_mm": 300, "depth_mm": 300, "height_mm": 1500, "x_mm": 2500, "y_mm": 2500, "rotation_deg": 0},
    ]
    with pytest.raises(SpecValidationError, match="lamp"):
        normalise_room_scene(document, package_overall=LISTENING_WALL_OVERALL)


# --- openings -----------------------------------------------------------------------


def test_overlapping_openings_name_both(rectangle_doc: dict) -> None:
    document = copy.deepcopy(rectangle_doc)
    document["openings"] = [
        {"wall": 2, "type": "door", "offset_mm": 100, "width_mm": 900, "height_mm": 2100},
        {"wall": 2, "type": "window", "offset_mm": 500, "width_mm": 900, "height_mm": 1200, "sill_mm": 900},
    ]
    with pytest.raises(SpecValidationError, match="wall 2"):
        normalise_room_scene(document, package_overall=LISTENING_WALL_OVERALL)


def test_an_opening_running_off_its_wall_is_refused(rectangle_doc: dict) -> None:
    document = copy.deepcopy(rectangle_doc)
    document["openings"] = [
        {"wall": 2, "type": "door", "offset_mm": 3800, "width_mm": 900, "height_mm": 2100}
    ]
    with pytest.raises(SpecValidationError, match="wall 2"):
        normalise_room_scene(document, package_overall=LISTENING_WALL_OVERALL)


def test_an_opening_above_the_ceiling_is_refused(rectangle_doc: dict) -> None:
    document = copy.deepcopy(rectangle_doc)
    document["openings"] = [
        {"wall": 2, "type": "window", "offset_mm": 100, "width_mm": 900, "height_mm": 1800, "sill_mm": 900}
    ]
    with pytest.raises(SpecValidationError, match="ceiling"):
        normalise_room_scene(document, package_overall=LISTENING_WALL_OVERALL)


def test_a_door_with_a_sill_is_refused(rectangle_doc: dict) -> None:
    document = copy.deepcopy(rectangle_doc)
    document["openings"] = [
        {"wall": 2, "type": "door", "offset_mm": 100, "width_mm": 900, "height_mm": 2100, "sill_mm": 50}
    ]
    with pytest.raises(SpecValidationError, match="sill"):
        normalise_room_scene(document, package_overall=LISTENING_WALL_OVERALL)


# --- the polygon itself --------------------------------------------------------------


def test_an_l_shaped_outline_is_refused(rectangle_doc: dict) -> None:
    document = copy.deepcopy(rectangle_doc)
    document["room"]["corners"] = [
        [0, 0], [4000, 0], [4000, 1500], [2000, 1500], [2000, 3500], [0, 3500]
    ]
    document["placement"] = {"wall": 0, "offset_mm": 0}
    with pytest.raises(SpecValidationError, match="convex"):
        normalise_room_scene(document, package_overall={"w": 500, "h": 500, "d": 100})


def test_too_few_corners_is_refused(rectangle_doc: dict) -> None:
    document = copy.deepcopy(rectangle_doc)
    document["room"]["corners"] = [[0, 0], [4000, 0], [2000, 3500]]
    with pytest.raises(SpecValidationError, match="between"):
        normalise_room_scene(document, package_overall=LISTENING_WALL_OVERALL)


def test_too_many_corners_is_refused(rectangle_doc: dict) -> None:
    document = copy.deepcopy(rectangle_doc)
    document["room"]["corners"] = [[i * 500, 0] for i in range(9)]
    with pytest.raises(SpecValidationError, match="between"):
        normalise_room_scene(document, package_overall=LISTENING_WALL_OVERALL)


def test_clockwise_corners_are_normalised_not_refused(rectangle_doc: dict) -> None:
    document = copy.deepcopy(rectangle_doc)
    document["room"]["corners"] = list(reversed(document["room"]["corners"]))
    ctx = normalise_room_scene(document, package_overall=LISTENING_WALL_OVERALL)
    assert len(ctx.corners) == 4


# --- output: the tier decides frames, resolution and engine ---------------------------


@pytest.mark.parametrize("kind", ["still", "turntable"])
def test_output_names_a_kind_only(rectangle_doc: dict, kind: str) -> None:
    document = copy.deepcopy(rectangle_doc)
    document["output"] = {"kind": kind}
    ctx = normalise_room_scene(document, package_overall=LISTENING_WALL_OVERALL)
    assert ctx.output == {"kind": kind}
    assert ctx.input_document()["output"] == {"kind": kind}


@pytest.mark.parametrize(
    ("kind", "field", "value"),
    [
        ("turntable", "frames", 36),
        ("still", "frames", 24),
        ("turntable", "resolution", "draft"),
        ("still", "resolution", "full"),
        ("still", "engine", "CYCLES"),
    ],
)
def test_a_tier_owned_output_field_is_refused_by_name(
    rectangle_doc: dict, kind: str, field: str, value: object
) -> None:
    document = copy.deepcopy(rectangle_doc)
    document["output"] = {"kind": kind, field: value}
    with pytest.raises(SpecValidationError, match=field):
        normalise_room_scene(document, package_overall=LISTENING_WALL_OVERALL)


def test_an_unknown_output_kind_is_refused(rectangle_doc: dict) -> None:
    document = copy.deepcopy(rectangle_doc)
    document["output"] = {"kind": "video"}
    with pytest.raises(SpecValidationError, match="output.kind"):
        normalise_room_scene(document, package_overall=LISTENING_WALL_OVERALL)


# --- executable-looking / unknown fields -----------------------------------------------


def test_an_unknown_top_level_field_is_refused(rectangle_doc: dict) -> None:
    document = copy.deepcopy(rectangle_doc)
    document["script"] = "import os; os.system('rm -rf /')"
    with pytest.raises(SpecValidationError, match="unknown"):
        normalise_room_scene(document, package_overall=LISTENING_WALL_OVERALL)


def test_an_unknown_furnishing_field_is_refused(rectangle_doc: dict) -> None:
    document = copy.deepcopy(rectangle_doc)
    document["furnishings"] = [
        {
            "name": "lamp",
            "width_mm": 300,
            "depth_mm": 300,
            "height_mm": 1500,
            "x_mm": 500,
            "y_mm": 500,
            "rotation_deg": 0,
            "module_path": "app.blender.generators.build_room_scene",
        }
    ]
    with pytest.raises(SpecValidationError, match="unknown"):
        normalise_room_scene(document, package_overall=LISTENING_WALL_OVERALL)


def test_missing_a_required_field_is_refused(rectangle_doc: dict) -> None:
    document = copy.deepcopy(rectangle_doc)
    del document["room"]["height_mm"]
    with pytest.raises(SpecValidationError, match="missing"):
        normalise_room_scene(document, package_overall=LISTENING_WALL_OVERALL)


def test_a_non_object_document_is_refused() -> None:
    with pytest.raises(SpecValidationError):
        normalise_room_scene([1, 2, 3], package_overall=LISTENING_WALL_OVERALL)  # type: ignore[arg-type]
