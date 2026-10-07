"""render_still.py and render_turntable.py inside the pinned Blender.

Every render here is at the `draft` tier (12 frames, 600 × 600, Eevee).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from tests.blender_fakes import png_size
from tests.blender_helpers import build_template, run_generator, tier_args

pytestmark = pytest.mark.blender



@pytest.fixture(scope="module")
def built(blender_bin: Path, tmp_path_factory: pytest.TempPathFactory) -> Path:
    return build_template(blender_bin, tmp_path_factory.mktemp("piece"))


def test_a_draft_still_is_600_square_on_eevee(blender_bin: Path, built: Path, tmp_path: Path) -> None:
    out = tmp_path / "still"
    result = run_generator(
        blender_bin, "render_still.py", "--blend", str(built / "model.blend"),
        "--out", str(out), *tier_args(),
    )
    assert result.returncode == 0, result.stderr[-800:]
    assert png_size(out / "still.png") == (600, 600)
    scene = json.loads((out / "scene.json").read_text(encoding="utf-8"))
    assert scene["engine"] == "BLENDER_EEVEE" and scene["resolution"] == 600


def test_a_draft_turntable_is_exactly_twelve_frames_with_a_viewer(
    blender_bin: Path, built: Path, tmp_path: Path
) -> None:
    out = tmp_path / "turn"
    result = run_generator(
        blender_bin, "render_turntable.py", "--blend", str(built / "model.blend"),
        "--out", str(out), *tier_args(),
    )
    assert result.returncode == 0, result.stderr[-800:]
    frames = sorted(entry.name for entry in (out / "frames").iterdir())
    assert frames == [f"frame_{i:03d}.png" for i in range(12)]
    assert all(png_size(out / "frames" / name) == (600, 600) for name in frames)
    assert "const frameCount = 12;" in (out / "viewer.html").read_text(encoding="utf-8")
    scene = json.loads((out / "scene.json").read_text(encoding="utf-8"))
    assert scene["frames"] == 12 and len(scene["cameras"]) == 12
    locations = {tuple(c["location_mm"]) for c in scene["cameras"]}
    assert len(locations) == 12, "each frame has its own camera position"


def test_a_pre_existing_output_is_refused_without_modification(
    blender_bin: Path, built: Path, tmp_path: Path
) -> None:
    out = tmp_path / "taken"
    out.mkdir()
    (out / "keep.txt").write_text("mine")
    result = run_generator(
        blender_bin, "render_turntable.py", "--blend", str(built / "model.blend"),
        "--out", str(out), *tier_args(),
    )
    assert result.returncode != 0 and "already exists" in result.stderr
    assert [entry.name for entry in out.iterdir()] == ["keep.txt"]


def test_a_missing_blend_exits_non_zero_and_leaves_nothing(blender_bin: Path, tmp_path: Path) -> None:
    out = tmp_path / "none"
    result = run_generator(
        blender_bin, "render_still.py", "--blend", str(tmp_path / "no.blend"),
        "--out", str(out), *tier_args(),
    )
    assert result.returncode != 0
    assert not out.exists() and not list(tmp_path.glob(".*tmp*"))


def test_a_piece_turntable_shows_its_dimension_lines_only_with_the_flag(
    blender_bin: Path, built: Path, tmp_path: Path
) -> None:
    runs = {}
    for label, extra in (("plain", []), ("dimensions", ["--dimensions"])):
        out = tmp_path / label
        result = run_generator(
            blender_bin, "render_turntable.py", "--blend", str(built / "model.blend"),
            "--out", str(out), *tier_args(), *extra,
        )
        assert result.returncode == 0, result.stderr[-800:]
        runs[label] = out
    plain = json.loads((runs["plain"] / "scene.json").read_text(encoding="utf-8"))
    shown = json.loads((runs["dimensions"] / "scene.json").read_text(encoding="utf-8"))
    assert (plain["dimensions"], shown["dimensions"]) == (False, True)
    # The orbit is the piece's own: the lines do not move the cameras.
    assert plain["cameras"] == shown["cameras"] and plain["target_mm"] == shown["target_mm"]
    for index in (0, 6):
        name = f"frames/frame_{index:03d}.png"
        assert (runs["plain"] / name).read_bytes() != (runs["dimensions"] / name).read_bytes()
