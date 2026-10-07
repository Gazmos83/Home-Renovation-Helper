"""room-composition: build_composition.py and render_composition.py inside the pinned Blender (run with --blender).

A fixture room holds one built piece (the custom-build starter), one stand-in and one
GLB library model; the build is checked for its objects and sizes, then a still is
rendered at tier `draft`.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from app.blender import storage
from app.blender.composition_contract import (
    parse_composition,
    place_items,
    room_geometry,
)
from app.blender.schemas import CustomBuildSpec
from app.render.tiers import load_tiers
from tests import model_fixtures as fx
from tests.blender_fakes import png_size
from tests.test_custom_build_generator import _build as build_piece
from tests.test_custom_build_generator import _inspect

pytestmark = [pytest.mark.blender, pytest.mark.slow]

BACKEND = Path(__file__).resolve().parents[1]
GENERATORS = BACKEND / "app/blender/generators"
ROOM = {
    "corners_mm": [[0, 0], [5000, 0], [5000, 4000], [0, 4000]], "height_mm": 2600, "wall_thickness_mm": 100,
    "openings": [{"wall": 0, "type": "door", "offset_mm": 3800, "width_mm": 900, "height_mm": 2100, "sill_mm": 0}],
}
MODEL_ID = "0b8f3c1e-0000-4000-8000-000000000001"


@pytest.fixture(scope="module")
def scene(blender_bin: Path, tmp_path_factory: pytest.TempPathFactory):
    root = tmp_path_factory.mktemp("renders")
    models = tmp_path_factory.mktemp("models")
    starter = json.loads((BACKEND / "fixtures/packages/templates/custom-build.json").read_text(encoding="utf-8"))
    spec = CustomBuildSpec.model_validate(starter).model_dump(mode="json")
    result, out = build_piece(blender_bin, spec, tmp_path_factory.mktemp("piece"))
    assert result.returncode == 0, result.stderr[-800:]
    piece = storage.version_dir(root, "cabinet", 1)
    piece.parent.mkdir(parents=True)
    out.replace(piece)
    storage.write_status(piece, status="succeeded")
    overall = json.loads((piece / "spec.json").read_text(encoding="utf-8"))["overall"]

    (models / MODEL_ID).mkdir()
    (models / MODEL_ID / "model.glb").write_bytes(fx.glb())

    parsed = parse_composition({
        "kind": "room_composition", "schema_version": 1, "units": "mm", "scope": {"room": "Wohnen"},
        "items": [
            {"id": "cabinet", "type": "piece", "package_id": "cabinet", "version": 1,
             "placement": {"wall": 1, "offset_mm": 500}},
            {"id": "sofa", "type": "stand-in", "name": "Sofa", "width_mm": 2200, "depth_mm": 950, "height_mm": 800,
             "colour": "#7a6a58", "placement": {"x_mm": 2200, "y_mm": 2600, "rotation_deg": 180}},
            {"id": "armchair", "type": "model", "model_id": MODEL_ID, "name": "Armchair",
             "width_mm": 800, "depth_mm": 700, "height_mm": 900,
             "placement": {"x_mm": 1200, "y_mm": 1200, "rotation_deg": 30}},
        ],
    }, max_items=30)
    document, _subjects = place_items(
        parsed, rooms={"Wohnen": room_geometry("Wohnen", ROOM)},
        piece_sizes={"cabinet": (overall["w"], overall["d"], overall["h"])}, scope_room="Wohnen",
    )
    for placed in document["resolved"]["items"]:
        if placed["id"] == "armchair":
            placed["source"] = {"kind": "glb", "entry": "model.glb"}
    folder = storage.composition_version_dir(root, "wohnen", 1)
    folder.mkdir(parents=True)
    (folder / storage.INPUT_FILE).write_text(json.dumps(document), encoding="utf-8")

    build_out = folder / ".build-out"
    result = subprocess.run(
        [str(blender_bin), "--background", "--python", str(GENERATORS / "build_composition.py"), "--",
         "--spec", str(folder / storage.INPUT_FILE), "--pieces", str(root), "--models", str(models),
         "--out", str(build_out)],
        capture_output=True, text=True, timeout=300, check=False,
    )
    assert result.returncode == 0, result.stderr[-1500:]
    return root, models, folder, build_out, overall


def test_the_build_publishes_the_blend_a_screenshot_and_a_report(scene) -> None:
    _root, _models, _folder, out, _overall = scene
    assert {p.name for p in out.iterdir()} == set(storage.COMPOSITION_FILES)
    assert png_size(out / "screenshot.png") == (800, 500)


def test_every_item_has_its_size_and_stands_on_the_floor(scene) -> None:
    _root, _models, _folder, out, overall = scene
    report = {item["id"]: item for item in json.loads((out / "report.json").read_text(encoding="utf-8"))["items"]}
    assert set(report) == {"cabinet", "sofa", "armchair"}
    chair = report["armchair"]
    # A model is stretched on each axis to exactly its stated size (measured 900 × 800 × 1000 mm).
    assert chair["scale"]["x"] == pytest.approx(800 / 900, abs=1e-3)
    assert chair["scale"]["y"] == pytest.approx(700 / 800, abs=1e-3)
    assert chair["scale"]["z"] == pytest.approx(0.9, abs=1e-3)
    # Measured in its own frame: turned 30°, it is still exactly its stated size.
    assert chair["final_mm"] == pytest.approx({"x": 800, "y": 700, "z": 900}, abs=1)
    assert report["sofa"]["final_mm"] == pytest.approx({"x": 2200, "y": 950, "z": 800}, abs=1)
    assert report["cabinet"]["final_mm"]["z"] == pytest.approx(overall["h"], abs=1)
    # Against wall 1 (turned 90°), its width still runs along the wall.
    assert report["cabinet"]["final_mm"]["x"] == pytest.approx(overall["w"], abs=25)
    for item in report.values():
        assert item["lowest_mm"] == pytest.approx(0, abs=1), item["id"]


def test_the_blend_holds_the_room_and_the_three_items(scene, blender_bin: Path) -> None:
    _root, _models, _folder, out, _overall = scene
    names = {o["name"] for o in _inspect(blender_bin, out / "model.blend")["objects"]}
    assert {"ITEM_cabinet", "ITEM_armchair", "STAND_sofa", "Floor", "Ceiling"} <= names
    assert any(name.startswith("Wall_") for name in names)


def test_a_draft_still_renders_from_the_stored_document(scene, blender_bin: Path, tmp_path: Path) -> None:
    root, models, folder, _out, _overall = scene
    draft = load_tiers().get("draft")
    result = subprocess.run(
        [str(blender_bin), "--background", "--python", str(GENERATORS / "render_composition.py"), "--",
         "--spec", str(folder / storage.INPUT_FILE), "--pieces", str(root), "--models", str(models),
         "--out", str(tmp_path / "still"), "--kind", "still",
         "--tier-frames", str(draft.frames), "--tier-resolution", str(draft.resolution),
         "--tier-engine", draft.blender_engine],
        capture_output=True, text=True, timeout=600, check=False,
    )
    assert result.returncode == 0, result.stderr[-1500:]
    assert png_size(tmp_path / "still" / "still.png") == (draft.resolution, draft.resolution)
    scene_record = json.loads((tmp_path / "still" / "scene.json").read_text(encoding="utf-8"))
    assert scene_record["output"]["kind"] == "still" and scene_record["input"]["scope"] == {"room": "Wohnen"}
