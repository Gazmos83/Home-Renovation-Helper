"""The `custom-build` starter builds headless and shows a cabinet (run with --blender)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.blender import storage
from tests.blender_fakes import png_size
from tests.test_custom_build_generator import BACKEND, _build, _inspect, _normalised

pytestmark = [pytest.mark.blender, pytest.mark.slow]

STARTER = BACKEND / "fixtures/packages/templates/custom-build.json"


def test_custom_build_template_builds_and_publishes_a_screenshot(blender_bin: Path, tmp_path: Path) -> None:
    result, out = _build(blender_bin, _normalised(STARTER), tmp_path)

    assert result.returncode == 0, result.stderr[-800:]
    assert {entry.name for entry in out.iterdir()} == set(storage.BUILD_FILES)
    assert png_size(out / "screenshot.png") == (800, 500)

    emitted = json.loads((out / "spec.json").read_text(encoding="utf-8"))
    assert emitted["overall"] == {"w": 800, "h": 1800, "d": 400}
    meshes = [o for o in _inspect(blender_bin, out / "model.blend")["objects"] if o["type"] == "MESH"]
    assert len(meshes) > 5, "the cabinet shows carcass panels, a back, shelves and two doors"


def test_adjustable_shelves_and_a_wall_shelf_build_with_saved_inputs(blender_bin: Path, tmp_path: Path) -> None:
    from app.blender.custom_build.derive import derive, drilling
    from app.blender.shop_csv import CUTLIST_FIELDS, HARDWARE_FIELDS, write_csv
    from tests.drill_helpers import build, inputs, module, rules, sheet, wall_shelf

    spec = build(
        modules=[module(
            shelves=1, adjustable_shelves=2,
            fronts=[{"type": "door", "count": 1, "opening": "hinge"}],
        )],
        wall_shelves=[wall_shelf(x=700, z=1400)],
    )
    saved = inputs(
        {
            "shelf-pin": sheet("shelf_pin", {"pitch_mm": {"value": 32}, "first_hole_mm": {"value": 50},
                                              "last_hole_mm": {"value": 50}, "pins_per_shelf": 4}),
            "hinge-concealed-110": sheet("hinge", {"end_distance_mm": {"min": 80, "max": 120}}),
        },
        rules(end={"min": 100, "max": 200}),
    )

    result, out = _build(blender_bin, spec, tmp_path, saved)
    assert result.returncode == 0, result.stderr[-800:]

    parts, hardware, _assembly = derive(spec, saved)
    expected = tmp_path / "expected"
    expected.mkdir()
    write_csv(expected / "cutlist.csv", parts, CUTLIST_FIELDS)
    write_csv(expected / "hardware.csv", hardware, HARDWARE_FIELDS)
    for name in ("cutlist.csv", "hardware.csv"):
        assert (out / name).read_text(encoding="utf-8") == (expected / name).read_text(encoding="utf-8"), name

    emitted = json.loads((out / "spec.json").read_text(encoding="utf-8"))
    assert emitted["drilling"] == drilling(spec, saved)

    objects = {o["name"]: o for o in _inspect(blender_bin, out / "model.blend")["objects"]}
    assert objects["wall-shelf-1"]["parent"] == "MOD_wall-shelf-1" and objects["MOD_wall-shelf-1"]["type"] == "EMPTY"
    assert "m-adjustable-shelf" in objects and "m-adjustable-shelf#2" in objects
    assert not [name for name in objects if "bracket" in name.casefold()]
