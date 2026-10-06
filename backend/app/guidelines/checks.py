"""The closed set of design checks the rules table can name (design-guidelines spec).

Placement checks read a normalised room-scene context (the footprint, the walls
and the openings); piece checks read a normalised `custom_build` document. A
check measures; the rule's limit and severity come from `config/design_rules.yaml`.
"""

from __future__ import annotations

import math
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Final

from pydantic import BaseModel, ConfigDict, Field

from app.blender.room_contract import Point, RoomBuildContext

Applies = str  # "placement" | "piece"


@dataclass(frozen=True, slots=True)
class Measurement:
    """What a check found: a value against a limit, in a unit, and whether it is a breach."""

    what: str
    value: str
    limit: str
    breached: bool


class FrontClearance(BaseModel):
    model_config = ConfigDict(extra="forbid")
    min_mm: float = Field(gt=0)


class DoorSwingClear(BaseModel):
    model_config = ConfigDict(extra="forbid")


class HeightRange(BaseModel):
    model_config = ConfigDict(extra="forbid")
    match: list[str] = Field(min_length=1, description="words found in a module's id or name")
    min_mm: float = Field(gt=0)
    max_mm: float = Field(gt=0)


class SpanEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")
    thickness_mm: int = Field(gt=0)
    max_span_mm: float = Field(gt=0)


class ShelfSpan(BaseModel):
    model_config = ConfigDict(extra="forbid")
    table: list[SpanEntry] = Field(min_length=1)


# --- placement checks ------------------------------------------------------------


def _ray_distance(origin: Point, direction: Point, corners: Sequence[Point]) -> float | None:
    """The distance from `origin` along `direction` to the nearest polygon edge, or `None`."""
    best: float | None = None
    ox, oy = origin
    dx, dy = direction
    n = len(corners)
    for i in range(n):
        (ax, ay), (bx, by) = corners[i], corners[(i + 1) % n]
        ex, ey = bx - ax, by - ay
        denominator = dx * ey - dy * ex
        if abs(denominator) < 1e-9:
            continue
        t = ((ax - ox) * ey - (ay - oy) * ex) / denominator
        u = ((ax - ox) * dy - (ay - oy) * dx) / denominator
        if t > 1e-6 and -1e-9 <= u <= 1 + 1e-9 and (best is None or t < best):
            best = t
    return best


def front_clearance(context: RoomBuildContext, params: FrontClearance) -> list[Measurement]:
    """The clear passage in front of the piece: the shortest free run from its front face to a wall.

    Three rays (both front corners, nudged inward, and the middle) are cast along
    the inward normal; walls only, since `room_fit` places a single piece.
    """
    _back_left, _back_right, front_right, front_left = context.placement["footprint"]
    nx, ny = context.placement["outward_normal"]
    direction = (-nx, -ny)
    middle = ((front_left[0] + front_right[0]) / 2, (front_left[1] + front_right[1]) / 2)
    ux, uy = front_right[0] - front_left[0], front_right[1] - front_left[1]
    length = math.hypot(ux, uy) or 1.0
    nudge = min(1.0, length / 4)
    left = (front_left[0] + ux / length * nudge, front_left[1] + uy / length * nudge)
    right = (front_right[0] - ux / length * nudge, front_right[1] - uy / length * nudge)
    runs = [d for d in (_ray_distance(p, direction, context.corners) for p in (left, middle, right)) if d is not None]
    if not runs:
        return []
    clear = min(runs)
    return [Measurement(
        what="clear passage in front of the piece", value=f"{clear:g} mm",
        limit=f"at least {params.min_mm:g} mm", breached=clear < params.min_mm,
    )]


def _swing_area(opening: Mapping[str, Any], wall: Any) -> list[Point]:
    """The square in front of a door that its leaf sweeps: the opening's width, that far into the room."""
    ax, ay = wall.start
    ux, uy = wall.direction
    nx, ny = wall.outward_normal
    width = float(opening["width_mm"])
    start = float(opening["offset_mm"])
    a = (ax + ux * start, ay + uy * start)
    b = (ax + ux * (start + width), ay + uy * (start + width))
    return [a, b, (b[0] - nx * width, b[1] - ny * width), (a[0] - nx * width, a[1] - ny * width)]


def _axes(polygon: Sequence[Point]) -> list[Point]:
    out = []
    for i in range(len(polygon)):
        (ax, ay), (bx, by) = polygon[i], polygon[(i + 1) % len(polygon)]
        out.append((-(by - ay), bx - ax))
    return out


def _overlap_depth(a: Sequence[Point], b: Sequence[Point]) -> float:
    """How far two convex polygons interpenetrate (0 when they only touch or are apart)."""
    least: float | None = None
    for ax, ay in (*_axes(a), *_axes(b)):
        norm = math.hypot(ax, ay) or 1.0
        pa = [(x * ax + y * ay) / norm for x, y in a]
        pb = [(x * ax + y * ay) / norm for x, y in b]
        depth = min(max(pa), max(pb)) - max(min(pa), min(pb))
        if depth <= 1e-6:
            return 0.0
        least = depth if least is None else min(least, depth)
    return least or 0.0


def door_swing_clear(context: RoomBuildContext, _params: DoorSwingClear) -> list[Measurement]:
    footprint = list(context.placement["footprint"])
    found = []
    for index, opening in enumerate(context.openings):
        if opening["type"] != "door":
            continue
        depth = _overlap_depth(footprint, _swing_area(opening, context.walls[opening["wall"]]))
        found.append(Measurement(
            what=f"overlap with the swing area of the door on wall {opening['wall']} (opening {index})",
            value=f"{depth:g} mm", limit="no overlap", breached=depth > 0,
        ))
    return found


# --- piece checks ----------------------------------------------------------------


def height_range(spec: Mapping[str, Any], params: HeightRange) -> list[Measurement]:
    """The top face of each module whose id or name holds one of the words."""
    words = [w.lower() for w in params.match]
    found = []
    for module in spec.get("modules", []):
        label = f"{module['id']} {module['name']}".lower()
        if not any(word in label for word in words):
            continue
        top = module["z"] + module["height"]
        found.append(Measurement(
            what=f"top face of module {module['id']!r}", value=f"{top:g} mm",
            limit=f"{params.min_mm:g} to {params.max_mm:g} mm", breached=not params.min_mm <= top <= params.max_mm,
        ))
    return found


def shelf_span(spec: Mapping[str, Any], params: ShelfSpan) -> list[Measurement]:
    """A shelf's span (the carcass's inner width) against the limit for its board thickness.

    The limit is the table entry for the board's thickness, or for the next thinner
    one; a board thinner than every entry has no stated limit and is not judged.
    """
    table = sorted(params.table, key=lambda entry: entry.thickness_mm)
    found = []
    for module in spec.get("modules", []):
        if not module.get("shelves"):
            continue
        thickness = spec["materials"][module["carcass"]]["thickness_mm"]
        entry = max((e for e in table if e.thickness_mm <= thickness), key=lambda e: e.thickness_mm, default=None)
        if entry is None:
            continue
        span = module["width"] - 2 * thickness
        found.append(Measurement(
            what=f"shelf span in module {module['id']!r} ({thickness} mm board)", value=f"{span:g} mm",
            limit=f"at most {entry.max_span_mm:g} mm", breached=span > entry.max_span_mm,
        ))
    return found


@dataclass(frozen=True, slots=True)
class CheckSpec:
    applies_to: Applies
    params: type[BaseModel]
    run: Callable[[Any, Any], list[Measurement]]


CHECKS: Final[dict[str, CheckSpec]] = {
    "front_clearance_mm": CheckSpec("placement", FrontClearance, front_clearance),
    "door_swing_clear": CheckSpec("placement", DoorSwingClear, door_swing_clear),
    "height_range_mm": CheckSpec("piece", HeightRange, height_range),
    "shelf_span_mm_for_thickness": CheckSpec("piece", ShelfSpan, shelf_span),
}
