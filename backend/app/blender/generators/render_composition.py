"""Render a still or a turntable of a room-composition version (room-composition).

Run only by the runner behind the render guard: the three `--tier-*` values come
from a guard ticket and nothing else decides frames, resolution or engine. The scene
is rebuilt from the version's stored document exactly as its build made it; a
turntable hides, per frame, the walls between the camera and the scene's centre.

    blender --background --python render_composition.py -- \
      --spec <version>/input.json --pieces <render root> --models <upload root>/models \
      --out /absolute/new-dir --kind still|turntable \
      --tier-frames 12 --tier-resolution 600 --tier-engine BLENDER_EEVEE
"""

from __future__ import annotations

import json
import math
import os
import shutil
import sys
import uuid
from pathlib import Path

import bpy
from mathutils import Vector

BACKEND_ROOT = Path(__file__).resolve().parents[3]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.blender.cli import (
    InputError,
    TierArguments,
    parse_composition_render_arguments,
)
from app.blender.generators import _composition as composition
from app.blender.generators import build_room_scene as room_gen
from app.blender.generators._scene import GeneratorError
from app.blender.room_contract import sight_clear
from app.render.viewer import render_viewer

EYE_HEIGHT_MM = 1500
PULL_IN_MM = 600
HIDE_THRESHOLD = 0.3


def _camera(name: str, xy: tuple[float, float], z_mm: float, target: tuple[float, float, float]) -> bpy.types.Object:
    m = composition.m
    camera = room_gen._add_camera(name, (m(xy[0]), m(xy[1]), m(z_mm)))
    room_gen._aim(camera, (m(target[0]), m(target[1]), m(target[2])))
    return camera


def _still(scene: composition.CompositionScene, out: Path) -> dict:
    """From the corner that sees the room's centre, pulled in, at eye height."""
    room = scene.rooms[0]
    target = scene.centre_mm
    corners = sorted(room.corners, key=lambda c: -math.hypot(c[0] - target[0], c[1] - target[1]))
    corner = next((c for c in corners if sight_clear(c, target, room.corners)), corners[0])
    direction = Vector((target[0] - corner[0], target[1] - corner[1]))
    direction = direction.normalized() if direction.length > 1e-6 else Vector((0, 1))
    xy = (corner[0] + direction.x * PULL_IN_MM, corner[1] + direction.y * PULL_IN_MM)
    bpy.context.scene.camera = _camera("CAM_Still", xy, EYE_HEIGHT_MM, (target[0], target[1], scene.ceiling_mm / 3))
    bpy.context.scene.render.filepath = str(out / "still.png")
    bpy.ops.render.render(write_still=True)
    return {"kind": "still", "camera": {"location_mm": [xy[0], xy[1], EYE_HEIGHT_MM]}}


def _turntable(scene: composition.CompositionScene, out: Path, frames: int) -> dict:
    (out / "frames").mkdir()
    centre = scene.centre_mm
    radius = room_gen.TURNTABLE_RADIUS_FACTOR * scene.radius_mm
    height = room_gen.TURNTABLE_HEIGHT_FACTOR * scene.ceiling_mm
    infos = []
    for index in range(frames):
        angle = 2 * math.pi * index / frames
        xy = (centre[0] + radius * math.cos(angle), centre[1] + radius * math.sin(angle))
        bpy.context.scene.camera = _camera(f"CAM_Turntable_{index:03d}", xy, height, (centre[0], centre[1], scene.ceiling_mm / 2))
        toward = Vector((math.cos(angle), math.sin(angle)))
        saved = room_gen._hidden(composition.walls_facing(scene, toward, HIDE_THRESHOLD))
        try:
            bpy.context.scene.render.filepath = str(out / "frames" / f"frame_{index:03d}.png")
            bpy.ops.render.render(write_still=True)
        finally:
            room_gen._restore(saved)
        infos.append({"index": index, "location_mm": [xy[0], xy[1], height], "hidden_walls": [obj.name for obj, *_ in saved]})
    (out / "viewer.html").write_text(render_viewer(frames, title="Room"), encoding="utf-8")
    return {"kind": "turntable", "frame_count": frames, "frames": infos}


def render(document: dict, pieces: Path, models: Path, out: Path, kind: str, tier: TierArguments) -> None:
    try:
        scene = composition.build_scene(document, pieces_root=pieces, models_root=models)
    except GeneratorError:
        raise
    except Exception as error:
        raise GeneratorError(f"build: {type(error).__name__}: {error}") from error
    try:
        room_gen._configure_render(tier)
        output = _still(scene, out) if kind == "still" else _turntable(scene, out, tier.frames)
    except Exception as error:
        raise GeneratorError(f"render: {type(error).__name__}: {error}") from error
    record = {
        "kind": "room_composition", "schema_version": 1, "units": "mm",
        "blender_version": bpy.app.version_string, "input": document, "items": scene.report,
        "output": {**output, "tier_frames": tier.frames, "resolution": tier.resolution, "engine": tier.engine},
    }
    (out / "scene.json").write_text(json.dumps(record, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    stage: Path | None = None
    try:
        spec, pieces, models, output_path, kind, tier = parse_composition_render_arguments(
            list(sys.argv if argv is None else argv)
        )
        document = json.loads(spec.read_text(encoding="utf-8"))
        stage = output_path.parent / f".{output_path.name}.tmp-{uuid.uuid4().hex}"
        stage.mkdir()
        render(document, pieces, models, stage, kind, tier)
        os.replace(stage, output_path)
        stage = None
        print(f"WROTE {output_path}")
        return 0
    except (GeneratorError, InputError) as error:
        print(str(error), file=sys.stderr)
    except Exception as error:  # noqa: BLE001 - Blender errors need a short operator-safe diagnostic
        print(f"render: {type(error).__name__}: {error}", file=sys.stderr)
    if stage is not None and stage.exists():
        shutil.rmtree(stage)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
