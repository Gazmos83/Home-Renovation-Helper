"""build_shell.py inside the pinned Blender: walls built once, openings cut, concave floors.

A build is not a render: it publishes a Workbench screenshot and needs no tier.
"""

from __future__ import annotations

import copy
import json
import subprocess
from pathlib import Path

import pytest

from tests.blender_fakes import png_size
from tests.blender_helpers import BACKEND, run_generator

pytestmark = pytest.mark.blender

FIXTURE = BACKEND / "fixtures/packages/apartment-two-room.json"
INSPECT = Path(__file__).with_name("blender_inspect_shell.py")


def build(blender_bin: Path, tmp_path: Path, document: dict, name: str = "shell"):
    spec = tmp_path / f"{name}.json"
    spec.write_text(json.dumps(document), encoding="utf-8")
    out = tmp_path / name
    result = run_generator(blender_bin, "build_shell.py", "--spec", str(spec), "--out", str(out))
    return result, out


def inspect(blender_bin: Path, blend: Path) -> dict:
    run = subprocess.run(
        [str(blender_bin), "--background", str(blend), "--python", str(INSPECT)],
        capture_output=True, text=True, timeout=300, check=False,
    )
    line = next(line for line in run.stdout.splitlines() if line.startswith("INSPECT "))
    return {obj["name"]: obj for obj in json.loads(line.removeprefix("INSPECT "))["objects"]}


def test_the_two_room_fixture_builds_with_one_shared_wall_and_its_door(blender_bin: Path, tmp_path: Path) -> None:
    document = json.loads(FIXTURE.read_text(encoding="utf-8"))
    result, out = build(blender_bin, tmp_path, document)
    assert result.returncode == 0, result.stderr[-800:]
    assert sorted(p.name for p in out.iterdir()) == ["model.blend", "model.glb", "screenshot.png", "shell.json"]
    assert png_size(out / "screenshot.png") == (800, 500)

    shell = json.loads((out / "shell.json").read_text(encoding="utf-8"))
    shared = [wall for wall in shell["walls"] if wall["shared"]]
    assert len(shell["walls"]) == 7 and len(shared) == 1
    wall = shared[0]
    assert {wall["a"][0], wall["b"][0]} == {5200.0}
    assert [(o["type"], o["offset_mm"], o["width_mm"]) for o in wall["openings"]] == [("door", 1200, 900)]

    objects = inspect(blender_bin, out / "model.blend")
    pieces = [name for name in objects if name.startswith(f"Wall_{wall['id']}_")]
    # Solid before the door, solid after it, and a lintel over it; no sill (a door).
    assert sorted(pieces) == [f"Wall_{wall['id']}_0", f"Wall_{wall['id']}_1", f"Wall_{wall['id']}_lintel_0"]
    # The shared wall is centred on x = 5200: 120 mm thick, so x in 5140..5260 (metres in Blender).
    solid = objects[f"Wall_{wall['id']}_0"]
    assert solid["min"][0] == pytest.approx(5.14, abs=1e-3) and solid["max"][0] == pytest.approx(5.26, abs=1e-3)
    # Only one wall object spans that line over the door's span: the door's gap is open.
    gap_lo, gap_hi = 1.2, 2.1
    in_gap = [
        name for name in pieces
        if "lintel" not in name and objects[name]["min"][1] < gap_hi - 1e-3 and objects[name]["max"][1] > gap_lo + 1e-3
        and objects[name]["min"][2] < 0.5
    ]
    assert in_gap == []
    assert {"Floor_Living room", "Floor_Bedroom", "Ceiling_Living room"} <= set(objects)


def test_an_l_shaped_room_has_an_l_shaped_floor(blender_bin: Path, tmp_path: Path) -> None:
    l_shape = [[0, 0], [4000, 0], [4000, 1500], [2000, 1500], [2000, 3500], [0, 3500]]
    document = copy.deepcopy(json.loads(FIXTURE.read_text(encoding="utf-8")))
    document["rooms"] = [{"name": "L room", "corners": l_shape, "openings": []}]
    result, out = build(blender_bin, tmp_path, document, "ell")
    assert result.returncode == 0, result.stderr[-800:]
    floor = inspect(blender_bin, out / "model.blend")["Floor_L room"]
    # 4 m × 1.5 m + 2 m × 2 m = 10 m²; a bounding rectangle would be 14 m².
    assert floor["top_area_m2"] == pytest.approx(10.0, rel=1e-3)
    assert floor["max"][0] == pytest.approx(4.0) and floor["max"][1] == pytest.approx(3.5)


def test_a_bad_document_exits_non_zero_naming_the_problem(blender_bin: Path, tmp_path: Path) -> None:
    document = json.loads(FIXTURE.read_text(encoding="utf-8"))
    document["rooms"][1]["corners"] = [[5000, 0], [8400, 0], [8400, 3800], [5000, 3800]]
    result, out = build(blender_bin, tmp_path, document, "bad")
    assert result.returncode != 0
    assert "validation:" in result.stderr and "overlap" in result.stderr
    assert not out.exists()


def test_an_existing_output_path_is_refused(blender_bin: Path, tmp_path: Path) -> None:
    document = json.loads(FIXTURE.read_text(encoding="utf-8"))
    (tmp_path / "shell").mkdir()
    result, _ = build(blender_bin, tmp_path, document)
    assert result.returncode != 0 and "already exists" in result.stderr
