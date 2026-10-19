"""Lamp lights for room compositions (room-lamp-lights): the configured factors and the
conversions the composition contract resolves before Blender sees a light.

Standard library only at import, like the composition contract that uses it, so it also
loads inside Blender; `load_lighting` reads `config/lighting.yaml` on the service side.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path
from typing import Final

DEFAULT_LIGHTING_PATH: Final = Path(__file__).resolve().parents[2] / "config" / "lighting.yaml"
_KEYS: Final = ("watts_per_lumen", "rig_factor_with_lamps", "max_lights")


@dataclass(frozen=True, slots=True)
class Lighting:
    watts_per_lumen: float = 0.05
    rig_factor_with_lamps: float = 0.5
    max_lights: int = 16


DEFAULT_LIGHTING: Final = Lighting()


def load_lighting(path: Path = DEFAULT_LIGHTING_PATH) -> Lighting:
    """The lighting configuration; a missing, unknown or invalid key is refused by name."""
    import yaml

    from app.config import ConfigurationError

    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as error:
        raise ConfigurationError(f"{path.name}: cannot be read ({error})") from None
    if not isinstance(raw, dict):
        raise ConfigurationError(f"{path.name}: must be a mapping of {', '.join(_KEYS)}")
    unknown = sorted(set(raw) - set(_KEYS))
    if unknown:
        raise ConfigurationError(f"{path.name}: unknown key {unknown[0]!r}")
    missing = [key for key in _KEYS if key not in raw]
    if missing:
        raise ConfigurationError(f"{path.name}: missing key {missing[0]!r}")
    for key in ("watts_per_lumen", "rig_factor_with_lamps"):
        value = raw[key]
        if isinstance(value, bool) or not isinstance(value, int | float) or value <= 0:
            raise ConfigurationError(f"{path.name}: {key} must be a number above 0")
    if raw["rig_factor_with_lamps"] > 1:
        raise ConfigurationError(f"{path.name}: rig_factor_with_lamps must be at most 1")
    lights = raw["max_lights"]
    if isinstance(lights, bool) or not isinstance(lights, int) or lights < 1:
        raise ConfigurationError(f"{path.name}: max_lights must be a whole number of at least 1")
    return Lighting(float(raw["watts_per_lumen"]), float(raw["rig_factor_with_lamps"]), lights)


def lumens_to_watts(lumens: float, lighting: Lighting) -> float:
    return round(lumens * lighting.watts_per_lumen, 3)


def _linear(channel: float) -> float:
    return channel / 12.92 if channel <= 0.04045 else ((channel + 0.055) / 1.055) ** 2.4


def kelvin_to_rgb(kelvin: float) -> list[float]:
    """A colour temperature as a linear RGB light colour, largest channel 1.0 (Tanner Helland's
    blackbody approximation): lower values are redder, higher ones bluer."""
    t = kelvin / 100
    red = 255.0 if t <= 66 else 329.698727446 * (t - 60) ** -0.1332047592
    green = 99.4708025861 * math.log(t) - 161.1195681661 if t <= 66 else 288.1221695283 * (t - 60) ** -0.0755148492
    if t >= 66:
        blue = 255.0
    elif t <= 19:
        blue = 0.0
    else:
        blue = 138.5177312231 * math.log(t - 10) - 305.0447927307
    channels = [min(255.0, max(0.0, c)) / 255 for c in (red, green, blue)]
    top = max(channels) or 1.0
    return [round(_linear(c / top), 4) for c in channels]
