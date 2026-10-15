"""Render tiers from configuration (render-guard; CLAUDE.md §6).

Two tiers, fixed by `config/render.yaml`: `draft` and `final` (two-tier-renders
removed `preview`, so a configuration still naming it is refused as unknown). A
missing, duplicated or unknown tier, an unknown key, an unknown engine or a
non-positive value stops startup by name — the same posture as model routing.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Final

import yaml

from app.config import ConfigurationError

TIER_NAMES: Final[tuple[str, ...]] = ("draft", "final")

# The engines a tier may name, mapped to Blender 5.2.1's RNA identifiers.
# `bpy.types.RenderSettings...enum_items` under-reports in background mode (it
# lists only BLENDER_EEVEE), so these were confirmed by assigning each one in
# the pinned binary; the generators still assign inside try/except TypeError.
ENGINES: Final[dict[str, str]] = {"eevee": "BLENDER_EEVEE", "cycles": "CYCLES"}

_TIER_KEYS: Final = frozenset({"frames", "resolution", "engine", "timeout_multiplier"})

DEFAULT_TIERS_PATH: Final = Path(__file__).resolve().parents[2] / "config" / "render.yaml"


class TierError(ConfigurationError):
    """The render configuration cannot produce the two tiers."""


@dataclass(frozen=True, slots=True)
class Tier:
    name: str
    frames: int
    resolution: int
    engine: str  # "eevee" | "cycles"
    timeout_multiplier: int

    @property
    def megapixels(self) -> float:
        return self.resolution * self.resolution / 1_000_000

    @property
    def blender_engine(self) -> str:
        return ENGINES[self.engine]

    def describe(self) -> str:
        return f"{self.frames} × {self.resolution}² {self.engine}"


@dataclass(frozen=True, slots=True)
class Tiers:
    _tiers: Mapping[str, Tier]

    def get(self, name: object) -> Tier:
        if not isinstance(name, str) or name not in self._tiers:
            raise TierError(
                f"unknown tier {name!r}; the tiers are {', '.join(TIER_NAMES)}"
            )
        return self._tiers[name]

    def items(self) -> list[tuple[str, Tier]]:
        return [(name, self._tiers[name]) for name in TIER_NAMES]

    def summary(self) -> dict[str, str]:
        return {name: tier.describe() for name, tier in self.items()}


class _NoDuplicatesLoader(yaml.SafeLoader):
    """Refuses a repeated key, so a duplicate tier is an error."""


def _no_duplicate_keys(loader: _NoDuplicatesLoader, node: yaml.MappingNode) -> dict:
    seen: set = set()
    for key_node, _ in node.value:
        key = loader.construct_object(key_node)
        if key in seen:
            raise TierError(f"render configuration names {key!r} more than once")
        seen.add(key)
    return loader.construct_mapping(node)


_NoDuplicatesLoader.add_constructor(
    yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, _no_duplicate_keys
)


def _positive_int(tier: str, key: str, value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise TierError(f"tier {tier!r}: {key} must be a positive integer, got {value!r}")
    return value


def load_tiers(path: Path = DEFAULT_TIERS_PATH) -> Tiers:
    try:
        raw = yaml.load(path.read_text(encoding="utf-8"), Loader=_NoDuplicatesLoader)
    except FileNotFoundError as error:
        raise TierError(f"render configuration not found: {path}") from error
    except yaml.YAMLError as error:
        raise TierError(f"render configuration is not valid YAML: {path}") from error

    if not isinstance(raw, Mapping) or not isinstance(raw.get("tiers"), Mapping):
        raise TierError("render configuration must have a 'tiers' mapping")
    declared = dict(raw["tiers"])

    unknown = sorted(str(name) for name in set(declared) - set(TIER_NAMES))
    if unknown:
        raise TierError(
            f"render configuration defines unknown tier(s): {', '.join(unknown)}; "
            f"only {', '.join(TIER_NAMES)} are allowed"
        )
    missing = [name for name in TIER_NAMES if name not in declared]
    if missing:
        raise TierError(f"render configuration is missing tier(s): {', '.join(missing)}")

    tiers: dict[str, Tier] = {}
    for name in TIER_NAMES:
        body = declared[name]
        if not isinstance(body, Mapping):
            raise TierError(f"tier {name!r} must be a mapping")
        extra = sorted(str(k) for k in set(body) - _TIER_KEYS)
        if extra:
            raise TierError(f"tier {name!r} has unknown key(s): {', '.join(extra)}")
        absent = sorted(_TIER_KEYS - set(body))
        if absent:
            raise TierError(f"tier {name!r} is missing key(s): {', '.join(absent)}")
        engine = body["engine"]
        if engine not in ENGINES:
            raise TierError(
                f"tier {name!r}: unknown engine {engine!r}; "
                f"known engines are {', '.join(sorted(ENGINES))}"
            )
        tiers[name] = Tier(
            name=name,
            frames=_positive_int(name, "frames", body["frames"]),
            resolution=_positive_int(name, "resolution", body["resolution"]),
            engine=engine,
            timeout_multiplier=_positive_int(
                name, "timeout_multiplier", body["timeout_multiplier"]
            ),
        )
    return Tiers(tiers)
