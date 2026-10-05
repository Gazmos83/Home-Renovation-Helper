"""The generators' argument contracts, without Blender."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.blender.cli import (
    InputError,
    load_custom_build,
    parse_generator_arguments,
    parse_render_arguments,
    parse_room_generator_arguments,
)

TEMPLATES = Path(__file__).resolve().parents[1] / "fixtures/packages/templates"
TIER = ["--tier-frames", "12", "--tier-resolution", "600", "--tier-engine", "BLENDER_EEVEE"]


def _file(tmp_path: Path, name: str, text: str = "{}") -> Path:
    path = tmp_path / name
    path.write_text(text)
    return path


def _package(tmp_path: Path) -> Path:
    folder = tmp_path / "pkg"
    folder.mkdir()
    (folder / "model.glb").write_bytes(b"glTF")
    (folder / "spec.json").write_text("{}")
    return folder


def test_a_build_resolves_spec_and_output(tmp_path: Path) -> None:
    spec = _file(tmp_path, "s.json")
    out = tmp_path / "out"
    assert parse_generator_arguments(["blender", "--", "--spec", str(spec), "--out", str(out)]) == (
        spec.resolve(),
        out.resolve(),
    )


def test_the_separator_is_required(tmp_path: Path) -> None:
    with pytest.raises(InputError, match="separator"):
        parse_generator_arguments(["--spec", "x", "--out", "y"])


def test_a_missing_spec_is_refused(tmp_path: Path) -> None:
    with pytest.raises(InputError, match="spec is not a readable file"):
        parse_generator_arguments(["--", "--spec", str(tmp_path / "no"), "--out", str(tmp_path / "o")])


def test_an_existing_output_is_refused(tmp_path: Path) -> None:
    spec = _file(tmp_path, "s.json")
    out = tmp_path / "out"
    out.mkdir()
    with pytest.raises(InputError, match="already exists"):
        parse_generator_arguments(["--", "--spec", str(spec), "--out", str(out)])


def test_a_missing_output_parent_is_refused(tmp_path: Path) -> None:
    spec = _file(tmp_path, "s.json")
    with pytest.raises(InputError, match="parent does not exist"):
        parse_generator_arguments(["--", "--spec", str(spec), "--out", str(tmp_path / "x" / "out")])


def test_a_missing_argument_is_an_input_error(tmp_path: Path) -> None:
    with pytest.raises(InputError, match="arguments"):
        parse_generator_arguments(["--", "--spec", "s"])


def test_a_render_resolves_blend_output_and_tier(tmp_path: Path) -> None:
    blend = _file(tmp_path, "model.blend")
    out = tmp_path / "r"
    got_blend, got_out, tier = parse_render_arguments(
        ["blender", "--", "--blend", str(blend), "--out", str(out), *TIER]
    )
    assert (got_blend, got_out) == (blend.resolve(), out.resolve())
    assert (tier.frames, tier.resolution, tier.engine) == (12, 600, "BLENDER_EEVEE")


@pytest.mark.parametrize(
    ("override", "message"),
    [
        (["--tier-frames", "0"], "tier-frames"),
        (["--tier-resolution", "-1"], "tier-resolution"),
        (["--tier-engine", "LUXCORE"], "tier-engine"),
    ],
)
def test_a_bad_tier_value_is_refused(tmp_path: Path, override: list[str], message: str) -> None:
    blend = _file(tmp_path, "model.blend")
    tier = dict(zip(TIER[::2], TIER[1::2], strict=True))
    tier.update(dict(zip(override[::2], override[1::2], strict=True)))
    flat = [item for pair in tier.items() for item in pair]
    with pytest.raises(InputError, match=message):
        parse_render_arguments(["--", "--blend", str(blend), "--out", str(tmp_path / "r"), *flat])


def test_a_render_without_a_tier_is_refused(tmp_path: Path) -> None:
    blend = _file(tmp_path, "model.blend")
    with pytest.raises(InputError, match="tier"):
        parse_render_arguments(["--", "--blend", str(blend), "--out", str(tmp_path / "r")])


def test_a_room_resolves_scene_package_output_and_tier(tmp_path: Path) -> None:
    scene = _file(tmp_path, "scene.json")
    package = _package(tmp_path)
    out = tmp_path / "room"
    got = parse_room_generator_arguments(
        ["--", "--scene", str(scene), "--package", str(package), "--out", str(out), *TIER]
    )
    assert got[:3] == (scene.resolve(), package.resolve(), out.resolve())
    assert got[3].frames == 12


def test_a_missing_package_directory_is_refused(tmp_path: Path) -> None:
    scene = _file(tmp_path, "scene.json")
    with pytest.raises(InputError, match="package directory does not exist"):
        parse_room_generator_arguments(
            ["--", "--scene", str(scene), "--package", str(tmp_path / "no"), "--out", str(tmp_path / "o"), *TIER]
        )


@pytest.mark.parametrize("missing", ["model.glb", "spec.json"])
def test_a_package_directory_missing_a_file_is_refused(tmp_path: Path, missing: str) -> None:
    scene = _file(tmp_path, "scene.json")
    package = _package(tmp_path)
    (package / missing).unlink()
    with pytest.raises(InputError, match=f"missing {missing}"):
        parse_room_generator_arguments(
            ["--", "--scene", str(scene), "--package", str(package), "--out", str(tmp_path / "o"), *TIER]
        )


def test_the_loader_accepts_a_normalised_build(tmp_path: Path) -> None:
    from app.blender.schemas import CustomBuildSpec

    document = json.loads((TEMPLATES / "fold-down-desk.json").read_text())
    normalised = CustomBuildSpec.model_validate(document).model_dump(mode="json")
    path = _file(tmp_path, "b.json", json.dumps(normalised))
    assert load_custom_build(path)["kind"] == "custom_build"


@pytest.mark.parametrize(
    ("change", "message"),
    [({"kind": "other"}, "kind"), ({"schema_version": 2}, "schema_version"), ({"units": "cm"}, "units")],
)
def test_the_loader_refuses_another_document(tmp_path: Path, change: dict, message: str) -> None:
    document = {"kind": "custom_build", "schema_version": 1, "units": "mm", **change}
    with pytest.raises(InputError, match=message):
        load_custom_build(_file(tmp_path, "b.json", json.dumps(document)))


def test_the_loader_names_malformed_json(tmp_path: Path) -> None:
    with pytest.raises(InputError, match="malformed JSON"):
        load_custom_build(_file(tmp_path, "b.json", "{not json"))
