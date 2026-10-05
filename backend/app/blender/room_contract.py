"""Dependency-free room-scene input contract, shared with Blender.

Mirrors `spec_contract.py`'s split (day 3): standard-library only, so a
background ``bpy`` process and the FastAPI service validate the exact same
document and derive the exact same geometry. Where the furniture contract
normalises primitive dimensions into one fixed shape, this contract
normalises a *traced* room — 4 to 8 interior corners, in millimetres, forming
a convex polygon — plus its openings, the wall a furniture package stands
against, the existing furnishings that stay in it, and the requested output.

A rectangular room is simply the four-corner case: a client's three intake
dimensions (width, depth, height) become the four corners
``(0, 0), (w, 0), (w, d), (0, d)`` at the API boundary, not a second contract.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from itertools import pairwise
from numbers import Real
from typing import Any, Final

from app.blender.spec_contract import SpecValidationError

KIND: Final = "room_scene"
SCHEMA_VERSION: Final = 1
UNITS: Final = "mm"

MIN_CORNERS: Final = 4
MAX_CORNERS: Final = 8
DEFAULT_WALL_THICKNESS_MM: Final = 100
_MAX_ROOM_DIMENSION_MM: Final = 30_000
_MAX_CEILING_MM: Final = 6_000
_OPENING_TYPES: Final = frozenset({"door", "window"})
_OUTPUT_KINDS: Final = frozenset({"still", "turntable"})

_TOP_LEVEL_REQUIRED: Final = frozenset(
    {"kind", "schema_version", "units", "room", "placement", "output"}
)
_TOP_LEVEL_OPTIONAL: Final = frozenset({"openings", "furnishings"})
_ROOM_REQUIRED: Final = frozenset({"corners", "height_mm"})
_ROOM_OPTIONAL: Final = frozenset({"wall_thickness_mm"})
_OPENING_REQUIRED: Final = frozenset({"wall", "type", "offset_mm", "width_mm", "height_mm"})
_OPENING_OPTIONAL: Final = frozenset({"sill_mm"})
_PLACEMENT_KEYS: Final = frozenset({"wall", "offset_mm"})
_FURNISHING_REQUIRED: Final = frozenset(
    {"name", "width_mm", "depth_mm", "height_mm", "x_mm", "y_mm", "rotation_deg"}
)
_FURNISHING_OPTIONAL: Final = frozenset({"z_mm"})

_TOL: Final = 1e-6

Point = tuple[float, float]


def _fail(message: str) -> None:
    raise SpecValidationError(message)


def _number(value: Any, field: str, *, allow_zero: bool = False, maximum: float | None = None) -> float:
    if isinstance(value, bool) or not isinstance(value, Real):
        _fail(f"{field} must be a number")
    number = float(value)
    if allow_zero:
        if number < 0:
            _fail(f"{field} must not be negative")
    elif number <= 0:
        _fail(f"{field} must be greater than zero")
    if maximum is not None and number > maximum:
        _fail(f"{field} must be at most {maximum:g}")
    return number


def _require_keys(document: Mapping[str, Any], required: frozenset[str], optional: frozenset[str], label: str) -> None:
    if not isinstance(document, Mapping):
        _fail(f"{label} must be an object")
    allowed = required | optional
    extra = sorted(set(document) - allowed)
    if extra:
        _fail(f"unknown {label} field: {extra[0]}")
    missing = sorted(required - set(document))
    if missing:
        _fail(f"missing {label} field: {missing[0]}")


# --- geometry helpers ---------------------------------------------------------------


def _signed_area_x2(corners: Sequence[Point]) -> float:
    total = 0.0
    n = len(corners)
    for i in range(n):
        x0, y0 = corners[i]
        x1, y1 = corners[(i + 1) % n]
        total += x0 * y1 - x1 * y0
    return total


def _is_convex_ccw(corners: Sequence[Point]) -> bool:
    """Every turn along a CCW polygon must be a left turn (or straight)."""
    n = len(corners)
    for i in range(n):
        ax, ay = corners[i]
        bx, by = corners[(i + 1) % n]
        cx, cy = corners[(i + 2) % n]
        cross = (bx - ax) * (cy - by) - (by - ay) * (cx - bx)
        if cross < -_TOL:
            return False
    return True


def _point_in_convex_polygon(point: Point, corners: Sequence[Point]) -> bool:
    """Whether `point` lies inside (or on the boundary of) a CCW convex polygon."""
    n = len(corners)
    for i in range(n):
        ax, ay = corners[i]
        bx, by = corners[(i + 1) % n]
        cross = (bx - ax) * (point[1] - ay) - (by - ay) * (point[0] - ax)
        if cross < -_TOL:
            return False
    return True


def _rotated_footprint(
    center_x: float, center_y: float, width: float, depth: float, rotation_deg: float
) -> tuple[Point, Point, Point, Point]:
    """The four world-space corners of a `width` x `depth` rectangle centred at
    (center_x, center_y), rotated `rotation_deg` about that centre."""
    angle = math.radians(rotation_deg)
    cos_a, sin_a = math.cos(angle), math.sin(angle)
    half_w, half_d = width / 2, depth / 2
    local = ((-half_w, -half_d), (half_w, -half_d), (half_w, half_d), (-half_w, half_d))
    world = []
    for lx, ly in local:
        world.append((center_x + lx * cos_a - ly * sin_a, center_y + lx * sin_a + ly * cos_a))
    return tuple(world)  # type: ignore[return-value]


def _rectangles_overlap(a: Sequence[Point], b: Sequence[Point]) -> bool:
    """Separating-axis test for two (possibly rotated) rectangles."""

    def axes(rect: Sequence[Point]) -> list[Point]:
        result = []
        n = len(rect)
        for i in range(n):
            x0, y0 = rect[i]
            x1, y1 = rect[(i + 1) % n]
            edge = (x1 - x0, y1 - y0)
            length = math.hypot(*edge)
            if length < _TOL:
                continue
            result.append((-edge[1] / length, edge[0] / length))
        return result

    for axis in axes(a) + axes(b):
        a_proj = [point[0] * axis[0] + point[1] * axis[1] for point in a]
        b_proj = [point[0] * axis[0] + point[1] * axis[1] for point in b]
        if max(a_proj) < min(b_proj) - _TOL or max(b_proj) < min(a_proj) - _TOL:
            return False
    return True


@dataclass(frozen=True)
class Wall:
    index: int
    start: Point
    end: Point
    length_mm: float
    direction: Point  # unit vector along the wall, start -> end
    outward_normal: Point  # unit vector pointing away from the room's interior


@dataclass(frozen=True)
class RoomBuildContext:
    """Normalised room-scene input plus every value derived from it."""

    corners: tuple[Point, ...]
    height_mm: float
    wall_thickness_mm: float
    walls: tuple[Wall, ...]
    openings: tuple[dict[str, Any], ...]
    placement: dict[str, Any]
    furnishings: tuple[dict[str, Any], ...]
    output: dict[str, Any]
    package_overall: dict[str, float]
    centroid: Point

    def input_document(self) -> dict[str, Any]:
        room: dict[str, Any] = {
            "corners": [list(corner) for corner in self.corners],
            "height_mm": self.height_mm,
            "wall_thickness_mm": self.wall_thickness_mm,
        }
        openings = [
            {
                "wall": o["wall"],
                "type": o["type"],
                "offset_mm": o["offset_mm"],
                "width_mm": o["width_mm"],
                "height_mm": o["height_mm"],
                "sill_mm": o["sill_mm"],
            }
            for o in self.openings
        ]
        furnishings = [
            {
                "name": f["name"],
                "width_mm": f["width_mm"],
                "depth_mm": f["depth_mm"],
                "height_mm": f["height_mm"],
                "x_mm": f["x_mm"],
                "y_mm": f["y_mm"],
                "rotation_deg": f["rotation_deg"],
                "z_mm": f["z_mm"],
            }
            for f in self.furnishings
        ]
        output: dict[str, Any] = {"kind": self.output["kind"]}
        return {
            "kind": KIND,
            "schema_version": SCHEMA_VERSION,
            "units": UNITS,
            "room": room,
            "openings": openings,
            "placement": {"wall": self.placement["wall"], "offset_mm": self.placement["offset_mm"]},
            "furnishings": furnishings,
            "output": output,
        }


def _normalise_corners(raw: Any) -> tuple[Point, ...]:
    if not isinstance(raw, Sequence) or isinstance(raw, (str, bytes)):
        _fail("room.corners must be a list of [x, y] points")
    if not (MIN_CORNERS <= len(raw) <= MAX_CORNERS):
        _fail(f"room.corners must have between {MIN_CORNERS} and {MAX_CORNERS} points")
    corners: list[Point] = []
    for index, point in enumerate(raw):
        if not isinstance(point, Sequence) or isinstance(point, (str, bytes)) or len(point) != 2:
            _fail(f"room.corners[{index}] must be a [x, y] pair")
        x = _number(point[0], f"room.corners[{index}].x", allow_zero=True, maximum=_MAX_ROOM_DIMENSION_MM * 2)
        y = _number(point[1], f"room.corners[{index}].y", allow_zero=True, maximum=_MAX_ROOM_DIMENSION_MM * 2)
        corners.append((x, y))

    area2 = _signed_area_x2(corners)
    if abs(area2) < _TOL:
        _fail("room.corners must enclose a non-zero area")
    if area2 < 0:
        corners = list(reversed(corners))
    if not _is_convex_ccw(corners):
        _fail("room.corners must form a convex polygon")
    return tuple(corners)


def _build_walls(corners: Sequence[Point]) -> tuple[Wall, ...]:
    n = len(corners)
    walls = []
    for i in range(n):
        ax, ay = corners[i]
        bx, by = corners[(i + 1) % n]
        dx, dy = bx - ax, by - ay
        length = math.hypot(dx, dy)
        ux, uy = dx / length, dy / length
        # Right of travel is outward for a CCW polygon (the same convention
        # `reference/mockup/build_listening_wall.py`'s `wall()` helper uses).
        walls.append(
            Wall(
                index=i,
                start=(ax, ay),
                end=(bx, by),
                length_mm=length,
                direction=(ux, uy),
                outward_normal=(uy, -ux),
            )
        )
    return tuple(walls)


def _normalise_openings(raw: Any, walls: Sequence[Wall], ceiling_mm: float) -> tuple[dict[str, Any], ...]:
    if raw is None:
        raw = []
    if not isinstance(raw, Sequence) or isinstance(raw, (str, bytes)):
        _fail("openings must be a list")
    openings: list[dict[str, Any]] = []
    for index, item in enumerate(raw):
        label = f"openings[{index}]"
        _require_keys(item, _OPENING_REQUIRED, _OPENING_OPTIONAL, label)
        wall_index = item["wall"]
        if not isinstance(wall_index, int) or isinstance(wall_index, bool) or not (0 <= wall_index < len(walls)):
            _fail(f"{label}.wall must be a valid wall index (0..{len(walls) - 1})")
        opening_type = item["type"]
        if opening_type not in _OPENING_TYPES:
            _fail(f"{label}.type must be one of {sorted(_OPENING_TYPES)}")
        offset = _number(item["offset_mm"], f"{label}.offset_mm", allow_zero=True)
        width = _number(item["width_mm"], f"{label}.width_mm")
        height = _number(item["height_mm"], f"{label}.height_mm")
        sill = _number(item.get("sill_mm", 0), f"{label}.sill_mm", allow_zero=True)
        if opening_type == "door" and sill != 0:
            _fail(f"{label} is a door and must not have a sill")
        wall_length = walls[wall_index].length_mm
        if offset + width > wall_length + _TOL:
            _fail(
                f"{label} does not fit wall {wall_index} "
                f"(needs {offset + width:.1f} mm, wall is {wall_length:.1f} mm)"
            )
        if sill + height > ceiling_mm + _TOL:
            _fail(f"{label} rises above the ceiling")
        openings.append(
            {
                "wall": wall_index,
                "type": opening_type,
                "offset_mm": offset,
                "width_mm": width,
                "height_mm": height,
                "sill_mm": sill,
            }
        )

    by_wall: dict[int, list[dict[str, Any]]] = {}
    for opening in openings:
        by_wall.setdefault(opening["wall"], []).append(opening)
    for wall_index, group in by_wall.items():
        ordered = sorted(group, key=lambda o: o["offset_mm"])
        for first, second in pairwise(ordered):
            if second["offset_mm"] < first["offset_mm"] + first["width_mm"] - _TOL:
                _fail(f"openings on wall {wall_index} overlap")
    return tuple(openings)


def _normalise_placement(
    raw: Any, walls: Sequence[Wall], corners: Sequence[Point], ceiling_mm: float, package_overall: Mapping[str, float]
) -> dict[str, Any]:
    _require_keys(raw, _PLACEMENT_KEYS, frozenset(), "placement")
    wall_index = raw["wall"]
    if not isinstance(wall_index, int) or isinstance(wall_index, bool) or not (0 <= wall_index < len(walls)):
        _fail(f"placement.wall must be a valid wall index (0..{len(walls) - 1})")
    offset = _number(raw["offset_mm"], "placement.offset_mm", allow_zero=True)

    wall = walls[wall_index]
    package_w = package_overall["w"]
    package_d = package_overall["d"]
    package_h = package_overall["h"]
    if offset + package_w > wall.length_mm + _TOL:
        _fail(
            f"the package does not fit wall {wall_index} "
            f"(needs {offset + package_w:.1f} mm, wall is {wall.length_mm:.1f} mm)"
        )
    if package_h > ceiling_mm + _TOL:
        _fail("the package is taller than the ceiling")

    ax, ay = wall.start
    ux, uy = wall.direction
    nx, ny = wall.outward_normal
    back_left = (ax + ux * offset, ay + uy * offset)
    back_right = (ax + ux * (offset + package_w), ay + uy * (offset + package_w))
    front_left = (back_left[0] - nx * package_d, back_left[1] - ny * package_d)
    front_right = (back_right[0] - nx * package_d, back_right[1] - ny * package_d)
    footprint = (back_left, back_right, front_right, front_left)
    for corner in footprint:
        if not _point_in_convex_polygon(corner, corners):
            _fail(f"the package's footprint on wall {wall_index} leaves the room")

    center = (
        (back_left[0] + back_right[0] + front_left[0] + front_right[0]) / 4,
        (back_left[1] + back_right[1] + front_left[1] + front_right[1]) / 4,
    )
    return {
        "wall": wall_index,
        "offset_mm": offset,
        "footprint": footprint,
        "center": center,
        "outward_normal": wall.outward_normal,
    }


def _normalise_furnishings(
    raw: Any, corners: Sequence[Point], package_footprint: Sequence[Point]
) -> tuple[dict[str, Any], ...]:
    if raw is None:
        raw = []
    if not isinstance(raw, Sequence) or isinstance(raw, (str, bytes)):
        _fail("furnishings must be a list")
    furnishings: list[dict[str, Any]] = []
    seen_names: set[str] = set()
    for index, item in enumerate(raw):
        label = f"furnishings[{index}]"
        _require_keys(item, _FURNISHING_REQUIRED, _FURNISHING_OPTIONAL, label)
        name = item["name"]
        if not isinstance(name, str) or not name.strip():
            _fail(f"{label}.name must be a non-blank string")
        name = name.strip()
        if name in seen_names:
            _fail(f"furnishing name {name!r} is used more than once")
        seen_names.add(name)

        width = _number(item["width_mm"], f"{label}.width_mm")
        depth = _number(item["depth_mm"], f"{label}.depth_mm")
        height = _number(item["height_mm"], f"{label}.height_mm")
        x = _number(item["x_mm"], f"{label}.x_mm", allow_zero=True, maximum=_MAX_ROOM_DIMENSION_MM * 2)
        y = _number(item["y_mm"], f"{label}.y_mm", allow_zero=True, maximum=_MAX_ROOM_DIMENSION_MM * 2)
        rotation = item["rotation_deg"]
        if isinstance(rotation, bool) or not isinstance(rotation, Real):
            _fail(f"{label}.rotation_deg must be a number")
        rotation = float(rotation)
        z = _number(item.get("z_mm", 0), f"{label}.z_mm", allow_zero=True)

        footprint = _rotated_footprint(x, y, width, depth, rotation)
        for corner in footprint:
            if not _point_in_convex_polygon(corner, corners):
                _fail(f"{label} ({name}) leaves the room")
        if _rectangles_overlap(footprint, package_footprint):
            _fail(f"{label} ({name}) overlaps the package")

        furnishings.append(
            {
                "name": name,
                "width_mm": width,
                "depth_mm": depth,
                "height_mm": height,
                "x_mm": x,
                "y_mm": y,
                "rotation_deg": rotation,
                "z_mm": z,
                "footprint": footprint,
            }
        )
    return tuple(furnishings)


def _normalise_output(raw: Any) -> dict[str, Any]:
    """`output` names a kind and nothing else: the render tier decides frames,
    resolution and engine, so `frames` and `resolution` are unknown fields here
    and refused by name like any other (render-guard design decision 7)."""
    if not isinstance(raw, Mapping):
        _fail("output must be an object")
    kind = raw.get("kind")
    if kind not in _OUTPUT_KINDS:
        _fail(f"output.kind must be one of {sorted(_OUTPUT_KINDS)}")
    _require_keys(raw, frozenset({"kind"}), frozenset(), "output")
    return {"kind": kind}


def normalise_room_scene(
    document: Mapping[str, Any], *, package_overall: Mapping[str, float]
) -> RoomBuildContext:
    """Validate a JSON-shaped room-scene document and derive its geometry.

    `package_overall` is the furniture package's already-validated `{w, h,
    d}` overall dimensions (`spec_contract.BuildContext.overall` on the
    service side, the published `spec.json`'s `overall` on the Blender side).
    """
    if not isinstance(document, Mapping):
        _fail("specification must be a JSON object")
    _require_keys(document, _TOP_LEVEL_REQUIRED, _TOP_LEVEL_OPTIONAL, "specification")
    if document["kind"] != KIND:
        _fail(f"kind must be {KIND!r}")
    if document["schema_version"] != SCHEMA_VERSION:
        _fail(f"schema_version must be {SCHEMA_VERSION}")
    if document["units"] != UNITS:
        _fail("units must be 'mm'")

    room = document["room"]
    _require_keys(room, _ROOM_REQUIRED, _ROOM_OPTIONAL, "room")
    corners = _normalise_corners(room["corners"])
    height_mm = _number(room["height_mm"], "room.height_mm", maximum=_MAX_CEILING_MM)
    wall_thickness_mm = _number(
        room.get("wall_thickness_mm", DEFAULT_WALL_THICKNESS_MM), "room.wall_thickness_mm"
    )
    walls = _build_walls(corners)

    openings = _normalise_openings(document.get("openings"), walls, height_mm)
    placement = _normalise_placement(document["placement"], walls, corners, height_mm, package_overall)
    furnishings = _normalise_furnishings(document.get("furnishings"), corners, placement["footprint"])
    output = _normalise_output(document["output"])

    centroid = (
        sum(x for x, _ in corners) / len(corners),
        sum(y for _, y in corners) / len(corners),
    )

    return RoomBuildContext(
        corners=corners,
        height_mm=height_mm,
        wall_thickness_mm=wall_thickness_mm,
        walls=walls,
        openings=openings,
        placement=placement,
        furnishings=furnishings,
        output=output,
        package_overall={"w": package_overall["w"], "h": package_overall["h"], "d": package_overall["d"]},
        centroid=centroid,
    )
