"""The two shop-data CSV contracts, shared by every producer of them.

Standard-library-only, like `spec_contract`: the Listening Wall generator
imports it inside Blender's own Python, and the backend's custom-build
derivation (`app.blender.custom_build.derive`) writes the same files without
Blender. One field order and one writer means a derived `cutlist.csv` and a
generated one cannot drift apart in shape.
"""

from __future__ import annotations

import csv
from collections.abc import Iterable
from pathlib import Path
from typing import Any, Final

CUTLIST_FIELDS: Final = [
    "id",
    "name",
    "qty",
    "l",
    "w",
    "t",
    "material",
    "grain",
    "banding",
    "notes",
    "module",
]
HARDWARE_FIELDS: Final = ["id", "item", "qty", "notes"]


def write_csv(path: Path, rows: Iterable[dict[str, Any]], fields: list[str]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="raise")
        writer.writeheader()
        writer.writerows(rows)
