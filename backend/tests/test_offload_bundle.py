"""render-offload: the generator bundle, and the --cycles-device flag."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from app.blender.cli import CYCLES_DEVICES, parse_render_arguments
from app.render.offload.bundle import BACKEND_ROOT, DATA_FILES, bundle_files
from tests.test_generator_cli import TIER


def names() -> set[str]:
    return {path.as_posix() for path in bundle_files()}


def test_the_bundle_holds_what_the_render_generators_import() -> None:
    found = names()
    for expected in (
        "app/__init__.py", "app/blender/__init__.py", "app/blender/cli.py", "app/blender/verify.py",
        "app/blender/storage.py", "app/blender/generators/_render.py", "app/blender/generators/_scene.py",
        "app/blender/generators/render_still.py", "app/blender/generators/render_turntable.py",
        "app/blender/generators/build_room_scene.py", "app/blender/custom_build/derive.py",
        "app/render/__init__.py", "app/render/viewer.py", "app/render/viewer.html",
    ):
        assert expected in found, expected


def test_the_bundle_leaves_the_application_behind() -> None:
    for path in names():
        assert not path.startswith(("app/agent", "app/api", "app/db", "app/auth", "app/pricing")), path
    assert "app/config.py" not in names()
    assert "app/render/guard.py" not in names()


def test_every_file_exists_and_data_files_are_included() -> None:
    for relative in bundle_files():
        assert (BACKEND_ROOT / relative).is_file()
    assert all(path in bundle_files() for path in DATA_FILES)


def test_the_default_device_is_the_cpu_and_the_others_are_accepted(tmp_path: Path) -> None:
    blend = tmp_path / "m.blend"
    blend.write_bytes(b"x")
    base = ["--", "--blend", str(blend), "--out", str(tmp_path / "o"), *TIER]
    assert parse_render_arguments(base)[2].device == "CPU"
    for device in CYCLES_DEVICES:
        assert parse_render_arguments([*base, "--cycles-device", device])[2].device == device


def test_an_unknown_device_is_refused_naming_it(tmp_path: Path) -> None:
    from app.blender.cli import InputError

    blend = tmp_path / "m.blend"
    blend.write_bytes(b"x")
    with pytest.raises(InputError, match="cycles-device"):
        parse_render_arguments(
            ["--", "--blend", str(blend), "--out", str(tmp_path / "o"), *TIER, "--cycles-device", "METAL"]
        )


# --- inside the pinned Blender -----------------------------------------------------------------------


@pytest.mark.blender
@pytest.mark.parametrize("device", ["CPU", "OPTIX", "CUDA", "HIP"])
def test_the_device_is_applied_to_cycles_without_rendering(blender_bin: Path, device: str) -> None:
    result = subprocess.run(
        [str(blender_bin), "--background", "--factory-startup", "--python",
         str(Path(__file__).with_name("blender_inspect_device.py")), "--", device],
        capture_output=True, text=True, timeout=300, check=False,
    )
    assert result.returncode == 0, result.stderr[-600:]
    line = next(line for line in result.stdout.splitlines() if line.startswith("INSPECT "))
    found = json.loads(line.removeprefix("INSPECT "))
    assert found["engine"] == "CYCLES"
    assert found["device"] == ("CPU" if device == "CPU" else "GPU")
    if device != "CPU":
        assert found["compute"] == device


@pytest.mark.blender
def test_the_bundle_runs_in_blenders_python_alone(blender_bin: Path, tmp_path: Path) -> None:
    """Copy only the bundle to an empty folder and start a generator with no arguments:
    it must get as far as refusing them, which proves every import resolved."""
    root = tmp_path / "backend"
    for relative in bundle_files():
        (root / relative).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(BACKEND_ROOT / relative, root / relative)
    for script in ("render_still.py", "render_turntable.py", "build_room_scene.py"):
        result = subprocess.run(
            [str(blender_bin), "--background", "--factory-startup", "--python",
             str(root / "app/blender/generators" / script), "--"],
            capture_output=True, text=True, timeout=300, check=False, cwd=tmp_path,
        )
        assert "ModuleNotFoundError" not in result.stderr + result.stdout, script
        assert result.returncode != 0 and "arguments:" in result.stderr, (script, result.stderr[-400:])
