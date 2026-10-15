"""build_room_scene.py inside the pinned Blender. Every render is a `draft`
(12 frames, 800 × 800, Eevee)."""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from tests.blender_fakes import png_size
from tests.blender_helpers import BACKEND, build_template, run_generator, tier_args

pytestmark = pytest.mark.blender

RECTANGLE = BACKEND / "fixtures/packages/room-scene-rectangle.json"


@pytest.fixture(scope="module")
def package(blender_bin: Path, tmp_path_factory: pytest.TempPathFactory) -> Path:
    return build_template(blender_bin, tmp_path_factory.mktemp("piece"))


def _scene_file(tmp_path: Path, kind: str, **output: object) -> Path:
    document = json.loads(RECTANGLE.read_text(encoding="utf-8"))
    document["output"] = {"kind": kind, **output}
    path = tmp_path / "scene.json"
    path.write_text(json.dumps(document), encoding="utf-8")
    return path


def _room(blender_bin: Path, package: Path, tmp_path: Path, scene: Path, **kwargs):
    out = tmp_path / "room"
    result = run_generator(
        blender_bin, "build_room_scene.py", "--scene", str(scene), "--package", str(package),
        "--out", str(out), *tier_args(), **kwargs,
    )
    return result, out


def test_a_draft_room_still_is_800_square(blender_bin: Path, package: Path, tmp_path: Path) -> None:
    result, out = _room(blender_bin, package, tmp_path, _scene_file(tmp_path, "still"))
    assert result.returncode == 0, result.stderr[-800:]
    assert {entry.name for entry in out.iterdir()} == {"still.png", "scene.json"}
    assert png_size(out / "still.png") == (800, 800)
    scene = json.loads((out / "scene.json").read_text(encoding="utf-8"))
    assert scene["output"]["resolution"] == 800 and scene["output"]["engine"] == "BLENDER_EEVEE"
    assert scene["input"]["output"] == {"kind": "still"}


def test_a_draft_room_turntable_is_twelve_frames_with_walls_hidden_per_frame(
    blender_bin: Path, package: Path, tmp_path: Path
) -> None:
    result, out = _room(blender_bin, package, tmp_path, _scene_file(tmp_path, "turntable"))
    assert result.returncode == 0, result.stderr[-800:]
    assert sorted(entry.name for entry in (out / "frames").iterdir()) == [
        f"frame_{i:03d}.png" for i in range(12)
    ]
    assert all(png_size(frame) == (800, 800) for frame in (out / "frames").iterdir())
    assert "const frameCount = 12;" in (out / "viewer.html").read_text(encoding="utf-8")
    scene = json.loads((out / "scene.json").read_text(encoding="utf-8"))
    assert scene["output"]["frame_count"] == 12 and scene["output"]["tier_frames"] == 12
    assert any(frame["hidden_walls"] for frame in scene["output"]["frames"])
    assert "resolved" in scene and scene["input"]["placement"]["wall"] == 0


@pytest.mark.parametrize("field", ["frames", "resolution"])
def test_a_tier_owned_output_field_exits_non_zero(
    blender_bin: Path, package: Path, tmp_path: Path, field: str
) -> None:
    scene = _scene_file(tmp_path, "turntable", **{field: 36 if field == "frames" else "draft"})
    result, out = _room(blender_bin, package, tmp_path, scene)
    assert result.returncode != 0 and field in result.stderr
    assert not out.exists()


def test_a_malformed_scene_document_exits_non_zero(
    blender_bin: Path, package: Path, tmp_path: Path
) -> None:
    document = copy.deepcopy(json.loads(RECTANGLE.read_text(encoding="utf-8")))
    document["placement"]["offset_mm"] = 99_000
    scene = tmp_path / "bad.json"
    scene.write_text(json.dumps(document), encoding="utf-8")
    result, out = _room(blender_bin, package, tmp_path, scene)
    assert result.returncode != 0 and "validation:" in result.stderr
    assert not out.exists()


def test_a_missing_package_file_exits_non_zero(blender_bin: Path, package: Path, tmp_path: Path) -> None:
    empty = tmp_path / "pkg"
    empty.mkdir()
    result, out = _room(blender_bin, empty, tmp_path, _scene_file(tmp_path, "still"))
    assert result.returncode != 0 and "missing model.glb" in result.stderr
    assert not out.exists()


def test_a_forced_render_failure_leaves_no_staging_directory(
    blender_bin: Path, package: Path, tmp_path: Path
) -> None:
    result, out = _room(
        blender_bin, package, tmp_path, _scene_file(tmp_path, "turntable"),
        env={"ROOM_SCENE_TEST_FAIL_PHASE": "render"},
    )
    assert result.returncode != 0 and "injected test render failure" in result.stderr
    assert not out.exists()
    assert [entry for entry in tmp_path.iterdir() if ".tmp-" in entry.name] == []


L_SHAPE = [[0, 0], [4000, 0], [4000, 1500], [2000, 1500], [2000, 3500], [0, 3500]]


def test_a_draft_still_of_an_l_shaped_room_renders_with_the_camera_inside_it(
    blender_bin: Path, package: Path, tmp_path: Path
) -> None:
    from app.blender.room_contract import _point_in_polygon

    document = json.loads(RECTANGLE.read_text(encoding="utf-8"))
    document["room"]["corners"] = L_SHAPE
    document["openings"] = []
    document["furnishings"] = []
    document["placement"] = {"wall": 0, "offset_mm": 500}
    document["output"] = {"kind": "still"}
    scene = tmp_path / "l-room.json"
    scene.write_text(json.dumps(document), encoding="utf-8")

    result, out = _room(blender_bin, package, tmp_path, scene)

    assert result.returncode == 0, result.stderr[-800:]
    assert png_size(out / "still.png") == (800, 800)
    produced = json.loads((out / "scene.json").read_text(encoding="utf-8"))
    camera = produced["output"]["camera"]["location_mm"]
    assert _point_in_polygon((camera[0], camera[1]), [tuple(map(float, c)) for c in L_SHAPE])
    assert len(produced["input"]["room"]["corners"]) == 6
