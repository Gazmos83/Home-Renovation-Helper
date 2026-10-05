"""Dependency-free apartment-shell input contract, shared with Blender.

Standard-library only, like `room_contract`, so a background `bpy` process and
the FastAPI service validate the same document and derive the same walls. An
apartment is several rooms in one plan frame (millimetres). Each room is checked
by the room rules; rooms of one apartment must not overlap in area; an edge two
rooms share is one wall, built once and centred on the shared line, while an
edge on the outside is extruded outward from its interior face.

Plausibility checks (door width, sill, ceiling, area against a printed area) are
warnings, never refusals: a real flat may be unusual.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from itertools import pairwise
from typing import Any, Final

from app.blender.room_contract import (
    DEFAULT_WALL_THICKNESS_MM,
    _signed_area_x2,
    normalise_room_shell,
)
from app.blender.spec_contract import SpecValidationError

KIND: Final = "apartment_shell"
SCHEMA_VERSION: Final = 1
UNITS: Final = "mm"

MAX_ROOMS: Final = 24
SHARED_TOLERANCE_MM: Final = 1.0
DOOR_WIDTH_RANGE_MM: Final = (700, 1000)
SILL_RANGE_MM: Final = (700, 1100)
CEILING_RANGE_MM: Final = (2300, 3200)
AREA_TOLERANCE: Final = 0.05

Point = tuple[float, float]


def _fail(message: str) -> None:
    raise SpecValidationError(message)


@dataclass(frozen=True)
class ShellRoom:
    name: str
    corners: tuple[Point, ...]
    height_mm: float
    openings: tuple[dict[str, Any], ...]


@dataclass(frozen=True)
class ShellWall:
    """One physical wall: a segment between two plan points."""

    id: str
    a: Point
    b: Point
    length_mm: float
    shared: bool
    rooms: tuple[str, ...]
    openings: tuple[dict[str, Any], ...]


@dataclass(frozen=True)
class ShellContext:
    name: str
    ceiling_height_mm: float
    wall_thickness_mm: float
    rooms: tuple[ShellRoom, ...]
    walls: tuple[ShellWall, ...]
    warnings: tuple[str, ...] = field(default=())

    def input_document(self) -> dict[str, Any]:
        return {
            "kind": KIND,
            "schema_version": SCHEMA_VERSION,
            "units": UNITS,
            "apartment": {
                "name": self.name,
                "ceiling_height_mm": self.ceiling_height_mm,
                "wall_thickness_mm": self.wall_thickness_mm,
            },
            "rooms": [
                {
                    "name": room.name,
                    "corners": [list(c) for c in room.corners],
                    "height_mm": room.height_mm,
                    "openings": [dict(o) for o in room.openings],
                }
                for room in self.rooms
            ],
        }


def polygon_area_m2(corners: Sequence[Point]) -> float:
    return abs(_signed_area_x2(corners)) / 2 / 1_000_000


# --- rooms must not overlap --------------------------------------------------------------


def _distance_to_segment(point: Point, a: Point, b: Point) -> float:
    dx, dy = b[0] - a[0], b[1] - a[1]
    length2 = dx * dx + dy * dy
    if length2 == 0:
        return math.hypot(point[0] - a[0], point[1] - a[1])
    t = max(0.0, min(1.0, ((point[0] - a[0]) * dx + (point[1] - a[1]) * dy) / length2))
    return math.hypot(point[0] - (a[0] + t * dx), point[1] - (a[1] + t * dy))


def _cross(o: Point, a: Point, b: Point) -> float:
    return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])


def _in_triangle(p: Point, a: Point, b: Point, c: Point) -> bool:
    return _cross(a, b, p) >= 0 and _cross(b, c, p) >= 0 and _cross(c, a, p) >= 0


def _triangulate(corners: Sequence[Point]) -> list[tuple[Point, Point, Point]]:
    """Ear-clip a counter-clockwise simple polygon into counter-clockwise triangles."""
    remaining = list(corners)
    triangles: list[tuple[Point, Point, Point]] = []
    while len(remaining) > 3:
        n = len(remaining)
        for i in range(n):
            a, b, c = remaining[i - 1], remaining[i], remaining[(i + 1) % n]
            if _cross(a, b, c) <= 1e-9:
                continue  # a reflex or straight vertex is not an ear
            if any(
                _in_triangle(p, a, b, c) for p in remaining if p not in (a, b, c)
            ):
                continue
            triangles.append((a, b, c))
            del remaining[i]
            break
        else:  # a degenerate sliver: drop a vertex so the loop ends
            del remaining[0]
    if len(remaining) == 3 and _cross(*remaining) > 1e-9:
        triangles.append((remaining[0], remaining[1], remaining[2]))
    return triangles


def _triangles_overlap(first: Sequence[Point], second: Sequence[Point]) -> bool:
    """Whether two triangles share area (touching is not overlap)."""
    for triangle in (first, second):
        for i in range(3):
            a, b = triangle[i], triangle[(i + 1) % 3]
            nx, ny = b[1] - a[1], a[0] - b[0]
            length = math.hypot(nx, ny)
            if length == 0:
                continue
            nx, ny = nx / length, ny / length
            p = [x * nx + y * ny for x, y in first]
            q = [x * nx + y * ny for x, y in second]
            if max(p) <= min(q) + SHARED_TOLERANCE_MM or max(q) <= min(p) + SHARED_TOLERANCE_MM:
                return False
    return True


def rooms_overlap(first: Sequence[Point], second: Sequence[Point]) -> bool:
    """Whether two simple polygons share area (touching along an edge is not overlap)."""
    second_triangles = _triangulate(second)
    return any(
        _triangles_overlap(t1, t2) for t1 in _triangulate(first) for t2 in second_triangles
    )


# --- shared walls ------------------------------------------------------------------------


@dataclass(frozen=True)
class _Edge:
    room: int
    index: int
    a: Point
    b: Point

    @property
    def length(self) -> float:
        return math.hypot(self.b[0] - self.a[0], self.b[1] - self.a[1])

    def direction(self) -> Point:
        length = self.length
        return ((self.b[0] - self.a[0]) / length, (self.b[1] - self.a[1]) / length)

    def param(self, point: Point) -> float:
        ux, uy = self.direction()
        return (point[0] - self.a[0]) * ux + (point[1] - self.a[1]) * uy


def _shared_interval(first: _Edge, second: _Edge) -> tuple[float, float] | None:
    """The interval along `first` that `second` overlaps, when they are collinear
    and opposite in direction (adjacent rooms); else `None`."""
    u = first.direction()
    v = second.direction()
    if abs(u[0] * v[1] - u[1] * v[0]) > 1e-3 or u[0] * v[0] + u[1] * v[1] > 0:
        return None
    for end in (second.a, second.b):
        # Perpendicular distance of the other edge's endpoints from this edge's line.
        if abs((end[0] - first.a[0]) * u[1] - (end[1] - first.a[1]) * u[0]) > SHARED_TOLERANCE_MM:
            return None
    lo = max(0.0, min(first.param(second.a), first.param(second.b)))
    hi = min(first.length, max(first.param(second.a), first.param(second.b)))
    return (lo, hi) if hi - lo > SHARED_TOLERANCE_MM else None


def _point_at(edge: _Edge, t: float) -> Point:
    ux, uy = edge.direction()
    return (edge.a[0] + ux * t, edge.a[1] + uy * t)


def _build_walls(rooms: Sequence[ShellRoom]) -> tuple[ShellWall, ...]:
    edges: list[_Edge] = []
    for r, room in enumerate(rooms):
        n = len(room.corners)
        for i in range(n):
            edges.append(_Edge(r, i, room.corners[i], room.corners[(i + 1) % n]))

    # For each edge, the intervals it shares with edges of other rooms.
    shared: dict[tuple[int, int], list[tuple[float, float, _Edge]]] = {}
    for first in edges:
        for second in edges:
            if first.room == second.room:
                continue
            interval = _shared_interval(first, second)
            if interval is not None:
                shared.setdefault((first.room, first.index), []).append((*interval, second))

    walls: list[ShellWall] = []

    def add_wall(a: Point, b: Point, is_shared: bool, names: tuple[str, ...], openings: list[dict[str, Any]]) -> None:
        walls.append(
            ShellWall(
                id=f"wall-{len(walls) + 1}",
                a=a,
                b=b,
                length_mm=math.hypot(b[0] - a[0], b[1] - a[1]),
                shared=is_shared,
                rooms=names,
                openings=tuple(sorted(openings, key=lambda o: o["offset_mm"])),
            )
        )

    for edge in edges:
        room = rooms[edge.room]
        own = [o for o in room.openings if o["wall"] == edge.index]
        intervals = sorted(shared.get((edge.room, edge.index), []), key=lambda item: item[0])
        cursor = 0.0
        pieces: list[tuple[float, float, _Edge | None]] = []
        for lo, hi, partner in intervals:
            if lo - cursor > SHARED_TOLERANCE_MM:
                pieces.append((cursor, lo, None))
            pieces.append((lo, hi, partner))
            cursor = hi
        if edge.length - cursor > SHARED_TOLERANCE_MM:
            pieces.append((cursor, edge.length, None))

        for lo, hi, partner in pieces:
            if partner is not None and partner.room < edge.room:
                continue  # the lower-numbered room's edge builds the shared wall
            inside = []
            for opening in own:
                start, end = opening["offset_mm"], opening["offset_mm"] + opening["width_mm"]
                if start >= lo - SHARED_TOLERANCE_MM and end <= hi + SHARED_TOLERANCE_MM:
                    inside.append({**opening, "offset_mm": start - lo})
                elif end > lo + SHARED_TOLERANCE_MM and start < hi - SHARED_TOLERANCE_MM:
                    _fail(
                        f"room {room.name!r} opening on wall {edge.index} crosses the boundary "
                        "between a shared wall and an outer wall"
                    )
            if partner is None:
                add_wall(_point_at(edge, lo), _point_at(edge, hi), False, (room.name,), inside)
                continue
            # The partner's openings, converted to this wall's offsets.
            other = rooms[partner.room]
            for opening in (o for o in other.openings if o["wall"] == partner.index):
                p0 = _point_at(partner, opening["offset_mm"])
                p1 = _point_at(partner, opening["offset_mm"] + opening["width_mm"])
                t0, t1 = sorted((edge.param(p0), edge.param(p1)))
                if t1 <= lo + SHARED_TOLERANCE_MM or t0 >= hi - SHARED_TOLERANCE_MM:
                    continue
                converted = {**opening, "offset_mm": t0 - lo, "width_mm": t1 - t0}
                twin = next(
                    (
                        o
                        for o in inside
                        if o["type"] == converted["type"]
                        and abs(o["offset_mm"] - converted["offset_mm"]) <= 5
                        and abs(o["width_mm"] - converted["width_mm"]) <= 5
                    ),
                    None,
                )
                if twin is None:
                    inside.append(converted)
            inside.sort(key=lambda o: o["offset_mm"])
            for first, second in pairwise(inside):
                if second["offset_mm"] < first["offset_mm"] + first["width_mm"] - SHARED_TOLERANCE_MM:
                    _fail(f"openings on the wall shared by {room.name!r} and {other.name!r} overlap")
            add_wall(_point_at(edge, lo), _point_at(edge, hi), True, (room.name, other.name), inside)
    return tuple(walls)


# --- plausibility ------------------------------------------------------------------------


def plausibility_warnings(
    rooms: Sequence[ShellRoom], printed_areas_m2: Mapping[str, float] | None = None
) -> tuple[str, ...]:
    """Warnings (never refusals) for figures outside the usual ranges."""
    warnings: list[str] = []
    low, high = CEILING_RANGE_MM
    for room in rooms:
        if not low <= room.height_mm <= high:
            warnings.append(
                f"{room.name}: ceiling {room.height_mm:g} mm is outside the usual {low}–{high} mm"
            )
        for index, opening in enumerate(room.openings):
            if opening["type"] == "door":
                lo, hi = DOOR_WIDTH_RANGE_MM
                if not lo <= opening["width_mm"] <= hi:
                    warnings.append(
                        f"{room.name}: door {index} is {opening['width_mm']:g} mm wide, "
                        f"outside the usual {lo}–{hi} mm"
                    )
            else:
                lo, hi = SILL_RANGE_MM
                if not lo <= opening["sill_mm"] <= hi:
                    warnings.append(
                        f"{room.name}: window {index} has a {opening['sill_mm']:g} mm sill, "
                        f"outside the usual {lo}–{hi} mm"
                    )
        printed = (printed_areas_m2 or {}).get(room.name)
        if printed:
            measured = polygon_area_m2(room.corners)
            if abs(measured - printed) / printed > AREA_TOLERANCE:
                warnings.append(
                    f"{room.name}: the outline gives {measured:.2f} m² but the plan prints "
                    f"{printed:.2f} m² (more than {AREA_TOLERANCE:.0%} apart)"
                )
    return tuple(warnings)


# --- the document ------------------------------------------------------------------------


def _number(value: Any, field_name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        _fail(f"{field_name} must be a number")
    if value <= 0:
        _fail(f"{field_name} must be greater than zero")
    return float(value)


def normalise_shell(
    document: Mapping[str, Any], *, printed_areas_m2: Mapping[str, float] | None = None
) -> ShellContext:
    """Validate an apartment-shell document and derive its walls and warnings."""
    if not isinstance(document, Mapping):
        _fail("specification must be a JSON object")
    allowed = {"kind", "schema_version", "units", "apartment", "rooms"}
    for key in document:
        if key not in allowed:
            _fail(f"specification: unknown field {key!r}")
    for key in allowed:
        if key not in document:
            _fail(f"specification: missing field {key!r}")
    if document["kind"] != KIND:
        _fail(f"kind must be {KIND!r}")
    if document["schema_version"] != SCHEMA_VERSION:
        _fail(f"schema_version must be {SCHEMA_VERSION}")
    if document["units"] != UNITS:
        _fail("units must be 'mm'")

    apartment = document["apartment"]
    if not isinstance(apartment, Mapping):
        _fail("apartment must be an object")
    name = apartment.get("name")
    if not isinstance(name, str) or not name.strip():
        _fail("apartment.name must be a non-blank string")
    ceiling = _number(apartment.get("ceiling_height_mm"), "apartment.ceiling_height_mm")
    thickness = _number(
        apartment.get("wall_thickness_mm", DEFAULT_WALL_THICKNESS_MM), "apartment.wall_thickness_mm"
    )

    raw_rooms = document["rooms"]
    if not isinstance(raw_rooms, Sequence) or isinstance(raw_rooms, (str, bytes)) or not raw_rooms:
        _fail("rooms must be a non-empty list")
    if len(raw_rooms) > MAX_ROOMS:
        _fail(f"rooms: at most {MAX_ROOMS} rooms")

    rooms: list[ShellRoom] = []
    seen: set[str] = set()
    for index, raw in enumerate(raw_rooms):
        label = f"rooms[{index}]"
        if not isinstance(raw, Mapping):
            _fail(f"{label} must be an object")
        for key in raw:
            if key not in {"name", "corners", "height_mm", "openings"}:
                _fail(f"{label}: unknown field {key!r}")
        room_name = raw.get("name")
        if not isinstance(room_name, str) or not room_name.strip():
            _fail(f"{label}.name must be a non-blank string")
        room_name = room_name.strip()
        if room_name in seen:
            _fail(f"room name {room_name!r} is used more than once")
        seen.add(room_name)
        height = raw.get("height_mm", ceiling)
        try:
            shell, openings = normalise_room_shell(
                {"corners": raw.get("corners"), "height_mm": height, "wall_thickness_mm": thickness},
                raw.get("openings"),
            )
        except SpecValidationError as error:
            raise SpecValidationError(f"room {room_name!r}: {error}") from None
        rooms.append(
            ShellRoom(
                name=room_name,
                corners=tuple((float(x), float(y)) for x, y in shell["corners"]),
                height_mm=float(shell["height_mm"]),
                openings=tuple(openings),
            )
        )

    for i, first in enumerate(rooms):
        for second in rooms[i + 1 :]:
            if rooms_overlap(first.corners, second.corners):
                _fail(f"rooms {first.name!r} and {second.name!r} overlap")

    walls = _build_walls(rooms)
    return ShellContext(
        name=name.strip(),
        ceiling_height_mm=ceiling,
        wall_thickness_mm=thickness,
        rooms=tuple(rooms),
        walls=walls,
        warnings=plausibility_warnings(rooms, printed_areas_m2),
    )
