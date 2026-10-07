"""Dependency-free room-composition contract, shared with Blender (room-composition).

A composition places several items in one house-file room, or in the rooms of one
apartment (which share the apartment's plan frame): approved piece versions,
stand-ins for bought furniture, and models from the owner's library. Validation
runs in two steps so this module stays standard-library only:

1. `parse_composition` checks the document's shape. Every unknown field is refused
   by name, and there are no output, frame, resolution or engine fields.
2. `place_items` checks each item against its room, given the room geometry and
   each piece's overall size that the caller looked up. It returns the stored form,
   whose `resolved` block holds what the headless build needs.

Item frame: width along local x, depth along local y, the front facing local +y.
A wall placement puts the item's back against the wall, rotated to the wall's
direction; a free placement puts its footprint centre at (x, y), rotated
`rotation_deg` counter-clockwise.
"""

from __future__ import annotations

import math
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from numbers import Real
from typing import Any, Final

from app.blender.room_contract import (
    Point,
    Wall,
    _build_walls,
    _footprint_inside,
    _normalise_corners,
    _normalise_openings,
    _rectangles_overlap,
    _require_keys,
    _rotated_footprint,
)
from app.blender.spec_contract import SpecValidationError

KIND: Final = "room_composition"
SCHEMA_VERSION: Final = 1
UNITS: Final = "mm"
ITEM_TYPES: Final = ("piece", "stand-in", "model")
MAX_SIZE_MM: Final = 10_000
_MAX_POSITION_MM: Final = 60_000
_TOL: Final = 1e-6
_ID: Final = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,38}[a-z0-9])?$")
_COLOUR: Final = re.compile(r"^#[0-9a-fA-F]{6}$")

_TOP_REQUIRED: Final = frozenset({"kind", "schema_version", "units", "scope", "items"})
_SCOPE_KEYS: Final = frozenset({"room", "apartment"})
_ITEM_COMMON: Final = frozenset({"id", "type", "placement"})
_ITEM_FIELDS: Final = {
    "piece": frozenset({"package_id", "version"}),
    "stand-in": frozenset({"name", "width_mm", "depth_mm", "height_mm", "colour"}),
    "model": frozenset({"model_id", "name", "width_mm", "depth_mm", "height_mm"}),
}
_WALL_PLACEMENT: Final = frozenset({"wall", "offset_mm"})
_FREE_PLACEMENT: Final = frozenset({"x_mm", "y_mm", "rotation_deg"})


def _fail(message: str) -> None:
    raise SpecValidationError(message)


def _whole(value: Any, field: str, *, low: int, high: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or not low <= value <= high:
        _fail(f"{field} must be a whole number from {low} to {high}")
    return value


def _number(value: Any, field: str, *, low: float, high: float) -> float:
    if isinstance(value, bool) or not isinstance(value, Real) or not low <= float(value) <= high:
        _fail(f"{field} must be a number from {low:g} to {high:g}")
    return float(value)


def _text(value: Any, field: str, limit: int = 120) -> str:
    if not isinstance(value, str) or not value.strip() or len(value.strip()) > limit:
        _fail(f"{field} must be a non-blank text of at most {limit} characters")
    return value.strip()


# --- step 1: the document's shape -------------------------------------------------------


def _parse_placement(raw: Any, label: str) -> dict[str, Any]:
    if not isinstance(raw, Mapping):
        _fail(f"{label} must be an object")
    keys = set(raw)
    if "wall" in keys or "offset_mm" in keys:
        _require_keys(raw, _WALL_PLACEMENT, frozenset(), label)
        return {
            "wall": _whole(raw["wall"], f"{label}.wall", low=0, high=63),
            "offset_mm": _number(raw["offset_mm"], f"{label}.offset_mm", low=0, high=_MAX_POSITION_MM),
        }
    _require_keys(raw, _FREE_PLACEMENT, frozenset(), label)
    return {
        "x_mm": _number(raw["x_mm"], f"{label}.x_mm", low=0, high=_MAX_POSITION_MM),
        "y_mm": _number(raw["y_mm"], f"{label}.y_mm", low=0, high=_MAX_POSITION_MM),
        "rotation_deg": _number(raw["rotation_deg"], f"{label}.rotation_deg", low=-360, high=360),
    }


def _parse_item(raw: Any, index: int, apartment: bool) -> dict[str, Any]:
    label = f"items[{index}]"
    if not isinstance(raw, Mapping):
        _fail(f"{label} must be an object")
    kind = raw.get("type")
    if kind not in ITEM_TYPES:
        _fail(f"{label}.type must be one of {list(ITEM_TYPES)}")
    if apartment and "room" not in raw:
        _fail(f"item {raw.get('id')!r} names no room; in an apartment every item names its room")
    room_key = frozenset({"room"}) if apartment else frozenset()
    _require_keys(raw, _ITEM_COMMON | _ITEM_FIELDS[kind] | room_key, frozenset(), label)
    item_id = raw["id"]
    if not isinstance(item_id, str) or not _ID.match(item_id):
        _fail(f"{label}.id must be a short slug (lowercase letters, digits and hyphens)")
    item: dict[str, Any] = {"id": item_id, "type": kind}
    if apartment:
        item["room"] = _text(raw["room"], f"item {item_id}: room")
    if kind == "piece":
        item["package_id"] = _text(raw["package_id"], f"{label}.package_id", 64)
        item["version"] = _whole(raw["version"], f"{label}.version", low=1, high=100_000)
    else:
        item["name"] = _text(raw["name"], f"{label}.name")
        for axis in ("width_mm", "depth_mm", "height_mm"):
            item[axis] = _whole(raw[axis], f"{label}.{axis}", low=1, high=MAX_SIZE_MM)
        if kind == "stand-in":
            colour = raw["colour"]
            if not isinstance(colour, str) or not _COLOUR.match(colour):
                _fail(f"{label}.colour must be #rrggbb")
            item["colour"] = colour.lower()
        else:
            item["model_id"] = _text(raw["model_id"], f"{label}.model_id", 64)
    item["placement"] = _parse_placement(raw["placement"], f"{label}.placement")
    return item


def parse_composition(document: Any, *, max_items: int) -> dict[str, Any]:
    """The document's normalised shape: scope and items, before any room is consulted."""
    if not isinstance(document, Mapping):
        _fail("the composition must be a JSON object")
    _require_keys(document, _TOP_REQUIRED, frozenset(), "composition")
    if document["kind"] != KIND:
        _fail(f"kind must be {KIND!r}")
    if document["schema_version"] != SCHEMA_VERSION:
        _fail(f"schema_version must be {SCHEMA_VERSION}")
    if document["units"] != UNITS:
        _fail("units must be 'mm'")
    scope = document["scope"]
    if not isinstance(scope, Mapping) or len(scope) != 1 or not set(scope) <= _SCOPE_KEYS:
        extra = sorted(set(scope) - _SCOPE_KEYS) if isinstance(scope, Mapping) else []
        if extra:
            _fail(f"unknown scope field: {extra[0]}")
        _fail("scope names exactly one of 'room' or 'apartment'")
    scope_type = next(iter(scope))
    scope_name = _text(scope[scope_type], f"scope.{scope_type}", 200)
    items = document["items"]
    if not isinstance(items, Sequence) or isinstance(items, (str, bytes)) or not items:
        _fail("items must be a non-empty list")
    if len(items) > max_items:
        _fail(f"a composition holds at most {max_items} items, not {len(items)}")
    parsed = [_parse_item(raw, index, scope_type == "apartment") for index, raw in enumerate(items)]
    seen: set[str] = set()
    for item in parsed:
        if item["id"] in seen:
            _fail(f"item id {item['id']!r} is used more than once")
        seen.add(item["id"])
    return {
        "kind": KIND, "schema_version": SCHEMA_VERSION, "units": UNITS,
        "scope": {scope_type: scope_name}, "items": parsed,
    }


# --- step 2: placing items in their rooms ----------------------------------------------------


@dataclass(frozen=True)
class RoomGeometry:
    name: str
    corners: tuple[Point, ...]
    height_mm: float
    wall_thickness_mm: float
    walls: tuple[Wall, ...]
    openings: tuple[dict[str, Any], ...]


def room_geometry(name: str, room: Mapping[str, Any]) -> RoomGeometry:
    """A house-file room (`corners_mm`, `height_mm`, `wall_thickness_mm`, `openings`) as geometry."""
    corners = _normalise_corners(room["corners_mm"])
    walls = _build_walls(corners)
    height = float(room["height_mm"])
    return RoomGeometry(
        name=name, corners=corners, height_mm=height, wall_thickness_mm=float(room["wall_thickness_mm"]),
        walls=walls, openings=_normalise_openings(room.get("openings") or [], walls, height),
    )


@dataclass(frozen=True)
class ItemSubject:
    """One placed item, shaped like a room-fit context so the placement design rules apply."""

    corners: tuple[Point, ...]
    walls: tuple[Wall, ...]
    openings: tuple[dict[str, Any], ...]
    placement: dict[str, Any]


def _wall_pose(item_id: str, room: RoomGeometry, wall_index: int, offset: float, size: tuple[float, float, float]):
    if wall_index >= len(room.walls):
        _fail(f"item {item_id}: wall {wall_index} does not exist in {room.name} (walls 0 to {len(room.walls) - 1})")
    wall = room.walls[wall_index]
    width, depth, _height = size
    if offset + width > wall.length_mm + _TOL:
        _fail(
            f"item {item_id} runs past the end of wall {wall_index} in {room.name} "
            f"(needs {offset + width:.0f} mm, the wall is {wall.length_mm:.0f} mm)"
        )
    ax, ay = wall.start
    ux, uy = wall.direction
    nx, ny = wall.outward_normal
    back_left = (ax + ux * offset, ay + uy * offset)
    back_right = (ax + ux * (offset + width), ay + uy * (offset + width))
    front_right = (back_right[0] - nx * depth, back_right[1] - ny * depth)
    front_left = (back_left[0] - nx * depth, back_left[1] - ny * depth)
    centre = ((back_left[0] + front_right[0]) / 2, (back_left[1] + front_right[1]) / 2)
    rotation = math.degrees(math.atan2(uy, ux))
    return (back_left, back_right, front_right, front_left), centre, rotation, wall.outward_normal


def _free_pose(placement: Mapping[str, Any], size: tuple[float, float, float]):
    width, depth, _height = size
    rotation = placement["rotation_deg"]
    footprint = _rotated_footprint(placement["x_mm"], placement["y_mm"], width, depth, rotation)
    angle = math.radians(rotation)
    outward = (math.sin(angle), -math.cos(angle))  # behind the item: the opposite of its front (+y)
    return footprint, (placement["x_mm"], placement["y_mm"]), rotation, outward


def _opening_zone(wall: Wall, opening: Mapping[str, Any], depth: float) -> tuple[Point, ...]:
    """The strip in front of an opening, `depth` deep into the room."""
    ax, ay = wall.start
    ux, uy = wall.direction
    nx, ny = wall.outward_normal
    s, e = opening["offset_mm"], opening["offset_mm"] + opening["width_mm"]
    a = (ax + ux * s, ay + uy * s)
    b = (ax + ux * e, ay + uy * e)
    return (a, b, (b[0] - nx * depth, b[1] - ny * depth), (a[0] - nx * depth, a[1] - ny * depth))


def _blocked_opening(
    item_id: str, room: RoomGeometry, footprint, placement: Mapping[str, Any], size: tuple[float, float, float]
) -> None:
    width, depth, height = size
    for index, opening in enumerate(room.openings):
        if opening["type"] == "window" and opening["sill_mm"] >= height:
            continue
        if "wall" in placement:
            if opening["wall"] != placement["wall"]:
                continue
            start, end = placement["offset_mm"], placement["offset_mm"] + width
            o_start, o_end = opening["offset_mm"], opening["offset_mm"] + opening["width_mm"]
            if o_end <= start + _TOL or o_start >= end - _TOL:
                continue
        else:
            zone = _opening_zone(room.walls[opening["wall"]], opening, max(depth, 1.0))
            if not _rectangles_overlap(footprint, zone):
                continue
            if _touching_only(footprint, zone):
                continue
        _fail(
            f"item {item_id} blocks the {opening['type']} on wall {opening['wall']} of {room.name} "
            f"(opening {index}, {opening['offset_mm']:g} to {opening['offset_mm'] + opening['width_mm']:g} mm along the wall)"
        )


def _touching_only(a: Sequence[Point], b: Sequence[Point]) -> bool:
    """Whether two overlapping-by-test rectangles only share an edge (no area in common)."""
    shrunk = _shrink(a, 0.5)
    return not _rectangles_overlap(shrunk, b)


def _shrink(rect: Sequence[Point], by: float) -> tuple[Point, ...]:
    cx = sum(p[0] for p in rect) / len(rect)
    cy = sum(p[1] for p in rect) / len(rect)
    result = []
    for x, y in rect:
        dx, dy = x - cx, y - cy
        length = math.hypot(dx, dy) or 1.0
        result.append((x - dx / length * by, y - dy / length * by))
    return tuple(result)


def place_items(
    parsed: Mapping[str, Any],
    *,
    rooms: Mapping[str, RoomGeometry],
    piece_sizes: Mapping[str, tuple[float, float, float]],
    scope_room: str | None = None,
) -> tuple[dict[str, Any], list[tuple[str, ItemSubject]]]:
    """Check every item against its room; the stored document and each item's rule subject.

    `rooms` holds the scope's rooms by name. `piece_sizes` maps each piece item's id to
    its version's overall (width, depth, height) in mm. In a room scope every item stands
    in `scope_room`; in an apartment scope each names its room.
    """
    placed: list[dict[str, Any]] = []
    subjects: list[tuple[str, ItemSubject]] = []
    footprints: list[tuple[str, str, tuple[Point, ...]]] = []
    for item in parsed["items"]:
        item_id = item["id"]
        room_name = item.get("room") or scope_room
        room = rooms.get(room_name or "")
        if room is None:
            _fail(f"item {item_id}: the room {room_name!r} is not part of this composition's scope")
        if item["type"] == "piece":
            size = piece_sizes[item_id]
        else:
            size = (float(item["width_mm"]), float(item["depth_mm"]), float(item["height_mm"]))
        if size[2] > room.height_mm + _TOL:
            _fail(f"item {item_id} is taller than the ceiling of {room.name} ({size[2]:.0f} mm, ceiling {room.height_mm:.0f} mm)")
        placement = item["placement"]
        if "wall" in placement:
            footprint, centre, rotation, outward = _wall_pose(item_id, room, placement["wall"], placement["offset_mm"], size)
        else:
            footprint, centre, rotation, outward = _free_pose(placement, size)
        if not _footprint_inside(footprint, room.corners):
            _fail(f"item {item_id} leaves the room {room.name}")
        _blocked_opening(item_id, room, footprint, placement, size)
        for other_id, other_room, other in footprints:
            if other_room == room.name and _rectangles_overlap(footprint, other) and not _touching_only(footprint, other):
                _fail(f"items {other_id} and {item_id} overlap")
        footprints.append((item_id, room.name, tuple(footprint)))
        subjects.append((item_id, ItemSubject(
            corners=room.corners, walls=room.walls, openings=room.openings,
            placement={"footprint": tuple(footprint), "outward_normal": outward,
                       **({"wall": placement["wall"], "offset_mm": placement["offset_mm"]} if "wall" in placement else {})},
        )))
        placed.append({
            "id": item_id, "room": room.name,
            "size_mm": {"w": size[0], "d": size[1], "h": size[2]},
            "centre_mm": [round(centre[0], 3), round(centre[1], 3)],
            "rotation_deg": round(rotation, 6),
        })
    used = {p["room"] for p in placed}
    stored = {
        **{key: parsed[key] for key in ("kind", "schema_version", "units", "scope", "items")},
        "resolved": {
            "rooms": [
                {
                    "name": room.name,
                    "corners": [list(c) for c in room.corners],
                    "height_mm": room.height_mm,
                    "wall_thickness_mm": room.wall_thickness_mm,
                    "openings": [dict(o) for o in room.openings],
                }
                for name, room in rooms.items() if name in used or scope_room == name
            ],
            "items": placed,
        },
    }
    return stored, subjects
