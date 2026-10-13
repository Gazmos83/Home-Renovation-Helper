"""Look and style presets for restyle-variants (CLAUDE.md §6; the restyle-variants spec).

`config/looks.yaml` holds piece looks, `config/styles.yaml` room styles. Both load at
startup and stop it by name on a bad colour, an out-of-range value, an unknown key or a
repeated id, the same posture as the render tiers. Appearance only: nothing here is a
material, a price or a dimension.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Annotated, Final

import yaml
from pydantic import BaseModel, ConfigDict, Field, StringConstraints, ValidationError

from app.config import ConfigurationError

CONFIG_DIR: Final = Path(__file__).resolve().parents[2] / "config"
DEFAULT_LOOKS_PATH: Final = CONFIG_DIR / "looks.yaml"
DEFAULT_STYLES_PATH: Final = CONFIG_DIR / "styles.yaml"

PresetId = Annotated[str, StringConstraints(pattern=r"^[a-z][a-z0-9-]{0,31}$")]
Colour = Annotated[str, StringConstraints(pattern=r"^#[0-9a-fA-F]{6}$")]
Unit = Annotated[float, Field(ge=0, le=1)]
Label = Annotated[str, StringConstraints(min_length=1, max_length=60)]
APPEARANCE_NOTE: Final = "appearance only, not a priced material"
_ID_PATTERN: Final = re.compile(r"^[a-z][a-z0-9-]{0,31}$")


class PresetError(ConfigurationError):
    """A look or style configuration cannot be used."""


class Look(BaseModel):
    """One piece look: how a material slot is drawn."""

    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    label: Label | None = None
    colour: Colour
    roughness: Unit
    metallic: Unit = 0.0
    grain: bool = False


class Surface(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    colour: Colour
    roughness: Unit


class World(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    colour: Colour
    strength: Annotated[float, Field(ge=0, le=5)]


class Style(BaseModel):
    """One room style: surfaces, light and stand-in colours."""

    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    label: Label | None = None
    wall: Surface
    ceiling: Surface
    floor: Surface
    world: World
    stand_ins: dict[Annotated[str, StringConstraints(min_length=1, max_length=40)], Colour] = {}
    fallback: Colour


@dataclass(frozen=True, slots=True)
class Presets:
    looks: Mapping[str, Look]
    styles: Mapping[str, Style]

    def look(self, preset_id: str) -> Look:
        found = self.looks.get(preset_id)
        if found is None:
            raise PresetError(f"unknown look {preset_id!r}; the looks are {', '.join(self.looks)}")
        return found

    def style(self, preset_id: str) -> Style:
        found = self.styles.get(preset_id)
        if found is None:
            raise PresetError(f"unknown style {preset_id!r}; the styles are {', '.join(self.styles)}")
        return found

    def summary(self) -> dict[str, list[str]]:
        return {"looks": list(self.looks), "styles": list(self.styles)}


class _NoDuplicatesLoader(yaml.SafeLoader):
    """Refuses a repeated key, so a duplicate preset id is an error."""


def _no_duplicate_keys(loader: _NoDuplicatesLoader, node: yaml.MappingNode) -> dict:
    seen: set = set()
    for key_node, _ in node.value:
        key = loader.construct_object(key_node)
        if key in seen:
            raise PresetError(f"preset configuration names {key!r} more than once")
        seen.add(key)
    return loader.construct_mapping(node)


_NoDuplicatesLoader.add_constructor(
    yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, _no_duplicate_keys
)


def _first_problem(error: ValidationError) -> str:
    problem = error.errors()[0]
    where = ".".join(str(part) for part in problem["loc"])
    return f"{where}: {problem['msg']}"


def _load(path: Path, section: str, model: type[BaseModel]) -> dict[str, BaseModel]:
    try:
        raw = yaml.load(path.read_text(encoding="utf-8"), Loader=_NoDuplicatesLoader)
    except FileNotFoundError as error:
        raise PresetError(f"preset configuration not found: {path}") from error
    except yaml.YAMLError as error:
        raise PresetError(f"preset configuration is not valid YAML: {path}") from error
    if not isinstance(raw, Mapping) or set(raw) != {section} or not isinstance(raw[section], Mapping):
        raise PresetError(f"{path.name} must hold exactly one '{section}' mapping")
    loaded: dict[str, BaseModel] = {}
    for preset_id, body in raw[section].items():
        if not isinstance(preset_id, str) or not _ID_PATTERN.match(preset_id):
            raise PresetError(f"{path.name}: {preset_id!r} is not a valid preset id")
        try:
            loaded[preset_id] = model.model_validate(body)
        except ValidationError as error:
            raise PresetError(f"{path.name}: {section[:-1]} {preset_id!r}: {_first_problem(error)}") from None
    if not loaded:
        raise PresetError(f"{path.name} defines no {section}")
    return loaded


def load_presets(
    looks_path: Path = DEFAULT_LOOKS_PATH, styles_path: Path = DEFAULT_STYLES_PATH
) -> Presets:
    return Presets(
        looks=_load(looks_path, "looks", Look),  # type: ignore[arg-type]
        styles=_load(styles_path, "styles", Style),  # type: ignore[arg-type]
    )
