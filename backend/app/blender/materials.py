"""The one material fact the spec validator needs: a sheet's stated thickness.

The pricing change (step 5) ports the full material-key normaliser and may
replace this helper. Until then `CustomBuildSpec` only has to catch a slot whose
`material` string names a sheet and a thickness that disagrees with
`thickness_mm` — the same rule the predecessor expressed through `material_key`.
Standard library only, so it is also importable inside Blender's Python.
"""

from __future__ import annotations

import re
from typing import Final

# Substrings that make a material string a *sheet* material (the predecessor's
# `_PANEL_CLASS_PHRASES`, class names dropped: only membership matters here).
_PANEL_PHRASES: Final[tuple[str, ...]] = (
    "oak-veneered birch",
    "multiplexplatte birke",
    "multiplex birke",
    "multiplex birch",
    "birch multiplex",
    "birch plywood",
    "leimholzplatte fichte",
    "leimholz fichte",
    "leimholz spruce",
    "spruce leimholz",
    "leimholzplatte buche",
    "leimholz buche",
    "leimholz beech",
    "beech leimholz",
    "tischlerplatte",
    "blockboard",
    "möbelbauplatte",
    "moebelbauplatte",
    "furniture board",
    "birch",
    "black mdf",
    "mdf",
)

# "18 mm oak-veneered birch" -> 18. Anchored to the start, so a cross-section
# such as "25×25×2 mm SHS" yields no thickness.
_LEADING_THICKNESS: Final = re.compile(r"^(\d+)\s*mm\b")


def panel_thickness_mm(material: str) -> int | None:
    """The thickness a sheet-material string states, or `None` when the string
    is not a sheet material or states no leading thickness."""
    lowered = material.strip().casefold()
    match = _LEADING_THICKNESS.match(lowered)
    if match is None:
        return None
    if not any(phrase in lowered for phrase in _PANEL_PHRASES):
        return None
    return int(match.group(1))
