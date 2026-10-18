"""build_custom_build.py inside the pinned Blender (run with --blender)."""

from __future__ import annotations

import csv
import json
import subprocess
from pathlib import Path

import pytest

from app.blender import storage
from app.blender.custom_build import derive as rules
from app.blender.schemas import CustomBuildSpec
from tests.blender_fakes import png_size

pytestmark = pytest.mark.blender

BACKEND = Path(__file__).resolve().parents[1]
GENERATOR = BACKEND / "app/blender/generators/build_custom_build.py"
INSPECT = Path(__file__).with_name("blender_inspect.py")
TEMPLATE = BACKEND / "fixtures/packages/templates/fold-down-desk.json"


def _normalised(path: Path = TEMPLATE) -> dict:
    document = json.loads(path.read_text(encoding="utf-8"))
    return CustomBuildSpec.model_validate(document).model_dump(mode="json")


def _build(
    blender_bin: Path, spec: dict, tmp_path: Path, inputs: dict | None = None
) -> tuple[subprocess.CompletedProcess, Path]:
    spec_path = tmp_path / "spec.json"
    spec_path.write_text(json.dumps(spec), encoding="utf-8")
    out = tmp_path / "out"
    extra: list[str] = []
    if inputs is not None:
        (tmp_path / "hardware_inputs.json").write_text(json.dumps(inputs), encoding="utf-8")
        extra = ["--hardware-data", str(tmp_path / "hardware_inputs.json")]
    result = subprocess.run(
        [str(blender_bin), "--background", "--python", str(GENERATOR), "--",
         "--spec", str(spec_path), "--out", str(out), *extra],
        capture_output=True, text=True, timeout=300, check=False,
    )
    return result, out


def _inspect(blender_bin: Path, blend: Path) -> dict:
    result = subprocess.run(
        [str(blender_bin), "--background", str(blend), "--python", str(INSPECT)],
        capture_output=True, text=True, timeout=120, check=False,
    )
    line = next(entry for entry in result.stdout.splitlines() if entry.startswith("INSPECT "))
    return json.loads(line[len("INSPECT "):])


@pytest.fixture(scope="module")
def built(blender_bin: Path, tmp_path_factory: pytest.TempPathFactory):
    tmp = tmp_path_factory.mktemp("build")
    spec = _normalised()
    result, out = _build(blender_bin, spec, tmp)
    assert result.returncode == 0, result.stderr[-800:]
    return spec, out


def test_the_template_builds_exactly_the_nine_files(built) -> None:
    _spec, out = built
    assert {entry.name for entry in out.iterdir()} == set(storage.BUILD_FILES)
    assert all(entry.stat().st_size > 0 for entry in out.iterdir())
    for name in ("screenshot.png", "front.png", "side.png", "top.png"):
        assert png_size(out / name) == (800, 500), name


def test_the_blend_file_carries_the_overall_dimensions_and_the_model_does_not(built, blender_bin: Path) -> None:
    _spec, out = built
    overall = json.loads((out / "spec.json").read_text(encoding="utf-8"))["overall"]
    objects = {o["name"]: o for o in _inspect(blender_bin, out / "model.blend")["objects"]}
    for axis, figure in (("W", overall["w"]), ("H", overall["h"]), ("D", overall["d"])):
        assert objects[f"DIM_Overall{axis}"]["type"] == "MESH"
        assert objects[f"DIM_Overall{axis}"]["parent"] == "MOD_Dimensions"
        label = objects[f"DIM_Label_{axis}"]
        assert (label["type"], label["text"], label["dimension"]) == ("FONT", f"{figure} mm", axis)
        assert label["faces"] == "CAM_Iso"
    assert objects["MOD_Dimensions"]["parent"] == "CustomBuild"
    glb = (out / "model.glb").read_bytes()
    assert b"DIM_" not in glb and b"MOD_Dimensions" not in glb


def test_the_emitted_spec_covers_every_mesh_in_one_layer(built, blender_bin: Path) -> None:
    _spec, out = built
    emitted = json.loads((out / "spec.json").read_text(encoding="utf-8"))
    for key in ("overall", "modules", "layers", "parts", "hardware", "assembly", "blender_version"):
        assert key in emitted
    layered = [name for names in emitted["layers"].values() for name in names]
    assert len(layered) == len(set(layered)), "each mesh is in exactly one layer"
    meshes = {o["name"] for o in _inspect(blender_bin, out / "model.blend")["objects"] if o["type"] == "MESH"}
    dimensions = {name for name in meshes if name.startswith("DIM_")}
    assert set(layered) == meshes - {"StudioFloor"} - dimensions


def test_shop_data_equals_the_derived_and_every_part_is_an_object(built, blender_bin: Path) -> None:
    spec, out = built
    parts, _hardware, _ = rules.derive(spec)
    with (out / "cutlist.csv").open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    assert [row["id"] for row in rows] == [part["id"] for part in parts]
    objects = {o["name"]: o for o in _inspect(blender_bin, out / "model.blend")["objects"]}
    module_empties = {f"MOD_{module['id']}" for module in spec["modules"]} | {"MOD_extras"}
    for part in parts:
        for n in range(1, int(part["qty"]) + 1):
            name = part["id"] if n == 1 else f"{part['id']}#{n}"
            assert name in objects, f"{name} is not an object"
            assert objects[name]["parent"] in module_empties


def test_a_build_sets_no_eevee_or_cycles_engine(built, blender_bin: Path) -> None:
    _spec, out = built
    assert _inspect(blender_bin, out / "model.blend")["engine"] == "BLENDER_WORKBENCH"


def test_an_invalid_document_publishes_nothing(blender_bin: Path, tmp_path: Path) -> None:
    spec = _normalised()
    spec["kind"] = "listening_wall"
    result, out = _build(blender_bin, spec, tmp_path)
    assert result.returncode != 0
    assert "kind must be 'custom_build'" in result.stderr
    assert not out.exists()
    assert [entry for entry in tmp_path.iterdir() if entry.name.startswith(".")] == []


# --- extra-part placement (extra-part-placement) --------------------------------------


def _placed_extras_spec() -> dict:
    document = json.loads(TEMPLATE.read_text(encoding="utf-8"))
    at = {"y": 0, "length_along": "x", "width_along": "y"}
    document["extra_parts"] = [
        {"id": "top-frame", "name": "Top frame", "qty": 1, "length": 1200, "width": 60, "material": "carcass",
         "placements": [{**at, "x": 0, "z": 1450}]},
        {"id": "post", "name": "Post", "qty": 1, "length": 900, "width": 45, "material": "carcass",
         "placements": [{"x": 1100, "y": 0, "z": 0, "length_along": "z", "width_along": "y"}]},
        {"id": "brace", "name": "Brace", "qty": 1, "length": 1000, "width": 60, "material": "carcass",
         "placements": [{**at, "x": 100, "z": 0, "tilt": {"towards": "z", "angle_deg": 30}}]},
        {"id": "brace-cut", "name": "Cut brace", "qty": 1, "length": 1000, "width": 60, "material": "carcass",
         "end_cuts": {"across": "width", "start_deg": 30, "end_deg": -30},
         "placements": [{"x": 100, "y": 200, "z": 0, "length_along": "x", "width_along": "z",
                         "tilt": {"towards": "z", "angle_deg": 30}}]},
        {"id": "spare-trim", "name": "Spare trim", "qty": 1, "length": 300, "width": 40, "material": "carcass"},
    ]
    return CustomBuildSpec.model_validate(document).model_dump(mode="json")


@pytest.fixture(scope="module")
def placed(blender_bin: Path, tmp_path_factory: pytest.TempPathFactory):
    tmp = tmp_path_factory.mktemp("placed")
    spec = _placed_extras_spec()
    result, out = _build(blender_bin, spec, tmp)
    assert result.returncode == 0, result.stderr[-800:]
    objects = {o["name"]: o for o in _inspect(blender_bin, out / "model.blend")["objects"]}
    return spec, out, objects


def _mm(vertices: list[list[float]]) -> list[tuple[float, float, float]]:
    return [tuple(round(v * 1000, 1) for v in vertex) for vertex in vertices]


def test_placed_extras_are_drawn_where_the_helper_puts_them(placed) -> None:
    spec, _out, objects = placed
    top = _mm(objects["top-frame"]["vertices"])
    # The scene is centred on x and y only, so heights are the build's own; the
    # top frame's corner fixes the shift for the other pieces.
    shift = (min(v[0] for v in top), min(v[1] for v in top))
    assert min(v[2] for v in top) == 1450 and max(v[2] for v in top) == 1468
    for part in spec["extra_parts"][:4]:
        expected = rules.extra_piece_corners(part, part["placements"][0], 18)
        drawn = sorted((round(x - shift[0], 1), round(y - shift[1], 1), z) for x, y, z in _mm(objects[part["id"]]["vertices"]))
        assert drawn == sorted(tuple(round(v, 1) for v in corner) for corner in expected), part["id"]
        assert objects[part["id"]]["parent"] == "MOD_extras"


def test_a_tilted_brace_rises_866_by_500_and_a_cut_brace_stands_plumb(placed) -> None:
    _spec, _out, objects = placed
    brace = _mm(objects["brace"]["vertices"])
    corner = min(brace, key=lambda v: (v[2], v[0]))
    assert any(abs(v[0] - corner[0] - 866.0) < 0.1 and abs(v[2] - corner[2] - 500.0) < 0.1 for v in brace)
    cut = _mm(objects["brace-cut"]["vertices"])
    assert len({v[0] for v in cut}) == 2


def test_an_unplaced_extra_still_lies_beside_the_build(placed) -> None:
    _spec, out, objects = placed
    trim = _mm(objects["spare-trim"]["vertices"])
    right = max(max(v[0] for v in _mm(objects[name]["vertices"])) for name in ("top-frame", "post", "brace"))
    assert min(v[0] for v in trim) >= right + 200 - 0.1
    assert {v[2] for v in trim} == {0.0, 18.0}
    assert png_size(out / "screenshot.png")[0] <= 800


# --- front handles (front-handles) ------------------------------------------------------


def _handles_spec(with_handles: bool = True) -> dict:
    bar = {"kind": "bar", "length": 900}
    drawer_bar = {"kind": "bar", "length": 160, "inset_mm": 30}
    module = {"x": 0, "y": 20, "z": 50, "width": 900, "height": 2034, "depth": 500, "carcass": "carcass", "back": "back"}
    document = {
        "kind": "custom_build", "schema_version": 1, "units": "mm", "name": "Handles",
        "materials": {
            "carcass": {"material": "16 mm Möbelbauplatte", "thickness_mm": 16},
            "back": {"material": "3 mm mdf", "thickness_mm": 3},
        },
        "modules": [
            {**module, "id": "left", "name": "Left",
             "fronts": [{"type": "door", "count": 2, "opening": "hinge", **({"handle": bar} if with_handles else {})}]},
            {**module, "id": "centre", "name": "Centre", "x": 900,
             "fronts": [{"type": "door", "count": 2, "opening": "hinge"},
                        {"type": "drawer", "count": 5, "height": 850, **({"handle": drawer_bar} if with_handles else {})}]},
        ],
    }
    return CustomBuildSpec.model_validate(document).model_dump(mode="json")


@pytest.fixture(scope="module")
def handled(blender_bin: Path, tmp_path_factory: pytest.TempPathFactory):
    built_pair = []
    for with_handles in (True, False):
        tmp = tmp_path_factory.mktemp("handles" if with_handles else "plain")
        result, out = _build(blender_bin, _handles_spec(with_handles), tmp)
        assert result.returncode == 0, result.stderr[-800:]
        objects = {o["name"]: o for o in _inspect(blender_bin, out / "model.blend")["objects"]}
        built_pair.append((out, objects))
    return built_pair


def _bounds(vertices: list[list[float]]) -> list[tuple[float, float]]:
    points = _mm(vertices)
    return [(min(p[axis] for p in points), max(p[axis] for p in points)) for axis in range(3)]


def test_door_handles_stand_on_the_meeting_edges_in_the_handles_layer(handled) -> None:
    (out, objects), _plain = handled
    layers = json.loads((out / "spec.json").read_text(encoding="utf-8"))["layers"]
    assert sorted(layers["handles"]) == sorted(
        ["left-door-1-handle", "left-door-1-handle#2"]
        + ["centre-drawer-2-front-handle"] + [f"centre-drawer-2-front-handle#{n}" for n in range(2, 6)]
    )
    for door, handle, edge in (("left-door-1", "left-door-1-handle", 1), ("left-door-1#2", "left-door-1-handle#2", 0)):
        door_x, door_y, door_z = _bounds(objects[door]["vertices"])
        hx, hy, hz = _bounds(objects[handle]["vertices"])
        centre_x = (hx[0] + hx[1]) / 2
        expected_x = door_x[1] - 40 if edge else door_x[0] + 40
        assert abs(centre_x - expected_x) < 0.2, handle
        assert abs((hz[0] + hz[1]) / 2 - (door_z[0] + door_z[1]) / 2) < 0.2
        assert abs(hz[1] - hz[0] - 900) < 0.2 and abs(hx[1] - hx[0] - 12) < 0.2
        assert abs(hy[0] - (door_y[0] - 30)) < 0.2 and abs(hy[1] - door_y[0]) < 0.2
        assert objects[handle]["parent"] == "MOD_left"
        assert objects[handle]["part_id"] is None


def test_five_drawer_handles_and_no_handle_in_the_cut_list(handled) -> None:
    (out, objects), (plain_out, _plain_objects) = handled
    assert all(f"centre-drawer-2-front-handle{suffix}" in objects for suffix in ["", "#2", "#3", "#4", "#5"])
    with (out / "cutlist.csv").open(newline="", encoding="utf-8") as handle:
        assert not any("handle" in row["id"] for row in csv.DictReader(handle))
    emitted = json.loads((out / "spec.json").read_text(encoding="utf-8"))
    plain = json.loads((plain_out / "spec.json").read_text(encoding="utf-8"))
    assert emitted["overall"] == plain["overall"]
    assert (out / "cutlist.csv").read_text(encoding="utf-8").replace("handle handle-bar-900-black", "handle as specified") == (
        plain_out / "cutlist.csv"
    ).read_text(encoding="utf-8")


def test_a_build_without_handles_has_no_handles_layer_or_object(handled) -> None:
    (_out, objects), (plain_out, plain_objects) = handled
    assert "handles" not in json.loads((plain_out / "spec.json").read_text(encoding="utf-8"))["layers"]
    assert not any("-handle" in name for name in plain_objects)
    assert {name for name in objects if "-handle" not in name} == set(plain_objects)


# --- door slats (door-slats) -------------------------------------------------------------


def _slats_spec(slats: dict | None, knob: bool = True) -> dict:
    door = {"type": "door", "count": 2, "opening": "hinge"}
    if knob:
        door["handle"] = {"kind": "knob"}
    if slats is not None:
        door["slats"] = {"material": "slats", "leaves": [2], **slats}
    document = {
        "kind": "custom_build", "schema_version": 1, "units": "mm", "name": "Kommode",
        "materials": {
            "carcass": {"material": "16 mm oak Möbelbauplatte", "thickness_mm": 16},
            "back": {"material": "3 mm mdf", "thickness_mm": 3},
            "slats": {"material": "12 mm anthracite MDF", "thickness_mm": 12},
        },
        "modules": [
            {"id": "kommode", "name": "Kommode", "x": 0, "y": 20, "z": 100, "width": 800, "height": 750,
             "depth": 400, "carcass": "carcass", "back": "back", "fronts": [door]},
        ],
    }
    return CustomBuildSpec.model_validate(document).model_dump(mode="json")


@pytest.fixture(scope="module")
def slatted(blender_bin: Path, tmp_path_factory: pytest.TempPathFactory):
    builds = {}
    for name, slats in (
        ("vertical", {"count": 8, "width": 30}),
        ("horizontal", {"count": 10, "width": 40, "orientation": "horizontal"}),
        ("plain", None),
    ):
        spec = _slats_spec(slats)
        result, out = _build(blender_bin, spec, tmp_path_factory.mktemp(f"slats-{name}"))
        assert result.returncode == 0, result.stderr[-800:]
        objects = {o["name"]: o for o in _inspect(blender_bin, out / "model.blend")["objects"]}
        builds[name] = (spec, out, objects)
    return builds


def _slat_names(count: int) -> list[str]:
    return ["kommode-door-1-slat"] + [f"kommode-door-1-slat#{n}" for n in range(2, count + 1)]


def test_vertical_slats_are_drawn_on_the_right_door_in_the_fronts_layer(slatted) -> None:
    _spec, out, objects = slatted["vertical"]
    layers = json.loads((out / "spec.json").read_text(encoding="utf-8"))["layers"]
    names = _slat_names(8)
    assert set(names) <= set(layers["fronts"])
    door_x, door_y, door_z = _bounds(objects["kommode-door-1#2"]["vertices"])
    first, last = (_bounds(objects[name]["vertices"]) for name in (names[0], names[-1]))
    assert abs(first[0][0] - door_x[0]) < 0.2 and abs(last[0][1] - door_x[1]) < 0.2
    xs = [_bounds(objects[name]["vertices"])[0][0] for name in names]
    assert xs == sorted(xs)
    for name in names:
        sx, sy, sz = _bounds(objects[name]["vertices"])
        assert abs(sx[1] - sx[0] - 30) < 0.2 and abs(sz[1] - sz[0] - 747) < 0.2
        assert abs(sy[1] - door_y[0]) < 0.2 and abs(sy[0] - (door_y[0] - 12)) < 0.2
        assert abs((sz[0] + sz[1]) / 2 - (door_z[0] + door_z[1]) / 2) < 0.2
        assert objects[name]["parent"] == "MOD_kommode"
        assert objects[name]["part_id"] == "kommode-door-1-slat"


def test_horizontal_slats_run_across_the_door_top_to_bottom(slatted) -> None:
    _spec, _out, objects = slatted["horizontal"]
    door_x, _door_y, door_z = _bounds(objects["kommode-door-1#2"]["vertices"])
    bounds = [_bounds(objects[name]["vertices"]) for name in _slat_names(10)]
    assert all(abs(b[0][0] - door_x[0]) < 0.2 and abs(b[0][1] - door_x[1]) < 0.2 for b in bounds)
    assert abs(bounds[0][2][1] - door_z[1]) < 0.2 and abs(bounds[-1][2][0] - door_z[0]) < 0.2
    tops = [b[2][1] for b in bounds]
    assert tops == sorted(tops, reverse=True)


def test_a_knob_on_slats_stands_proud_of_the_slats(slatted) -> None:
    for name in ("vertical", "horizontal"):
        _spec, _out, objects = slatted[name]
        door_y = _bounds(objects["kommode-door-1"]["vertices"])[1]
        left_knob = _bounds(objects["kommode-door-1-handle"]["vertices"])[1]
        right_knob = _bounds(objects["kommode-door-1-handle#2"]["vertices"])[1]
        assert abs(left_knob[0] - (door_y[0] - 25)) < 0.2, name
        assert abs(right_knob[0] - (door_y[0] - 12 - 25)) < 0.2, name
        assert abs(right_knob[1] - (door_y[0] - 12)) < 0.2, name


def test_the_slat_row_and_its_warning_reach_the_cut_list(slatted) -> None:
    spec, out, _objects = slatted["vertical"]
    with (out / "cutlist.csv").open(newline="", encoding="utf-8") as handle:
        rows = {row["id"]: row for row in csv.DictReader(handle)}
    parts, _hardware, _assembly = rules.derive(spec)
    derived = next(row for row in parts if row["id"] == "kommode-door-1-slat")
    assert rows["kommode-door-1-slat"]["notes"] == derived["notes"]
    assert (rows["kommode-door-1-slat"]["qty"], rows["kommode-door-1-slat"]["l"]) == ("8", "747")
    assert "Warning: the handle on door 2 of kommode-door-1 is mounted over the slats" in derived["notes"]
    plain = json.loads((slatted["plain"][1] / "spec.json").read_text(encoding="utf-8"))
    assert json.loads((out / "spec.json").read_text(encoding="utf-8"))["overall"] == plain["overall"]


def test_a_build_without_slats_draws_the_same_objects(slatted) -> None:
    _spec, plain_out, plain_objects = slatted["plain"]
    _spec, _out, objects = slatted["vertical"]
    assert not any("-slat" in name for name in plain_objects)
    assert {name for name in objects if "-slat" not in name} == set(plain_objects)
    with (plain_out / "cutlist.csv").open(newline="", encoding="utf-8") as handle:
        assert not any(row["id"].endswith("-slat") for row in csv.DictReader(handle))


def test_an_anthracite_slot_is_drawn_dark(slatted) -> None:
    _spec, _out, objects = slatted["vertical"]
    assert objects["kommode-door-1-slat"]["colours"] == [[0.09, 0.09, 0.1]]


# --- door leaf materials (door-leaf-materials) ------------------------------------------------------


def test_a_black_right_door_is_drawn_black_beside_the_oak_one(blender_bin: Path, tmp_path: Path) -> None:
    from tests.test_custom_build_boxes import _black_right_spec

    spec = _black_right_spec()
    result, out = _build(blender_bin, spec, tmp_path)
    assert result.returncode == 0, result.stderr[-800:]
    objects = {o["name"]: o for o in _inspect(blender_bin, out / "model.blend")["objects"]}
    left, right = (_bounds(objects[name]["vertices"]) for name in ("kommode-door-1-1", "kommode-door-1-2"))
    assert left[0][1] < right[0][0]
    assert abs(left[2][0] - right[2][0]) < 0.2 and abs(left[2][1] - right[2][1]) < 0.2
    assert objects["kommode-door-1-2"]["colours"] == [[0.035, 0.035, 0.04]]
    assert objects["kommode-door-1-1"]["colours"] == [[0.48, 0.29, 0.145]]
    slats = [_bounds(objects[name]["vertices"]) for name in objects if name.startswith("kommode-door-1-2-slat")]
    assert len(slats) == 8
    assert all(right[0][0] - 0.2 <= sx[0] and sx[1] <= right[0][1] + 0.2 for sx, _sy, _sz in slats)


# --- drawn hardware (hardware-catalog) -------------------------------------------------------------


def _sheet(kind: str, values: dict) -> dict:
    return {"kind": kind, "maker": "Test", "model": "T1", "values": values, "source": "test sheet",
            "source_kind": "manual", "updated_at": "2026-10-16T00:00:00"}


def _hardware_build() -> tuple[dict, dict]:
    from app.blender.hardware_catalog import default_catalog

    document = {
        "kind": "custom_build", "schema_version": 1, "units": "mm", "name": "Hardware",
        "materials": {"carcass": {"material": "18 mm Spanplatte", "thickness_mm": 18},
                      "back": {"material": "3 mm HDF", "thickness_mm": 3}},
        "modules": [
            {"id": "wardrobe", "name": "Wardrobe", "x": 0, "y": 0, "z": 0, "width": 932, "height": 2000, "depth": 600,
             "carcass": "carcass", "back": "back", "shelves": 1, "shelf_positions_mm": [1800],
             "hanging_rails": [{"z": 1650}], "fronts": [{"type": "door", "count": 2, "opening": "hinge"}]},
            {"id": "cabinet", "name": "Cabinet", "x": 932, "y": 0, "z": 0, "width": 600, "height": 900, "depth": 500,
             "carcass": "carcass", "back": "back", "adjustable_shelves": 2,
             "fronts": [{"type": "drawer", "count": 1, "height": 200}, {"type": "door", "count": 1, "opening": "hinge"}]},
        ],
    }
    inputs = {"rules": {}, "hardware_catalog": default_catalog().frozen(), "data_sheets": {
        "hinge-concealed-110": _sheet("hinge", {"cup_diameter_mm": {"value": 35}, "cup_depth_mm": {"value": 13},
                                                "cup_edge_distance_mm": {"value": 4}, "end_distance_mm": {"value": 100}}),
        "shelf-pin": _sheet("shelf_pin", {"front_setback_mm": {"value": 37}, "rear_setback_mm": {"value": 37},
                                          "pins_per_shelf": 4}),
    }}
    return CustomBuildSpec.model_validate(document).model_dump(mode="json"), inputs


@pytest.fixture(scope="module")
def hardwared(blender_bin: Path, tmp_path_factory: pytest.TempPathFactory):
    spec, inputs = _hardware_build()
    result, out = _build(blender_bin, spec, tmp_path_factory.mktemp("hardware"), inputs)
    assert result.returncode == 0, result.stderr[-800:]
    objects = {o["name"]: o for o in _inspect(blender_bin, out / "model.blend")["objects"]}
    return out, objects


def test_every_shown_piece_is_one_object_in_the_hardware_layer(hardwared) -> None:
    out, objects = hardwared
    emitted = json.loads((out / "spec.json").read_text(encoding="utf-8"))
    layer = sorted(emitted["layers"]["hardware"])
    handles = sum(1 for line in emitted["hardware"] if line["id"].startswith("handle-"))
    assert len(layer) == sum(line["shown"] for line in emitted["hardware"]) - handles
    for line in ("hinge-concealed-110", "shelf-pin", "drawer-runner-450", "rail-oval-30x15-894", "rail-support-oval"):
        assert f"{line}#1" in layer, line
    hinge = objects["hinge-concealed-110#1"]
    assert hinge["hardware_key"] == "hinge-concealed-110" and hinge["part_id"] is None
    assert hinge["materials"] == ["Hardware nickel"] and hinge["metallic"] == [1.0]
    assert hinge["modifiers"] == ["BEVEL"]
    assert objects["rail-oval-30x15-894#1"]["materials"] == ["Hardware chrome"]
    assert objects["shelf-pin#1"]["parent"] == "MOD_cabinet"
    assert not any(name.startswith("confirmat") for name in objects)


def test_the_rail_hangs_at_its_height_between_the_bay_sides(hardwared) -> None:
    _out, objects = hardwared
    x, _y, z = _bounds(objects["rail-oval-30x15-894#1"]["vertices"])
    assert abs((z[0] + z[1]) / 2 - 1668) < 0.5 and abs(z[1] - z[0] - 30) < 0.5
    assert abs(x[1] - x[0] - 894) < 0.5


def test_hardware_adds_no_cut_list_row(hardwared) -> None:
    out, _objects = hardwared
    with (out / "cutlist.csv").open(newline="", encoding="utf-8") as handle:
        ids = [row["id"] for row in csv.DictReader(handle)]
    assert not any(part.startswith(("hinge", "shelf-pin", "drawer-runner", "rail")) for part in ids)



# --- mounting (approval-reading-list) --------------------------------------------------


def test_a_wall_mounting_draws_the_same_objects(built, blender_bin: Path, tmp_path: Path) -> None:
    plain_spec, plain_out = built
    marked = json.loads(json.dumps(plain_spec))
    for module in marked["modules"]:
        module["mounting"] = "wall"
    result, out = _build(blender_bin, marked, tmp_path)
    assert result.returncode == 0, result.stderr[-800:]

    def shape(folder: Path) -> dict:
        return {o["name"]: o for o in _inspect(blender_bin, folder / "model.blend")["objects"]}

    assert shape(out) == shape(plain_out)
    assert (out / "cutlist.csv").read_text(encoding="utf-8") == (plain_out / "cutlist.csv").read_text(encoding="utf-8")
