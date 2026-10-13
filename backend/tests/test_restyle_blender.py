"""restyle-variants: render_restyle.py inside the pinned Blender (run with --blender).

A piece restyle recolours the named material and leaves `model.blend` byte-identical; a
room restyle recolours walls, floor, ceiling and the stand-in, and leaves the placed piece
and the library model as built.
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
from pathlib import Path

import pytest

from app.restyle.presets import DEFAULT_LOOKS_PATH, DEFAULT_STYLES_PATH, load_presets
from app.restyle.request import piece_variants, room_variants
from tests.blender_fakes import png_size
from tests.blender_helpers import tier_args
from tests.test_composition_blender import scene  # noqa: F401 - the module fixture

pytestmark = [pytest.mark.blender, pytest.mark.slow]

BACKEND = Path(__file__).resolve().parents[1]
GENERATORS = BACKEND / "app/blender/generators"
PRESETS = load_presets(DEFAULT_LOOKS_PATH, DEFAULT_STYLES_PATH)
# The piece in the shared fixture is built from this stored spec; slots are read from it, as the service reads `input.json`.
STARTER = json.loads((BACKEND / "fixtures/packages/templates/custom-build.json").read_text(encoding="utf-8"))


def _restyle(blender_bin: Path, payload: dict, out: Path, *inputs: str) -> subprocess.CompletedProcess:
    payload_path = out.parent / f"{out.name}.json"
    payload_path.write_text(json.dumps(payload), encoding="utf-8")
    return subprocess.run(
        [str(blender_bin), "--background", "--python", str(GENERATORS / "render_restyle.py"), "--",
         "--restyle", str(payload_path), "--out", str(out), *inputs, *tier_args()],
        capture_output=True, text=True, timeout=600, check=False,
    )


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_a_piece_restyle_renders_a_still_and_leaves_the_built_model_alone(
    scene, blender_bin: Path, tmp_path: Path  # noqa: F811
) -> None:
    root, _models, _folder, _out, _overall = scene
    piece = root / "cabinet" / "v1"
    slot = next(iter(STARTER["materials"]))
    before = _digest(piece / "model.blend")
    [plan] = piece_variants(STARTER, [{slot: "sage-green"}], PRESETS)
    result = _restyle(blender_bin, plan.payload, tmp_path / "walnut", "--blend", str(piece / "model.blend"))
    assert result.returncode == 0, result.stderr[-1500:]
    assert png_size(tmp_path / "walnut" / "still.png") == (600, 600)
    record = json.loads((tmp_path / "walnut" / "scene.json").read_text(encoding="utf-8"))
    assert record["source"] == "restyle" and record["materials_changed"]
    assert _digest(piece / "model.blend") == before


def test_a_look_for_a_material_the_model_lacks_is_refused_by_name(
    scene, blender_bin: Path, tmp_path: Path  # noqa: F811
) -> None:
    root, *_ = scene
    payload = {"mode": "piece", "materials": {"99 mm unobtainium": {
        "colour": "#112233", "roughness": 0.4, "metallic": 0.0, "grain": False}}}
    result = _restyle(blender_bin, payload, tmp_path / "x", "--blend", str(root / "cabinet" / "v1" / "model.blend"))
    assert result.returncode != 0 and "unobtainium" in result.stderr
    assert not (tmp_path / "x").exists()


def test_a_grain_look_renders(scene, blender_bin: Path, tmp_path: Path) -> None:  # noqa: F811
    root, *_ = scene
    [plan] = piece_variants(STARTER, [{next(iter(STARTER["materials"])): "walnut"}], PRESETS)
    assert plan.payload["materials"][next(iter(plan.payload["materials"]))]["grain"] is True
    result = _restyle(blender_bin, plan.payload, tmp_path / "grain", "--blend", str(root / "cabinet" / "v1" / "model.blend"))
    assert result.returncode == 0, result.stderr[-1500:]


def test_a_room_restyle_renders_a_still_from_the_stored_document(
    scene, blender_bin: Path, tmp_path: Path  # noqa: F811
) -> None:
    root, models, folder, _out, _overall = scene
    [plan] = room_variants(["japandi"], PRESETS)
    result = _restyle(
        blender_bin, plan.payload, tmp_path / "room",
        "--spec", str(folder / "input.json"), "--pieces", str(root), "--models", str(models),
    )
    assert result.returncode == 0, result.stderr[-1500:]
    assert png_size(tmp_path / "room" / "still.png") == (600, 600)


def test_a_room_style_changes_the_shell_and_stand_in_but_not_the_piece_or_the_model(
    scene, blender_bin: Path  # noqa: F811
) -> None:
    root, models, folder, _out, _overall = scene
    [plan] = room_variants(["industrial"], PRESETS)
    result = subprocess.run(
        [str(blender_bin), "--background", "--python", str(BACKEND / "tests/blender_inspect_restyle.py")],
        capture_output=True, text=True, timeout=300, check=False,
        env={**os.environ, "RESTYLE_SPEC": str(folder / "input.json"), "RESTYLE_PIECES": str(root),
             "RESTYLE_MODELS": str(models), "RESTYLE_STYLE": json.dumps(plan.payload)},
    )
    line = next(entry for entry in result.stdout.splitlines() if entry.startswith("INSPECT "))
    data = json.loads(line[len("INSPECT "):])
    before, after = data["before"], data["after"]
    for name in ("Floor", "Ceiling", "STAND_sofa"):
        assert before[name] != after[name], name
    assert any(before[n] != after[n] for n in before if n.startswith("Wall_"))
    untouched = [n for n in data["items"] if n != "STAND_sofa" and n in before]
    assert untouched, "the piece and the library model are placed items"
    for name in untouched:
        assert before[name] == after[name], name
