"""restyle-variants: look and style presets load, and a bad one stops startup by name."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.restyle.presets import (
    DEFAULT_LOOKS_PATH,
    DEFAULT_STYLES_PATH,
    PresetError,
    load_presets,
)

LOOK = "    colour: \"#5a3e2b\"\n    roughness: 0.4\n"
STYLE = (
    "    wall: {colour: \"#ffffff\", roughness: 0.9}\n"
    "    ceiling: {colour: \"#ffffff\", roughness: 0.9}\n"
    "    floor: {colour: \"#aaaaaa\", roughness: 0.5}\n"
    "    world: {colour: \"#ffffff\", strength: 1.0}\n"
    "    fallback: \"#cccccc\"\n"
)


def _write(tmp_path: Path, looks: str, styles: str | None = None) -> tuple[Path, Path]:
    looks_path = tmp_path / "looks.yaml"
    styles_path = tmp_path / "styles.yaml"
    looks_path.write_text(looks, encoding="utf-8")
    styles_path.write_text(styles if styles is not None else f"styles:\n  calm:\n{STYLE}", encoding="utf-8")
    return looks_path, styles_path


def test_shipped_presets_load_and_list_ids() -> None:
    presets = load_presets(DEFAULT_LOOKS_PATH, DEFAULT_STYLES_PATH)
    assert len(presets.looks) >= 6
    assert len(presets.styles) >= 4
    assert {"walnut", "white-lacquer"} <= set(presets.looks)
    assert {"scandi", "japandi", "industrial", "warm-modern"} <= set(presets.styles)
    assert presets.summary()["looks"][0] in presets.looks


def test_bad_colour_names_the_preset_and_field(tmp_path: Path) -> None:
    paths = _write(tmp_path, "looks:\n  bad:\n    colour: walnut\n    roughness: 0.4\n")
    with pytest.raises(PresetError) as caught:
        load_presets(*paths)
    assert "bad" in str(caught.value)
    assert "colour" in str(caught.value)


def test_roughness_out_of_range_is_refused(tmp_path: Path) -> None:
    paths = _write(tmp_path, "looks:\n  rough:\n    colour: \"#112233\"\n    roughness: 1.2\n")
    with pytest.raises(PresetError, match="roughness"):
        load_presets(*paths)


def test_unknown_key_is_refused(tmp_path: Path) -> None:
    paths = _write(tmp_path, f"looks:\n  odd:\n{LOOK}    texture_path: x.png\n")
    with pytest.raises(PresetError, match="texture_path"):
        load_presets(*paths)


def test_duplicate_id_is_refused(tmp_path: Path) -> None:
    paths = _write(tmp_path, f"looks:\n  same:\n{LOOK}  same:\n{LOOK}")
    with pytest.raises(PresetError, match="same"):
        load_presets(*paths)


def test_invalid_id_is_refused(tmp_path: Path) -> None:
    paths = _write(tmp_path, f"looks:\n  Bad Id:\n{LOOK}")
    with pytest.raises(PresetError, match="Bad Id"):
        load_presets(*paths)


def test_bad_style_names_the_style(tmp_path: Path) -> None:
    paths = _write(tmp_path, f"looks:\n  ok:\n{LOOK}", "styles:\n  calm:\n    wall: {colour: red, roughness: 0.5}\n")
    with pytest.raises(PresetError, match="calm"):
        load_presets(*paths)
