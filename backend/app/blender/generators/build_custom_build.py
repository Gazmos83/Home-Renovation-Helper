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
    parse_generator_arguments,
)
from app.blender.custom_build import derive as rules
from app.blender.generators._scene import (
    GeneratorError,
    export_glb,
    hidden_for_presentation,
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

Box = tuple[tuple[float, float, float], tuple[float, float, float]]  # (size, centre), mm


@dataclass
class BuildState:
    spec: Mapping[str, Any]
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
    shelves = module["shelves"]
    if shelves:
        step = (height - 2 * t) / (shelves + 1)
        pieces[f"{mid}-shelf"] = (
            "shelves",
            [
                ((inner_w, inner_d, t), (x + width / 2, y + inner_d / 2, z + t + step * (k + 1)))
                for k in range(shelves)
            ],
        )

    rects = rules.front_layout(module)
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
            pieces[prefix] = ("fronts", [panel(rect) for rect in entry])
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
    return pieces


def _extra_boxes(spec: Mapping[str, Any], right_edge: float, front_edge: float) -> dict[str, tuple[str, list[Box]]]:
    """Extra parts have no position in the specification: laid flat beside the build."""
    pieces: dict[str, tuple[str, list[Box]]] = {}
    offset_y = front_edge
    for extra in spec.get("extra_parts") or []:
        t = spec["materials"][extra["material"]]["thickness_mm"]
        boxes: list[Box] = []
        for _ in range(extra["qty"]):
            boxes.append(
                (
                    (extra["length"], extra["width"], t),
                    (right_edge + 200 + extra["length"] / 2, offset_y + extra["width"] / 2, t / 2),
                )
            )
            offset_y += extra["width"] + 20
        pieces[extra["id"]] = ("extras", boxes)
    return pieces


# --- the scene ----------------------------------------------------------------------------------


_COLOURS: tuple[tuple[str, tuple[float, float, float], float, float], ...] = (
    ("oak", (0.48, 0.29, 0.145), 0.45, 0.0),
    ("black", (0.035, 0.035, 0.04), 0.55, 0.0),
    ("mdf", (0.62, 0.55, 0.45), 0.6, 0.0),
    ("birch", (0.72, 0.62, 0.42), 0.5, 0.0),
    ("shs", (0.12, 0.12, 0.13), 0.32, 1.0),
    ("steel", (0.12, 0.12, 0.13), 0.32, 1.0),
    ("aluminium", (0.55, 0.56, 0.58), 0.3, 1.0),
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


def _box(state: BuildState, name: str, box: Box, material: str, layer: str, collection: bpy.types.Collection, parent: bpy.types.Object) -> None:
    size, centre = box
    bpy.ops.mesh.primitive_cube_add(size=1, location=tuple(m(value) for value in centre))
    obj = bpy.context.active_object
    obj.name = name
    obj.data.name = name
    obj.scale = tuple(m(value) for value in size)
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
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
    return (
        float(min(module["x"] for module in modules)),
        float(min(module["y"] for module in modules)),
        float(min(module["z"] for module in modules)),
        overall,
    )


def _override_count(boxes: list[Box], qty: int) -> list[Box]:
    """A part override may change a row's quantity: drop pieces, or add copies beside the last.

    Placed geometry keeps the rule sizes; only the count follows the override,
    so every cut-list piece still has exactly one object.
    """
    if qty <= len(boxes):
        return boxes[:qty]
    (size, (cx, cy, cz)) = boxes[-1]
    extra = [(size, (cx + (n + 1) * (size[0] + 20), cy, cz)) for n in range(qty - len(boxes))]
    return boxes + extra


def _build_scene(state: BuildState, parts: list[dict[str, Any]]) -> None:
    spec = state.spec
    _reset_scene()
    x0, y0, z0, overall = _frame(spec)
    # Centred on x and y; z stays the real height, so a
    # wall cabinet hangs where it will hang.
    shift = (x0 + overall["w"] / 2, y0 + overall["d"] / 2, 0.0)

    def at(box: Box) -> Box:
        size, (cx, cy, cz) = box
        return size, (cx - shift[0], cy - shift[1], cz - shift[2])

    root_collection = _collection("CustomBuild")
    root = _empty("CustomBuild", (0, 0, 0), root_collection, None)
    root["overall_w_mm"] = overall["w"]
    root["overall_h_mm"] = overall["h"]
    root["overall_d_mm"] = overall["d"]

    pieces: dict[str, tuple[str, str, list[Box]]] = {}
    for module in spec["modules"]:
        for row_id, (layer, boxes) in _module_boxes(module, spec["materials"]).items():
            pieces[row_id] = (module["id"], layer, boxes)
    for row_id, (layer, boxes) in _extra_boxes(spec, x0 + overall["w"], y0).items():
        pieces[row_id] = (rules.EXTRAS_MODULE, layer, boxes)

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
        for n, box in enumerate(boxes, start=1):
            name = row["id"] if n == 1 else f"{row['id']}#{n}"
            _box(state, name, at(box), row["material"], layer, collections[owner], empties[owner])

    _build_cameras_lights(overall, z0)
    bpy.ops.mesh.primitive_plane_add(size=max(6.0, m(max(overall.values())) * 3), location=(0, 0, 0))
    floor = bpy.context.active_object
    floor.name = "StudioFloor"
    floor.data.name = "StudioFloor"
    floor.data.materials.append(_material(state, "Studio floor birch"))


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
    scale = max(1.0, reach * 1.4)
    _add_camera("CAM_Front", (0, -distance, target[2]), (math.radians(90), 0, 0), ortho=True, scale=scale)
    _add_camera("CAM_Side", (distance, 0, target[2]), (math.radians(90), 0, math.radians(90)), ortho=True, scale=scale)
    _add_camera("CAM_Top", (0, 0, target[2] + distance), (0, 0, 0), ortho=True, scale=scale)
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
    emitted = rules.emitted_spec(state.spec)
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


def _build_package(spec: Mapping[str, Any], output_dir: Path) -> None:
    state = BuildState(spec=spec)
    parts, hardware, _assembly = rules.derive(spec)
    try:
        _build_scene(state, parts)
    except GeneratorError:
        raise
    except Exception as error:
        raise GeneratorError(f"build: {type(error).__name__}: {error}") from error
    try:
        _write_shop_data(state, output_dir, parts, hardware)
        _write_screenshot(output_dir / "screenshot.png")
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
        spec_path, output_path = parse_generator_arguments(list(sys.argv if argv is None else argv))
        spec = load_custom_build(spec_path)
        stage = output_path.parent / f".{output_path.name}.tmp-{uuid.uuid4().hex}"
        stage.mkdir()
        _build_package(spec, stage)
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
