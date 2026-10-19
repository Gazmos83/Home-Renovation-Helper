"""The room-composition scene, shared by its build and its render (room-composition).

Builds one room (with `build_room_scene`'s shell, materials and lights) or one
apartment (with `build_shell`'s shared walls), then places every item of a stored
composition document from its `resolved` block:

* a piece from its built version's `model.glb`;
* a stand-in as a box in its colour;
* a library model with the bundled glTF or OBJ importer, stretched on each axis to
  exactly its stated size, its lowest point on the floor.

A ceiling-layer stand-in or model hangs instead: its lowest point is at the resolved
item's `base_mm`, which puts its top at its room's ceiling (composition-ceiling-layer).
A hidden item is not placed; the report lists it with `hidden: true`, and every placed
item's report entry names it and lists its meshes (hidden-room-items).
An LED strip is an emissive bar on its wall with one rectangular area light, and a lamp's
light is `LGT_Lamp_<id>` (room-lamp-lights, room-led-strips).
A floor finish gives every floor a procedural tile material from the Brick Texture node;
`flat_floor` swaps in a plain tile colour while the screenshot and `model.glb` are made
(room-floor-finish).

Importable only inside Blender. Nothing here renders; `render_composition.py` does,
behind the render guard. The only importers called are the two that the checked-in
generators use, on files that passed the model-library checks (CLAUDE.md §8).
"""

from __future__ import annotations

import math
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import bpy
from mathutils import Matrix, Vector

from app.blender.composition_contract import (
    apartment_wall_labels,
    room_geometry,
    surface_map,
)
from app.blender.generators import build_room_scene as room_gen
from app.blender.generators import build_shell as shell_gen
from app.blender.generators._scene import GeneratorError
from app.blender.generators.check_model import import_objects, measure
from app.blender.room_contract import interior_point
from app.blender.shell_contract import normalise_shell
from app.blender.spec_contract import SpecValidationError

MM = 0.001


def m(value: float) -> float:
    return float(value) * MM


@dataclass
class CompositionScene:
    document: dict[str, Any]
    rooms: list[Any] = field(default_factory=list)  # room shims: corners, walls, height_mm, centroid
    centre_mm: tuple[float, float] = (0.0, 0.0)
    ceiling_mm: float = 2500.0
    radius_mm: float = 1000.0
    report: list[dict[str, Any]] = field(default_factory=list)
    # Every placed item's meshes, for the surface map's `items`.
    item_meshes: list[Any] = field(default_factory=list)
    # The floors that carry the document's tile finish, if it has one (room-floor-finish).
    floors: list[Any] = field(default_factory=list)


def _shim(room: dict[str, Any]) -> SimpleNamespace:
    geometry = room_geometry(room["name"], {
        "corners_mm": room["corners"], "height_mm": room["height_mm"],
        "wall_thickness_mm": room["wall_thickness_mm"], "openings": room["openings"],
    })
    return SimpleNamespace(
        name=geometry.name, corners=geometry.corners, walls=geometry.walls, openings=geometry.openings,
        height_mm=geometry.height_mm, wall_thickness_mm=geometry.wall_thickness_mm,
        centroid=interior_point(geometry.corners),
        # Below 1 when the room has lamp lights; a document from before them has none (room-lamp-lights).
        rig_factor=float(room.get("rig_factor", 1.0)),
    )


def _bounds(rooms: list[Any]) -> tuple[float, float, float, float]:
    xs = [c[0] for room in rooms for c in room.corners]
    ys = [c[1] for room in rooms for c in room.corners]
    return min(xs), min(ys), max(xs), max(ys)


def _build_shells(scene: CompositionScene, state: SimpleNamespace) -> None:
    resolved = scene.document["resolved"]
    if "apartment" in scene.document["scope"]:
        shell = SimpleNamespace(context=normalise_shell(resolved["shell"]), materials={}, mesh_names=set())
        shell_gen._build_scene(shell)  # resets the scene, builds every floor, ceiling and shared wall once
        room_gen._build_materials(state)
    else:
        room_gen._reset_scene()
        room_gen._build_materials(state)
        state.context = scene.rooms[0]
        room_gen._build_room_shell(state, room_gen._collection("Room"))
    for room in scene.rooms:
        state.context = room
        room_gen._build_lights(state, room.rig_factor)


def _wrap(name: str, objects: list[bpy.types.Object], collection: bpy.types.Collection) -> bpy.types.Object:
    """One empty named `ITEM_<id>` holding `objects` (their world transforms kept)."""
    empty = bpy.data.objects.new(name, None)
    empty.empty_display_type = "PLAIN_AXES"
    collection.objects.link(empty)
    for obj in objects:
        if obj.parent is None or obj.parent not in objects:
            world = obj.matrix_world.copy()
            obj.parent = empty
            obj.matrix_world = world
        room_gen._link(obj, collection)
    return empty


def _local_bounds(meshes: list[bpy.types.Object]) -> tuple[Vector, Vector]:
    points = [obj.matrix_world @ Vector(corner) for obj in meshes for corner in obj.bound_box]
    low = Vector((min(p.x for p in points), min(p.y for p in points), min(p.z for p in points)))
    high = Vector((max(p.x for p in points), max(p.y for p in points), max(p.z for p in points)))
    return low, high


def _pose(empty: bpy.types.Object, low: Vector, high: Vector, item: dict[str, Any], scale: Vector) -> None:
    """Scale, turn and move the wrapped objects so their footprint centre is the item's
    centre and their lowest point is on the floor (or at `base_mm` for a ceiling-layer item).
    An imported model's front is local -Y;
    the composition's item frame faces +Y, hence the extra half turn."""
    centre_local = Vector(((low.x + high.x) / 2, (low.y + high.y) / 2, low.z))
    rotation = math.radians(item["rotation_deg"]) + math.pi
    turn = Matrix.Rotation(rotation, 4, "Z")
    stretch = Matrix.Diagonal((*scale, 1.0))
    offset = turn @ stretch @ centre_local
    cx, cy = item["centre_mm"]
    empty.matrix_world = Matrix.Translation(Vector((m(cx), m(cy), m(item.get("base_mm", 0.0)))) - offset) @ turn @ stretch


def _place_piece(item: dict[str, Any], source: dict[str, Any], pieces_root: Path, collection) -> list[bpy.types.Object]:
    folder = pieces_root / source["package_id"] / f"v{source['version']}"
    if not (folder / "model.glb").is_file():
        raise GeneratorError(f"build: {source['package_id']} version {source['version']} has no built model")
    imported = import_objects(folder / "model.glb", "glb")
    meshes = [obj for obj in imported if obj.type == "MESH"]
    if not meshes:
        raise GeneratorError(f"build: {source['package_id']} version {source['version']} has no mesh")
    empty = _wrap(f"ITEM_{item['id']}", imported, collection)
    low, high = _local_bounds(meshes)
    _pose(empty, low, high, item, Vector((1.0, 1.0, 1.0)))
    return meshes


def _place_model(item: dict[str, Any], source: dict[str, Any], models_root: Path, collection) -> tuple[list, Vector]:
    path = models_root / source["model_id"] / source["entry"]
    imported = import_objects(path, source["kind"])
    meshes = [obj for obj in imported if obj.type == "MESH"]
    if not meshes:
        raise GeneratorError(f"build: the model {item['id']} has no mesh")
    size, _triangles, _low = measure(meshes)
    if min(size.values()) <= 0:
        raise GeneratorError(f"build: the model {item['id']} is flat on one axis and cannot be stretched")
    stated = item["size_mm"]
    scale = Vector((stated["w"] / size["x"], stated["d"] / size["y"], stated["h"] / size["z"]))
    empty = _wrap(f"ITEM_{item['id']}", imported, collection)
    low, high = _local_bounds(meshes)
    _pose(empty, low, high, item, scale)
    return meshes, scale


def _linear(channel: float) -> float:
    """An sRGB channel (as `#rrggbb` gives it) in the linear space shader colours use."""
    return channel / 12.92 if channel <= 0.04045 else ((channel + 0.055) / 1.055) ** 2.4


def _place_stand_in(item: dict[str, Any], colour: str, collection) -> list[bpy.types.Object]:
    size = item["size_mm"]
    mesh = bpy.data.meshes.new(f"STAND_{item['id']}")
    w, d, h = m(size["w"]), m(size["d"]), m(size["h"])
    verts = [(x, y, z) for z in (0, h) for y in (-d / 2, d / 2) for x in (-w / 2, w / 2)]
    faces = [(0, 2, 3, 1), (4, 5, 7, 6), (0, 1, 5, 4), (2, 6, 7, 3), (0, 4, 6, 2), (1, 3, 7, 5)]
    mesh.from_pydata(verts, [], faces)
    mesh.update()
    obj = bpy.data.objects.new(f"STAND_{item['id']}", mesh)
    collection.objects.link(obj)
    material = bpy.data.materials.new(f"Colour_{item['id']}")
    material.use_nodes = True
    shader = next((n for n in material.node_tree.nodes if n.type == "BSDF_PRINCIPLED"), None)
    rgb = tuple(_linear(int(colour[i:i + 2], 16) / 255) for i in (1, 3, 5))
    if shader is not None:
        shader.inputs["Base Color"].default_value = (*rgb, 1)
    material.diffuse_color = (*rgb, 1)
    obj.data.materials.append(material)
    cx, cy = item["centre_mm"]
    obj.location = (m(cx), m(cy), m(item.get("base_mm", 0.0)))
    obj.rotation_euler[2] = math.radians(item["rotation_deg"])
    return [obj]


def _final(meshes: list[bpy.types.Object], rotation_deg: float) -> tuple[dict[str, float], float]:
    """The placed item's size in its own frame (width, depth, height in mm), turned back by
    its rotation so a turned item is not measured by its world bounding box, and its lowest
    point above the floor in mm."""
    bpy.context.view_layer.update()
    depsgraph = bpy.context.evaluated_depsgraph_get()
    unturn = Matrix.Rotation(-math.radians(rotation_deg), 4, "Z")
    low = Vector((float("inf"),) * 3)
    high = Vector((float("-inf"),) * 3)
    for obj in meshes:
        evaluated = obj.evaluated_get(depsgraph)
        mesh = evaluated.to_mesh()
        try:
            for vertex in mesh.vertices:
                point = unturn @ (evaluated.matrix_world @ vertex.co)
                low = Vector(map(min, low, point))
                high = Vector(map(max, high, point))
        finally:
            evaluated.to_mesh_clear()
    size = high - low
    return {"x": round(size.x * 1000, 1), "y": round(size.y * 1000, 1), "z": round(size.z * 1000, 1)}, round(low.z * 1000, 1)


def build_scene(document: dict[str, Any], *, pieces_root: Path, models_root: Path) -> CompositionScene:
    """The whole composition in the current Blender session, with its build report."""
    scene = CompositionScene(document=document)
    resolved = document["resolved"]
    scene.rooms = [_shim(room) for room in resolved["rooms"]]
    x0, y0, x1, y1 = _bounds(scene.rooms)
    scene.centre_mm = ((x0 + x1) / 2, (y0 + y1) / 2)
    if len(scene.rooms) == 1:
        scene.centre_mm = tuple(scene.rooms[0].centroid)
    scene.ceiling_mm = max(room.height_mm for room in scene.rooms)
    scene.radius_mm = max(math.hypot(c[0] - scene.centre_mm[0], c[1] - scene.centre_mm[1])
                          for room in scene.rooms for c in room.corners)
    state = SimpleNamespace(context=None, materials={})
    _build_shells(scene, state)

    items = room_gen._collection("03_Items")
    by_id = {item["id"]: item for item in document["items"]}
    for placed in resolved["items"]:
        item = by_id[placed["id"]]
        if placed.get("hidden"):
            scene.report.append({"id": item["id"], "type": item["type"], "hidden": True})
            continue
        entry: dict[str, Any] = {"id": item["id"], "type": item["type"], "stated_mm": placed["size_mm"]}
        entry["name"] = f"{item['package_id']} v{item['version']}" if item["type"] == "piece" else item["name"]
        if item["type"] == "led-strip":
            meshes = _place_led_strip(placed, items)
            entry["strip"] = {key: placed["strip"][key] for key in (
                "length_mm", "lumens_per_m", "kelvin", "watts", "wall", "offset_mm", "mount_height_mm", "facing",
            )}
        elif item["type"] == "piece":
            meshes = _place_piece(placed, item, pieces_root, items)
        elif item["type"] == "model":
            meshes, scale = _place_model(placed, {**item, **placed.get("source", {})}, models_root, items)
            entry["scale"] = {"x": round(scale.x, 4), "y": round(scale.y, 4), "z": round(scale.z, 4)}
        else:
            meshes = _place_stand_in(placed, item["colour"], items)
        entry["final_mm"], entry["lowest_mm"] = _final(meshes, placed["rotation_deg"])
        entry["meshes"] = sorted(obj.name for obj in meshes)
        if "light" in placed:
            entry["light"] = _add_lamp_light(item["id"], placed["light"], meshes, items)
        scene.report.append(entry)
        scene.item_meshes.extend(meshes)
    if document.get("floor"):
        _apply_floor_finish(scene, document["floor"])
    return scene


# A spot lamp's fixed cone (room-lamp-lights).
SPOT_CONE_DEG = 70.0
SPOT_BLEND = 0.3
POINT_RADIUS_MM = 50.0


def _add_lamp_light(item_id: str, light: dict[str, Any], meshes: list[bpy.types.Object], collection) -> dict[str, Any]:
    """`LGT_Lamp_<id>` at the position the contract resolved, in the light's kelvin colour and
    power; the lamp's own meshes cast no shadow, so the light leaves its shade or box."""
    kind = "SPOT" if light["type"] == "spot" else "POINT"
    data = bpy.data.lights.new(f"LGT_Lamp_{item_id}", kind)
    data.energy = float(light["watts"])
    data.color = tuple(light["rgb"])
    data.shadow_soft_size = m(POINT_RADIUS_MM)
    if kind == "SPOT":
        # A spot light shines along its local -Z, which is straight down unrotated.
        data.spot_size = math.radians(SPOT_CONE_DEG)
        data.spot_blend = SPOT_BLEND
    lamp = bpy.data.objects.new(f"LGT_Lamp_{item_id}", data)
    collection.objects.link(lamp)
    x, y, z = light["at_mm"]
    lamp.location = (m(x), m(y), m(z))
    for obj in meshes:
        obj.visible_shadow = False
    return {key: light[key] for key in ("type", "lumens", "kelvin", "watts", "at_mm")}


STRIP_LIGHT_GAP_MM = 2.0
STRIP_GLOW = 5.0


def _place_led_strip(placed: dict[str, Any], collection) -> list[bpy.types.Object]:
    """The strip's bar along its wall at its height, glowing in its kelvin colour, and the area
    light `LGT_Strip_<id>` of its length, 2 mm off the face it shines from (room-led-strips)."""
    strip = placed["strip"]
    size = placed["size_mm"]
    mesh = bpy.data.meshes.new(f"STRIP_{placed['id']}")
    w, d, h = m(size["w"]), m(size["d"]), m(size["h"])
    verts = [(x, y, z) for z in (0, h) for y in (-d / 2, d / 2) for x in (-w / 2, w / 2)]
    faces = [(0, 2, 3, 1), (4, 5, 7, 6), (0, 1, 5, 4), (2, 6, 7, 3), (0, 4, 6, 2), (1, 3, 7, 5)]
    mesh.from_pydata(verts, [], faces)
    mesh.update()
    bar = bpy.data.objects.new(f"STRIP_{placed['id']}", mesh)
    collection.objects.link(bar)
    material = bpy.data.materials.new(f"Strip_{placed['id']}")
    material.use_nodes = True
    shader = next(n for n in material.node_tree.nodes if n.type == "BSDF_PRINCIPLED")
    shader.inputs["Base Color"].default_value = (1, 1, 1, 1)
    shader.inputs["Emission Color"].default_value = (*strip["rgb"], 1)
    shader.inputs["Emission Strength"].default_value = STRIP_GLOW
    material.diffuse_color = (*strip["rgb"], 1)
    bar.data.materials.append(material)
    cx, cy = placed["centre_mm"]
    base = placed["base_mm"]
    bar.location = (m(cx), m(cy), m(base))
    bar.rotation_euler[2] = math.radians(placed["rotation_deg"])
    bar.visible_shadow = False

    data = bpy.data.lights.new(f"LGT_Strip_{placed['id']}", "AREA")
    data.shape = "RECTANGLE"
    data.size = w
    data.size_y = d
    data.energy = float(strip["watts"])
    data.color = tuple(strip["rgb"])
    light = bpy.data.objects.new(f"LGT_Strip_{placed['id']}", data)
    collection.objects.link(light)
    along = Vector((math.cos(math.radians(placed["rotation_deg"])), math.sin(math.radians(placed["rotation_deg"])), 0))
    inward = Vector((*strip["inward"], 0))
    gap = m(STRIP_LIGHT_GAP_MM)
    centre = Vector((m(cx), m(cy), m(base) + h / 2))
    # An area light shines along its local -Z: its Z axis is the opposite of where it faces.
    if strip["facing"] == "down":
        shine, at = Vector((0, 0, -1)), centre - Vector((0, 0, h / 2 + gap))
    elif strip["facing"] == "up":
        shine, at = Vector((0, 0, 1)), centre + Vector((0, 0, h / 2 + gap))
    else:
        shine, at = inward, centre + inward * (d / 2 + gap)
    z_axis = -shine
    y_axis = z_axis.cross(along)
    basis = Matrix((along, y_axis, z_axis)).transposed()
    light.matrix_world = Matrix.Translation(at) @ basis.to_4x4()
    return [bar]


def rig_factors(scene: CompositionScene) -> dict[str, float]:
    """Each room's rig factor, for the build report."""
    return {room.name: room.rig_factor for room in scene.rooms}


def _rgb(colour: str) -> tuple[float, float, float]:
    return tuple(_linear(int(colour[i:i + 2], 16) / 255) for i in (1, 3, 5))


def _floor_objects(scene: CompositionScene) -> list[bpy.types.Object]:
    """The floor meshes of the scope, from the surface map (`floor`, or `<room>: floor`)."""
    return [
        bpy.data.objects[name]
        for label, names in surfaces(scene).items() if label == "floor" or label.endswith(": floor")
        for name in names
    ]


def _apply_floor_finish(scene: CompositionScene, finish: dict[str, Any]) -> None:
    """Every floor gets one tile material: a Brick Texture in object space, so its units are
    metres from the plan's origin and the joints follow any outline the floor has."""
    material = bpy.data.materials.new("Floor_Tiles")
    material.use_nodes = True
    nodes, links = material.node_tree.nodes, material.node_tree.links
    shader = next(n for n in nodes if n.type == "BSDF_PRINCIPLED")
    coords = nodes.new("ShaderNodeTexCoord")
    brick = nodes.new("ShaderNodeTexBrick")
    grout = m(finish["grout_width_mm"])
    tile = _rgb(finish["tile_colour"])
    brick.inputs["Scale"].default_value = 1.0
    brick.inputs["Mortar Size"].default_value = grout
    brick.inputs["Mortar Smooth"].default_value = 0.0
    brick.inputs["Bias"].default_value = 0.0
    # A tile's visible face is its stated size: the joint is added to each brick.
    brick.inputs["Brick Width"].default_value = m(finish["tile_width_mm"]) + grout
    brick.inputs["Row Height"].default_value = m(finish["tile_length_mm"]) + grout
    brick.inputs["Color1"].default_value = (*tile, 1)
    brick.inputs["Color2"].default_value = (*tile, 1)
    brick.inputs["Mortar"].default_value = (*_rgb(finish["grout_colour"]), 1)
    brick.offset = 0.5 if finish["pattern"] == "staggered" else 0.0
    brick.offset_frequency = 2
    brick.squash = 1.0
    brick.squash_frequency = 2
    links.new(coords.outputs["Object"], brick.inputs["Vector"])
    links.new(brick.outputs["Color"], shader.inputs["Base Color"])
    shader.inputs["Roughness"].default_value = 0.35
    material.diffuse_color = (*tile, 1)
    scene.floors = _floor_objects(scene)
    for obj in scene.floors:
        obj.data.materials.clear()
        obj.data.materials.append(material)


@contextmanager
def flat_floor(scene: CompositionScene):
    """While the screenshot and `model.glb` are made, the tiled floors show the plain tile colour
    (a procedural texture does not export as a colour); the tile material is back afterwards."""
    finish = scene.document.get("floor")
    if not finish or not scene.floors:
        yield
        return
    flat = bpy.data.materials.new("Floor_Tiles_Flat")
    flat.use_nodes = True
    shader = next(n for n in flat.node_tree.nodes if n.type == "BSDF_PRINCIPLED")
    tile = _rgb(finish["tile_colour"])
    shader.inputs["Base Color"].default_value = (*tile, 1)
    flat.diffuse_color = (*tile, 1)
    kept = {obj.name: list(obj.data.materials) for obj in scene.floors}
    for obj in scene.floors:
        obj.data.materials.clear()
        obj.data.materials.append(flat)
    try:
        yield
    finally:
        for obj in scene.floors:
            obj.data.materials.clear()
            for material in kept[obj.name]:
                obj.data.materials.append(material)
        bpy.data.materials.remove(flat)


def surfaces(scene: CompositionScene) -> dict[str, list[str]]:
    """The scene's surface map: each wall, floor and ceiling (per room in an apartment) and the items."""
    meshes = [obj.name for obj in bpy.context.scene.objects if obj.type == "MESH"]
    labels = None
    if "apartment" in scene.document["scope"]:
        labels = apartment_wall_labels(normalise_shell(scene.document["resolved"]["shell"]).walls)
    try:
        return surface_map(meshes, [obj.name for obj in scene.item_meshes], labels)
    except SpecValidationError as error:
        raise GeneratorError(f"build: {error}") from None


def extent_mm(scene: CompositionScene) -> dict[str, list[float]]:
    """The rooms' plan bounds and the highest ceiling, for framing the 3D view."""
    x0, y0, x1, y1 = _bounds(scene.rooms)
    return {"min": [x0, y0, 0.0], "max": [x1, y1, float(scene.ceiling_mm)]}


def wall_objects() -> list[bpy.types.Object]:
    return [obj for obj in bpy.data.objects if obj.type == "MESH" and obj.name.startswith("Wall_")]


def walls_facing(scene: CompositionScene, direction: Vector, threshold: float) -> list[bpy.types.Object]:
    """The walls on the camera's side of the scene centre, hidden for a turntable frame."""
    centre = Vector((m(scene.centre_mm[0]), m(scene.centre_mm[1])))
    hidden = []
    for obj in wall_objects():
        corners = [obj.matrix_world @ Vector(c) for c in obj.bound_box]
        mid = Vector((sum(p.x for p in corners) / 8, sum(p.y for p in corners) / 8)) - centre
        if mid.length > 1e-6 and mid.normalized().dot(direction) > threshold:
            hidden.append(obj)
    return hidden
