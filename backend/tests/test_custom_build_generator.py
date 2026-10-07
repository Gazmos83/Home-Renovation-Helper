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


def _build(blender_bin: Path, spec: dict, tmp_path: Path) -> tuple[subprocess.CompletedProcess, Path]:
    spec_path = tmp_path / "spec.json"
    spec_path.write_text(json.dumps(spec), encoding="utf-8")
    out = tmp_path / "out"
    result = subprocess.run(
        [str(blender_bin), "--background", "--python", str(GENERATOR), "--",
         "--spec", str(spec_path), "--out", str(out)],
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
