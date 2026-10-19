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

from app.blender.lighting import (
    DEFAULT_LIGHTING,
    Lighting,
    kelvin_to_rgb,
    lumens_to_watts,
)
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
LED_STRIP: Final = "led-strip"
ITEM_TYPES: Final = ("piece", "stand-in", "model", LED_STRIP)
MAX_SIZE_MM: Final = 10_000
FLOOR_LAYER: Final = "floor"
FLOOR_LAYER_MAX_MM: Final = 30
CEILING_LAYER: Final = "ceiling"
LAYERS: Final = (FLOOR_LAYER, CEILING_LAYER)
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
    LED_STRIP: frozenset({"name", "length_mm", "lumens_per_m", "kelvin", "mount_height_mm"}),
}
# An LED strip's bar, 15 mm deep off the wall and 10 mm thick (room-led-strips).
STRIP_DEPTH_MM: Final = 15.0
STRIP_THICKNESS_MM: Final = 10.0
STRIP_FACINGS: Final = ("down", "up", "out")
# A floor finish over the whole outline (room-floor-finish).
_FLOOR_REQUIRED: Final = frozenset({"tile_width_mm", "tile_length_mm", "tile_colour", "grout_colour", "grout_width_mm"})
FLOOR_PATTERNS: Final = ("grid", "staggered")
_TILE_MM: Final = (20, 2500)
_GROUT_MM: Final = (0, 20)
# An item's light (room-lamp-lights).
_LIGHT_KEYS: Final = frozenset({"type", "lumens", "kelvin"})
LIGHT_TYPES: Final = ("point", "spot")
_LIGHT_ABOVE_BASE_MM: Final = 50.0
_LIGHT_BELOW_TOP_MM: Final = 50.0
_WALL_PLACEMENT: Final = frozenset({"wall", "offset_mm"})
# A piece hung on its wall: the height of its underside above the floor (conversation-continuity).
MOUNT_HEIGHT: Final = "mount_height_mm"
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
        _require_keys(raw, _WALL_PLACEMENT, frozenset({MOUNT_HEIGHT}), label)
        placement = {
            "wall": _whole(raw["wall"], f"{label}.wall", low=0, high=63),
            "offset_mm": _number(raw["offset_mm"], f"{label}.offset_mm", low=0, high=_MAX_POSITION_MM),
        }
        if MOUNT_HEIGHT in raw:
            # The upper bound is the room's ceiling, checked when the piece is placed. A number, not
            # a whole one: the saved place stores it as computed, such as 1700.0.
            placement[MOUNT_HEIGHT] = _number(raw[MOUNT_HEIGHT], f"{label}.{MOUNT_HEIGHT}", low=0, high=MAX_SIZE_MM)
        return placement
    if MOUNT_HEIGHT in keys:
        _fail(f"{label}: {MOUNT_HEIGHT} needs a wall placement")
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
    # Any item may be hidden: kept in the layout, left out of the build (hidden-room-items).
    if kind == "piece":
        extra = frozenset()
    elif kind == LED_STRIP:
        extra = frozenset({"facing"})
    else:
        extra = frozenset({"layer", "light"})
    optional = frozenset({"hidden"}) | extra
    _require_keys(raw, _ITEM_COMMON | _ITEM_FIELDS[kind] | room_key, optional, label)
    item_id = raw["id"]
    if not isinstance(item_id, str) or not _ID.match(item_id):
        _fail(f"{label}.id must be a short slug (lowercase letters, digits and hyphens)")
    item: dict[str, Any] = {"id": item_id, "type": kind}
    if apartment:
        item["room"] = _text(raw["room"], f"item {item_id}: room")
    if kind == "piece":
        item["package_id"] = _text(raw["package_id"], f"{label}.package_id", 64)
        item["version"] = _whole(raw["version"], f"{label}.version", low=1, high=100_000)
    elif kind == LED_STRIP:
        item["name"] = _text(raw["name"], f"{label}.name")
        item["length_mm"] = _whole(raw["length_mm"], f"item {item_id}: length_mm", low=100, high=10_000)
        item["lumens_per_m"] = _whole(raw["lumens_per_m"], f"item {item_id}: lumens_per_m", low=50, high=3000)
        item["kelvin"] = _whole(raw["kelvin"], f"item {item_id}: kelvin", low=1800, high=6500)
        # The upper bound is the room's ceiling, checked when the strip is placed.
        item["mount_height_mm"] = _whole(raw["mount_height_mm"], f"item {item_id}: mount_height_mm", low=0, high=MAX_SIZE_MM)
        facing = raw.get("facing", "down")
        if facing not in STRIP_FACINGS:
            _fail(f"item {item_id}: facing must be one of {list(STRIP_FACINGS)}")
        item["facing"] = facing
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
        if "layer" in raw:
            # A floor-layer item lies flat on the floor, such as a rug (composition-floor-layer); a
            # ceiling-layer item hangs from the ceiling, such as a pendant lamp (composition-ceiling-layer).
            if raw["layer"] not in LAYERS:
                _fail(f"item {item_id}: layer must be one of {list(LAYERS)}")
            if raw["layer"] == FLOOR_LAYER and item["height_mm"] > FLOOR_LAYER_MAX_MM:
                _fail(f"item {item_id} is on the floor layer and may be at most {FLOOR_LAYER_MAX_MM} mm tall, not {item['height_mm']} mm")
            item["layer"] = raw["layer"]
        if "light" in raw:
            # A lamp gives light (room-lamp-lights); a rug lying on the floor does not.
            if item.get("layer") == FLOOR_LAYER:
                _fail(f"item {item_id} is on the floor layer and cannot carry light")
            item["light"] = _parse_light(raw["light"], item_id)
    if "hidden" in raw:
        if not isinstance(raw["hidden"], bool):
            _fail(f"item {item_id}: hidden must be true or false")
        # Only `true` is kept, so `hidden: false` is stored as if the field were absent.
        if raw["hidden"]:
            item["hidden"] = True
    item["placement"] = _parse_placement(raw["placement"], f"{label}.placement")
    if MOUNT_HEIGHT in item["placement"] and kind != "piece":
        _fail(f"item {item_id}: {MOUNT_HEIGHT} is only for a piece placed on a wall")
    if kind == LED_STRIP and "wall" not in item["placement"]:
        _fail(f"item {item_id}: an LED strip is fixed to a wall; place it with wall and offset_mm")
    return item


def _parse_light(raw: Any, item_id: str) -> dict[str, Any]:
    if not isinstance(raw, Mapping):
        _fail(f"item {item_id}: light must be an object")
    _require_keys(raw, _LIGHT_KEYS, frozenset(), f"item {item_id} light")
    if raw["type"] not in LIGHT_TYPES:
        _fail(f"item {item_id}: light type must be one of {list(LIGHT_TYPES)}")
    return {
        "type": raw["type"],
        "lumens": _whole(raw["lumens"], f"item {item_id}: light lumens", low=10, high=10_000),
        "kelvin": _whole(raw["kelvin"], f"item {item_id}: light kelvin", low=1800, high=6500),
    }


def _parse_floor(raw: Any) -> dict[str, Any]:
    """A floor finish, normalised with its pattern filled in (room-floor-finish)."""
    if not isinstance(raw, Mapping):
        _fail("floor must be an object")
    _require_keys(raw, _FLOOR_REQUIRED, frozenset({"pattern"}), "floor")
    finish: dict[str, Any] = {
        axis: _whole(raw[axis], f"floor.{axis}", low=_TILE_MM[0], high=_TILE_MM[1])
        for axis in ("tile_width_mm", "tile_length_mm")
    }
    for key in ("tile_colour", "grout_colour"):
        colour = raw[key]
        if not isinstance(colour, str) or not _COLOUR.match(colour):
            _fail(f"floor.{key} must be #rrggbb")
        finish[key] = colour.lower()
    finish["grout_width_mm"] = _number(raw["grout_width_mm"], "floor.grout_width_mm", low=_GROUT_MM[0], high=_GROUT_MM[1])
    pattern = raw.get("pattern", "grid")
    if pattern not in FLOOR_PATTERNS:
        _fail(f"floor.pattern must be one of {list(FLOOR_PATTERNS)}")
    finish["pattern"] = pattern
    return finish


def floor_summary(finish: Mapping[str, Any]) -> str:
    """A floor finish in one line, for the confirmation, the change list and the composition note."""
    return (
        f"{finish['tile_width_mm']:g} × {finish['tile_length_mm']:g} mm tiles, {finish['pattern']}, "
        f"tile {finish['tile_colour']}, grout {finish['grout_width_mm']:g} mm {finish['grout_colour']}"
    )


def parse_composition(document: Any, *, max_items: int) -> dict[str, Any]:
    """The document's normalised shape: scope and items, before any room is consulted."""
    if not isinstance(document, Mapping):
        _fail("the composition must be a JSON object")
    _require_keys(document, _TOP_REQUIRED, frozenset({"floor"}), "composition")
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
    if not isinstance(items, Sequence) or isinstance(items, (str, bytes)):
        _fail("items must be a list")
    # A room may be composed with no furniture (rooms-page); an apartment may not.
    if not items and scope_type == "apartment":
        _fail("an apartment composition needs at least one item")
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
        **({"floor": _parse_floor(document["floor"])} if "floor" in document else {}),
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
    item_id: str, room: RoomGeometry, footprint, placement: Mapping[str, Any], size: tuple[float, float, float],
    base: float = 0.0, top: float | None = None,
) -> None:
    """`base` is the height of the item's lowest point: above 0 only for a ceiling-layer item or a
    hung piece, which clears every opening whose top it hangs above. `top` is a hung piece's top,
    which a window's sill must reach for the piece to clear it; otherwise the item's height."""
    width, depth, height = size
    reach = height if top is None else top
    for index, opening in enumerate(room.openings):
        if opening["type"] == "window" and opening["sill_mm"] >= reach:
            continue
        if base >= opening["sill_mm"] + opening["height_mm"] - _TOL:
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


def _where(placement: Mapping[str, Any]) -> str:
    """A placement as a refusal names it: wall index and offset, or the free position."""
    if "wall" in placement:
        return f"wall {placement['wall']}, offset {placement['offset_mm']:g} mm"
    return f"free at x {placement['x_mm']:g}, y {placement['y_mm']:g} mm, rotated {placement['rotation_deg']:g}°"


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
    lighting: Lighting = DEFAULT_LIGHTING,
) -> tuple[dict[str, Any], list[tuple[str, ItemSubject]]]:
    """Check every item against its room; the stored document and each item's rule subject.

    `rooms` holds the scope's rooms by name. `piece_sizes` maps each piece item's id to
    its version's overall (width, depth, height) in mm. In a room scope every item stands
    in `scope_room`; in an apartment scope each names its room.
    """
    placed: list[dict[str, Any]] = []
    subjects: list[tuple[str, ItemSubject]] = []
    footprints: list[tuple[str, str, tuple[Point, ...], str, str | None, float, float]] = []
    strips: list[tuple[str, str, int, float, float, float]] = []
    for item in parsed["items"]:
        item_id = item["id"]
        room_name = item.get("room") or scope_room
        room = rooms.get(room_name or "")
        if room is None:
            _fail(f"item {item_id}: the room {room_name!r} is not part of this composition's scope")
        if item["type"] == LED_STRIP:
            # A strip lies on its wall: it is checked against openings and other strips only.
            placed.append(_place_strip(item, room, strips, lighting))
            continue
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
        # A floor-layer item (a rug) blocks no opening, lies under standing items and takes no
        # placement rule; it still stays inside the room and clear of other floor-layer items.
        # A ceiling-layer item hangs from `base` up to the ceiling: it clashes with another item
        # only where their heights meet, blocks only an opening it hangs below the top of, and
        # takes no placement rule.
        layer = item.get("layer")
        hung = MOUNT_HEIGHT in placement
        base = room.height_mm - size[2] if layer == CEILING_LAYER else float(placement.get(MOUNT_HEIGHT, 0))
        top = base + size[2]
        if hung and top > room.height_mm + _TOL:
            _fail(
                f"item {item_id} would hang with its top at {top:.0f} mm, above the ceiling of "
                f"{room.name} ({room.height_mm:.0f} mm)"
            )
        if item.get("hidden"):
            # A hidden item keeps its shape checks above but blocks nothing: no opening check,
            # no overlap either way and no placement rule (hidden-room-items).
            placed.append({
                "id": item_id, "room": room.name,
                "size_mm": {"w": size[0], "d": size[1], "h": size[2]},
                "centre_mm": [round(centre[0], 3), round(centre[1], 3)],
                "rotation_deg": round(rotation, 6),
                **({"base_mm": round(base, 3)} if layer == CEILING_LAYER or hung else {}),
                "hidden": True,
            })
            continue
        if layer != FLOOR_LAYER:
            _blocked_opening(item_id, room, footprint, placement, size, base, top if hung else None)
        for other_id, other_room, other, other_where, other_layer, other_base, other_top in footprints:
            # A ceiling-layer item or a hung piece clashes only where the heights meet.
            if CEILING_LAYER in (layer, other_layer) or base > 0 or other_base > 0:
                clash = base < other_top - _TOL and other_base < top - _TOL
            else:
                clash = other_layer == layer
            if (other_room == room.name and clash
                    and _rectangles_overlap(footprint, other) and not _touching_only(footprint, other)):
                _fail(f"items {other_id} ({other_where}) and {item_id} ({_where(placement)}) overlap")
        footprints.append((item_id, room.name, tuple(footprint), _where(placement), layer, base, top))
        if layer is None:
            subjects.append((item_id, ItemSubject(
                corners=room.corners, walls=room.walls, openings=room.openings,
                placement={"footprint": tuple(footprint), "outward_normal": outward,
                           **({"wall": placement["wall"], "offset_mm": placement["offset_mm"]} if "wall" in placement else {})},
            )))
        resolved_item = {
            "id": item_id, "room": room.name,
            "size_mm": {"w": size[0], "d": size[1], "h": size[2]},
            "centre_mm": [round(centre[0], 3), round(centre[1], 3)],
            "rotation_deg": round(rotation, 6),
            **({"base_mm": round(base, 3)} if layer == CEILING_LAYER or hung else {}),
        }
        if "light" in item:
            resolved_item["light"] = _resolved_light(item["light"], centre, base, size[2], layer, lighting)
        placed.append(resolved_item)
    lit_rooms = {p["room"] for p in placed if "light" in p or "strip" in p}
    lights = sum(1 for p in placed if "light" in p or "strip" in p)
    if lights > lighting.max_lights:
        _fail(f"a composition holds at most {lighting.max_lights} lights, not {lights}")
    used = {p["room"] for p in placed}
    stored = {
        **{key: parsed[key] for key in ("kind", "schema_version", "units", "scope", "items", "floor") if key in parsed},
        "resolved": {
            "rooms": [
                {
                    "name": room.name,
                    "corners": [list(c) for c in room.corners],
                    "height_mm": room.height_mm,
                    "wall_thickness_mm": room.wall_thickness_mm,
                    "openings": [dict(o) for o in room.openings],
                    # The room's rig lights are dimmed when it has lamp lights (room-lamp-lights).
                    "rig_factor": lighting.rig_factor_with_lamps if room.name in lit_rooms else 1.0,
                }
                for name, room in rooms.items() if name in used or scope_room == name
            ],
            "items": placed,
        },
    }
    return stored, subjects


def _place_strip(
    item: Mapping[str, Any], room: RoomGeometry, strips: list[tuple[str, str, int, float, float, float]],
    lighting: Lighting,
) -> dict[str, Any]:
    """An LED strip on its wall (room-led-strips): its bar's derived size, and its light."""
    item_id = item["id"]
    placement = item["placement"]
    wall, offset = placement["wall"], placement["offset_mm"]
    length, low = float(item["length_mm"]), float(item["mount_height_mm"])
    high = low + STRIP_THICKNESS_MM
    if high > room.height_mm - _TOL:
        _fail(f"item {item_id} reaches the ceiling of {room.name} (strip at {low:.0f} mm, ceiling {room.height_mm:.0f} mm)")
    size = (length, STRIP_DEPTH_MM, STRIP_THICKNESS_MM)
    footprint, centre, rotation, outward = _wall_pose(item_id, room, wall, offset, size)
    if not _footprint_inside(footprint, room.corners):
        _fail(f"item {item_id} leaves the room {room.name}")
    resolved: dict[str, Any] = {
        "id": item_id, "room": room.name,
        "size_mm": {"w": size[0], "d": size[1], "h": size[2]},
        "centre_mm": [round(centre[0], 3), round(centre[1], 3)],
        "rotation_deg": round(rotation, 6),
        "base_mm": round(low, 3),
    }
    if item.get("hidden"):
        return {**resolved, "hidden": True}
    end = offset + length
    for index, opening in enumerate(room.openings):
        if opening["wall"] != wall:
            continue
        o_start, o_end = opening["offset_mm"], opening["offset_mm"] + opening["width_mm"]
        o_low, o_high = opening["sill_mm"], opening["sill_mm"] + opening["height_mm"]
        if o_start < end - _TOL and offset < o_end - _TOL and o_low < high - _TOL and low < o_high - _TOL:
            _fail(
                f"item {item_id} crosses the {opening['type']} on wall {wall} of {room.name} "
                f"(opening {index}, {o_start:g} to {o_end:g} mm along the wall, {o_low:g} to {o_high:g} mm high)"
            )
    for other_id, other_room, other_wall, other_start, other_end, other_low in strips:
        if (other_room == room.name and other_wall == wall
                and other_start < end - _TOL and offset < other_end - _TOL
                and other_low < high - _TOL and low < other_low + STRIP_THICKNESS_MM - _TOL):
            _fail(f"LED strips {other_id} and {item_id} overlap on wall {wall} of {room.name}")
    strips.append((item_id, room.name, wall, offset, end, low))
    resolved["strip"] = {
        "length_mm": item["length_mm"], "lumens_per_m": item["lumens_per_m"], "kelvin": item["kelvin"],
        "watts": lumens_to_watts(length / 1000 * item["lumens_per_m"], lighting),
        "rgb": kelvin_to_rgb(item["kelvin"]),
        "facing": item["facing"], "wall": wall, "offset_mm": offset, "mount_height_mm": item["mount_height_mm"],
        # Into the room, away from the wall.
        "inward": [round(-outward[0], 6), round(-outward[1], 6)],
    }
    return resolved


def _resolved_light(
    light: Mapping[str, Any], centre: Point, base: float, height: float, layer: str | None, lighting: Lighting,
) -> dict[str, Any]:
    """Where the build puts an item's light and how strong and warm it is: centred on the
    footprint, 50 mm above a hanging item's lowest point or 50 mm below a standing item's top
    (at least half its height)."""
    if layer == CEILING_LAYER:
        z = base + _LIGHT_ABOVE_BASE_MM
    else:
        z = max(height - _LIGHT_BELOW_TOP_MM, height / 2)
    return {
        **light,
        "watts": lumens_to_watts(light["lumens"], lighting),
        "rgb": kelvin_to_rgb(light["kelvin"]),
        "at_mm": [round(centre[0], 3), round(centre[1], 3), round(z, 3)],
    }


# --- the surface map (app-check-2026-10-09) --------------------------------------------------

ITEMS_SURFACE: Final = "items"


def _surface_order(label: str) -> tuple[int, str, int, int]:
    if label == ITEMS_SURFACE:
        return (1, "", 0, 0)
    room, _sep, rest = label.rpartition(": ")
    if rest.startswith("wall "):
        return (0, room, 0, int(rest[5:]))
    return (0, room, 1 if rest == "floor" else 2, 0)


def surface_map(
    mesh_names: Sequence[str], item_meshes: Sequence[str], wall_labels: Mapping[str, str] | None = None
) -> dict[str, list[str]]:
    """Each surface the owner can switch, with the mesh names it holds, in display order.

    A room's walls are `Wall_<index>_…` (wall `<index + 1>`), its floor `Floor` and its
    ceiling `Ceiling`. An apartment's walls are `Wall_<wall id>_…`, labelled by
    `wall_labels` (wall id → "<room>: wall <n>"), and each room's floor and ceiling are
    `Floor_<room>` and `Ceiling_<room>`. Every placed item's meshes are `items`. Raises
    `SpecValidationError` naming a mesh no surface takes, so every mesh is mapped once.
    """
    items = set(item_meshes)
    apartment = wall_labels is not None
    surfaces: dict[str, list[str]] = {}
    for name in sorted(mesh_names):
        label: str | None = None
        if name in items:
            label = ITEMS_SURFACE
        elif name.startswith("Wall_"):
            key = name.split("_")[1]
            if apartment:
                label = wall_labels.get(key)
            elif key.isdigit():
                label = f"wall {int(key) + 1}"
        elif not apartment and name in ("Floor", "Ceiling"):
            label = name.lower()
        elif apartment and name.startswith("Floor_"):
            label = f"{name[len('Floor_'):]}: floor"
        elif apartment and name.startswith("Ceiling_"):
            label = f"{name[len('Ceiling_'):]}: ceiling"
        if label is None:
            _fail(f"surface map: no surface takes the mesh {name!r}")
        surfaces.setdefault(label, []).append(name)
    return {label: surfaces[label] for label in sorted(surfaces, key=_surface_order)}


def apartment_wall_labels(walls: Sequence[Any]) -> dict[str, str]:
    """An apartment shell's wall ids as "<room>: wall <n>", numbered per room in build order.

    A wall two rooms share is built once, so it is labelled by the first room it names.
    """
    counts: dict[str, int] = {}
    labels = {}
    for wall in walls:
        room = wall.rooms[0]
        counts[room] = counts.get(room, 0) + 1
        labels[wall.id] = f"{room}: wall {counts[room]}"
    return labels
