"""Build a custom-build package inside Blender 5.2 in background mode.

Usage (the arguments after ``--`` belong to this script)::

    blender --background --python build_custom_build.py -- \
      --spec custom-build.json --out /absolute/new-package-directory

The shop data comes from ``app.blender.custom_build.derive`` — the same
standard-library module the backend derived the package's ``cutlist.csv`` and
``hardware.csv`` from when it was created — so the generated lists equal the
derived ones row for row. This script only adds geometry: one editable box
object per cut-list piece (the first named exactly by its cut-list id, any
further ones ``<id>#<n>``), parented to one empty per module so the studio can
explode them, fronts modelled closed, and each object in exactly one of the
layers ``carcass``, ``backs``, ``shelves``, ``fronts`` and ``extras``.

It also draws the overall width, height and depth as dimension lines with their
figures in mm (``DIM_*`` under ``MOD_Dimensions``), kept out of ``model.glb`` and
the iso screenshot, and writes Workbench views from the front, side and top with
the lines each view faces (piece-inspector).

It imports only the backend's standard-library contracts, never the FastAPI
environment. A build is not a render: it publishes `screenshot.png`, a Workbench
(solid-shading) frame for progress checks, and no Eevee or Cycles image
(render-guard design decision 5).
"""

from __future__ import annotations

import json
import math
import os
import shutil
import sys
import uuid
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import bpy
from mathutils import Vector

BACKEND_ROOT = Path(__file__).resolve().parents[3]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.blender.cli import (
    InputError,
    load_custom_build,
    load_hardware_inputs,
    parse_build_arguments,
)
from app.blender.custom_build import derive as rules
from app.blender.generators._scene import (
    GeneratorError,
    export_glb,
    face_camera,
    hidden,
    hidden_for_presentation,
    is_dimension,
    set_engine,
)
from app.blender.generators._scene import (
    add_camera as _add_camera,
)
from app.blender.generators._scene import (
    aim_at as _aim_at,
)
from app.blender.generators._scene import (
    collection as _collection,
)
from app.blender.generators._scene import (
    link as _link,
)
from app.blender.generators._scene import (
    reset_scene as _reset_scene,
)
from app.blender.layers import LayerRegistry
from app.blender.shop_csv import (
    CUTLIST_FIELDS,
    HARDWARE_FIELDS,
    write_csv,
)
from app.blender.verify import VerificationError, verify_build

MM = 0.001
SCREENSHOT_SIZE = (800, 500)
# Each straight-on view: its camera, its file, and the dimensions it faces.
VIEWS: tuple[tuple[str, str, frozenset[str]], ...] = (
    ("CAM_Front", "front.png", frozenset({"W", "H"})),
    ("CAM_Side", "side.png", frozenset({"D", "H"})),
    ("CAM_Top", "top.png", frozenset({"W", "D"})),
)
DIMENSION_OFFSET_MM = 100
INK = (0.03, 0.03, 0.035)
PAPER = (0.93, 0.9, 0.84)

Box = tuple[tuple[float, float, float], tuple[float, float, float]]  # (size, centre), mm


@dataclass(frozen=True)
class Placement:
    """One cut-list piece in build millimetres: a box, a rotated box, or an n-gon prism."""

    size: tuple[float, float, float]
    centre: tuple[float, float, float]
    rotation_deg: tuple[float, float, float] = (0.0, 0.0, 0.0)
    verts: tuple[tuple[float, float, float], ...] | None = None
    faces: tuple[tuple[int, ...], ...] | None = None


@dataclass
class BuildState:
    spec: Mapping[str, Any]
    inputs: Mapping[str, Any] | None = None
    materials: dict[str, bpy.types.Material] = field(default_factory=dict)
    layers: LayerRegistry = field(default_factory=lambda: LayerRegistry.for_layers(rules.LAYER_NAMES))


def m(value: float) -> float:
    return float(value) * MM


# --- where each cut-list piece sits --------------------------------------------------------


def _module_boxes(module: Mapping[str, Any], materials: Mapping[str, Any]) -> dict[str, tuple[str, list[Box]]]:
    """Every piece of one module, by cut-list row id: (layer, boxes in build millimetres)."""
    t = materials[module["carcass"]]["thickness_mm"]
    back = module.get("back")
    b = materials[back]["thickness_mm"] if back is not None else 0
    x, y, z = module["x"], module["y"], module["z"]
    width, height, depth = module["width"], module["height"], module["depth"]
    inner_w, inner_d = width - 2 * t, depth - b
    mid = module["id"]
    pieces: dict[str, tuple[str, list[Box]]] = {
        f"{mid}-side": (
            "carcass",
            [
                ((t, inner_d, height), (x + t / 2, y + inner_d / 2, z + height / 2)),
                ((t, inner_d, height), (x + width - t / 2, y + inner_d / 2, z + height / 2)),
            ],
        ),
        f"{mid}-top-bottom": (
            "carcass",
            [
                ((inner_w, inner_d, t), (x + width / 2, y + inner_d / 2, z + t / 2)),
                ((inner_w, inner_d, t), (x + width / 2, y + inner_d / 2, z + height - t / 2)),
            ],
        ),
    }
    if back is not None:
        pieces[f"{mid}-back"] = (
            "backs",
            [((width, b, height), (x + width / 2, y + depth - b / 2, z + height / 2))],
        )
    if rules.uses_divider_layout(module) or module.get("shelf_depths_mm"):
        if module.get("dividers") and not rules.uses_divider_layout(module):
            found = rules.bays(module, t)
            if len(found) > 1:
                pieces[f"{mid}-divider"] = (
                    "carcass",
                    [
                        ((t, inner_d, height - 2 * t), (x + t + left + bay_w + t / 2, y + inner_d / 2, z + height / 2))
                        for left, bay_w in found[:-1]
                    ],
                )
        pieces.update(_divider_layout_pieces(module, t, b))
        _add_front_boxes(pieces, module, materials, t, b)
        return pieces
    shelves = module["shelves"]
    adjustable = module.get("adjustable_shelves", 0)
    # Each shelf sits at its level by its kind: the fixed shelves lowest unless `shelf_kinds` says
    # otherwise; evenly spaced unless the module states a spacing or positions (custom_build.derive).
    fixed_centres = [z + centre for centre in rules.kind_centres(module, t, "fixed")]
    adjustable_centres = [z + centre for centre in rules.kind_centres(module, t, "adjustable")]
    found = rules.bays(module, t)
    if len(found) > 1:
        pieces[f"{mid}-divider"] = (
            "carcass",
            [
                ((t, inner_d, height - 2 * t), (x + t + left + bay_w + t / 2, y + inner_d / 2, z + height / 2))
                for left, bay_w in found[:-1]
            ],
        )
    widths = rules.bay_cut_widths(module, t)
    for prefix, name, count, heights, clearance in (
        (f"{mid}-shelf", "Fixed shelf", shelves, fixed_centres, 0),
        (f"{mid}-adjustable-shelf", "Adjustable shelf", adjustable, adjustable_centres, rules.ADJUSTABLE_SHELF_CLEARANCE_MM),
    ):
        if not count:
            continue
        if len(found) == 1:
            board_w = math.floor(inner_w - clearance) if clearance else inner_w
            pieces[prefix] = (
                "shelves",
                [((board_w, inner_d, t), (x + width / 2, y + inner_d / 2, centre)) for centre in heights],
            )
            continue
        rows = rules.bay_rows(prefix, name, count, widths)
        for index, (row_id, _, _, cut_w) in enumerate(rows):
            # One row covers every bay when the bays share a width; otherwise row n is bay n.
            covered = found if len(rows) == 1 else [found[index]]
            board_w = math.floor(cut_w - clearance) if clearance else cut_w
            pieces[row_id] = (
                "shelves",
                [
                    ((board_w, inner_d, t), (x + t + left + bay_w / 2, y + inner_d / 2, centre))
                    for left, bay_w in covered
                    for centre in heights
                ],
            )

    _add_front_boxes(pieces, module, materials, t, b)
    return pieces


def _divider_layout_pieces(module: Mapping[str, Any], t: int, b: int) -> dict[str, tuple[str, list[Box]]]:
    """Dividers between named boards and the shelf boards they split, from the cut list's own rows."""
    x, y, z = module["x"], module["y"], module["z"]
    inner_d = module["depth"] - b
    pieces: dict[str, tuple[str, list[Box]]] = {}
    for row_id, length, places in rules.divider_rows(module, t, b):
        pieces[row_id] = (
            "carcass",
            [
                ((t, inner_d, length), (x + place.left + t / 2, y + inner_d / 2, z + place.bottom + length / 2))
                for place in places
            ],
        )
    for row_id, _name, _kind, width, _depth, boards in rules.shelf_rows(module, t, b):
        pieces[row_id] = (
            "shelves",
            [
                (
                    (width, board.depth, t),
                    (x + board.x0 + board.width / 2, y + board.y0 + board.depth / 2, z + board.centre),
                )
                for board in boards
            ],
        )
    return pieces


def _add_front_boxes(
    pieces: dict[str, tuple[str, list[Box]]], module: Mapping[str, Any], materials: Mapping[str, Any], t: int, b: int
) -> None:
    """A rectangular module's fronts and drawer boxes, by cut-list row id."""
    back = module.get("back")
    x, y, z = module["x"], module["y"], module["z"]
    width = module["width"]
    inner_w, inner_d = width - 2 * t, module["depth"] - b
    mid = module["id"]
    rects = rules.front_layout(module, t, b)
    slat_records = rules.slat_layout(module, materials, t, b)
    bottom_t = materials[back]["thickness_mm"] if back is not None else t
    for index, front in enumerate(module["fronts"]):
        entry = [rect for rect in rects if rect["entry"] == index]
        prefix = f"{mid}-{front['type']}-{index + 1}"

        def panel(rect: Mapping[str, Any]) -> Box:
            # Closed, in front of the carcass face.
            return (
                (rect["w"], t, rect["h"]),
                (x + rect["x"] + rect["w"] / 2, y - t / 2, z + rect["z"] + rect["h"] / 2),
            )

        if front["type"] != "drawer":
            # One piece per cut-list row: doors cut from different slots are a row each (door-leaf-materials).
            for (row_id, _position), rect in zip(rules.door_rows(module, front, index, len(entry)), entry, strict=True):
                pieces.setdefault(row_id, ("fronts", []))[1].append(panel(rect))
            for record in slat_records:
                if record["entry"] != index:
                    continue
                # Glued in front of the door face, in slat_layout's order (door-slats).
                pieces.setdefault(f"{record['row']}-slat", ("fronts", []))[1].append(
                    (
                        (record["w"], record["thickness"], record["h"]),
                        (x + record["x"], y - t - record["thickness"] / 2, z + record["z"]),
                    )
                )
            continue
        runner = rules.runner_length(inner_d) or 0
        box_w = inner_w - 2 * rules.DRAWER_SIDE_CLEARANCE_MM
        sides: list[Box] = []
        backs: list[Box] = []
        bottoms: list[Box] = []
        for rect in entry:
            box_h = rect["h"] - rules.DRAWER_BOX_HEIGHT_REDUCTION_MM
            base = z + rect["z"] + rules.DRAWER_BOX_HEIGHT_REDUCTION_MM / 2
            left = x + t + rules.DRAWER_SIDE_CLEARANCE_MM
            for side_x in (left + t / 2, left + box_w - t / 2):
                sides.append(((t, runner, box_h), (side_x, y + runner / 2, base + box_h / 2)))
            backs.append(((box_w - 2 * t, t, box_h), (x + width / 2, y + runner - t / 2, base + box_h / 2)))
            bottoms.append(((box_w, runner, bottom_t), (x + width / 2, y + runner / 2, base - bottom_t / 2)))
        pieces[f"{prefix}-front"] = ("fronts", [panel(rect) for rect in entry])
        pieces[f"{prefix}-side"] = ("fronts", sides)
        pieces[f"{prefix}-back"] = ("fronts", backs)
        pieces[f"{prefix}-bottom"] = ("fronts", bottoms)


def _rotate_y(x: float, z: float, deg: float) -> tuple[float, float]:
    angle = math.radians(deg)
    cos, sin = math.cos(angle), math.sin(angle)
    return x * cos + z * sin, -x * sin + z * cos


def _rotate_z(x: float, y: float, deg: float) -> tuple[float, float]:
    angle = math.radians(deg)
    cos, sin = math.cos(angle), math.sin(angle)
    return x * cos - y * sin, x * sin + y * cos


def _fold_sign(fold: rules.SideFold) -> int:
    return 1 if (fold.side == "left") == (fold.towards == "inside") else -1


def _horizontal_board(module: Mapping[str, Any], profile: rules.FoldProfile, z0: float, z1: float) -> Placement:
    """A rectangle cut to the smallest inner width along `z0`–`z1`, centred on that slice."""
    t = profile.t
    inner_d = profile.inner_d
    width = rules.min_inner_width(profile, 0, inner_d, z0, z1)
    samples = [(0.0, z0), (0.0, z1), (inner_d, z0), (inner_d, z1)]
    for fold in profile.folds:
        if fold.along == "height" and z0 < fold.from_mm < z1:
            samples.extend([(0.0, float(fold.from_mm)), (inner_d, float(fold.from_mm))])
        if fold.along == "depth":
            samples.extend([(float(fold.from_mm), z0), (float(fold.from_mm), z1)])
    y_at, z_at = min(samples, key=lambda p: rules.inner_width_at(profile, p[0], p[1]))
    left = rules.inner_left_x(profile, y_at, z_at)
    right = left + width
    x, y, z = module["x"], module["y"], module["z"]
    return Placement(
        (width, inner_d, t),
        (x + (left + right) / 2, y + inner_d / 2, z + (z0 + z1) / 2),
    )


def _folded_side_placements(
    module: Mapping[str, Any], profile: rules.FoldProfile, fold: rules.SideFold
) -> tuple[Placement, Placement]:
    """The two rectangular boards of a folded side, the second rotated by `angle_deg`."""
    t = profile.t
    x, y, z = module["x"], module["y"], module["z"]
    inner_d = profile.inner_d
    sign = _fold_sign(fold)
    if fold.side == "left":
        join_x, rel_x, lower_x = x, t / 2, x + t / 2
    else:
        join_x, rel_x, lower_x = x + profile.width, -t / 2, x + profile.width - t / 2
    if fold.along == "height":
        lower = Placement((t, inner_d, fold.from_mm), (lower_x, y + inner_d / 2, z + fold.from_mm / 2))
        ry = sign * fold.angle_deg
        dx, dz = _rotate_y(rel_x, fold.slope_mm / 2, ry)
        upper = Placement(
            (t, inner_d, fold.slope_mm),
            (join_x + dx, y + inner_d / 2, z + fold.from_mm + dz),
            rotation_deg=(0.0, ry, 0.0),
        )
        return lower, upper
    lower = Placement((t, fold.from_mm, profile.height), (lower_x, y + fold.from_mm / 2, z + profile.height / 2))
    rz = -sign * fold.angle_deg
    dx, dy = _rotate_z(rel_x, fold.slope_mm / 2, rz)
    upper = Placement(
        (t, fold.slope_mm, profile.height),
        (join_x + dx, y + fold.from_mm + dy, z + profile.height / 2),
        rotation_deg=(0.0, 0.0, rz),
    )
    return lower, upper


def _back_prism(module: Mapping[str, Any], profile: rules.FoldProfile) -> Placement:
    outline = rules.back_outline(profile)
    x, y, z = module["x"], module["y"], module["z"]
    y0 = y + profile.inner_d
    y1 = y + profile.depth
    verts = tuple((x + ox, y0, z + oz) for ox, oz in outline) + tuple((x + ox, y1, z + oz) for ox, oz in outline)
    n = len(outline)
    faces = (tuple(range(n)), tuple(range(2 * n - 1, n - 1, -1)))
    sides = tuple((i, (i + 1) % n, n + (i + 1) % n, n + i) for i in range(n))
    xs = [v[0] for v in verts]
    ys = [v[1] for v in verts]
    zs = [v[2] for v in verts]
    return Placement(
        (max(xs) - min(xs), max(ys) - min(ys), max(zs) - min(zs)),
        ((min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2, (min(zs) + max(zs)) / 2),
        verts=verts,
        faces=faces + sides,
    )


def _folded_module_pieces(
    module: Mapping[str, Any], materials: Mapping[str, Any]
) -> dict[str, tuple[str, list[Placement]]]:
    """Every piece of a folded module, by cut-list row id."""
    t = materials[module["carcass"]]["thickness_mm"]
    back = module.get("back")
    b = materials[back]["thickness_mm"] if back is not None else 0
    profile = rules.fold_profile(module, t, b)
    x, y, z = module["x"], module["y"], module["z"]
    inner_d = profile.inner_d
    mid = module["id"]
    pieces: dict[str, tuple[str, list[Placement]]] = {}

    for side in ("left", "right"):
        fold = profile.fold_on(side)
        if fold is None:
            cx = x + t / 2 if side == "left" else x + profile.width - t / 2
            pieces[f"{mid}-side-{side}"] = (
                "carcass",
                [Placement((t, inner_d, profile.height), (cx, y + inner_d / 2, z + profile.height / 2))],
            )
            continue
        first, second = _folded_side_placements(module, profile, fold)
        if fold.along == "height":
            pieces[f"{mid}-side-{side}-lower"] = ("carcass", [first])
            pieces[f"{mid}-side-{side}-upper"] = ("carcass", [second])
        else:
            pieces[f"{mid}-side-{side}-front"] = ("carcass", [first])
            pieces[f"{mid}-side-{side}-back"] = ("carcass", [second])

    bottom = _horizontal_board(module, profile, 0, t)
    top = _horizontal_board(module, profile, profile.height - t, profile.height)
    if bottom.size[0] == top.size[0]:
        pieces[f"{mid}-top-bottom"] = ("carcass", [bottom, top])
    else:
        pieces[f"{mid}-bottom"] = ("carcass", [bottom])
        pieces[f"{mid}-top"] = ("carcass", [top])

    if back is not None:
        pieces[f"{mid}-back"] = ("backs", [_back_prism(module, profile)])

    if module.get("dividers") or module.get("shelf_depths_mm"):
        for row_id, (layer, boxes) in _divider_layout_pieces(module, t, b).items():
            pieces[row_id] = (layer, [Placement(size, centre) for size, centre in boxes])
        _add_folded_fronts(pieces, module, materials, profile, t, b)
        return pieces

    centres = [z + centre for centre in rules.kind_centres(module, t, "fixed")]
    shelves: list[Placement] = []
    for centre in centres:
        shelves.append(_horizontal_board(module, profile, centre - t / 2, centre + t / 2))
    if shelves:
        widths = [board.size[0] for board in shelves]
        if len(set(widths)) == 1:
            pieces[f"{mid}-shelf"] = ("shelves", shelves)
        else:
            for index, board in enumerate(shelves, start=1):
                pieces[f"{mid}-shelf-{index}"] = ("shelves", [board])

    adj_centres = [z + centre for centre in rules.kind_centres(module, t, "adjustable")]
    adjustable: list[Placement] = []
    for centre in adj_centres:
        board = _horizontal_board(module, profile, centre - t / 2, centre + t / 2)
        cut_w = math.floor(board.size[0] - rules.ADJUSTABLE_SHELF_CLEARANCE_MM)
        adjustable.append(Placement((cut_w, board.size[1], board.size[2]), board.centre))
    if adjustable:
        widths = [board.size[0] for board in adjustable]
        if len(set(widths)) == 1:
            pieces[f"{mid}-adjustable-shelf"] = ("shelves", adjustable)
        else:
            for index, board in enumerate(adjustable, start=1):
                pieces[f"{mid}-adjustable-shelf-{index}"] = ("shelves", [board])

    _add_folded_fronts(pieces, module, materials, profile, t, b)
    return pieces


def _add_folded_fronts(
    pieces: dict[str, tuple[str, list[Placement]]],
    module: Mapping[str, Any],
    materials: Mapping[str, Any],
    profile: rules.FoldProfile,
    t: int,
    b: int,
) -> None:
    """A folded module's fronts and drawer boxes, by cut-list row id."""
    back = module.get("back")
    y, z = module["y"], module["z"]
    inner_d = profile.inner_d
    mid = module["id"]
    rects = rules.front_layout(module, t, b)
    bottom_t = materials[back]["thickness_mm"] if back is not None else t
    inner_w = profile.width - 2 * t
    for index, front in enumerate(module["fronts"]):
        entry = [rect for rect in rects if rect["entry"] == index]
        prefix = f"{mid}-{front['type']}-{index + 1}"
        if front["type"] != "drawer":
            for part_id, leaves in rules._group_leaves(prefix, entry):
                pieces[part_id] = ("fronts", [_front_placement(module, leaf, t) for leaf in leaves])
            continue
        for part_id, leaves in rules._group_leaves(f"{prefix}-front", entry):
            pieces[part_id] = ("fronts", [_front_placement(module, leaf, t) for leaf in leaves])
        runner = rules.runner_length(inner_d) or 0
        box_groups: dict[tuple[int, int], list[dict[str, Any]]] = {}
        for rect in entry:
            box_w = rules._drawer_box_width(profile, inner_w, rect)
            box_h = math.floor(rect["h"]) - rules.DRAWER_BOX_HEIGHT_REDUCTION_MM
            box_groups.setdefault((box_w, box_h), []).append(rect)
        split_box = len(box_groups) > 1
        for box_index, ((box_w, box_h), group) in enumerate(box_groups.items(), start=1):
            suffix = f"-{box_index}" if split_box else ""
            sides: list[Placement] = []
            backs: list[Placement] = []
            bottoms: list[Placement] = []
            for rect in group:
                slice_board = _horizontal_board(module, profile, rect["z"], rect["z"] + rect["h"])
                cx = slice_board.centre[0]
                left = cx - box_w / 2
                base = z + rect["z"] + rules.DRAWER_BOX_HEIGHT_REDUCTION_MM / 2
                for side_x in (left + t / 2, left + box_w - t / 2):
                    sides.append(Placement((t, runner, box_h), (side_x, y + runner / 2, base + box_h / 2)))
                backs.append(Placement((box_w - 2 * t, t, box_h), (cx, y + runner - t / 2, base + box_h / 2)))
                bottoms.append(Placement((box_w, runner, bottom_t), (cx, y + runner / 2, base - bottom_t / 2)))
            pieces[f"{prefix}-side{suffix}"] = ("fronts", sides)
            pieces[f"{prefix}-back{suffix}"] = ("fronts", backs)
            pieces[f"{prefix}-bottom{suffix}"] = ("fronts", bottoms)


def _front_placement(module: Mapping[str, Any], leaf: Mapping[str, Any], t: int) -> Placement:
    x, y, z = module["x"], module["y"], module["z"]
    if leaf.get("rectangular", True):
        return Placement(
            (leaf["w"], t, leaf["h"]),
            (x + leaf["x"] + leaf["w"] / 2, y - t / 2, z + leaf["z"] + leaf["h"] / 2),
        )
    net = leaf["net"]
    y0, y1 = y - t, y
    verts = tuple((x + ox, y0, z + oz) for ox, oz in net) + tuple((x + ox, y1, z + oz) for ox, oz in net)
    n = len(net)
    faces = (tuple(range(n)), tuple(range(2 * n - 1, n - 1, -1)))
    sides = tuple((i, (i + 1) % n, n + (i + 1) % n, n + i) for i in range(n))
    xs = [v[0] for v in verts]
    ys = [v[1] for v in verts]
    zs = [v[2] for v in verts]
    return Placement(
        (max(xs) - min(xs), max(ys) - min(ys), max(zs) - min(zs)),
        ((min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2, (min(zs) + max(zs)) / 2),
        verts=verts,
        faces=faces + sides,
    )


def _extra_boxes(spec: Mapping[str, Any], right_edge: float, front_edge: float) -> dict[str, tuple[str, list[Placement]]]:
    """Placed extra parts sit at their stated corners and turns; the rest are laid flat beside the build."""
    pieces: dict[str, tuple[str, list[Placement]]] = {}
    offset_y = front_edge
    for extra in spec.get("extra_parts") or []:
        t = spec["materials"][extra["material"]]["thickness_mm"]
        placed: list[Placement] = []
        if extra.get("placements"):
            placed = [_extra_piece(extra, placement, t) for placement in extra["placements"]]
        else:
            for _ in range(extra["qty"]):
                if extra.get("end_cuts") is not None:
                    flat = {"x": right_edge + 200, "y": offset_y, "z": 0, "length_along": "x", "width_along": "y"}
                    placed.append(_extra_piece(extra, flat, t))
                else:
                    placed.append(
                        Placement(
                            (extra["length"], extra["width"], t),
                            (right_edge + 200 + extra["length"] / 2, offset_y + extra["width"] / 2, t / 2),
                        )
                    )
                offset_y += extra["width"] + 20
        pieces[extra["id"]] = ("extras", placed)
    return pieces


def _extra_piece(extra: Mapping[str, Any], placement: Mapping[str, Any], t: int) -> Placement:
    """One extra-part piece as a mesh from the corners `derive` gives the schema and the overall size."""
    verts = rules.extra_piece_corners(extra, placement, t)
    xs = [v[0] for v in verts]
    ys = [v[1] for v in verts]
    zs = [v[2] for v in verts]
    return Placement(
        (max(xs) - min(xs), max(ys) - min(ys), max(zs) - min(zs)),
        ((min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2, (min(zs) + max(zs)) / 2),
        verts=verts,
        faces=rules.extra_piece_faces(placement),
    )


# Modelled handles (front-handles): how far a bar stands proud on its posts, how far
# in from each end a post sits, and a knob's depth and facets.
BAR_PROUD_MM = 30
POST_INSET_MM = 15
KNOB_DEPTH_MM = 25
KNOB_SIDES = 16


def _cuboid(x0: float, x1: float, y0: float, y1: float, z0: float, z1: float, base: int) -> tuple[list[tuple[float, float, float]], list[tuple[int, ...]]]:
    verts = [(x, y, z) for z in (z0, z1) for y in (y0, y1) for x in (x0, x1)]
    faces = [(0, 2, 3, 1), (4, 5, 7, 6), (0, 1, 5, 4), (2, 6, 7, 3), (0, 4, 6, 2), (1, 3, 7, 5)]
    return verts, [tuple(base + i for i in face) for face in faces]


def _handle_shape(record: Mapping[str, Any], cx: float, front_y: float, cz: float) -> Placement:
    """One handle as a single mesh in build millimetres, standing proud of the front face at `front_y`."""
    verts: list[tuple[float, float, float]] = []
    faces: list[tuple[int, ...]] = []
    if record["kind"] == "knob":
        radius = rules.KNOB_DIAMETER_MM / 2
        for y in (front_y - KNOB_DEPTH_MM, front_y):
            for n in range(KNOB_SIDES):
                angle = 2 * math.pi * n / KNOB_SIDES
                verts.append((cx + radius * math.cos(angle), y, cz + radius * math.sin(angle)))
        faces.append(tuple(range(KNOB_SIDES - 1, -1, -1)))
        faces.append(tuple(range(KNOB_SIDES, 2 * KNOB_SIDES)))
        for n in range(KNOB_SIDES):
            following = (n + 1) % KNOB_SIDES
            faces.append((n, following, KNOB_SIDES + following, KNOB_SIDES + n))
        return Placement((0.0, 0.0, 0.0), (cx, front_y, cz), verts=tuple(verts), faces=tuple(faces))
    half = rules.BAR_SECTION_MM / 2
    along, length = ("z" if record["orientation"] == "vertical" else "x"), record["length"]
    bar_y0, bar_y1 = front_y - BAR_PROUD_MM, front_y - BAR_PROUD_MM + rules.BAR_SECTION_MM
    # Two posts 15 mm in from the ends, or one in the middle of a bar too short for two.
    reach = length / 2 - POST_INSET_MM - half
    offsets = (-reach, reach) if reach > half else (0.0,)
    boxes = [(-length / 2, length / 2, bar_y0, bar_y1)] + [(o - half, o + half, bar_y1, front_y) for o in offsets]
    for a0, a1, y0, y1 in boxes:
        if along == "z":
            box = _cuboid(cx - half, cx + half, y0, y1, cz + a0, cz + a1, len(verts))
        else:
            box = _cuboid(cx + a0, cx + a1, y0, y1, cz - half, cz + half, len(verts))
        verts.extend(box[0])
        faces.extend(box[1])
    return Placement((0.0, 0.0, 0.0), (cx, front_y, cz), verts=tuple(verts), faces=tuple(faces))


def _handle_pieces(spec: Mapping[str, Any]) -> list[tuple[str, str, str, str, Placement]]:
    """Every modelled handle: (object name, owning module, finish, key, shape), in front-row order."""
    pieces: list[tuple[str, str, str, str, Placement]] = []
    for module in spec["modules"]:
        t = spec["materials"][module["carcass"]]["thickness_mm"]
        back = module.get("back")
        b = spec["materials"][back]["thickness_mm"] if back is not None else 0
        # A handle on a slatted leaf stands proud of the slats' face (door-slats).
        slat_depth = {
            (record["row"], record["leaf"]): record["thickness"]
            for record in rules.slat_layout(module, spec["materials"], t, b)
        }
        for record in rules.handle_layout(module, t, b):
            name = f"{record['row']}-handle" + (f"#{record['leaf'] + 1}" if record["leaf"] else "")
            front_y = module["y"] - t - slat_depth.get((record["row"], record["leaf"]), 0)
            shape = _handle_shape(record, module["x"] + record["x"], front_y, module["z"] + record["z"])
            pieces.append((name, module["id"], record["finish"], record["key"], shape))
    return pieces


# Drawn hardware (hardware-catalog): each piece of `rules.hardware_layout` is one object named
# `<line id>#<n>`, built here in its own frame around the record's anchor point, so pieces of one line
# with the same geometry share one mesh. Facets per round section, and the bevel each piece gets.
HARDWARE_SIDES = 20
HARDWARE_BEVEL_MM = 0.4
# Physically based metal per finish: (base colour, roughness, metallic); hardware-catalog design 5.
HARDWARE_FINISHES: dict[str, tuple[tuple[float, float, float], float, float]] = {
    "chrome": ((0.8, 0.8, 0.82), 0.08, 1.0),
    "nickel": ((0.66, 0.64, 0.6), 0.2, 1.0),
    "steel": ((0.56, 0.57, 0.58), 0.3, 1.0),
    "aluminium": ((0.82, 0.83, 0.85), 0.35, 1.0),
    "brass": ((0.71, 0.53, 0.23), 0.25, 1.0),
    "black": ((0.03, 0.03, 0.035), 0.5, 0.3),
}

Mesh = tuple[list[tuple[float, float, float]], list[tuple[int, ...]], list[int]]  # verts, faces, smooth faces


def _add_box(mesh: Mesh, x0: float, x1: float, y0: float, y1: float, z0: float, z1: float) -> None:
    verts, faces = _cuboid(min(x0, x1), max(x0, x1), min(y0, y1), max(y0, y1), min(z0, z1), max(z0, z1), len(mesh[0]))
    mesh[0].extend(verts)
    mesh[1].extend(faces)


def _add_tube(
    mesh: Mesh, axis: str, start: float, end: float, centre: tuple[float, float], radii: tuple[float, float]
) -> None:
    """A capped round (or oval) section along `axis` from `start` to `end`; `centre` and `radii` are in
    the two other axes, in x-y-z order. Its side faces are smoothed."""
    verts, faces, smooth = mesh
    base = len(verts)
    lo, hi = min(start, end), max(start, end)
    for at in (lo, hi):
        for n in range(HARDWARE_SIDES):
            angle = 2 * math.pi * n / HARDWARE_SIDES
            a = centre[0] + radii[0] * math.cos(angle)
            b = centre[1] + radii[1] * math.sin(angle)
            verts.append({"x": (at, a, b), "y": (a, at, b), "z": (a, b, at)}[axis])
    ring = range(HARDWARE_SIDES)
    first = tuple(base + n for n in ring)
    second = tuple(base + HARDWARE_SIDES + n for n in ring)
    faces.append(first[::-1] if axis != "y" else first)
    faces.append(second if axis != "y" else second[::-1])
    for n in ring:
        following = (n + 1) % HARDWARE_SIDES
        smooth.append(len(faces))
        faces.append((base + n, base + following, base + HARDWARE_SIDES + following, base + HARDWARE_SIDES + n))


def _hardware_mesh(record: Mapping[str, Any]) -> tuple[tuple[Any, ...], tuple[float, float, float], Mesh]:
    """(geometry signature, anchor point in build mm, mesh around that anchor) for one layout record."""
    size, shape = record["size"], record["shape"]
    mesh: Mesh = ([], [], [])
    if shape == "hinge_concealed":
        cx, cy, cz = record["cup"]
        sign = -1 if record["side"] == "left" else 1
        reach = record["plate_x"] - cx  # to the side's inner face
        radius = size["cup_diameter_mm"] / 2
        _add_tube(mesh, "y", -size["cup_depth_mm"], 1.0, (0.0, 0.0), (radius, radius))
        thickness = size["plate_thickness_mm"]
        arm_w, arm_h = size["arm_width_mm"], size["arm_height_mm"]
        _add_box(mesh, -sign * radius * 0.4, reach - sign * thickness, 1.0, 1.0 + arm_h, -arm_w / 2, arm_w / 2)
        _add_box(mesh, reach - sign * thickness, reach, 2.0, 2.0 + size["plate_length_mm"],
                 -size["plate_height_mm"] / 2, size["plate_height_mm"] / 2)
        return (record["line"], shape, record["side"], round(reach, 3)), (cx, cy, cz), mesh
    if shape == "shelf_pin":
        radius = size["diameter_mm"] / 2
        facing = record["facing"]
        _add_tube(mesh, "x", 0.0, facing * size["length_mm"], (0.0, -radius), (radius, radius))
        return (record["line"], shape, facing), record["at"], mesh
    if shape == "drawer_runner":
        span = record["right_x"] - record["left_x"]
        width, height, length = size["width_mm"], size["height_mm"], record["length"]
        _add_box(mesh, 0.0, width, 0.0, length, 0.0, height)
        _add_box(mesh, span - width, span, 0.0, length, 0.0, height)
        return (record["line"], shape, span), (record["left_x"], record["y0"], record["z"]), mesh
    if shape == "hanging_rail":
        _add_tube(mesh, "x", 0.0, record["length"], (0.0, 0.0), (size["width_mm"] / 2, size["height_mm"] / 2))
        return (record["line"], shape, record["length"]), (record["x0"], record["y"], record["z"]), mesh
    if shape == "rail_support":
        x, y, z = record["at"]
        width, height, thickness = size["width_mm"], size["height_mm"], size["thickness_mm"]
        if record["mount"] == "side":
            _add_box(mesh, 0.0, record["facing"] * thickness, -width / 2, width / 2, -height / 2, height / 2)
            return (record["line"], shape, record["facing"]), (x, y, z), mesh
        drop = record["top_z"] - z
        _add_box(mesh, -thickness / 2, thickness / 2, -width / 4, width / 4, 0.0, drop)
        return (record["line"], shape, "above", round(drop, 3)), (x, y, z), mesh
    if shape == "shelf_bracket":
        arm = min(size["arm_length_mm"], record["depth"] - 10)
        width, thickness = size["width_mm"], size["thickness_mm"]
        _add_box(mesh, -width / 2, width / 2, -thickness, 0.0, -size["height_mm"], 0.0)
        _add_box(mesh, -width / 2, width / 2, -arm, 0.0, -thickness, 0.0)
        return (record["line"], shape, round(arm, 3)), record["at"], mesh
    raise GeneratorError(f"build: hardware shape {shape!r} cannot be drawn")


def _hardware_material(state: BuildState, finish: str) -> bpy.types.Material:
    name = f"Hardware {finish}"
    existing = state.materials.get(name)
    if existing is not None:
        return existing
    colour, roughness, metallic = HARDWARE_FINISHES.get(finish, HARDWARE_FINISHES["steel"])
    material = bpy.data.materials.new(name)
    material.diffuse_color = (*colour, 1)
    material.metallic = metallic
    material.roughness = roughness
    material.use_nodes = True
    shader = next((node for node in material.node_tree.nodes if node.type == "BSDF_PRINCIPLED"), None)
    if shader is not None:
        shader.inputs["Base Color"].default_value = (*colour, 1)
        shader.inputs["Roughness"].default_value = roughness
        shader.inputs["Metallic"].default_value = metallic
    state.materials[name] = material
    return material


def _draw_hardware(
    state: BuildState,
    shift: tuple[float, float, float],
    collections: Mapping[str, bpy.types.Collection],
    empties: Mapping[str, bpy.types.Object],
) -> None:
    """Draw every `hardware_layout` record in the `hardware` layer, one object per piece."""
    import bmesh  # only inside Blender; the box tests import this module with a stand-in `bpy`

    meshes: dict[tuple[Any, ...], bpy.types.Mesh] = {}
    numbers: dict[str, int] = {}
    for record in rules.hardware_layout(state.spec, state.inputs):
        signature, anchor, (verts, faces, smooth) = _hardware_mesh(record)
        signature = (*signature, record["finish"])
        mesh = meshes.get(signature)
        if mesh is None:
            mesh = bpy.data.meshes.new(f"HW_{record['line']}_{len(meshes) + 1}")
            mesh.from_pydata([tuple(m(value) for value in vertex) for vertex in verts], [], [list(face) for face in faces])
            shaped = bmesh.new()
            shaped.from_mesh(mesh)
            bmesh.ops.recalc_face_normals(shaped, faces=shaped.faces)
            shaped.to_mesh(mesh)
            shaped.free()
            for index in smooth:
                mesh.polygons[index].use_smooth = True
            mesh.update()
            mesh.materials.append(_hardware_material(state, record["finish"]))
            meshes[signature] = mesh
        numbers[record["line"]] = numbers.get(record["line"], 0) + 1
        name = f"{record['line']}#{numbers[record['line']]}"
        obj = bpy.data.objects.new(name, mesh)
        obj.location = tuple(m(value - offset) for value, offset in zip(anchor, shift, strict=True))
        bevel = obj.modifiers.new("Bevel", "BEVEL")
        bevel.width = m(HARDWARE_BEVEL_MM)
        bevel.segments = 2
        bevel.limit_method = "ANGLE"
        owner = record["module"]
        parent = empties[owner]
        obj.parent = parent
        obj.matrix_parent_inverse = parent.matrix_world.inverted()
        _link(obj, collections[owner])
        obj["hardware_key"] = record["key"]
        state.layers.add(name, rules.HARDWARE_LAYER)


def _wall_shelf_boxes(spec: Mapping[str, Any]) -> dict[str, tuple[str, list[Box]]]:
    """Each wall shelf is one board at its stated position; brackets are never drawn."""
    pieces: dict[str, tuple[str, list[Box]]] = {}
    for shelf in spec.get("wall_shelves") or []:
        t = spec["materials"][shelf["material"]]["thickness_mm"]
        size = (shelf["length"], shelf["depth"], t)
        centre = (shelf["x"] + shelf["length"] / 2, shelf["y"] + shelf["depth"] / 2, shelf["z"] + t / 2)
        pieces[shelf["id"]] = ("shelves", [(size, centre)])
    return pieces


# --- the scene ----------------------------------------------------------------------------------


_COLOURS: tuple[tuple[str, tuple[float, float, float], float, float], ...] = (
    ("oak", (0.48, 0.29, 0.145), 0.45, 0.0),
    ("anthracite", (0.09, 0.09, 0.1), 0.5, 0.0),
    ("anthrazit", (0.09, 0.09, 0.1), 0.5, 0.0),
    ("black", (0.035, 0.035, 0.04), 0.55, 0.0),
    ("mdf", (0.62, 0.55, 0.45), 0.6, 0.0),
    ("birch", (0.72, 0.62, 0.42), 0.5, 0.0),
    ("shs", (0.12, 0.12, 0.13), 0.32, 1.0),
    ("steel", (0.12, 0.12, 0.13), 0.32, 1.0),
    ("aluminium", (0.55, 0.56, 0.58), 0.3, 1.0),
    ("brass", (0.71, 0.53, 0.23), 0.3, 1.0),
)


def _material(state: BuildState, name: str) -> bpy.types.Material:
    existing = state.materials.get(name)
    if existing is not None:
        return existing
    colour, roughness, metallic = (0.7, 0.66, 0.6), 0.5, 0.0
    lowered = name.casefold()
    for keyword, candidate, candidate_roughness, candidate_metallic in _COLOURS:
        if keyword in lowered:
            colour, roughness, metallic = candidate, candidate_roughness, candidate_metallic
            break
    material = bpy.data.materials.new(name)
    # The viewport colour the Workbench screenshot shows; the Principled node
    # below is what Eevee and Cycles read.
    material.diffuse_color = (*colour, 1)
    material.use_nodes = True
    shader = next((node for node in material.node_tree.nodes if node.type == "BSDF_PRINCIPLED"), None)
    if shader is not None:
        shader.inputs["Base Color"].default_value = (*colour, 1)
        shader.inputs["Roughness"].default_value = roughness
        shader.inputs["Metallic"].default_value = metallic
    state.materials[name] = material
    return material


def _empty(name: str, location: tuple[float, float, float], collection: bpy.types.Collection, parent: bpy.types.Object | None) -> bpy.types.Object:
    obj = bpy.data.objects.new(name, None)
    obj.empty_display_type = "PLAIN_AXES"
    obj.empty_display_size = 0.08
    obj.location = tuple(m(value) for value in location)
    if parent is not None:
        obj.parent = parent
        obj.matrix_parent_inverse = parent.matrix_world.inverted()
    _link(obj, collection)
    return obj


def _box(state: BuildState, name: str, box: Box, material: str, layer: str, collection: bpy.types.Collection, parent: bpy.types.Object, rotation_deg: tuple[float, float, float] = (0.0, 0.0, 0.0)) -> None:
    size, centre = box
    bpy.ops.mesh.primitive_cube_add(size=1, location=tuple(m(value) for value in centre))
    obj = bpy.context.active_object
    obj.name = name
    obj.data.name = name
    obj.scale = tuple(m(value) for value in size)
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    if rotation_deg != (0.0, 0.0, 0.0):
        obj.rotation_euler = tuple(math.radians(value) for value in rotation_deg)
    obj.data.materials.append(_material(state, material))
    obj.parent = parent
    obj.matrix_parent_inverse = parent.matrix_world.inverted()
    _link(obj, collection)
    obj["part_id"] = name.split("#", 1)[0]
    state.layers.add(name, layer)


def _prism(
    state: BuildState,
    name: str,
    verts_mm: tuple[tuple[float, float, float], ...],
    faces: tuple[tuple[int, ...], ...],
    material: str,
    layer: str,
    collection: bpy.types.Collection,
    parent: bpy.types.Object,
) -> None:
    mesh = bpy.data.meshes.new(name)
    mesh.from_pydata([tuple(m(value) for value in vertex) for vertex in verts_mm], [], [list(face) for face in faces])
    mesh.update()
    obj = bpy.data.objects.new(name, mesh)
    obj.data.materials.append(_material(state, material))
    obj.parent = parent
    obj.matrix_parent_inverse = parent.matrix_world.inverted()
    _link(obj, collection)
    obj["part_id"] = name.split("#", 1)[0]
    state.layers.add(name, layer)


def _frame(spec: Mapping[str, Any]) -> tuple[float, float, float, dict[str, int]]:
    """The build's left, front and bottom edge, and its overall size."""
    overall = rules.overall(spec)
    modules = spec["modules"]
    if spec.get("envelope") is not None or not modules:
        return 0.0, 0.0, 0.0, overall
    xs: list[float] = []
    ys: list[float] = []
    zs: list[float] = []
    materials = spec["materials"]
    for module in modules:
        t = materials[module["carcass"]]["thickness_mm"]
        b = materials[module["back"]]["thickness_mm"] if module.get("back") is not None else 0
        x0, y0, z0, _w, _d, _h = rules.module_bounds(module, t, b)
        xs.append(module["x"] + x0)
        ys.append(module["y"] + y0)
        zs.append(module["z"] + z0)
    for shelf in spec.get("wall_shelves") or []:
        xs.append(shelf["x"])
        ys.append(shelf["y"])
        zs.append(shelf["z"])
    for corners in rules.placed_extra_corners(spec):
        xs.extend(corner[0] for corner in corners)
        ys.extend(corner[1] for corner in corners)
        zs.extend(corner[2] for corner in corners)
    return float(min(xs)), float(min(ys)), float(min(zs)), overall


def _override_count(boxes: list[Placement], qty: int) -> list[Placement]:
    """A part override may change a row's quantity: drop pieces, or add copies beside the last.

    Placed geometry keeps the rule sizes; only the count follows the override,
    so every cut-list piece still has exactly one object.
    """
    if qty <= len(boxes):
        return boxes[:qty]
    last = boxes[-1]
    extra = []
    for n in range(qty - len(boxes)):
        dx = (n + 1) * (last.size[0] + 20)
        verts = None if last.verts is None else tuple((vx + dx, vy, vz) for vx, vy, vz in last.verts)
        extra.append(
            Placement(
                last.size,
                (last.centre[0] + dx, last.centre[1], last.centre[2]),
                last.rotation_deg,
                verts,
                last.faces,
            )
        )
    return boxes + extra


def _build_scene(state: BuildState, parts: list[dict[str, Any]]) -> None:
    spec = state.spec
    _reset_scene()
    x0, y0, z0, overall = _frame(spec)
    # Centred on x and y; z stays the real height, so a
    # wall cabinet hangs where it will hang.
    shift = (x0 + overall["w"] / 2, y0 + overall["d"] / 2, 0.0)

    def at_placement(placed: Placement) -> Placement:
        cx, cy, cz = placed.centre
        centre = (cx - shift[0], cy - shift[1], cz - shift[2])
        verts = None
        if placed.verts is not None:
            verts = tuple((vx - shift[0], vy - shift[1], vz - shift[2]) for vx, vy, vz in placed.verts)
        return Placement(placed.size, centre, placed.rotation_deg, verts, placed.faces)

    def as_placements(boxes: list[Box]) -> list[Placement]:
        return [Placement(size, centre) for size, centre in boxes]

    root_collection = _collection("CustomBuild")
    root = _empty("CustomBuild", (0, 0, 0), root_collection, None)
    root["overall_w_mm"] = overall["w"]
    root["overall_h_mm"] = overall["h"]
    root["overall_d_mm"] = overall["d"]

    pieces: dict[str, tuple[str, str, list[Placement]]] = {}
    for module in spec["modules"]:
        laid = (
            _folded_module_pieces(module, spec["materials"])
            if module.get("side_folds")
            else {row_id: (layer, as_placements(boxes)) for row_id, (layer, boxes) in _module_boxes(module, spec["materials"]).items()}
        )
        for row_id, (layer, placements) in laid.items():
            pieces[row_id] = (module["id"], layer, placements)
    for row_id, (layer, placements) in _extra_boxes(spec, x0 + overall["w"], y0).items():
        pieces[row_id] = (rules.EXTRAS_MODULE, layer, placements)
    for row_id, (layer, boxes) in _wall_shelf_boxes(spec).items():
        pieces[row_id] = (row_id, layer, as_placements(boxes))

    empties: dict[str, bpy.types.Object] = {}
    collections: dict[str, bpy.types.Collection] = {}
    for index, module in enumerate(spec["modules"]):
        centre = (
            module["x"] + module["width"] / 2 - shift[0],
            module["y"] + module["depth"] / 2 - shift[1],
            module["z"] + module["height"] / 2,
        )
        collections[module["id"]] = _collection(f"{index + 1:02d}_{module['id']}", root_collection)
        empties[module["id"]] = _empty(f"MOD_{module['id']}", centre, collections[module["id"]], root)
    for index, shelf in enumerate(spec.get("wall_shelves") or [], start=len(spec["modules"])):
        thickness = spec["materials"][shelf["material"]]["thickness_mm"]
        centre = (
            shelf["x"] + shelf["length"] / 2 - shift[0],
            shelf["y"] + shelf["depth"] / 2 - shift[1],
            shelf["z"] + thickness / 2,
        )
        collections[shelf["id"]] = _collection(f"{index + 1:02d}_{shelf['id']}", root_collection)
        empties[shelf["id"]] = _empty(f"MOD_{shelf['id']}", centre, collections[shelf["id"]], root)
    if spec.get("extra_parts"):
        collections[rules.EXTRAS_MODULE] = _collection("99_extras", root_collection)
        empties[rules.EXTRAS_MODULE] = _empty("MOD_extras", (0, 0, 0), collections[rules.EXTRAS_MODULE], root)

    for row in parts:
        owner, layer, boxes = pieces.get(row["id"], (None, None, []))
        if owner is not None and boxes and "[overridden:" in row["notes"]:
            boxes = _override_count(boxes, int(row["qty"]))
        if owner is None or len(boxes) != int(row["qty"]):
            raise GeneratorError(
                f"build: cut-list row {row['id']!r} has {row['qty']} pieces but {len(boxes)} were placed"
            )
        for n, placed in enumerate(boxes, start=1):
            name = row["id"] if n == 1 else f"{row['id']}#{n}"
            shifted = at_placement(placed)
            if shifted.verts is not None and shifted.faces is not None:
                _prism(state, name, shifted.verts, shifted.faces, row["material"], layer, collections[owner], empties[owner])
            else:
                _box(
                    state, name, (shifted.size, shifted.centre), row["material"], layer,
                    collections[owner], empties[owner], shifted.rotation_deg,
                )

    for name, owner, finish, key, shape in _handle_pieces(spec):
        shifted = at_placement(shape)
        _prism(state, name, shifted.verts, shifted.faces, f"Handle {finish}", "handles", collections[owner], empties[owner])
        handle = bpy.data.objects[name]
        del handle["part_id"]
        handle["hardware_key"] = key
    _draw_hardware(state, shift, collections, empties)

    _build_dimensions(overall, z0, root_collection, root)
    _build_cameras_lights(overall, z0)
    bpy.ops.mesh.primitive_plane_add(size=max(6.0, m(max(overall.values())) * 3), location=(0, 0, 0))
    floor = bpy.context.active_object
    floor.name = "StudioFloor"
    floor.data.name = "StudioFloor"
    floor.data.materials.append(_material(state, "Studio floor birch"))


def _label_size(overall: Mapping[str, int]) -> float:
    """A dimension figure's height in mm: 4 % of the largest overall size, at least 40."""
    return max(40.0, max(overall["w"], overall["h"], overall["d"]) * 0.04)


def _ink() -> bpy.types.Material:
    material = bpy.data.materials.new("Ink")
    material.diffuse_color = (*INK, 1)
    material.use_nodes = True
    shader = next((node for node in material.node_tree.nodes if node.type == "BSDF_PRINCIPLED"), None)
    if shader is not None:
        shader.inputs["Base Color"].default_value = (*INK, 1)
        shader.inputs["Roughness"].default_value = 0.9
    return material


def _dimension_box(name: str, axis: str, size: tuple[float, float, float], centre: tuple[float, float, float],
                   material: bpy.types.Material, collection: bpy.types.Collection, parent: bpy.types.Object) -> None:
    mesh = bpy.data.meshes.new(name)
    sx, sy, sz = (m(value) / 2 for value in size)
    verts = [(x, y, z) for z in (-sz, sz) for y in (-sy, sy) for x in (-sx, sx)]
    faces = [(0, 2, 3, 1), (4, 5, 7, 6), (0, 1, 5, 4), (2, 6, 7, 3), (0, 4, 6, 2), (1, 3, 7, 5)]
    mesh.from_pydata(verts, [], faces)
    mesh.materials.append(material)
    obj = bpy.data.objects.new(name, mesh)
    obj.location = tuple(m(value) for value in centre)
    obj.parent = parent
    obj["dimension"] = axis
    collection.objects.link(obj)


def _dimension_label(axis: str, figure: int, size_mm: float, centre: tuple[float, float, float], align: str,
                     material: bpy.types.Material, collection: bpy.types.Collection, parent: bpy.types.Object) -> None:
    curve = bpy.data.curves.new(f"DIM_Label_{axis}", type="FONT")
    curve.body = f"{figure} mm"
    curve.size = m(size_mm)
    curve.align_x = align
    curve.align_y = "CENTER"
    curve.materials.append(material)
    obj = bpy.data.objects.new(f"DIM_Label_{axis}", curve)
    obj.location = tuple(m(value) for value in centre)
    obj.parent = parent
    obj["dimension"] = axis
    collection.objects.link(obj)


def _build_dimensions(overall: Mapping[str, int], z0: float, root_collection: bpy.types.Collection,
                      root: bpy.types.Object) -> None:
    """The overall width, height and depth as lines with ticks and their figures in mm.

    The piece spans x -w/2..w/2, y -d/2..d/2 (front at -y) and z z0..z0+h. Each line
    sits outside those bounds, where the views that face it can see it: width along
    the front's foot, height up the front-left corner, depth under the left side
    (the extra parts lie to the right). Each figure is set beside its line in both
    views that show it.
    """
    w, h, d = overall["w"], overall["h"], overall["d"]
    largest = max(w, h, d)
    thick = max(6.0, largest * 0.004)
    tick = thick * 8
    text = _label_size(overall)
    gap = DIMENSION_OFFSET_MM
    collection = _collection("09_Dimensions", root_collection)
    holder = _empty("MOD_Dimensions", (0, 0, 0), collection, root)
    ink = _ink()
    front, left, top = -d / 2 - gap, -w / 2 - gap, z0 + h
    below = z0 - gap
    lines = {
        # axis: (line size, line centre, end centres, tick size, label centre, label alignment)
        "W": ((w, thick, thick), (0, front, z0), [(-w / 2, front, z0), (w / 2, front, z0)],
              (thick, tick, tick), (0, front - text * 0.9, z0 - text * 0.9), "CENTER"),
        "H": ((thick, thick, h), (left, front, z0 + h / 2), [(left, front, z0), (left, front, top)],
              (tick, tick, thick), (left - text * 0.4, front, z0 + h / 2), "RIGHT"),
        "D": ((thick, d, thick), (left, 0, below), [(left, -d / 2, below), (left, d / 2, below)],
              (tick, thick, tick), (left - text * 0.4, d / 2, below - text * 0.9), "RIGHT"),
    }
    figures = {"W": w, "H": h, "D": d}
    for axis, (size, centre, ends, tick_size, label_centre, align) in lines.items():
        _dimension_box(f"DIM_Overall{axis}", axis, size, centre, ink, collection, holder)
        for n, end in enumerate(ends, start=1):
            _dimension_box(f"DIM_Overall{axis}_tick{n}", axis, tick_size, end, ink, collection, holder)
        _dimension_label(axis, figures[axis], text, label_centre, align, ink, collection, holder)


def _build_cameras_lights(overall: Mapping[str, int], z0: float) -> None:
    """Cameras framing the build's overall bounds, and a three-light rig scaled to it."""
    target = (0.0, 0.0, m(z0 + overall["h"] / 2))
    reach = m(max(overall["w"], overall["h"], overall["d"]))
    # The iso camera sits about 2.2 of the build's diagonals
    # away; the same ratio frames any build's bounds with a margin.
    diagonal = m(math.sqrt(overall["w"] ** 2 + overall["h"] ** 2 + overall["d"] ** 2))
    distance = max(2.0, diagonal * 2.2)
    direction = Vector((3.2, -4.5, 2.5)).normalized()
    iso = _add_camera("CAM_Iso", tuple(Vector(target) + direction * distance), (0, 0, 0))
    _aim_at(iso, target)
    # Each straight-on camera frames its two sides of the build and the dimension
    # lines and figures beside them, in the views' 800 × 500 frame.
    margin = m(2 * (DIMENSION_OFFSET_MM + _label_size(overall) * 5))
    aspect = SCREENSHOT_SIZE[1] / SCREENSHOT_SIZE[0]

    def ortho(across: float, up: float) -> float:
        return max(1.0, max(m(across) + margin, (m(up) + margin) / aspect) * 1.05)

    w, h, d = overall["w"], overall["h"], overall["d"]
    _add_camera("CAM_Front", (0, -distance, target[2]), (math.radians(90), 0, 0), ortho=True, scale=ortho(w, h))
    _add_camera("CAM_Side", (distance, 0, target[2]), (math.radians(90), 0, math.radians(90)), ortho=True, scale=ortho(d, h))
    _add_camera("CAM_Top", (0, 0, target[2] + distance), (0, 0, 0), ortho=True, scale=ortho(w, d))
    for camera in ("CAM_Iso", "CAM_Front", "CAM_Side", "CAM_Top"):
        bpy.data.objects[camera].data.clip_end = max(20.0, distance * 4)
    bpy.context.scene.camera = bpy.data.objects["CAM_Iso"]
    factor = max(1.0, reach / 1.5)
    for name, location, energy, size, rotation in (
        ("LGT_Key", (2.2, -2.4, 2.4), 250, 1.2, (math.radians(55), 0, math.radians(35))),
        ("LGT_Fill", (-2.5, -1.6, 1.6), 80, 1.8, (math.radians(70), 0, math.radians(-40))),
        ("LGT_Rim", (0.2, 2.4, 2.2), 120, 1.0, (math.radians(40), 0, math.radians(180))),
    ):
        data = bpy.data.lights.new(name, "AREA")
        data.energy = energy * factor * factor
        data.shadow_soft_size = size * factor
        light = bpy.data.objects.new(name, data)
        bpy.context.scene.collection.objects.link(light)
        light.location = tuple(value * factor for value in location[:2]) + (target[2] + location[2] * factor,)
        light.rotation_euler = rotation


# --- the package ------------------------------------------------------------------------------


def _write_shop_data(state: BuildState, output_dir: Path, parts: list[dict[str, Any]], hardware: list[dict[str, Any]]) -> None:
    emitted = rules.emitted_spec(state.spec, state.inputs)
    emitted["blender_version"] = bpy.app.version_string
    emitted["layers"] = state.layers.as_json()
    emitted["notes"] = [
        "All dimensions millimetres.",
        "Generated in Blender from the same rule-table derivation as the package's derived shop data.",
    ]
    (output_dir / "spec.json").write_text(
        json.dumps(emitted, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    write_csv(output_dir / "cutlist.csv", parts, CUTLIST_FIELDS)
    write_csv(output_dir / "hardware.csv", hardware, HARDWARE_FIELDS)


def _write_screenshot(output_path: Path) -> None:
    """A Workbench frame of `CAM_Iso`: shape, proportion and layers, no tier."""
    scene = bpy.context.scene
    set_engine("BLENDER_WORKBENCH")
    scene.render.resolution_x = SCREENSHOT_SIZE[0]
    scene.render.resolution_y = SCREENSHOT_SIZE[1]
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.render.film_transparent = False
    scene.display.shading.light = "STUDIO"
    scene.display.shading.color_type = "MATERIAL"
    camera = bpy.data.objects.get("CAM_Iso")
    if camera is None:
        raise GeneratorError("screenshot: CAM_Iso is missing")
    scene.camera = camera
    scene.render.filepath = str(output_path)
    with hidden_for_presentation():
        bpy.ops.render.render(write_still=True)


def _write_views(output_dir: Path) -> None:
    """Workbench frames from the front, side and top cameras, each with the dimension
    lines it faces and the figures turned to it; no tier (piece-inspector)."""
    scene = bpy.context.scene
    # A Workbench render's background is the world colour: light, like a drawing
    # sheet, so the dark lines and figures read. The iso screenshot keeps its own.
    world = scene.world
    saved_colour = tuple(world.color)
    world.color = PAPER
    for camera_name, file_name, shown in VIEWS:
        camera = bpy.data.objects.get(camera_name)
        if camera is None:
            raise GeneratorError(f"views: {camera_name} is missing")
        scene.camera = camera
        face_camera(camera)
        scene.render.filepath = str(output_dir / file_name)

        def unseen(obj: bpy.types.Object, shown: frozenset[str] = shown) -> bool:
            if obj.name == "StudioFloor":
                return True
            return is_dimension(obj) and obj.get("dimension") is not None and obj["dimension"] not in shown

        with hidden(unseen):
            bpy.ops.render.render(write_still=True)
    world.color = saved_colour
    # The saved file opens on the iso camera, the figures facing it.
    scene.camera = bpy.data.objects["CAM_Iso"]
    face_camera(scene.camera)


def _build_package(spec: Mapping[str, Any], output_dir: Path, inputs: Mapping[str, Any] | None = None) -> None:
    state = BuildState(spec=spec, inputs=inputs)
    parts, hardware, _assembly = rules.derive(spec, inputs)
    try:
        _build_scene(state, parts)
    except GeneratorError:
        raise
    except Exception as error:
        raise GeneratorError(f"build: {type(error).__name__}: {error}") from error
    try:
        _write_shop_data(state, output_dir, parts, hardware)
        _write_screenshot(output_dir / "screenshot.png")
        _write_views(output_dir)
    except GeneratorError:
        raise
    except Exception as error:
        raise GeneratorError(f"screenshot: {type(error).__name__}: {error}") from error
    try:
        export_glb(state.layers.names, output_dir / "model.glb")
        bpy.ops.wm.save_as_mainfile(filepath=str(output_dir / "model.blend"), check_existing=False)
    except GeneratorError:
        raise
    except Exception as error:
        raise GeneratorError(f"export: {type(error).__name__}: {error}") from error
    try:
        verify_build(output_dir)
    except VerificationError as error:
        raise GeneratorError(f"publish: {error}") from error
    except Exception as error:
        raise GeneratorError(f"publish: {type(error).__name__}: {error}") from error


def main(argv: list[str] | None = None) -> int:
    stage: Path | None = None
    try:
        spec_path, output_path, hardware_path = parse_build_arguments(list(sys.argv if argv is None else argv))
        spec = load_custom_build(spec_path)
        inputs = load_hardware_inputs(hardware_path)
        stage = output_path.parent / f".{output_path.name}.tmp-{uuid.uuid4().hex}"
        stage.mkdir()
        _build_package(spec, stage, inputs)
        os.replace(stage, output_path)
        stage = None
        print(f"WROTE {output_path}")
        return 0
    except (GeneratorError, InputError) as error:
        print(str(error), file=sys.stderr)
    except Exception as error:  # noqa: BLE001 - Blender errors need a short operator-safe diagnostic
        print(f"build: {type(error).__name__}: {error}", file=sys.stderr)
    if stage is not None and stage.exists():
        shutil.rmtree(stage)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
