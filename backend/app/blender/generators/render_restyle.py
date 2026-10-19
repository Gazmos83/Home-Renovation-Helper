"""Render one restyled draft turntable of a built version, in memory (restyle-variants).

Run only by the runner behind the render guard: the three `--tier-*` values come from a
guard ticket and nothing else decides frames, resolution or engine. The built
`model.blend` is opened (a piece) or the composition is rebuilt from its stored document,
the look or style is applied to the open scene, and a turntable is rendered with the same
cameras as the version's own (two-tier-renders). Its first frame is copied to `still.png`
as the variant's picture. Nothing is saved: the version's files are never touched.

    blender --background --python render_restyle.py -- \
      --restyle looks.json --out /absolute/new-dir --blend model.blend \
      --tier-frames 12 --tier-resolution 800 --tier-engine BLENDER_EEVEE
    blender --background --python render_restyle.py -- \
      --restyle style.json --out /absolute/new-dir --spec input.json --pieces <root> --models <dir> \
      --tier-frames 12 --tier-resolution 800 --tier-engine BLENDER_EEVEE

The restyle file is validated by the backend before it gets here (`app.restyle.request`).
"""

from __future__ import annotations

import json
import os
import shutil
import sys
import uuid
from pathlib import Path
from typing import Any

import bpy

BACKEND_ROOT = Path(__file__).resolve().parents[3]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.blender.cli import InputError, TierArguments, parse_restyle_arguments
from app.blender.generators import _composition as composition
from app.blender.generators import build_room_scene as room_gen
from app.blender.generators import render_composition, render_turntable
from app.blender.generators._scene import GeneratorError
from app.blender.verify import VerificationError, verify_frames, verify_png

# Blender names a data block with at most this many bytes of the material string.
_NAME_LIMIT = 63


def _linear(channel: float) -> float:
    return channel / 12.92 if channel <= 0.04045 else ((channel + 0.055) / 1.055) ** 2.4


def _rgb(colour: str) -> tuple[float, float, float]:
    """An sRGB `#rrggbb` in the linear space shader colours use."""
    return tuple(_linear(int(colour[i:i + 2], 16) / 255) for i in (1, 3, 5))  # type: ignore[return-value]


def _principled(material: bpy.types.Material) -> bpy.types.Node:
    material.use_nodes = True
    shader = next((node for node in material.node_tree.nodes if node.type == "BSDF_PRINCIPLED"), None)
    if shader is None:
        raise GeneratorError(f"restyle: material {material.name!r} has no Principled BSDF")
    return shader


def _drop_links(material: bpy.types.Material, socket: bpy.types.NodeSocket) -> None:
    for link in list(material.node_tree.links):
        if link.to_socket == socket:
            material.node_tree.links.remove(link)


def _paint(material: bpy.types.Material, colour: str, roughness: float, metallic: float, grain: bool) -> None:
    """Set a material's appearance. `grain` adds a plain procedural banding, not a texture file."""
    rgb = _rgb(colour)
    material.diffuse_color = (*rgb, 1)
    shader = _principled(material)
    base = shader.inputs["Base Color"]
    _drop_links(material, base)
    base.default_value = (*rgb, 1)
    shader.inputs["Roughness"].default_value = roughness
    shader.inputs["Metallic"].default_value = metallic
    if not grain:
        return
    nodes, links = material.node_tree.nodes, material.node_tree.links
    coordinate = nodes.new("ShaderNodeTexCoord")
    wave = nodes.new("ShaderNodeTexWave")
    wave.wave_type = "BANDS"
    wave.inputs["Scale"].default_value = 6.0
    wave.inputs["Distortion"].default_value = 3.0
    wave.inputs["Detail"].default_value = 2.0
    ramp = nodes.new("ShaderNodeValToRGB")
    ramp.color_ramp.elements[0].color = (*(c * 0.7 for c in rgb), 1)
    ramp.color_ramp.elements[1].color = (*rgb, 1)
    links.new(coordinate.outputs["Object"], wave.inputs["Vector"])
    links.new(wave.outputs["Color"], ramp.inputs["Fac"])
    links.new(ramp.outputs["Color"], base)


def _matches(material: bpy.types.Material, wanted: str) -> bool:
    return material.name == wanted or (len(material.name) >= _NAME_LIMIT and wanted.startswith(material.name))


def apply_piece(payload: dict[str, Any]) -> list[str]:
    """Restyle the open piece's materials, named by the spec's material strings. Returns what changed."""
    changed: list[str] = []
    for wanted, look in payload["materials"].items():
        found = [material for material in bpy.data.materials if _matches(material, wanted)]
        if not found:
            raise GeneratorError(f"restyle: the built model has no material {wanted!r}; rebuild the version")
        for material in found:
            _paint(material, look["colour"], look["roughness"], look["metallic"], look["grain"])
            changed.append(material.name)
    return changed


def _surface_kind(label: str) -> str | None:
    if label.endswith("floor") or label == "floor":
        return "floor"
    if label.endswith("ceiling") or label == "ceiling":
        return "ceiling"
    if "wall" in label:
        return "wall"
    return None


def _world(colour: str, strength: float) -> None:
    world = bpy.context.scene.world
    if world is None:
        return
    world.use_nodes = True
    background = next((node for node in world.node_tree.nodes if node.type == "BACKGROUND"), None)
    if background is not None:
        background.inputs["Color"].default_value = (*_rgb(colour), 1)
        background.inputs["Strength"].default_value = strength


def apply_room(scene: composition.CompositionScene, style: dict[str, Any]) -> None:
    """Restyle walls, floor, ceiling, world and stand-ins of a rebuilt composition.

    Pieces and library models are not touched. Each surface kind gets its own new material,
    so no shared material leaks one surface's colour onto another. A tiled floor keeps its
    finish (room-floor-finish).
    """
    made: dict[str, bpy.types.Material] = {}
    for kind in ("wall", "floor", "ceiling"):
        spec = style[kind]
        material = bpy.data.materials.new(f"Restyle_{kind}")
        _paint(material, spec["colour"], spec["roughness"], 0.0, False)
        made[kind] = material
    for label, names in composition.surfaces(scene).items():
        kind = _surface_kind(label)
        if kind is None or (kind == "floor" and scene.document.get("floor")):
            continue
        for name in names:
            obj = bpy.data.objects[name]
            obj.data.materials.clear()
            obj.data.materials.append(made[kind])
    _world(style["world"]["colour"], style["world"]["strength"])
    colours = {key.casefold(): value for key, value in style["stand_ins"].items()}
    names = {item["id"]: str(item.get("name", "")).casefold() for item in scene.document["items"]}
    for item in scene.document["items"]:
        if item["type"] != "stand-in":
            continue
        obj = bpy.data.objects.get(f"STAND_{item['id']}")
        if obj is None or not obj.data.materials:
            continue
        colour = next(
            (value for key, value in colours.items() if key and key in names[item["id"]]), style["fallback"]
        )
        _paint(obj.data.materials[0], colour, 0.7, 0.0, False)


def _write_scene(out: Path, tier: TierArguments, kind: str, extra: dict[str, Any]) -> None:
    (out / "scene.json").write_text(
        json.dumps(
            {
                "kind": f"restyle_{kind}",
                "source": "restyle",
                "frames": tier.frames,
                "resolution": tier.resolution,
                "engine": tier.engine,
                "blender_version": bpy.app.version_string,
                **extra,
            },
            indent=2,
        ),
        encoding="utf-8",
    )


def _poster(stage: Path, tier: TierArguments) -> None:
    """Check the turntable and copy its first frame to `still.png`, the variant's picture."""
    verify_frames(stage, tier.frames, tier.resolution)
    shutil.copyfile(stage / "frames" / "frame_000.png", stage / "still.png")
    verify_png(stage / "still.png", (tier.resolution, tier.resolution))


def _piece(arguments, payload: dict[str, Any], stage: Path) -> None:
    bpy.ops.wm.open_mainfile(filepath=str(arguments.blend))
    changed = apply_piece(payload)
    render_turntable.fill(stage, arguments.tier)
    _poster(stage, arguments.tier)
    _write_scene(stage, arguments.tier, "piece", {"materials_changed": changed})


def _room(arguments, payload: dict[str, Any], stage: Path) -> None:
    document = json.loads(arguments.spec.read_text(encoding="utf-8"))
    scene = composition.build_scene(document, pieces_root=arguments.pieces, models_root=arguments.models)
    apply_room(scene, payload["style"])
    room_gen._configure_render(arguments.tier)
    # Walls between the camera and the room are hidden per frame, as in the room's own turntable.
    render_composition._turntable(scene, stage, arguments.tier.frames)
    _poster(stage, arguments.tier)
    _write_scene(stage, arguments.tier, "room", {"items": scene.report})


def main(argv: list[str] | None = None) -> int:
    stage: Path | None = None
    try:
        arguments = parse_restyle_arguments(list(sys.argv if argv is None else argv))
        payload = json.loads(arguments.restyle.read_text(encoding="utf-8"))
        stage = arguments.out.parent / f".{arguments.out.name}.tmp-{uuid.uuid4().hex}"
        stage.mkdir()
        if payload.get("mode") == "piece" and arguments.blend is not None:
            _piece(arguments, payload, stage)
        elif payload.get("mode") == "room" and arguments.spec is not None:
            _room(arguments, payload, stage)
        else:
            raise InputError("arguments: the restyle mode does not match the inputs given")
        os.replace(stage, arguments.out)
        stage = None
        print(f"WROTE {arguments.out}")
        return 0
    except (GeneratorError, InputError, VerificationError) as error:
        print(str(error), file=sys.stderr)
    except Exception as error:  # noqa: BLE001 - Blender errors need a short operator-safe diagnostic
        print(f"render: {type(error).__name__}: {error}", file=sys.stderr)
    if stage is not None and stage.exists():
        shutil.rmtree(stage)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
