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


# --- a ceiling-layer item hangs from the ceiling (composition-ceiling-layer) ---------------


def test_ceiling_layer_items_hang_with_their_top_at_the_ceiling(blender_bin: Path, tmp_path: Path) -> None:
    root, models = tmp_path / "renders", tmp_path / "models"
    (models / MODEL_ID).mkdir(parents=True)
    (models / MODEL_ID / "model.glb").write_bytes(fx.glb())
    parsed = parse_composition({
        "kind": "room_composition", "schema_version": 1, "units": "mm", "scope": {"room": "Essen"},
        "items": [
            {"id": "table", "type": "stand-in", "name": "Table", "width_mm": 1600, "depth_mm": 900,
             "height_mm": 750, "colour": "#8a6a48", "placement": {"x_mm": 2500, "y_mm": 2000, "rotation_deg": 0}},
            {"id": "pendant", "type": "model", "model_id": MODEL_ID, "name": "Pendelleuchte Calisto",
             "width_mm": 500, "depth_mm": 500, "height_mm": 1100, "layer": "ceiling",
             "placement": {"x_mm": 2500, "y_mm": 2000, "rotation_deg": 0}},
            {"id": "spot", "type": "stand-in", "name": "Spot", "width_mm": 300, "depth_mm": 300,
             "height_mm": 300, "colour": "#202020", "layer": "ceiling",
             "placement": {"x_mm": 1000, "y_mm": 1000, "rotation_deg": 30}},
        ],
    }, max_items=30)
    document, _subjects = place_items(
        parsed, rooms={"Essen": room_geometry("Essen", {**ROOM, "height_mm": 2500})}, piece_sizes={},
        scope_room="Essen",
    )
    for placed in document["resolved"]["items"]:
        if placed["id"] == "pendant":
            placed["source"] = {"kind": "glb", "entry": "model.glb"}
    folder = storage.composition_version_dir(root, "essen", 1)
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
    report = {item["id"]: item for item in json.loads((out / "report.json").read_text(encoding="utf-8"))["items"]}
    base = {item["id"]: item.get("base_mm", 0.0) for item in document["resolved"]["items"]}
    assert base == {"table": 0.0, "pendant": 1400.0, "spot": 2200.0}
    for item_id, item in report.items():
        assert item["lowest_mm"] == pytest.approx(base[item_id], abs=1), item_id
    assert report["pendant"]["final_mm"] == pytest.approx({"x": 500, "y": 500, "z": 1100}, abs=1)
    assert report["spot"]["final_mm"] == pytest.approx({"x": 300, "y": 300, "z": 300}, abs=1)
    for item_id in ("pendant", "spot"):
        assert report[item_id]["lowest_mm"] + report[item_id]["final_mm"]["z"] == pytest.approx(2500, abs=1)


def test_a_hung_piece_is_built_with_its_underside_at_its_height(scene, blender_bin: Path) -> None:
    """conversation-continuity: a piece placed with mount_height_mm hangs at that height."""
    root, models, _folder, _out, overall = scene
    tall = {**ROOM, "height_mm": overall["h"] + 1500}
    parsed = parse_composition({
        "kind": "room_composition", "schema_version": 1, "units": "mm", "scope": {"room": "Flur"},
        "items": [{"id": "cabinet", "type": "piece", "package_id": "cabinet", "version": 1,
                   "placement": {"wall": 1, "offset_mm": 500, "mount_height_mm": 1000}}],
    }, max_items=30)
    document, _subjects = place_items(
        parsed, rooms={"Flur": room_geometry("Flur", tall)},
        piece_sizes={"cabinet": (overall["w"], overall["d"], overall["h"])}, scope_room="Flur",
    )
    out = _build_document(blender_bin, root, models, "flur", document)
    report = {item["id"]: item for item in json.loads((out / "report.json").read_text(encoding="utf-8"))["items"]}
    assert report["cabinet"]["lowest_mm"] == pytest.approx(1000, abs=1)
    assert report["cabinet"]["final_mm"]["z"] == pytest.approx(overall["h"], abs=1)


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


# --- hidden items and per-item meshes (hidden-room-items) ------------------------------------


def _hall(items: list[dict]) -> dict:
    parsed = parse_composition({
        "kind": "room_composition", "schema_version": 1, "units": "mm", "scope": {"room": "Hall"}, "items": items,
    }, max_items=30)
    document, _subjects = place_items(parsed, rooms={"Hall": room_geometry("Hall", ROOM)}, piece_sizes={}, scope_room="Hall")
    return document


TABLE = {"id": "table", "type": "stand-in", "name": "Table", "width_mm": 1600, "depth_mm": 900, "height_mm": 750,
         "colour": "#8a6a48", "placement": {"x_mm": 2500, "y_mm": 1500, "rotation_deg": 0}}


def test_a_hidden_sofa_is_left_out_of_the_build(blender_bin: Path, tmp_path: Path) -> None:
    from app.blender.verify import glb_mesh_nodes

    (tmp_path / "models").mkdir()
    sofa = {"id": "sofa", "type": "stand-in", "name": "Sofa", "width_mm": 2200, "depth_mm": 950, "height_mm": 800,
            "colour": "#7a6a58", "hidden": True, "placement": {"x_mm": 2500, "y_mm": 1500, "rotation_deg": 0}}
    out = _build_document(blender_bin, tmp_path / "renders", tmp_path / "models", "hall", _hall([TABLE, sofa]))
    report = {item["id"]: item for item in json.loads((out / "report.json").read_text(encoding="utf-8"))["items"]}
    assert report["sofa"] == {"id": "sofa", "type": "stand-in", "hidden": True}
    assert report["table"]["name"] == "Table" and report["table"]["meshes"] == ["STAND_table"]
    assert "STAND_sofa" not in glb_mesh_nodes(out / "model.glb")


def test_only_hidden_items_build_the_room_alone(blender_bin: Path, tmp_path: Path) -> None:
    (tmp_path / "models").mkdir()
    out = _build_document(blender_bin, tmp_path / "renders", tmp_path / "models", "hall", _hall([{**TABLE, "hidden": True}]))
    report = json.loads((out / "report.json").read_text(encoding="utf-8"))
    assert report["items"] == [{"id": "table", "type": "stand-in", "hidden": True}]
    assert "items" not in report["surfaces"]


def test_each_items_meshes_are_listed_under_items_once(scene) -> None:
    _root, _models, _folder, out, _overall = scene
    report = json.loads((out / "report.json").read_text(encoding="utf-8"))
    by_id = {item["id"]: item for item in report["items"]}
    assert by_id["cabinet"]["name"] == "cabinet v1" and by_id["armchair"]["name"] == "Armchair"
    owned = [name for item in report["items"] for name in item["meshes"]]
    assert all(item["meshes"] for item in report["items"])
    assert len(owned) == len(set(owned))
    assert set(owned) == set(report["surfaces"]["items"])


# --- the floor finish (room-floor-finish) -----------------------------------------------------

L_ROOM = {
    "corners_mm": [[0, 0], [5000, 0], [5000, 2000], [2500, 2000], [2500, 4000], [0, 4000]],
    "height_mm": 2500, "wall_thickness_mm": 100, "openings": [],
}
TILES = {"tile_width_mm": 600, "tile_length_mm": 600, "tile_colour": "#e8e4dc", "grout_colour": "#9a958c",
         "grout_width_mm": 3}


def _floored(finish: dict | None) -> dict:
    document = {"kind": "room_composition", "schema_version": 1, "units": "mm", "scope": {"room": "Wohnen"}, "items": []}
    if finish is not None:
        document["floor"] = finish
    parsed = parse_composition(document, max_items=30)
    stored, _subjects = place_items(parsed, rooms={"Wohnen": room_geometry("Wohnen", L_ROOM)}, piece_sizes={}, scope_room="Wohnen")
    return stored


def _floors(blender_bin: Path, blend: Path) -> dict:
    result = subprocess.run(
        [str(blender_bin), "--background", str(blend), "--python", str(BACKEND / "tests/blender_inspect_floor.py")],
        capture_output=True, text=True, timeout=300, check=False,
    )
    line = next(entry for entry in result.stdout.splitlines() if entry.startswith("INSPECT "))
    return json.loads(line[len("INSPECT "):])


def _glb_material_colour(glb: Path, node_name: str) -> list[float]:
    import struct

    data = glb.read_bytes()
    length, _kind = struct.unpack_from("<II", data, 12)
    document = json.loads(data[20:20 + length])
    node = next(n for n in document["nodes"] if n.get("name") == node_name)
    primitive = document["meshes"][node["mesh"]]["primitives"][0]
    material = document["materials"][primitive["material"]]
    return material["pbrMetallicRoughness"].get("baseColorFactor", [1, 1, 1, 1])


def test_tiles_cover_an_l_shaped_floor_and_the_glb_shows_their_colour(blender_bin: Path, tmp_path: Path) -> None:
    (tmp_path / "models").mkdir()
    out = _build_document(blender_bin, tmp_path / "renders", tmp_path / "models", "wohnen", _floored(TILES))
    report = json.loads((out / "report.json").read_text(encoding="utf-8"))
    assert report["floor"] == {**TILES, "grout_width_mm": 3.0, "pattern": "grid"}
    floor = _floors(blender_bin, out / "model.blend")["Floor"]
    # Every polygon of the floor, inner corner included, uses the tile material.
    assert floor["materials"] == ["Floor_Tiles"]
    assert floor["brick"] == pytest.approx({"brick_width": 0.603, "row_height": 0.603, "mortar_size": 0.003, "offset": 0.0})
    # The 3D view shows the plain tile colour (#e8e4dc in linear light).
    colour = _glb_material_colour(out / "model.glb", "Floor")
    assert colour[:3] == pytest.approx([0.807, 0.776, 0.716], abs=0.01)


def test_a_staggered_plank_floor_offsets_every_other_row(blender_bin: Path, tmp_path: Path) -> None:
    (tmp_path / "models").mkdir()
    planks = {**TILES, "tile_width_mm": 200, "tile_length_mm": 1200, "grout_width_mm": 0, "pattern": "staggered"}
    out = _build_document(blender_bin, tmp_path / "renders", tmp_path / "models", "wohnen", _floored(planks))
    brick = _floors(blender_bin, out / "model.blend")["Floor"]["brick"]
    assert brick == pytest.approx({"brick_width": 0.2, "row_height": 1.2, "mortar_size": 0.0, "offset": 0.5})


def test_without_a_finish_the_floor_keeps_its_default_material(blender_bin: Path, tmp_path: Path) -> None:
    (tmp_path / "models").mkdir()
    out = _build_document(blender_bin, tmp_path / "renders", tmp_path / "models", "wohnen", _floored(None))
    report = json.loads((out / "report.json").read_text(encoding="utf-8"))
    assert "floor" not in report
    floor = _floors(blender_bin, out / "model.blend")["Floor"]
    assert floor["materials"] == ["Floor"] and floor["brick"] is None


# --- lamp lights (room-lamp-lights) -----------------------------------------------------------


def _lights(blender_bin: Path, blend: Path) -> dict:
    result = subprocess.run(
        [str(blender_bin), "--background", str(blend), "--python", str(BACKEND / "tests/blender_inspect_lights.py")],
        capture_output=True, text=True, timeout=300, check=False,
    )
    line = next(entry for entry in result.stdout.splitlines() if entry.startswith("INSPECT "))
    return json.loads(line[len("INSPECT "):])


def _essen(items: list[dict]) -> dict:
    parsed = parse_composition({
        "kind": "room_composition", "schema_version": 1, "units": "mm", "scope": {"room": "Essen"}, "items": items,
    }, max_items=30)
    document, _subjects = place_items(
        parsed, rooms={"Essen": room_geometry("Essen", {**ROOM, "height_mm": 2500})}, piece_sizes={}, scope_room="Essen",
    )
    return document


def test_lamp_lights_are_built_at_their_heights_and_dim_the_rig(blender_bin: Path, tmp_path: Path) -> None:
    (tmp_path / "models").mkdir()
    pendant = {"id": "pendant", "type": "stand-in", "name": "Pendant", "width_mm": 500, "depth_mm": 500,
               "height_mm": 1100, "colour": "#d8c8a8", "layer": "ceiling",
               "light": {"type": "point", "lumens": 800, "kelvin": 2700},
               "placement": {"x_mm": 2500, "y_mm": 2000, "rotation_deg": 0}}
    lamp = {"id": "floor-lamp", "type": "stand-in", "name": "Floor lamp", "width_mm": 400, "depth_mm": 400,
            "height_mm": 1600, "colour": "#202020", "light": {"type": "spot", "lumens": 600, "kelvin": 3000},
            "placement": {"x_mm": 600, "y_mm": 600, "rotation_deg": 0}}
    lit = _build_document(blender_bin, tmp_path / "lit", tmp_path / "models", "essen", _essen([TABLE, pendant, lamp]))
    plain = _build_document(blender_bin, tmp_path / "plain", tmp_path / "models", "essen", _essen([TABLE]))

    report = json.loads((lit / "report.json").read_text(encoding="utf-8"))
    by_id = {item["id"]: item for item in report["items"]}
    assert by_id["pendant"]["light"] == {"type": "point", "lumens": 800, "kelvin": 2700, "watts": 40.0,
                                         "at_mm": [2500, 2000, 1450]}
    assert by_id["floor-lamp"]["light"]["at_mm"][2] == 1550 and "light" not in by_id["table"]
    assert report["rig_factors"] == {"Essen": 0.5}
    assert json.loads((plain / "report.json").read_text(encoding="utf-8"))["rig_factors"] == {"Essen": 1.0}

    seen = _lights(blender_bin, lit / "model.blend")
    assert seen["lights"]["LGT_Lamp_pendant"]["type"] == "POINT"
    assert seen["lights"]["LGT_Lamp_pendant"]["energy"] == pytest.approx(40.0)
    assert seen["lights"]["LGT_Lamp_pendant"]["z_mm"] == pytest.approx(1450, abs=0.5)
    assert seen["lights"]["LGT_Lamp_floor-lamp"]["type"] == "SPOT"
    assert seen["lights"]["LGT_Lamp_floor-lamp"]["z_mm"] == pytest.approx(1550, abs=0.5)
    assert seen["shadows"] == {"STAND_pendant": False, "STAND_floor-lamp": False, "STAND_table": True}
    rig = _lights(blender_bin, plain / "model.blend")["lights"]
    for name in ("LGT_Ceiling", "LGT_Key", "LGT_Fill"):
        assert seen["lights"][name]["energy"] == pytest.approx(rig[name]["energy"] * 0.5), name


# --- LED strips (room-led-strips) -------------------------------------------------------------


def test_led_strips_build_a_glowing_bar_and_an_area_light_facing_their_way(blender_bin: Path, tmp_path: Path) -> None:
    (tmp_path / "models").mkdir()
    down = {"id": "under-cabinets", "type": "led-strip", "name": "Under-cabinet", "length_mm": 2400,
            "lumens_per_m": 500, "kelvin": 3000, "mount_height_mm": 1450, "placement": {"wall": 2, "offset_mm": 400}}
    up = {"id": "cove", "type": "led-strip", "name": "Cove", "length_mm": 1000, "lumens_per_m": 300,
          "kelvin": 2700, "mount_height_mm": 2200, "facing": "up", "placement": {"wall": 1, "offset_mm": 500}}
    out = _build_document(blender_bin, tmp_path / "renders", tmp_path / "models", "essen", _essen([down, up]))
    report = json.loads((out / "report.json").read_text(encoding="utf-8"))
    by_id = {item["id"]: item for item in report["items"]}
    assert by_id["under-cabinets"]["strip"] == {
        "length_mm": 2400, "lumens_per_m": 500, "kelvin": 3000, "watts": 60.0,
        "wall": 2, "offset_mm": 400, "mount_height_mm": 1450, "facing": "down",
    }
    assert set(report["surfaces"]["items"]) == {"STRIP_under-cabinets", "STRIP_cove"}
    assert report["rig_factors"] == {"Essen": 0.5}
    result = subprocess.run(
        [str(blender_bin), "--background", str(out / "model.blend"), "--python", str(BACKEND / "tests/blender_inspect_strips.py")],
        capture_output=True, text=True, timeout=300, check=False,
    )
    seen = json.loads(next(line for line in result.stdout.splitlines() if line.startswith("INSPECT "))[len("INSPECT "):])
    bar = seen["STRIP_under-cabinets"]
    assert bar["low_mm"] == pytest.approx(1450, abs=0.5) and bar["shadow"] is False
    assert bar["length_mm"] == pytest.approx((2400**2 + 15**2 + 10**2) ** 0.5, abs=1)
    light = seen["LGT_Strip_under-cabinets"]
    assert light["type"] == "AREA" and light["shape"] == "RECTANGLE"
    assert light["energy"] == pytest.approx(60.0) and light["size_mm"] == pytest.approx(2400, abs=0.5)
    assert light["shine"] == pytest.approx([0, 0, -1], abs=1e-4)
    assert seen["LGT_Strip_cove"]["shine"] == pytest.approx([0, 0, 1], abs=1e-4)
