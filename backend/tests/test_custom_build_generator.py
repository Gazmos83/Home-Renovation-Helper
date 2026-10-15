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
