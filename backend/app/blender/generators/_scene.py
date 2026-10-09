"""Helpers shared by the generators that run inside Blender 5.2.

Extracted from the predecessor's Listening Wall generator, which this repository
does not carry. Importable only inside Blender (`bpy`, `mathutils`).
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

import bpy
from mathutils import Vector

MM = 0.001


class GeneratorError(RuntimeError):
    """Expected, concise failure surfaced to the runner or a shell user."""


def m(value: float) -> float:
    return float(value) * MM


def set_engine(engine: str) -> None:
    """Assign a render engine by RNA identifier.

    The enum listing under-reports in background mode (it names only
    BLENDER_EEVEE), so the value is assigned and a refusal is reported with the
    identifiers Blender says it accepts.
    """
    try:
        bpy.context.scene.render.engine = engine
    except TypeError as error:
        raise GeneratorError(f"render: engine {engine!r} is not available: {error}") from error


def reset_scene() -> None:
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    scene.unit_settings.system = "METRIC"
    scene.unit_settings.scale_length = 1.0
    scene.unit_settings.length_unit = "MILLIMETERS"
    scene.render.resolution_percentage = 100
    # No .blend1 backup means a published package has exactly the six files.
    bpy.context.preferences.filepaths.save_version = 0
    world = bpy.data.worlds.new("Studio")
    scene.world = world
    world.use_nodes = True
    shader = world.node_tree.nodes.get("Background")
    if shader is not None:
        shader.inputs["Color"].default_value = (0.93, 0.9, 0.84, 1)
        shader.inputs["Strength"].default_value = 0.85


def collection(name: str, parent: bpy.types.Collection | None = None) -> bpy.types.Collection:
    created = bpy.data.collections.new(name)
    (parent or bpy.context.scene.collection).children.link(created)
    return created


def link(obj: bpy.types.Object, target: bpy.types.Collection) -> None:
    for current in list(obj.users_collection):
        current.objects.unlink(obj)
    target.objects.link(obj)


def add_camera(
    name: str,
    location: tuple[float, float, float],
    rotation: tuple[float, float, float],
    *,
    ortho: bool = False,
    scale: float = 2.4,
) -> bpy.types.Object:
    data = bpy.data.cameras.new(name)
    camera = bpy.data.objects.new(name, data)
    bpy.context.scene.collection.objects.link(camera)
    camera.location = location
    camera.rotation_euler = rotation
    if ortho:
        data.type = "ORTHO"
        data.ortho_scale = scale
    else:
        data.lens = 50
    data.clip_start = 0.05
    data.clip_end = 20
    return camera


def aim_at(camera: bpy.types.Object, target: tuple[float, float, float]) -> None:
    """Orient a perspective camera by its target, not brittle Euler literals."""
    camera.rotation_euler = (Vector(target) - camera.location).to_track_quat("-Z", "Y").to_euler()


def _is_presentation_helper(obj: bpy.types.Object) -> bool:
    return (
        obj.name == "StudioFloor"
        or obj.name.startswith("Ceiling_")  # an apartment shell's ceilings hide the rooms from above
        or obj.name.startswith("DIM_")
        or obj.name.startswith("MOD_Dimensions")
    )


@contextmanager
def hidden(predicate) -> Iterator[None]:
    """Hide every object `predicate` selects, from viewport and render, then
    restore exactly what each one was."""
    saved: list[tuple[bpy.types.Object, bool, bool]] = []
    for obj in bpy.context.scene.objects:
        if predicate(obj):
            saved.append((obj, obj.hide_get(), obj.hide_render))
            obj.hide_set(True)
            obj.hide_render = True
    try:
        yield
    finally:
        for obj, hide_viewport, hide_render in saved:
            obj.hide_set(hide_viewport)
            obj.hide_render = hide_render


def is_dimension(obj: bpy.types.Object) -> bool:
    """A dimension line, tick or figure (piece-inspector), or the empty holding them."""
    return obj.name.startswith("DIM_") or obj.name.startswith("MOD_Dimensions")


def face_camera(camera: bpy.types.Object) -> None:
    """Turn every dimension figure to face `camera`, so it reads in that camera's frames."""
    for obj in bpy.context.scene.objects:
        if obj.type == "FONT" and obj.name.startswith("DIM_"):
            constraint = obj.constraints.get("Face camera") or obj.constraints.new("COPY_ROTATION")
            constraint.name = "Face camera"
            constraint.target = camera


def hidden_for_presentation() -> hidden:
    """Hide the studio floor and dimension helpers (the piece alone)."""
    return hidden(_is_presentation_helper)


def export_glb(layer_names: set[str], output_path: Path, *, hide_helpers: bool = True) -> None:
    """Export the visible meshes as GLB, refusing when the layer map and the
    visible meshes disagree (the spec's `layers` must cover every mesh).

    `hide_helpers=False` keeps the presentation helpers (a room composition's
    ceilings are a surface the owner switches)."""
    helper = _is_presentation_helper if hide_helpers else (lambda obj: False)
    with hidden(lambda obj: obj.type in {"CAMERA", "LIGHT"} or helper(obj)):
        visible = {
            obj.name
            for obj in bpy.context.scene.objects
            if obj.type == "MESH" and not obj.hide_get()
        }
        if visible != layer_names:
            raise GeneratorError(
                "export: layer map does not match visible meshes "
                f"(missing={sorted(visible - layer_names)}, extra={sorted(layer_names - visible)})"
            )
        bpy.ops.export_scene.gltf(
            filepath=str(output_path),
            export_format="GLB",
            export_apply=True,
            export_yup=True,
            export_cameras=False,
            export_extras=True,
            export_lights=False,
            use_visible=True,
            export_animations=False,
            export_skins=False,
            export_morph=False,
        )
