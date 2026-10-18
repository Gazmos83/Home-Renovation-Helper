#!/usr/bin/env python3
"""Generate chunked Blender Python that builds an apartment shell from a manifest.

The generated code is meant to be sent to Blender through MCP execute_blender_code,
one chunk at a time. It uses only bpy and mathutils.
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path


MATERIALS = {
    "oak_floor": (0.45, 0.28, 0.14, 0.45, 0.0),
    "warm_white_paint": (0.78, 0.75, 0.70, 0.55, 0.0),
    "matte_white": (0.82, 0.82, 0.80, 0.7, 0.0),
    "glass": (0.85, 0.90, 0.92, 0.05, 1.0),
    "door_wood": (0.25, 0.14, 0.07, 0.4, 0.0),
}


def load(path: Path) -> dict:
    return json.loads(path.read_text())


def polygon(room: dict) -> list[tuple[float, float]]:
    pts = [(float(p[0]), float(p[1])) for p in room["polygon"]]
    if len(pts) >= 2 and pts[0] == pts[-1]:
        pts = pts[:-1]
    area = 0.0
    for i, (x1, y1) in enumerate(pts):
        x2, y2 = pts[(i + 1) % len(pts)]
        area += x1 * y2 - x2 * y1
    if area < 0:
        pts.reverse()
    return pts


def centroid(pts: list[tuple[float, float]]) -> tuple[float, float]:
    return sum(p[0] for p in pts) / len(pts), sum(p[1] for p in pts) / len(pts)


def edge_key(a: tuple[float, float], b: tuple[float, float]) -> tuple:
    qa = (round(a[0], 3), round(a[1], 3))
    qb = (round(b[0], 3), round(b[1], 3))
    return tuple(sorted((qa, qb)))


def outward(a, b, center) -> tuple[float, float]:
    dx, dy = b[0] - a[0], b[1] - a[1]
    length = math.hypot(dx, dy) or 1.0
    n1 = (dy / length, -dx / length)
    mid = ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)
    toward = (center[0] - mid[0], center[1] - mid[1])
    if n1[0] * toward[0] + n1[1] * toward[1] > 0:
        return (-n1[0], -n1[1])
    return n1


def py_header() -> str:
    return '''import bpy
import math
from mathutils import Vector

def ensure_collection(name):
    col = bpy.data.collections.get(name)
    if col is None:
        col = bpy.data.collections.new(name)
        bpy.context.scene.collection.children.link(col)
    return col

def link(obj, col):
    for c in list(obj.users_collection):
        c.objects.unlink(obj)
    col.objects.link(obj)

def principled(name, base, roughness, transmission=0.0):
    mat = bpy.data.materials.get(name)
    if mat is None:
        mat = bpy.data.materials.new(name)
        mat.use_nodes = True
    nt = mat.node_tree
    bsdf = next(n for n in nt.nodes if n.type == "BSDF_PRINCIPLED")
    bsdf.inputs["Base Color"].default_value = (*base, 1)
    bsdf.inputs["Roughness"].default_value = roughness
    if "Transmission Weight" in bsdf.inputs:
        bsdf.inputs["Transmission Weight"].default_value = transmission
    elif "Transmission" in bsdf.inputs:
        bsdf.inputs["Transmission"].default_value = transmission
    mat.diffuse_color = (*base, 1)
    return mat

def assign(obj, mat_name):
    mat = bpy.data.materials.get(mat_name)
    if mat is None:
        return
    if obj.data.materials:
        obj.data.materials[0] = mat
    else:
        obj.data.materials.append(mat)
'''


def scene_chunk(data: dict) -> str:
    height = float(data.get("ceiling_height_m", 2.5))
    lines = [
        py_header(),
        "scene = bpy.context.scene",
        "scene.unit_settings.system = 'METRIC'",
        "scene.unit_settings.scale_length = 1.0",
        "scene.unit_settings.length_unit = 'METERS'",
        "for name in ('Shell', 'Openings', 'Cameras', 'Lights', 'Furniture', 'References'):",
        "    ensure_collection(name)",
        "for obj in list(bpy.data.objects):",
        "    if obj.name in {'Cube', 'Light', 'Camera'}:",
        "        bpy.data.objects.remove(obj, do_unlink=True)",
    ]
    for name, (r, g, b, rough, trans) in MATERIALS.items():
        lines.append(
            f"principled({name!r}, ({r}, {g}, {b}), {rough}, {trans})"
        )
    lines.append(f"print('apartment scene ready, ceiling {height} m')")
    return "\n".join(lines) + "\n"


def rooms_chunk(data: dict) -> str:
    height = float(data.get("ceiling_height_m", 2.5))
    thick = float(data.get("wall_thickness_m", 0.12))
    slab = float(data.get("slab_thickness_m", 0.18))
    lines = [py_header(), "shell = ensure_collection('Shell')", "walls = []"]
    edge_owners: dict[tuple, int] = {}
    for room in data["rooms"]:
        for i, a in enumerate(polygon(room)):
            b = polygon(room)[(i + 1) % len(polygon(room))]
            edge_owners[edge_key(a, b)] = edge_owners.get(edge_key(a, b), 0) + 1

    seen = set()
    for room in data["rooms"]:
        pts = polygon(room)
        center = centroid(pts)
        rid = room["id"]
        floor_mat = room.get("floor_material", "oak_floor")
        wall_mat = room.get("wall_material", "warm_white_paint")
        ceil_mat = room.get("ceiling_material", "matte_white")
        xs = [p[0] for p in pts]
        ys = [p[1] for p in pts]
        # Bounding floor is a stand-in; the agent replaces it with the real polygon mesh if the room is non-rectangular.
        lines.append(f"# room {rid}")
        lines.append("bpy.ops.mesh.primitive_plane_add(size=1)")
        lines.append("floor = bpy.context.active_object")
        lines.append(f"floor.name = 'floor_{rid}'")
        lines.append(f"floor.scale = ({max(xs)-min(xs)}, {max(ys)-min(ys)}, 1)")
        lines.append(f"floor.location = ({(min(xs)+max(xs))/2}, {(min(ys)+max(ys))/2}, {-slab/2})")
        lines.append("link(floor, shell)")
        lines.append(f"assign(floor, {floor_mat!r})")
        lines.append("bpy.ops.mesh.primitive_plane_add(size=1)")
        lines.append("ceil = bpy.context.active_object")
        lines.append(f"ceil.name = 'ceiling_{rid}'")
        lines.append(f"ceil.scale = ({max(xs)-min(xs)}, {max(ys)-min(ys)}, 1)")
        lines.append(f"ceil.location = ({(min(xs)+max(xs))/2}, {(min(ys)+max(ys))/2}, {height})")
        lines.append("link(ceil, shell)")
        lines.append(f"assign(ceil, {ceil_mat!r})")
        for i, a in enumerate(pts):
            b = pts[(i + 1) % len(pts)]
            key = edge_key(a, b)
            if key in seen:
                continue
            seen.add(key)
            length = math.dist(a, b)
            mid = ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)
            angle = math.atan2(b[1] - a[1], b[0] - a[0])
            shared = edge_owners[key] > 1
            if shared:
                ox, oy = 0.0, 0.0
            else:
                nx, ny = outward(a, b, center)
                ox, oy = nx * thick / 2, ny * thick / 2
            lines.append("bpy.ops.mesh.primitive_cube_add(size=1)")
            lines.append("wall = bpy.context.active_object")
            lines.append(f"wall.name = 'wall_{rid}_{i}'")
            lines.append(f"wall.dimensions = ({length}, {thick}, {height})")
            lines.append(f"wall.location = ({mid[0] + ox}, {mid[1] + oy}, {height / 2})")
            lines.append(f"wall.rotation_euler[2] = {angle}")
            lines.append("link(wall, shell)")
            lines.append(f"assign(wall, {wall_mat!r})")
            lines.append("walls.append(wall)")
    lines.append(f"print('built {len(data['rooms'])} rooms')")
    return "\n".join(lines) + "\n"


def openings_chunk(data: dict) -> str:
    thick = float(data.get("wall_thickness_m", 0.12))
    lines = [
        py_header(),
        "openings = ensure_collection('Openings')",
        "shell_walls = [o for o in bpy.data.objects if o.name.startswith('wall_')]",
    ]
    for opening in data.get("openings") or []:
        a = (float(opening["from"][0]), float(opening["from"][1]))
        b = (float(opening["to"][0]), float(opening["to"][1]))
        mid = ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)
        angle = math.atan2(b[1] - a[1], b[0] - a[0])
        width = float(opening["width_m"])
        oheight = float(opening["height_m"])
        sill = float(opening.get("sill_m", 0))
        kind = opening.get("kind", "opening")
        lines.append("bpy.ops.mesh.primitive_cube_add(size=1)")
        lines.append("cutter = bpy.context.active_object")
        lines.append(f"cutter.name = 'cut_{opening['id']}'")
        lines.append(f"cutter.dimensions = ({width}, {thick * 3}, {oheight})")
        lines.append(f"cutter.location = ({mid[0]}, {mid[1]}, {sill + oheight / 2})")
        lines.append(f"cutter.rotation_euler[2] = {angle}")
        lines.append("cutter.display_type = 'WIRE'")
        lines.append("link(cutter, openings)")
        lines.append("for wall in shell_walls:")
        lines.append("    if (wall.location.xy - cutter.location.xy).length < max(wall.dimensions.x, wall.dimensions.y):")
        lines.append("        mod = wall.modifiers.new(cutter.name, 'BOOLEAN')")
        lines.append("        mod.operation = 'DIFFERENCE'")
        lines.append("        mod.object = cutter")
        lines.append("        mod.solver = 'FLOAT'")
        if kind == "window":
            lines.append("bpy.ops.mesh.primitive_cube_add(size=1)")
            lines.append("glass = bpy.context.active_object")
            lines.append(f"glass.name = 'glass_{opening['id']}'")
            lines.append(f"glass.dimensions = ({width - 0.08}, 0.01, {oheight - 0.08})")
            lines.append(f"glass.location = ({mid[0]}, {mid[1]}, {sill + oheight / 2})")
            lines.append(f"glass.rotation_euler[2] = {angle}")
            lines.append("link(glass, openings)")
            lines.append("assign(glass, 'glass')")
        if kind == "door":
            lines.append("bpy.ops.mesh.primitive_cube_add(size=1)")
            lines.append("door = bpy.context.active_object")
            lines.append(f"door.name = 'door_{opening['id']}'")
            lines.append(f"door.dimensions = ({width - 0.04}, 0.04, {oheight - 0.02})")
            lines.append(f"door.location = ({mid[0]}, {mid[1]}, {oheight / 2})")
            lines.append(f"door.rotation_euler[2] = {angle}")
            lines.append("link(door, openings)")
            lines.append("assign(door, 'door_wood')")
    lines.append("print('openings cut')")
    return "\n".join(lines) + "\n"


def cameras_chunk(data: dict) -> str:
    lines = [py_header(), "cams = ensure_collection('Cameras')"]
    for photo in data.get("photos") or []:
        cam = photo.get("camera") or {}
        loc = cam.get("location")
        look = cam.get("look_at")
        if not loc or not look:
            continue
        lens = photo.get("lens_mm", 24)
        lines.append("cam_data = bpy.data.cameras.new(" + repr("cam_" + photo["id"]) + ")")
        lines.append(f"cam_data.lens = {float(lens)}")
        lines.append("cam_data.clip_end = 100")
        lines.append("cam_obj = bpy.data.objects.new(cam_data.name, cam_data)")
        lines.append(f"cam_obj.location = ({loc[0]}, {loc[1]}, {loc[2]})")
        lines.append(
            f"direction = Vector(({look[0]}, {look[1]}, {look[2]})) - cam_obj.location"
        )
        lines.append("cam_obj.rotation_euler = direction.to_track_quat('-Z', 'Y').to_euler()")
        lines.append("link(cam_obj, cams)")
        lines.append("bpy.context.scene.camera = cam_obj")
    lines.append("print('cameras placed')")
    return "\n".join(lines) + "\n"


def render_chunk(data: dict) -> str:
    lines = [
        py_header(),
        "scene = bpy.context.scene",
        "scene.render.engine = 'CYCLES'",
        "scene.cycles.device = 'GPU'",
        "scene.cycles.samples = 128",
        "scene.cycles.use_denoising = True",
        "scene.view_settings.view_transform = 'AgX'",
        "scene.view_settings.look = 'AgX - Medium High Contrast'",
        "scene.render.resolution_x = 1280",
        "scene.render.resolution_y = 720",
        "scene.render.resolution_percentage = 100",
        "scene.render.image_settings.file_format = 'PNG'",
        "world = scene.world or bpy.data.worlds.new('World')",
        "scene.world = world",
        "world.use_nodes = True",
        "bg = world.node_tree.nodes.get('Background')",
        "if bg:",
        "    bg.inputs['Color'].default_value = (0.55, 0.62, 0.7, 1)",
        "    bg.inputs['Strength'].default_value = 0.35",
        "lights = ensure_collection('Lights')",
    ]
    for light in data.get("lights") or []:
        loc = light["location"]
        rot = light.get("rotation_euler_deg", [0, 0, 0])
        size = light.get("size_m", [1.2, 1.2])
        if isinstance(size, (int, float)):
            size = [size, size]
        lines.append(f"light_data = bpy.data.lights.new({light['id']!r}, {light.get('type', 'AREA')!r})")
        lines.append(f"light_data.energy = {float(light.get('energy', 80))}")
        lines.append(f"light_data.size = {float(size[0])}")
        if light.get("type", "AREA") == "AREA":
            lines.append(f"light_data.size_y = {float(size[1])}")
        lines.append(f"light_obj = bpy.data.objects.new({light['id']!r}, light_data)")
        lines.append(f"light_obj.location = ({loc[0]}, {loc[1]}, {loc[2]})")
        lines.append(
            f"light_obj.rotation_euler = ({math.radians(rot[0])}, {math.radians(rot[1])}, {math.radians(rot[2])})"
        )
        lines.append("link(light_obj, lights)")
    lines.append("print('cycles preview settings applied')")
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    data = load(args.manifest)
    args.out.mkdir(parents=True, exist_ok=True)
    chunks = {
        "01_scene.py": scene_chunk(data),
        "02_rooms.py": rooms_chunk(data),
        "03_openings.py": openings_chunk(data),
        "04_cameras.py": cameras_chunk(data),
        "05_render.py": render_chunk(data),
    }
    for name, text in chunks.items():
        (args.out / name).write_text(text)
        print(f"wrote {args.out / name} ({len(text.splitlines())} lines)")


if __name__ == "__main__":
    main()
