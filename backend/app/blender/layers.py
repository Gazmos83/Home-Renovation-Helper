"""Portable presentation-layer bookkeeping for Blender furniture packages."""

from __future__ import annotations

from dataclasses import dataclass, field

from app.blender.custom_build.derive import LAYER_NAMES


class LayerRegistrationError(ValueError):
    """An exportable object cannot be represented in the package layer map."""


@dataclass
class LayerRegistry:
    """Record each exportable mesh exactly once in one supported logical layer.

    Defaults to the custom build's layers `carcass/backs/shelves/fronts/extras`;
    `for_layers` builds one over another set.
    """

    groups: dict[str, list[str]] = field(
        default_factory=lambda: {name: [] for name in LAYER_NAMES}
    )
    names: set[str] = field(default_factory=set)

    @classmethod
    def for_layers(cls, layer_names: tuple[str, ...]) -> LayerRegistry:
        return cls(groups={name: [] for name in layer_names})

    def add(self, name: str, layer: str | None) -> None:
        if layer not in self.groups:
            raise LayerRegistrationError(
                f"exportable object {name!r} needs a supported logical layer"
            )
        if name in self.names:
            raise LayerRegistrationError(f"duplicate presentation object name {name!r}")
        self.names.add(name)
        self.groups[layer].append(name)

    def as_json(self) -> dict[str, list[str]]:
        """Each layer's mesh names; a layer with no meshes is omitted."""
        return {layer: sorted(names) for layer, names in self.groups.items() if names}
