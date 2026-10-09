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


# --- an empty room (rooms-page) ------------------------------------------------------------


def test_an_empty_room_builds_the_room_alone_and_renders_a_draft_still(
    blender_bin: Path, tmp_path: Path
) -> None:
    root, models = tmp_path / "renders", tmp_path / "models"
    models.mkdir()
    parsed = parse_composition({
        "kind": "room_composition", "schema_version": 1, "units": "mm", "scope": {"room": "Hall"}, "items": [],
    }, max_items=30)
    document, subjects = place_items(
        parsed, rooms={"Hall": room_geometry("Hall", ROOM)}, piece_sizes={}, scope_room="Hall",
    )
    assert subjects == []
    folder = storage.composition_version_dir(root, "hall", 1)
    folder.mkdir(parents=True)
    (folder / storage.INPUT_FILE).write_text(json.dumps(document), encoding="utf-8")

    out = folder / ".build-out"
    result = subprocess.run(
        [str(blender_bin), "--background", "--python", str(GENERATORS / "build_composition.py"), "--",
         "--spec", str(folder / storage.INPUT_FILE), "--pieces", str(root), "--models", str(models),
         "--out", str(out)],
        capture_output=True, text=True, timeout=300, check=False,
    )
    assert result.returncode == 0, result.stderr[-1500:]
    assert json.loads((out / "report.json").read_text(encoding="utf-8"))["items"] == []
    assert (out / "screenshot.png").is_file()
    names = {o["name"] for o in _inspect(blender_bin, out / "model.blend")["objects"]}
    assert {"Floor", "Ceiling"} <= names and any(name.startswith("Wall_") for name in names)
    assert not any(name.startswith(("ITEM_", "STAND_")) for name in names)

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


# --- the 3D model and its surface map (app-check-2026-10-09) ---------------------------------


def _build_document(blender_bin: Path, root: Path, models: Path, slug: str, document: dict) -> Path:
    folder = storage.composition_version_dir(root, slug, 1)
    folder.mkdir(parents=True)
    (folder / storage.INPUT_FILE).write_text(json.dumps(document), encoding="utf-8")
    out = folder / ".build-out"
    result = subprocess.run(
        [str(blender_bin), "--background", "--python", str(GENERATORS / "build_composition.py"), "--",
         "--spec", str(folder / storage.INPUT_FILE), "--pieces", str(root), "--models", str(models),
         "--out", str(out)],
        capture_output=True, text=True, timeout=300, check=False,
    )
    assert result.returncode == 0, result.stderr[-1500:]
    return out


def _mapped(out: Path) -> tuple[dict, list[str]]:
    from app.blender.verify import glb_mesh_nodes

    surfaces = json.loads((out / "report.json").read_text(encoding="utf-8"))["surfaces"]
    listed = [name for names in surfaces.values() for name in names]
    assert sorted(listed) == sorted(glb_mesh_nodes(out / "model.glb"))
    assert len(listed) == len(set(listed))
    return surfaces, listed


STAND_IN = {"id": "bench", "type": "stand-in", "name": "Bench", "width_mm": 1200, "depth_mm": 400, "height_mm": 450,
            "colour": "#7a6a58", "placement": {"wall": 2, "offset_mm": 500}}


@pytest.mark.parametrize("items", [[], [STAND_IN]], ids=["empty", "stand-in"])
def test_a_four_walled_hall_publishes_its_model_and_surface_map(blender_bin: Path, tmp_path: Path, items) -> None:
    root, models = tmp_path / "renders", tmp_path / "models"
    models.mkdir()
    parsed = parse_composition({
        "kind": "room_composition", "schema_version": 1, "units": "mm", "scope": {"room": "Hall"}, "items": items,
    }, max_items=30)
    document, _subjects = place_items(parsed, rooms={"Hall": room_geometry("Hall", ROOM)}, piece_sizes={}, scope_room="Hall")
    out = _build_document(blender_bin, root, models, "hall", document)
    assert {p.name for p in out.iterdir()} == set(storage.COMPOSITION_FILES)
    surfaces, _listed = _mapped(out)
    expected = ["wall 1", "wall 2", "wall 3", "wall 4", "floor", "ceiling"] + (["items"] if items else [])
    assert list(surfaces) == expected
    assert surfaces["floor"] == ["Floor"] and surfaces["ceiling"] == ["Ceiling"]
    if items:
        assert surfaces["items"] == ["STAND_bench"]
    extent = json.loads((out / "report.json").read_text(encoding="utf-8"))["extent_mm"]
    assert extent == {"min": [0, 0, 0.0], "max": [5000, 4000, 2600.0]}


def test_an_apartments_surfaces_are_named_by_room(blender_bin: Path, tmp_path: Path) -> None:
    from app.agent.house_file import validate_apartment

    root, models = tmp_path / "renders", tmp_path / "models"
    models.mkdir()
    rooms = [
        {"name": "Wohnen", "corners_mm": [[0, 0], [5000, 0], [5000, 4000], [0, 4000]]},
        {"name": "Küche", "corners_mm": [[5000, 0], [8000, 0], [8000, 4000], [5000, 4000]]},
    ]
    shell = validate_apartment("Wohnung", 2600, 100, rooms).input_document()
    parsed = parse_composition({
        "kind": "room_composition", "schema_version": 1, "units": "mm", "scope": {"apartment": "Wohnung"},
        "items": [{**STAND_IN, "room": "Küche"}],
    }, max_items=30)
    geometry = {
        room["name"]: room_geometry(room["name"], {"corners_mm": room["corners"], "height_mm": room["height_mm"],
                                                   "wall_thickness_mm": shell["apartment"]["wall_thickness_mm"],
                                                   "openings": room["openings"]})
        for room in shell["rooms"]
    }
    document, _subjects = place_items(parsed, rooms=geometry, piece_sizes={})
    document["resolved"]["shell"] = shell
    out = _build_document(blender_bin, root, models, "apartment-wohnung", document)
    surfaces, _listed = _mapped(out)
    assert "Wohnen: wall 1" in surfaces and "Küche: wall 1" in surfaces
    assert surfaces["Wohnen: floor"] == ["Floor_Wohnen"] and surfaces["Küche: ceiling"] == ["Ceiling_Küche"]
    assert surfaces["items"] == ["STAND_bench"]
    assert list(surfaces)[-1] == "items"
