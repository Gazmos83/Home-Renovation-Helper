"""Build an apartment shell inside Blender 5.2 in background mode.

Usage (the arguments after ``--`` belong to this script)::

    blender --background --python build_shell.py -- \
      --spec shell.json --out /absolute/new-shell-directory

Floors and ceilings follow each room's outline (concave included); every wall is
one solid segment per stretch between openings plus a lintel and a sill, built
once even when two rooms share it — a shared wall is centred on the shared line,
an outer wall is extruded outward from its interior face. Openings are cut by
splitting intervals, not by booleans. Publishes `model.glb` (without ceilings,
so the viewer sees into the rooms), `model.blend`, `shell.json` and a Workbench
`screenshot.png`; a build is not a render and needs no tier.

It imports only the backend's standard-library contracts, never the FastAPI
environment.
"""

from __future__ import annotations

import json
import math
import os
import shutil
import sys
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import bmesh
import bpy
from mathutils import Vector

BACKEND_ROOT = Path(__file__).resolve().parents[3]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.blender.cli import InputError, load_shell, parse_generator_arguments
from app.blender.generators._scene import (
    GeneratorError,
    export_glb,
    hidden_for_presentation,
    set_engine,
)
from app.blender.generators._scene import add_camera as _add_camera
from app.blender.generators._scene import aim_at as _aim_at
from app.blender.generators._scene import collection as _collection
from app.blender.generators._scene import reset_scene as _reset_scene
from app.blender.shell_contract import ShellContext, ShellWall, normalise_shell
from app.blender.verify import VerificationError, verify_shell

MM = 0.001
SCREENSHOT_SIZE = (800, 500)
SLAB_MM = 20
JOIN_TOLERANCE_MM = 1.0

_COLOURS = {
    "Floor": ((0.55, 0.40, 0.26), 0.5),
    "Wall": ((0.90, 0.88, 0.84), 0.9),
    "Ceiling": ((0.95, 0.95, 0.94), 0.9),
}


@dataclass
class ShellState:
    context: ShellContext
    materials: dict[str, bpy.types.Material] = field(default_factory=dict)
    mesh_names: set[str] = field(default_factory=set)


def m(value: float) -> float:
    return float(value) * MM


def _material(state: ShellState, key: str) -> bpy.types.Material:
    existing = state.materials.get(key)
    if existing is not None:
        return existing
    colour, roughness = _COLOURS[key]
    material = bpy.data.materials.new(key)
    material.diffuse_color = (*colour, 1)
    material.use_nodes = True
    shader = next((node for node in material.node_tree.nodes if node.type == "BSDF_PRINCIPLED"), None)
    if shader is not None:
        shader.inputs["Base Color"].default_value = (*colour, 1)
        shader.inputs["Roughness"].default_value = roughness
    state.materials[key] = material
    return material


def _prism(
    state: ShellState,
    name: str,
    polygon_mm: list[tuple[float, float]],
    z0_mm: float,
    z1_mm: float,
    collection: bpy.types.Collection,
    material: str,
) -> bpy.types.Object:
    """A closed solid from a 2D polygon extruded between two heights (millimetres)."""
    poly = [(m(x), m(y)) for x, y in polygon_mm]
    z0, z1 = m(z0_mm), m(z1_mm)
    n = len(poly)
    verts = [(x, y, z0) for x, y in poly] + [(x, y, z1) for x, y in poly]
    faces = [tuple(range(n - 1, -1, -1)), tuple(range(n, 2 * n))]
    for i in range(n):
        j = (i + 1) % n
        faces.append((i, j, j + n, i + n))
    mesh = bpy.data.meshes.new(name)
    mesh.from_pydata(verts, [], faces)
    mesh.update()
    bm = bmesh.new()
    bm.from_mesh(mesh)
    if n > 4:
        # An L- or U-shaped room's floor and ceiling are concave n-gons.
        bmesh.ops.triangulate(bm, faces=bm.faces[:])
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(mesh)
    bm.free()
    obj = bpy.data.objects.new(name, mesh)
    collection.objects.link(obj)
    obj.data.materials.append(_material(state, material))
    state.mesh_names.add(name)
    return obj


# --- walls ---------------------------------------------------------------------------------


def _complement(full: tuple[float, float], holes: list[tuple[float, float]]) -> list[tuple[float, float]]:
    lo, hi = full
    ordered = sorted((max(a, lo), min(b, hi)) for a, b in holes if b > a)
    out: list[tuple[float, float]] = []
    cursor = lo
    for a, b in ordered:
        if a > cursor:
            out.append((cursor, a))
        cursor = max(cursor, b)
    if cursor < hi:
        out.append((cursor, hi))
    return out


def _near(p: tuple[float, float], q: tuple[float, float]) -> bool:
    return math.hypot(p[0] - q[0], p[1] - q[1]) <= JOIN_TOLERANCE_MM


def _convex_at(corners, index: int) -> bool:
    n = len(corners)
    ax, ay = corners[index - 1]
    bx, by = corners[index]
    cx, cy = corners[(index + 1) % n]
    return (bx - ax) * (cy - by) - (by - ay) * (cx - bx) >= 0


def _overrun(ctx: ShellContext, wall: ShellWall, point: tuple[float, float]) -> float:
    """How far an outer wall runs past `point` so two outer walls meet at a convex corner.

    Only at a convex corner of the wall's own room that no other room shares;
    a shared wall and a reflex corner need none.
    """
    if wall.shared:
        return 0.0
    room = next(r for r in ctx.rooms if r.name == wall.rooms[0])
    for other in ctx.rooms:
        if other is not room and any(_near(point, c) for c in other.corners):
            return 0.0
    for index, corner in enumerate(room.corners):
        if _near(point, corner):
            return ctx.wall_thickness_mm if _convex_at(room.corners, index) else 0.0
    return 0.0


def _wall_height(ctx: ShellContext, wall: ShellWall) -> float:
    return max(r.height_mm for r in ctx.rooms if r.name in wall.rooms)


def _segment_polygon(
    wall: ShellWall, s: float, e: float, thickness: float
) -> list[tuple[float, float]]:
    """The four plan corners of one stretch of a wall, `s`..`e` along it."""
    length = wall.length_mm
    ux, uy = (wall.b[0] - wall.a[0]) / length, (wall.b[1] - wall.a[1]) / length
    nx, ny = uy, -ux  # right of travel: outward for a counter-clockwise room
    near, far = (-thickness / 2, thickness / 2) if wall.shared else (0.0, thickness)

    def at(t: float, d: float) -> tuple[float, float]:
        return (wall.a[0] + ux * t + nx * d, wall.a[1] + uy * t + ny * d)

    return [at(s, near), at(e, near), at(e, far), at(s, far)]


def _build_wall(state: ShellState, collection: bpy.types.Collection, wall: ShellWall) -> None:
    ctx = state.context
    thickness = ctx.wall_thickness_mm
    height = _wall_height(ctx, wall)
    holes = [(o["offset_mm"], o["offset_mm"] + o["width_mm"]) for o in wall.openings]
    full = (-_overrun(ctx, wall, wall.a), wall.length_mm + _overrun(ctx, wall, wall.b))
    for index, (s, e) in enumerate(_complement(full, holes)):
        _prism(state, f"Wall_{wall.id}_{index}", _segment_polygon(wall, s, e, thickness), 0, height, collection, "Wall")
    for index, opening in enumerate(wall.openings):
        s, e = opening["offset_mm"], opening["offset_mm"] + opening["width_mm"]
        polygon = _segment_polygon(wall, s, e, thickness)
        top = opening["sill_mm"] + opening["height_mm"]
        if top < height - 1e-6:
            _prism(state, f"Wall_{wall.id}_lintel_{index}", polygon, top, height, collection, "Wall")
        if opening["sill_mm"] > 1e-6:
            _prism(state, f"Wall_{wall.id}_sill_{index}", polygon, 0, opening["sill_mm"], collection, "Wall")


# --- the scene -----------------------------------------------------------------------------


def _bounds(ctx: ShellContext) -> tuple[float, float, float, float]:
    xs = [c[0] for room in ctx.rooms for c in room.corners]
    ys = [c[1] for room in ctx.rooms for c in room.corners]
    return min(xs), min(ys), max(xs), max(ys)


def _build_scene(state: ShellState) -> None:
    ctx = state.context
    _reset_scene()
    rooms_collection = _collection("01_Rooms")
    walls_collection = _collection("02_Walls")
    for room in ctx.rooms:
        corners = [list(c) for c in room.corners]
        _prism(state, f"Floor_{room.name}", corners, -SLAB_MM, 0, rooms_collection, "Floor")
        _prism(state, f"Ceiling_{room.name}", corners, room.height_mm, room.height_mm + SLAB_MM, rooms_collection, "Ceiling")
    for wall in ctx.walls:
        _build_wall(state, walls_collection, wall)

    x0, y0, x1, y1 = _bounds(ctx)
    centre = (m((x0 + x1) / 2), m((y0 + y1) / 2), m(ctx.ceiling_height_mm / 2))
    diagonal = m(math.hypot(x1 - x0, y1 - y0))
    distance = max(6.0, diagonal * 2.3)
    direction = Vector((0.4, -0.6, 1.0)).normalized()
    camera = _add_camera("CAM_Iso", tuple(Vector(centre) + direction * distance), (0, 0, 0))
    camera.data.clip_end = max(20.0, distance * 4)
    _aim_at(camera, centre)
    bpy.context.scene.camera = camera

    sun_data = bpy.data.lights.new("LGT_Sun", "SUN")
    sun_data.energy = 3.0
    sun = bpy.data.objects.new("LGT_Sun", sun_data)
    bpy.context.scene.collection.objects.link(sun)
    sun.rotation_euler = (math.radians(50), math.radians(10), math.radians(35))


def _write_screenshot(output_path: Path) -> None:
    """A Workbench frame of `CAM_Iso`: layout and proportion, no tier."""
    scene = bpy.context.scene
    set_engine("BLENDER_WORKBENCH")
    scene.render.resolution_x, scene.render.resolution_y = SCREENSHOT_SIZE
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


def _write_shell_json(state: ShellState, output_dir: Path) -> None:
    ctx = state.context
    x0, y0, x1, y1 = _bounds(ctx)
    document = {
        "kind": "apartment_shell",
        "blender_version": bpy.app.version_string,
        "input": ctx.input_document(),
        "walls": [
            {
                "id": wall.id,
                "a": list(wall.a),
                "b": list(wall.b),
                "length_mm": wall.length_mm,
                "shared": wall.shared,
                "rooms": list(wall.rooms),
                "openings": [dict(o) for o in wall.openings],
            }
            for wall in ctx.walls
        ],
        "bounds_mm": {"x": [x0, x1], "y": [y0, y1], "height": ctx.ceiling_height_mm},
        "warnings": list(ctx.warnings),
        "notes": [
            "All dimensions millimetres, in the plan's one frame.",
            "A shared wall is centred on the shared line; an outer wall is extruded outward from its room's interior face.",
        ],
    }
    (output_dir / "shell.json").write_text(
        json.dumps(document, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )


def _build_package(document: dict[str, Any], output_dir: Path) -> None:
    state = ShellState(context=normalise_shell(document))
    try:
        _build_scene(state)
    except GeneratorError:
        raise
    except Exception as error:
        raise GeneratorError(f"build: {type(error).__name__}: {error}") from error
    try:
        _write_shell_json(state, output_dir)
        _write_screenshot(output_dir / "screenshot.png")
    except GeneratorError:
        raise
    except Exception as error:
        raise GeneratorError(f"screenshot: {type(error).__name__}: {error}") from error
    try:
        # Ceilings stay in the .blend but out of the GLB, so a viewer sees into the rooms.
        export_glb({name for name in state.mesh_names if not name.startswith("Ceiling_")}, output_dir / "model.glb")
        bpy.ops.wm.save_as_mainfile(filepath=str(output_dir / "model.blend"), check_existing=False)
    except GeneratorError:
        raise
    except Exception as error:
        raise GeneratorError(f"export: {type(error).__name__}: {error}") from error
    try:
        verify_shell(output_dir)
    except VerificationError as error:
        raise GeneratorError(f"publish: {error}") from error


def main(argv: list[str] | None = None) -> int:
    stage: Path | None = None
    try:
        spec_path, output_path = parse_generator_arguments(list(sys.argv if argv is None else argv))
        document = load_shell(spec_path)
        stage = output_path.parent / f".{output_path.name}.tmp-{uuid.uuid4().hex}"
        stage.mkdir()
        _build_package(document, stage)
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
