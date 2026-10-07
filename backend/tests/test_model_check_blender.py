"""model-assets: check_model.py inside the pinned Blender imports each accepted form (run with --blender)."""

from __future__ import annotations

import io
import json
import subprocess
import zipfile
from pathlib import Path

import pytest

from tests import model_fixtures as fx

pytestmark = [pytest.mark.blender, pytest.mark.slow]

CHECK = Path(__file__).resolve().parents[1] / "app/blender/generators/check_model.py"


def _check(blender_bin: Path, model: Path, kind: str, out: Path) -> dict:
    result = subprocess.run(
        [str(blender_bin), "--background", "--factory-startup", "--python", str(CHECK), "--",
         "--model", str(model), "--kind", kind, "--out", str(out)],
        capture_output=True, text=True, timeout=180, check=False,
    )
    assert result.returncode == 0, result.stderr[-800:]
    return json.loads((out / "check.json").read_text(encoding="utf-8"))


def _unzip(content: bytes, target: Path) -> None:
    with zipfile.ZipFile(io.BytesIO(content)) as archive:
        archive.extractall(target)


@pytest.mark.parametrize("form", ["glb", "gltf", "obj"])
def test_each_form_imports_with_its_size_and_triangles(blender_bin: Path, tmp_path: Path, form: str) -> None:
    folder = tmp_path / "model"
    folder.mkdir()
    if form == "glb":
        (folder / "model.glb").write_bytes(fx.glb())
        entry = folder / "model.glb"
    elif form == "gltf":
        _unzip(fx.gltf_zip(), folder)
        entry = folder / "box.gltf"
    else:
        _unzip(fx.obj_zip(), folder)
        entry = folder / "box.obj"
    report = _check(blender_bin, entry, form, tmp_path / "out")
    assert report["triangles"] == 12
    size = report["size_mm"]
    # Width, depth and height in Blender's Z-up frame, whatever the file's own up axis.
    assert size["x"] == pytest.approx(900, abs=1)
    assert size["y"] == pytest.approx(800, abs=1)
    assert size["z"] == pytest.approx(1000, abs=1)
