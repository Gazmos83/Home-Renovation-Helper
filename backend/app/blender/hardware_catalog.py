"""The checked-in hardware catalog (`config/hardware.yaml`): how each hardware item looks (hardware-catalog).

Each entry names an item key, or a key pattern with one trailing `*`, a shape from a closed set,
that shape's visual sizes in mm, a finish, whether the app's rules count the item, and the phrases
that identify it in a hand-written hardware line. The sizes describe the drawn shape only; they are
never drilling or engineering values. Loading refuses a malformed entry naming the file and the
entry; the application loads the catalog at startup. A version freezes the catalog into its
hardware inputs (`frozen()`), so the standard-library derive and the generator read the same copy.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import cache
from pathlib import Path
from typing import Any, Final, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from app.blender.custom_build.derive import resolve_catalog_entry
from app.config import ConfigurationError

DEFAULT_CATALOG_PATH: Final = Path(__file__).resolve().parents[2] / "config" / "hardware.yaml"

Shape = Literal[
    "hinge_concealed", "shelf_pin", "drawer_runner", "shelf_bracket", "hanging_rail", "rail_support", "bar", "knob",
]
Finish = Literal["black", "aluminium", "steel", "brass", "nickel", "chrome"]
Size = Field(gt=0, le=2000)


class HardwareCatalogError(ConfigurationError):
    """The catalog is unusable. The message names the file and the entry."""


class _SizeModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class HingeSize(_SizeModel):
    cup_diameter_mm: float = Size
    cup_depth_mm: float = Size
    arm_width_mm: float = Size
    arm_height_mm: float = Size
    plate_length_mm: float = Size
    plate_height_mm: float = Size
    plate_thickness_mm: float = Size


class ShelfPinSize(_SizeModel):
    diameter_mm: float = Size
    length_mm: float = Size


class RunnerSize(_SizeModel):
    width_mm: float = Size
    height_mm: float = Size


class BracketSize(_SizeModel):
    arm_length_mm: float = Size
    height_mm: float = Size
    width_mm: float = Size
    thickness_mm: float = Size


class RailSize(_SizeModel):
    width_mm: float = Size
    height_mm: float = Size


class RailSupportSize(_SizeModel):
    width_mm: float = Size
    height_mm: float = Size
    thickness_mm: float = Size


class BarSize(_SizeModel):
    section_mm: float = Size
    proud_mm: float = Size


class KnobSize(_SizeModel):
    diameter_mm: float = Size
    depth_mm: float = Size


SIZE_MODELS: Final[dict[str, type[_SizeModel]]] = {
    "hinge_concealed": HingeSize,
    "shelf_pin": ShelfPinSize,
    "drawer_runner": RunnerSize,
    "shelf_bracket": BracketSize,
    "hanging_rail": RailSize,
    "rail_support": RailSupportSize,
    "bar": BarSize,
    "knob": KnobSize,
}

_KEY = r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$"
_PATTERN = r"^[A-Za-z0-9][A-Za-z0-9._-]{0,62}\*$"


class CatalogEntryIn(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    key: str | None = Field(default=None, pattern=_KEY)
    pattern: str | None = Field(default=None, pattern=_PATTERN)
    shape: Shape
    size: dict[str, Any]
    finish: Finish
    rule_counted: bool = False
    matches: list[str] = Field(default=[], max_length=20)

    @model_validator(mode="after")
    def _one_name(self) -> CatalogEntryIn:
        if (self.key is None) == (self.pattern is None):
            raise ValueError("give exactly one of key and pattern")
        return self


@dataclass(frozen=True, slots=True)
class CatalogEntry:
    name: str  # the key, or the pattern with its `*`
    shape: str
    size: dict[str, float]
    finish: str
    rule_counted: bool
    matches: tuple[str, ...]

    def as_json(self) -> dict[str, Any]:
        named = {"pattern": self.name} if self.name.endswith("*") else {"key": self.name}
        return {
            **named, "shape": self.shape, "size": dict(self.size), "finish": self.finish,
            "rule_counted": self.rule_counted, "matches": list(self.matches),
        }


@dataclass(frozen=True, slots=True)
class Catalog:
    entries: tuple[CatalogEntry, ...]

    def frozen(self) -> list[dict[str, Any]]:
        """The catalog as plain data, for a version's hardware inputs."""
        return [entry.as_json() for entry in self.entries]

    def entry_for(self, key: str) -> CatalogEntry | None:
        """The exact key's entry, else the entry of the longest pattern prefix the key starts with."""
        found = resolve_catalog_entry(self.frozen(), key)
        if found is None:
            return None
        name = found.get("key") or found["pattern"]
        return next(entry for entry in self.entries if entry.name == name)


def load_catalog(path: Path = DEFAULT_CATALOG_PATH) -> Catalog:
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise HardwareCatalogError(f"hardware catalog not found: {path}") from None
    except yaml.YAMLError as error:
        raise HardwareCatalogError(f"{path.name} is not valid YAML: {error}") from None
    if not isinstance(raw, dict) or not isinstance(raw.get("entries"), list):
        raise HardwareCatalogError(f"{path.name}: needs an 'entries' list")
    return parse_catalog(raw["entries"], path.name)


def parse_catalog(items: list[Any], file_name: str = "hardware.yaml") -> Catalog:
    entries: list[CatalogEntry] = []
    names: set[str] = set()
    for index, item in enumerate(items):
        label = item.get("key") or item.get("pattern") if isinstance(item, dict) else None
        label = repr(label) if label else f"#{index + 1}"
        try:
            entry = CatalogEntryIn.model_validate(item)
        except ValidationError as error:
            first = error.errors()[0]
            where = ".".join(str(part) for part in first["loc"])
            given = first.get("input")
            got = f" (got {given!r})" if isinstance(given, (str, int, float, bool)) else ""
            raise HardwareCatalogError(f"{file_name}: entry {label}: {where}: {first['msg']}{got}") from None
        name = entry.key or entry.pattern
        assert name is not None
        if name in names:
            raise HardwareCatalogError(f"{file_name}: entry {name!r} is listed twice")
        names.add(name)
        try:
            size = SIZE_MODELS[entry.shape].model_validate(entry.size)
        except ValidationError as error:
            first = error.errors()[0]
            field = ".".join(str(part) for part in first["loc"])
            raise HardwareCatalogError(
                f"{file_name}: entry {name!r}: size.{field}: {first['msg']} (shape {entry.shape})"
            ) from None
        phrases = tuple(phrase.strip().casefold() for phrase in entry.matches if phrase.strip())
        entries.append(
            CatalogEntry(
                name=name, shape=entry.shape, size={k: float(v) for k, v in size.model_dump().items()},
                finish=entry.finish, rule_counted=entry.rule_counted, matches=phrases,
            )
        )
    return Catalog(tuple(entries))


@cache
def default_catalog() -> Catalog:
    """The shipped catalog, loaded once; startup calls it so a broken file stops the service."""
    return load_catalog()
