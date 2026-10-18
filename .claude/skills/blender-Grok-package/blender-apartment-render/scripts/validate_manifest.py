#!/usr/bin/env python3
"""Validate an apartment measurement manifest before Blender generation."""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path


def fail(errors: list[str], message: str) -> None:
    errors.append(message)


def as_point(value, label: str, errors: list[str]) -> tuple[float, float] | None:
    if not isinstance(value, (list, tuple)) or len(value) < 2:
        fail(errors, f"{label} must be [x, y]")
        return None
    try:
        return float(value[0]), float(value[1])
    except (TypeError, ValueError):
        fail(errors, f"{label} coordinates must be numbers")
        return None


def signed_area(points: list[tuple[float, float]]) -> float:
    area = 0.0
    for i, (x1, y1) in enumerate(points):
        x2, y2 = points[(i + 1) % len(points)]
        area += x1 * y2 - x2 * y1
    return area / 2.0


def validate(data: dict) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []

    if data.get("units") not in (None, "meters"):
        fail(errors, "units must be meters; convert the plan before generating")

    height = data.get("ceiling_height_m", 2.5)
    thickness = data.get("wall_thickness_m", 0.12)
    if not isinstance(height, (int, float)) or height <= 1.8 or height > 6:
        fail(errors, "ceiling_height_m should be between 1.8 and 6")
    if not isinstance(thickness, (int, float)) or thickness <= 0 or thickness > 0.6:
        fail(errors, "wall_thickness_m should be between 0 and 0.6")

    rooms = data.get("rooms")
    if not isinstance(rooms, list) or not rooms:
        fail(errors, "rooms must be a non-empty list")
        return errors, warnings

    room_ids = set()
    for room in rooms:
        rid = room.get("id")
        if not rid or rid in room_ids:
            fail(errors, f"room id missing or duplicated: {rid}")
            continue
        room_ids.add(rid)
        raw = room.get("polygon") or []
        points = []
        for i, p in enumerate(raw):
            point = as_point(p, f"{rid}.polygon[{i}]", errors)
            if point:
                points.append(point)
        if len(points) >= 2 and points[0] == points[-1]:
            points = points[:-1]
            warnings.append(f"{rid}: dropped repeated closing vertex")
        if len(points) < 3:
            fail(errors, f"{rid}: polygon needs at least 3 vertices")
            continue
        for i, a in enumerate(points):
            b = points[(i + 1) % len(points)]
            if math.dist(a, b) < 0.05:
                fail(errors, f"{rid}: edge {i} is shorter than 5 cm")
        area = signed_area(points)
        if abs(area) < 0.5:
            fail(errors, f"{rid}: area {abs(area):.2f} m² is implausibly small")
        if area < 0:
            warnings.append(f"{rid}: polygon is clockwise; generator will reverse it")

    openings = data.get("openings") or []
    for opening in openings:
        oid = opening.get("id", "<unnamed>")
        if opening.get("room") and opening["room"] not in room_ids:
            fail(errors, f"{oid}: room {opening['room']} does not exist")
        if opening.get("kind") not in ("window", "door", "opening"):
            fail(errors, f"{oid}: kind must be window, door, or opening")
        as_point(opening.get("from"), f"{oid}.from", errors)
        as_point(opening.get("to"), f"{oid}.to", errors)
        width = opening.get("width_m")
        height_o = opening.get("height_m")
        sill = opening.get("sill_m", 0)
        if not isinstance(width, (int, float)) or width < 0.3:
            fail(errors, f"{oid}: width_m must be >= 0.3")
        if not isinstance(height_o, (int, float)) or height_o < 0.3:
            fail(errors, f"{oid}: height_m must be >= 0.3")
        if isinstance(sill, (int, float)) and isinstance(height_o, (int, float)):
            if sill + height_o > height + 0.05:
                fail(errors, f"{oid}: sill + height exceeds ceiling")

    for photo in data.get("photos") or []:
        pid = photo.get("id", "<unnamed>")
        if photo.get("room") and photo["room"] not in room_ids:
            fail(errors, f"{pid}: room {photo['room']} does not exist")
        cam = photo.get("camera") or {}
        loc = cam.get("location")
        look = cam.get("look_at")
        if loc is not None and (not isinstance(loc, list) or len(loc) != 3):
            fail(errors, f"{pid}: camera.location must be [x, y, z]")
        if look is not None and (not isinstance(look, list) or len(look) != 3):
            fail(errors, f"{pid}: camera.look_at must be [x, y, z]")
        if not photo.get("file"):
            warnings.append(f"{pid}: no file path; camera match cannot be checked visually")

    return errors, warnings


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate an apartment manifest")
    parser.add_argument("manifest", type=Path)
    args = parser.parse_args()
    data = json.loads(args.manifest.read_text())
    errors, warnings = validate(data)
    rooms = data.get("rooms") or []
    print(f"project: {data.get('project', 'untitled')}")
    print(f"rooms: {len(rooms)}  openings: {len(data.get('openings') or [])}  photos: {len(data.get('photos') or [])}")
    for warning in warnings:
        print(f"warning: {warning}")
    if errors:
        for error in errors:
            print(f"error: {error}")
        return 1
    print("valid")
    return 0


if __name__ == "__main__":
    sys.exit(main())
