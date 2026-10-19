"""room-lamp-lights: the lighting configuration and its conversions."""

from __future__ import annotations

from pathlib import Path

import pytest

from app import main
from app.blender.lighting import (
    DEFAULT_LIGHTING,
    Lighting,
    kelvin_to_rgb,
    load_lighting,
    lumens_to_watts,
)
from app.config import ConfigurationError, Settings


def _write(tmp_path: Path, text: str) -> Path:
    path = tmp_path / "lighting.yaml"
    path.write_text(text, encoding="utf-8")
    return path


def test_the_shipped_file_loads_the_defaults() -> None:
    assert load_lighting() == Lighting(watts_per_lumen=0.05, rig_factor_with_lamps=0.5, max_lights=16)
    assert load_lighting() == DEFAULT_LIGHTING


def test_800_lumens_are_40_watts() -> None:
    assert lumens_to_watts(800, DEFAULT_LIGHTING) == 40.0


def test_warm_light_is_redder_than_daylight() -> None:
    warm, cool = kelvin_to_rgb(2700), kelvin_to_rgb(6500)
    assert max(warm) == 1.0 and max(cool) == 1.0
    assert warm[2] / warm[0] < cool[2] / cool[0]
    assert warm[0] >= warm[1] >= warm[2]


@pytest.mark.parametrize(
    ("text", "named"),
    [
        ("watts_per_lumen: 0.05\nrig_factor_with_lamps: 0.5\nmax_lights: 16\nlux: 3\n", "lux"),
        ("watts_per_lumen: 0.05\nmax_lights: 16\n", "rig_factor_with_lamps"),
        ("watts_per_lumen: -1\nrig_factor_with_lamps: 0.5\nmax_lights: 16\n", "watts_per_lumen"),
        ("watts_per_lumen: 0.05\nrig_factor_with_lamps: 0.5\nmax_lights: 0\n", "max_lights"),
    ],
)
def test_a_malformed_file_is_refused_naming_the_key(tmp_path: Path, text: str, named: str) -> None:
    with pytest.raises(ConfigurationError, match=named):
        load_lighting(_write(tmp_path, text))


def test_a_malformed_file_stops_startup(monkeypatch: pytest.MonkeyPatch) -> None:
    def broken():
        raise ConfigurationError("lighting.yaml: unknown key 'lux'")

    monkeypatch.setattr(main, "load_lighting", broken)
    settings = Settings(
        database_url="postgresql+psycopg://unused@localhost/unused", openrouter_api_key="sk-or-test",
        cors_origins="http://localhost:5173", owner_email="owner@example.com",
        owner_password="an-initial-owner-password", gateway_probe_enabled=False, _env_file=None,
    )
    with pytest.raises(ConfigurationError, match="lighting.yaml"):
        main.create_app(settings)
