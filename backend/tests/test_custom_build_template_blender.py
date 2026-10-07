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
