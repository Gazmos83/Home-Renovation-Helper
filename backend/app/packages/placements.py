"""A piece version's stored place in a room (view-piece-in-room).

`<version folder>/placements/<room-slug>.json` holds the wall, the offset along it,
the distance from the wall's left end as the owner gave it, and the room-scene
document a render in that room uses. It lives in the version folder, so it goes
with its version and a new version has none until one is chosen.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any
from uuid import uuid4

from app.blender import storage

PLACEMENTS_DIR = "placements"


def placement_file(folder: Path, room_name: str) -> Path:
    return folder / PLACEMENTS_DIR / f"{storage.apartment_slug(room_name)}.json"


def read_placement(folder: Path, room_name: str) -> dict[str, Any] | None:
    """The stored placement of this version in `room_name`, or `None`."""
    try:
        stored = json.loads(placement_file(folder, room_name).read_text(encoding="utf-8"))
    except (OSError, ValueError, storage.InvalidPackageId):
        return None
    return stored if isinstance(stored, dict) else None


def write_placement(folder: Path, room_name: str, placement: dict[str, Any]) -> None:
    """Store the placement, replacing an earlier one in the same room."""
    target = placement_file(folder, room_name)
    target.parent.mkdir(exist_ok=True)
    temp = target.parent / f".{target.name}.{uuid4().hex}.tmp"
    temp.write_text(json.dumps(placement, indent=2), encoding="utf-8")
    os.replace(temp, target)
