"""Render a turntable of a built package, at the tier the guard authorised.

    blender --background --python render_turntable.py -- \
      --blend model.blend --out /new/dir \
      --tier-frames 12 --tier-resolution 600 --tier-engine BLENDER_EEVEE

Writes `frames/frame_000.png` … and `scene.json` into the new directory, plus
`viewer.html` beside them. The frame count, resolution and engine come from the
runner, from a guard ticket.

The camera orbits the build's bounding-box centre at the iso camera's own
elevation and distance, starting from where `CAM_Iso` already sits.

With `--dimensions` (passed only for a piece's own turntable) the piece's
dimension lines stay visible and their figures turn to face the camera in every
frame; without it they are hidden like the studio floor (piece-inspector).
"""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import bpy
from mathutils import Vector

BACKEND_ROOT = Path(__file__).resolve().parents[3]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.blender.cli import TierArguments
from app.blender.generators import _render
from app.blender.generators._scene import (
    GeneratorError,
    aim_at,
    face_camera,
    hidden,
    hidden_for_presentation,
    is_dimension,
)
from app.blender.verify import verify_frames
from app.render.viewer import render_viewer


def _build_centre() -> Vector:
    """The centre of every mesh's bounding box, the studio floor and the dimension
    lines excluded."""
    points = [
        obj.matrix_world @ Vector(corner)
        for obj in bpy.data.objects
        if obj.type == "MESH" and obj.name != "StudioFloor" and not is_dimension(obj)
        for corner in obj.bound_box
    ]
    if not points:
        raise GeneratorError("render: model.blend has no mesh to orbit")
    low = Vector(tuple(min(p[i] for p in points) for i in range(3)))
    high = Vector(tuple(max(p[i] for p in points) for i in range(3)))
    return (low + high) / 2


def fill(stage: Path, tier: TierArguments) -> None:
    _render.configure_render(tier)
    iso = bpy.data.objects.get("CAM_Iso")
    if iso is None:
        raise GeneratorError("render: CAM_Iso is missing from model.blend")
    centre = _build_centre()
    offset = iso.location - centre
    radius = math.hypot(offset.x, offset.y)
    height = offset.z
    start = math.atan2(offset.y, offset.x)

    camera = bpy.data.objects.new("CAM_Turntable", iso.data)
    bpy.context.scene.collection.objects.link(camera)
    scene = bpy.context.scene
    scene.camera = camera

    frames_dir = stage / "frames"
    frames_dir.mkdir()
    infos = []
    if tier.dimensions:
        face_camera(camera)
        concealed = hidden(lambda obj: obj.name == "StudioFloor")
    else:
        concealed = hidden_for_presentation()
    with concealed:
        for index in range(tier.frames):
            angle = start + 2 * math.pi * index / tier.frames
            camera.location = centre + Vector((radius * math.cos(angle), radius * math.sin(angle), height))
            aim_at(camera, tuple(centre))
            scene.render.filepath = str(frames_dir / f"frame_{index:03d}.png")
            bpy.ops.render.render(write_still=True)
            infos.append(
                {"index": index, "location_mm": [round(v * 1000, 1) for v in camera.location]}
            )
    verify_frames(stage, tier.frames, tier.resolution)
    (stage / "scene.json").write_text(
        json.dumps(
            {
                "kind": "turntable",
                "frames": tier.frames,
                "resolution": tier.resolution,
                "engine": tier.engine,
                "dimensions": tier.dimensions,
                "blender_version": bpy.app.version_string,
                "target_mm": [round(v * 1000, 1) for v in centre],
                "cameras": infos,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    (stage / "viewer.html").write_text(
        render_viewer(
            tier.frames, title="Package", meta=f"{tier.resolution}×{tier.resolution} {tier.engine}"
        ),
        encoding="utf-8",
    )


def main(argv: list[str] | None = None) -> int:
    return _render.run(list(sys.argv if argv is None else argv), fill)


if __name__ == "__main__":
    raise SystemExit(main())
