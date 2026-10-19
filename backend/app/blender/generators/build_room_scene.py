"""Build a room scene around a built furniture package, in Blender 5.2
background mode (scene-rendering).

Usage (the arguments after ``--`` belong to this script)::

    blender --background --python build_room_scene.py -- \
      --scene room-scene.json --package /absolute/version-dir \
      --out /absolute/new-room-dir \
      --tier-frames 12 --tier-resolution 600 --tier-engine BLENDER_EEVEE

Only the standard-library `room_contract` is imported for validation; the
already-built package is composed by importing its `model.glb`, never by
rebuilding furniture geometry. Placement uses the imported mesh's own bounding
box, so no furniture-specific parameter is needed here. The three `--tier-*`
values come from the runner, from a guard ticket: the scene document names a
kind only (still or turntable) and the tier decides frames, resolution and
engine.
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

import bpy
from mathutils import Vector

BACKEND_ROOT = Path(__file__).resolve().parents[3]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.blender.cli import (
    InputError,
    TierArguments,
    load_json,
    parse_room_generator_arguments,
)
from app.blender.generators import _render
from app.blender.generators._scene import (
    GeneratorError,
    complement_intervals,
    is_convex_vertex,
    m,
    prism,
)
from app.blender.generators._scene import collection as _collection
from app.blender.generators._scene import link as _link
from app.blender.room_contract import (
    RoomBuildContext,
    SpecValidationError,
    normalise_room_scene,
    sight_clear,
)
from app.blender.verify import (
    VerificationError,
    verify_frames,
    verify_png,
)
from app.render.viewer import render_viewer

STILL_FILES = frozenset({"still.png", "scene.json"})
TURNTABLE_FILES = frozenset({"frames", "scene.json", "viewer.html"})
TURNTABLE_FRAME_HIDE_THRESHOLD = 0.3  # cos of the angle past which a wall hides
CAMERA_EYE_HEIGHT_MM = 1500
CAMERA_PULL_IN_MM = 600
TURNTABLE_RADIUS_FACTOR = 1.1
# A fraction *of* the ceiling height, kept strictly below it: the ceiling is
# never hidden (only walls are), so a camera at or above roofline looks
# straight into the solid ceiling slab instead of the room beneath it.
TURNTABLE_HEIGHT_FACTOR = 0.8


@dataclass
class RoomBuildState:
    context: RoomBuildContext
    package_overall: dict[str, float]
    tier: TierArguments
    materials: dict[str, bpy.types.Material] = field(default_factory=dict)
    imported_mesh_names: set[str] = field(default_factory=set)
    package_empty: bpy.types.Object | None = None


# --- scene / material setup ---------------------------------------------------------


def _reset_scene() -> None:
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    scene.unit_settings.system = "METRIC"
    scene.unit_settings.scale_length = 1.0
    scene.unit_settings.length_unit = "MILLIMETERS"
    scene.render.resolution_percentage = 100
    bpy.context.preferences.filepaths.save_version = 0
    world = bpy.data.worlds.new("Room")
    scene.world = world
    world.use_nodes = True
    shader = world.node_tree.nodes.get("Background")
    if shader is not None:
        # Deliberately dim and neutral: the room is lit by `_build_lights`'s
        # fixtures, not the world. A bright, wall-coloured world previously
        # washed every wall out into the sky with no visible edge or shadow.
        shader.inputs["Color"].default_value = (0.05, 0.05, 0.06, 1)
        shader.inputs["Strength"].default_value = 0.15


def _material(state: RoomBuildState, name: str, color: tuple[float, float, float], *, roughness: float = 0.85) -> None:
    material = bpy.data.materials.new(name)
    material.use_nodes = True
    shader = material.node_tree.nodes.get("Principled BSDF")
    if shader is not None:
        shader.inputs["Base Color"].default_value = (*color, 1)
        shader.inputs["Roughness"].default_value = roughness
        shader.inputs["Metallic"].default_value = 0.0
    state.materials[name] = material


def _build_materials(state: RoomBuildState) -> None:
    _material(state, "Wall", (0.80, 0.76, 0.68))
    _material(state, "Floor", (0.42, 0.30, 0.19), roughness=0.5)
    _material(state, "Ceiling", (0.92, 0.92, 0.90))
    _material(state, "Furnishing", (0.42, 0.45, 0.52), roughness=0.7)


def _aim(obj: bpy.types.Object, target: tuple[float, float, float]) -> None:
    obj.rotation_euler = (Vector(target) - Vector(obj.location)).to_track_quat("-Z", "Y").to_euler()


def _area_light(
    name: str, location: tuple[float, float, float], energy: float, size: float
) -> bpy.types.Object:
    data = bpy.data.lights.new(name, "AREA")
    data.energy = energy
    data.size = size
    obj = bpy.data.objects.new(name, data)
    bpy.context.scene.collection.objects.link(obj)
    obj.location = location
    return obj


def _build_lights(state: RoomBuildState) -> None:
    """Three area lights scaled to the room's own floor area and ceiling
    height, so a 14 m² fixture and a 32 m² one are both readably lit without
    per-fixture tuning (the original mock-up's fixed three-light rig
    only has to work for one object size, so it hardcodes its energies)."""

    ctx = state.context
    n = len(ctx.corners)
    area_mm2 = abs(
        sum(
            ctx.corners[i][0] * ctx.corners[(i + 1) % n][1]
            - ctx.corners[(i + 1) % n][0] * ctx.corners[i][1]
            for i in range(n)
        )
    ) / 2
    area_m2 = area_mm2 / 1_000_000
    cx, cy = ctx.centroid
    ceiling = ctx.height_mm
    # Bigger, dimmer-per-Watt fixtures than a first pass used: a light this
    # size close to nearby furniture previously blew every near surface out
    # to flat white even though far walls looked correctly exposed.
    size = max(2.0, math.sqrt(area_m2) * 0.9)
    energy = max(150.0, area_m2 * 18)

    ceiling_light = _area_light("LGT_Ceiling", (m(cx), m(cy), m(ceiling - 100)), energy, size)
    _aim(ceiling_light, (m(cx), m(cy), 0.0))

    key_x, key_y = cx - (cx - ctx.corners[0][0]) * 0.6, cy - (cy - ctx.corners[0][1]) * 0.6
    key_light = _area_light("LGT_Key", (m(key_x), m(key_y), m(ceiling * 0.85)), energy * 0.5, size * 0.8)
    _aim(key_light, (m(cx), m(cy), m(ceiling * 0.35)))

    fill_x, fill_y = cx + (cx - ctx.corners[0][0]) * 0.6, cy + (cy - ctx.corners[0][1]) * 0.6
    fill_light = _area_light("LGT_Fill", (m(fill_x), m(fill_y), m(ceiling * 0.7)), energy * 0.25, size)
    _aim(fill_light, (m(cx), m(cy), m(ceiling * 0.35)))


# --- geometry: one general "extruded polygon" primitive, floor/ceiling/walls all use it


def _prism(
    state: RoomBuildState,
    name: str,
    polygon_mm: list[tuple[float, float]],
    z0_mm: float,
    z1_mm: float,
    collection: bpy.types.Collection,
    material_key: str,
) -> bpy.types.Object:
    """A closed solid from a 2D polygon (millimetres) extruded between two heights
    (millimetres): the one primitive floor, ceiling and every wall segment are built from."""
    obj = prism(name, polygon_mm, z0_mm, z1_mm, collection)
    obj.data.materials.append(state.materials[material_key])
    return obj


def _wall_segment_polygon(wall, s: float, e: float, thickness: float) -> list[tuple[float, float]]:
    """The four world-space corners of one wall segment, `s`..`e` along the
    wall's own direction, extruded outward by `thickness` from the interior
    edge (so interior room dimensions are exactly the traced ones)."""

    ax, ay = wall.start
    ux, uy = wall.direction
    nx, ny = wall.outward_normal
    inner_s = (ax + ux * s, ay + uy * s)
    inner_e = (ax + ux * e, ay + uy * e)
    outer_s = (inner_s[0] + nx * thickness, inner_s[1] + ny * thickness)
    outer_e = (inner_e[0] + nx * thickness, inner_e[1] + ny * thickness)
    return [inner_s, inner_e, outer_e, outer_s]


def _build_floor_ceiling(state: RoomBuildState, collection: bpy.types.Collection) -> None:
    corners = [list(c) for c in state.context.corners]
    ceiling = state.context.height_mm
    _prism(state, "Floor", corners, -20, 0, collection, "Floor")
    _prism(state, "Ceiling", corners, ceiling, ceiling + 20, collection, "Ceiling")


def _build_wall(state: RoomBuildState, collection: bpy.types.Collection, wall) -> None:
    thickness = state.context.wall_thickness_mm
    ceiling = state.context.height_mm
    wall_openings = [o for o in state.context.openings if o["wall"] == wall.index]

    holes = [(o["offset_mm"], o["offset_mm"] + o["width_mm"]) for o in wall_openings]
    # Overrun an end by the wall thickness so adjacent walls meet cleanly at a
    # convex corner. At a reflex corner (the inner corner of an L) the overrun
    # would poke into the room, and the neighbouring wall already covers it.
    corners = state.context.corners
    count = len(corners)
    start_over = thickness if is_convex_vertex(corners, wall.index) else 0.0
    end_over = thickness if is_convex_vertex(corners, (wall.index + 1) % count) else 0.0
    full_range = (-start_over, wall.length_mm + end_over)
    for index, (s, e) in enumerate(complement_intervals(full_range, holes)):
        polygon = _wall_segment_polygon(wall, s, e, thickness)
        _prism(state, f"Wall_{wall.index}_{index}", polygon, 0, ceiling, collection, "Wall")

    for index, opening in enumerate(wall_openings):
        s, e = opening["offset_mm"], opening["offset_mm"] + opening["width_mm"]
        polygon = _wall_segment_polygon(wall, s, e, thickness)
        top = opening["sill_mm"] + opening["height_mm"]
        if top < ceiling - 1e-6:
            _prism(state, f"Wall_{wall.index}_lintel_{index}", polygon, top, ceiling, collection, "Wall")
        if opening["sill_mm"] > 1e-6:
            _prism(state, f"Wall_{wall.index}_sill_{index}", polygon, 0, opening["sill_mm"], collection, "Wall")


def _build_room_shell(state: RoomBuildState, room_collection: bpy.types.Collection) -> None:
    _build_floor_ceiling(state, _collection("01_FloorCeiling", room_collection))
    walls_collection = _collection("02_Walls", room_collection)
    for wall in state.context.walls:
        _build_wall(state, walls_collection, wall)


# --- furnishings: plain named boxes ---------------------------------------------------


def _build_furnishing(state: RoomBuildState, collection: bpy.types.Collection, furnishing: dict[str, Any]) -> None:
    name = f"FURN_{furnishing['name']}"
    bpy.ops.mesh.primitive_cube_add(
        size=1,
        location=(m(furnishing["x_mm"]), m(furnishing["y_mm"]), m(furnishing["z_mm"] + furnishing["height_mm"] / 2)),
    )
    obj = bpy.context.active_object
    obj.name = name
    obj.data.name = name
    obj.scale = (m(furnishing["width_mm"]), m(furnishing["depth_mm"]), m(furnishing["height_mm"]))
    obj.rotation_euler[2] = math.radians(furnishing["rotation_deg"])
    bpy.ops.object.transform_apply(location=False, rotation=True, scale=True)
    obj.data.materials.append(state.materials["Furnishing"])
    _link(obj, collection)


def _build_furnishings(state: RoomBuildState, room_collection: bpy.types.Collection) -> None:
    if not state.context.furnishings:
        return
    collection = _collection("04_Furnishings", room_collection)
    for furnishing in state.context.furnishings:
        _build_furnishing(state, collection, furnishing)


# --- importing and placing the published package --------------------------------------


def _import_package(package_dir: Path) -> list[bpy.types.Object]:
    before = set(bpy.data.objects)
    bpy.ops.import_scene.gltf(filepath=str(package_dir / "model.glb"))
    imported = [obj for obj in bpy.data.objects if obj not in before]
    if not imported:
        raise GeneratorError("build: the package GLB imported no objects")
    return imported


def _place_package(state: RoomBuildState, imported: list[bpy.types.Object], collection: bpy.types.Collection) -> bpy.types.Object:
    """Wrap the imported meshes in one empty and place them by their own
    bounding box - never by a furniture-specific parameter name, so this
    generator stays valid for any future furniture type."""

    meshes = [obj for obj in imported if obj.type == "MESH"]
    if not meshes:
        raise GeneratorError("build: the package GLB contains no mesh objects")
    state.imported_mesh_names = {obj.name for obj in meshes}

    points = [obj.matrix_world @ Vector(corner) for obj in meshes for corner in obj.bound_box]
    xs = [p.x for p in points]
    ys = [p.y for p in points]
    zs = [p.z for p in points]
    # Authoring convention shared with the original mock-up's cameras
    # (its `CAM_Iso` looks from -Y toward the origin): local -Y is the front,
    # local +Y is the back, and the object's base sits at local Z = 0.
    center_x, back_y, floor_z = (min(xs) + max(xs)) / 2, max(ys), min(zs)

    empty = bpy.data.objects.new("PackagePlacement", None)
    empty.empty_display_type = "PLAIN_AXES"
    bpy.context.scene.collection.objects.link(empty)
    for obj in imported:
        if obj.parent is None or obj.parent not in imported:
            world_matrix = obj.matrix_world.copy()
            obj.parent = empty
            obj.matrix_world = world_matrix
        _link(obj, collection)
    _link(empty, collection)

    nx, ny = state.context.placement["outward_normal"]
    theta = math.atan2(-nx, ny)  # rotates local +Y onto (nx, ny)
    cos_t, sin_t = math.cos(theta), math.sin(theta)
    rotated_x = center_x * cos_t - back_y * sin_t
    rotated_y = center_x * sin_t + back_y * cos_t

    back_left, back_right = state.context.placement["footprint"][0], state.context.placement["footprint"][1]
    target_x = m((back_left[0] + back_right[0]) / 2)
    target_y = m((back_left[1] + back_right[1]) / 2)

    empty.rotation_euler[2] = theta
    empty.location = (target_x - rotated_x, target_y - rotated_y, -floor_z)
    state.package_empty = empty
    return empty


# --- cameras --------------------------------------------------------------------------


def _add_camera(name: str, location: tuple[float, float, float]) -> bpy.types.Object:
    data = bpy.data.cameras.new(name)
    data.lens = 24
    data.clip_start = 0.05
    data.clip_end = 40
    camera = bpy.data.objects.new(name, data)
    bpy.context.scene.collection.objects.link(camera)
    camera.location = location
    return camera


def _still_camera(state: RoomBuildState) -> dict[str, Any]:
    ctx = state.context
    package_wall = ctx.walls[ctx.placement["wall"]]
    target_xy = ctx.placement["center"]
    # The corner farthest from the piece's wall that can see the piece without
    # the line of sight leaving the room (in an L the farthest corner may not).
    ordered = sorted(
        ctx.corners,
        key=lambda c: -abs(
            (c[0] - package_wall.start[0]) * package_wall.outward_normal[0]
            + (c[1] - package_wall.start[1]) * package_wall.outward_normal[1]
        ),
    )
    corner = next((c for c in ordered if sight_clear(c, target_xy, ctx.corners)), ordered[0])
    direction = Vector((target_xy[0] - corner[0], target_xy[1] - corner[1]))
    if direction.length > 1e-6:
        direction.normalize()
    else:
        direction = Vector((0, -1))
    position_xy = (corner[0] + direction.x * CAMERA_PULL_IN_MM, corner[1] + direction.y * CAMERA_PULL_IN_MM)
    location = (m(position_xy[0]), m(position_xy[1]), m(CAMERA_EYE_HEIGHT_MM))
    target = (m(target_xy[0]), m(target_xy[1]), m(state.package_overall["h"] / 2))

    camera = _add_camera("CAM_Still", location)
    _aim(camera, target)
    bpy.context.scene.camera = camera
    return {
        "location_mm": [position_xy[0], position_xy[1], CAMERA_EYE_HEIGHT_MM],
        "target_mm": [target_xy[0], target_xy[1], state.package_overall["h"] / 2],
    }


def _polygon_radius(corners: list[tuple[float, float]], centroid: tuple[float, float]) -> float:
    return max(math.hypot(x - centroid[0], y - centroid[1]) for x, y in corners)


def _turntable_cameras(state: RoomBuildState, frame_count: int) -> list[dict[str, Any]]:
    """One camera per frame, orbiting the room's centroid at a fixed height.

    Blender's own frame range is not used: each frame is rendered as its own
    still with its own camera and wall visibility, then written to
    `frames/frame_%03d.png`, which keeps the naming the retained reference
    viewer (`reference/viewer.html`) already expects.
    """

    ctx = state.context
    centroid = ctx.centroid
    radius = TURNTABLE_RADIUS_FACTOR * _polygon_radius(list(ctx.corners), centroid)
    height = TURNTABLE_HEIGHT_FACTOR * ctx.height_mm
    target = (m(centroid[0]), m(centroid[1]), m(ctx.height_mm / 2))

    frames = []
    for index in range(frame_count):
        angle = 2 * math.pi * index / frame_count
        position_xy = (centroid[0] + radius * math.cos(angle), centroid[1] + radius * math.sin(angle))
        location = (m(position_xy[0]), m(position_xy[1]), m(height))
        camera = _add_camera(f"CAM_Turntable_{index:03d}", location)
        _aim(camera, target)

        direction_to_camera = Vector((position_xy[0] - centroid[0], position_xy[1] - centroid[1]))
        if direction_to_camera.length > 1e-6:
            direction_to_camera.normalize()
        hidden_walls = [
            wall.index
            for wall in ctx.walls
            if direction_to_camera.x * wall.outward_normal[0] + direction_to_camera.y * wall.outward_normal[1]
            > TURNTABLE_FRAME_HIDE_THRESHOLD
        ]
        frames.append(
            {
                "index": index,
                "camera": camera,
                "hidden_walls": hidden_walls,
                "location_mm": [position_xy[0], position_xy[1], height],
            }
        )
    return frames


# --- rendering --------------------------------------------------------------------


def _configure_render(tier: TierArguments) -> None:
    _render.configure_render(tier)
    # Blender's shipped default (AgX in 5.2) rolls off bright highlights
    # gracefully; "Standard" clips them to flat white instead, which a
    # nearby light on a large flat furnishing surface reached first.
    bpy.context.scene.view_settings.exposure = -0.4


def _hidden(objects: list[bpy.types.Object]) -> list[tuple[bpy.types.Object, bool, bool]]:
    saved = []
    for obj in objects:
        saved.append((obj, obj.hide_get(), obj.hide_render))
        obj.hide_set(True)
        obj.hide_render = True
    return saved


def _restore(saved: list[tuple[bpy.types.Object, bool, bool]]) -> None:
    for obj, hide_viewport, hide_render in saved:
        obj.hide_set(hide_viewport)
        obj.hide_render = hide_render


def _walls_by_index(collection_name: str = "02_Walls") -> dict[int, list[bpy.types.Object]]:
    by_wall: dict[int, list[bpy.types.Object]] = {}
    for obj in bpy.data.objects:
        if not obj.name.startswith("Wall_"):
            continue
        wall_index = int(obj.name.split("_")[1])
        by_wall.setdefault(wall_index, []).append(obj)
    return by_wall


def _render_still(state: RoomBuildState, output_dir: Path) -> dict[str, Any]:
    _configure_render(state.tier)
    camera_info = _still_camera(state)
    bpy.context.scene.render.filepath = str(output_dir / "still.png")
    bpy.ops.render.render(write_still=True)
    return {"kind": "still", "camera": camera_info}


def _render_turntable(state: RoomBuildState, output_dir: Path, frame_count: int) -> dict[str, Any]:
    _configure_render(state.tier)
    frames_dir = output_dir / "frames"
    frames_dir.mkdir()
    walls_by_index = _walls_by_index()
    frame_infos = []
    for frame in _turntable_cameras(state, frame_count):
        bpy.context.scene.camera = frame["camera"]
        objects_to_hide = [
            obj for index in frame["hidden_walls"] for obj in walls_by_index.get(index, [])
        ]
        saved = _hidden(objects_to_hide)
        try:
            bpy.context.scene.render.filepath = str(frames_dir / f"frame_{frame['index']:03d}.png")
            bpy.ops.render.render(write_still=True)
        finally:
            _restore(saved)
        frame_infos.append(
            {
                "index": frame["index"],
                "location_mm": frame["location_mm"],
                "hidden_walls": frame["hidden_walls"],
            }
        )
    return {"kind": "turntable", "frame_count": frame_count, "frames": frame_infos}


# --- scene.json, verification and staged publication -----------------------------------


def _write_scene_data(state: RoomBuildState, output_render: dict[str, Any], output_dir: Path) -> None:
    ctx = state.context
    scene = {
        "kind": "room_scene",
        "schema_version": 1,
        "blender_version": bpy.app.version_string,
        "units": "mm",
        "input": ctx.input_document(),
        "resolved": {
            "corners": [list(c) for c in ctx.corners],
            "walls": [
                {
                    "index": wall.index,
                    "start": list(wall.start),
                    "end": list(wall.end),
                    "length_mm": wall.length_mm,
                    "outward_normal": list(wall.outward_normal),
                }
                for wall in ctx.walls
            ],
            "placement": {
                "wall": ctx.placement["wall"],
                "offset_mm": ctx.placement["offset_mm"],
                "center_mm": list(ctx.placement["center"]),
            },
            "centroid_mm": list(ctx.centroid),
            "package_overall_mm": state.package_overall,
        },
        "output": {
            **output_render,
            "tier_frames": state.tier.frames,
            "resolution": state.tier.resolution,
            "engine": state.tier.engine,
        },
    }
    (output_dir / "scene.json").write_text(
        json.dumps(scene, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )


def _verify_still(output_dir: Path, size: int) -> None:
    names = {path.name for path in output_dir.iterdir()}
    if names != STILL_FILES:
        raise GeneratorError(f"publish: expected {sorted(STILL_FILES)}, got {sorted(names)}")
    json.loads((output_dir / "scene.json").read_text(encoding="utf-8"))
    verify_png(output_dir / "still.png", (size, size))


def _verify_turntable(output_dir: Path, frame_count: int, size: int) -> None:
    top_level = {path.name for path in output_dir.iterdir()}
    if top_level != TURNTABLE_FILES:
        raise GeneratorError(f"publish: expected {sorted(TURNTABLE_FILES)}, got {sorted(top_level)}")
    json.loads((output_dir / "scene.json").read_text(encoding="utf-8"))
    verify_frames(output_dir, frame_count, size)


def _build_scene(state: RoomBuildState, package_dir: Path, output_dir: Path) -> None:
    try:
        _reset_scene()
        _build_materials(state)
        room_collection = _collection("Room")
        _build_room_shell(state, room_collection)
        _build_lights(state)
        _build_furnishings(state, room_collection)
        package_collection = _collection("03_Package", room_collection)
        imported = _import_package(package_dir)
        _place_package(state, imported, package_collection)

        layers = json.loads((package_dir / "spec.json").read_text(encoding="utf-8")).get("layers", {})
        expected_names = {name for names in layers.values() for name in names}
        if expected_names and expected_names != state.imported_mesh_names:
            missing = sorted(expected_names - state.imported_mesh_names)
            extra = sorted(state.imported_mesh_names - expected_names)
            raise GeneratorError(
                f"build: imported meshes do not match the package's layers (missing={missing}, extra={extra})"
            )
    except GeneratorError:
        raise
    except Exception as error:
        raise GeneratorError(f"build: {type(error).__name__}: {error}") from error

    try:
        if state.context.output["kind"] == "still":
            output_render = _render_still(state, output_dir)
            _write_scene_data(state, output_render, output_dir)
        else:
            frame_count = state.tier.frames
            if os.environ.get("ROOM_SCENE_TEST_FAIL_PHASE") == "render":
                raise RuntimeError("injected test render failure")
            output_render = _render_turntable(state, output_dir, frame_count)
            _write_scene_data(state, output_render, output_dir)
            (output_dir / "viewer.html").write_text(
                render_viewer(
                    frame_count,
                    title="Room",
                    meta=f"{state.tier.resolution}×{state.tier.resolution} {state.tier.engine}",
                ),
                encoding="utf-8",
            )
    except GeneratorError:
        raise
    except Exception as error:
        raise GeneratorError(f"render: {type(error).__name__}: {error}") from error

    try:
        if state.context.output["kind"] == "still":
            _verify_still(output_dir, state.tier.resolution)
        else:
            _verify_turntable(output_dir, state.tier.frames, state.tier.resolution)
    except GeneratorError:
        raise
    except VerificationError as error:
        raise GeneratorError(f"publish: {error}") from error
    except Exception as error:
        raise GeneratorError(f"publish: {type(error).__name__}: {error}") from error


def main(argv: list[str] | None = None) -> int:
    stage: Path | None = None
    try:
        scene_path, package_dir, output_path, tier = parse_room_generator_arguments(
            list(sys.argv if argv is None else argv)
        )
        document = load_json(scene_path)
        package_spec = json.loads((package_dir / "spec.json").read_text(encoding="utf-8"))
        package_overall = package_spec.get("overall")
        if not isinstance(package_overall, dict):
            raise InputError(f"validation: {package_dir / 'spec.json'} has no 'overall' dimensions")
        try:
            context = normalise_room_scene(document, package_overall=package_overall)
        except SpecValidationError as error:
            raise InputError(f"validation: {error}") from error

        stage = output_path.parent / f".{output_path.name}.tmp-{uuid.uuid4().hex}"
        stage.mkdir()
        state = RoomBuildState(context=context, package_overall=package_overall, tier=tier)
        _build_scene(state, package_dir, stage)
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
