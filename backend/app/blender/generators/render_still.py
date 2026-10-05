"""Render one still of a built package, at the tier the guard authorised.

    blender --background --python render_still.py -- \
      --blend model.blend --out /new/dir \
      --tier-frames 12 --tier-resolution 600 --tier-engine BLENDER_EEVEE

Writes `still.png` and `scene.json` into the new directory. The three
`--tier-*` values come from the runner, from a guard ticket; this script never
chooses a frame count, resolution or engine itself.
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import bpy

BACKEND_ROOT = Path(__file__).resolve().parents[3]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.blender.cli import TierArguments
from app.blender.generators import _render
from app.blender.generators._scene import (
    GeneratorError,
    hidden_for_presentation,
)
from app.blender.verify import verify_png


def fill(stage: Path, tier: TierArguments) -> None:
    _render.configure_render(tier)
    camera = bpy.data.objects.get("CAM_Iso")
    if camera is None:
        raise GeneratorError("render: CAM_Iso is missing from model.blend")
    scene = bpy.context.scene
    scene.camera = camera
    scene.render.filepath = str(stage / "still.png")
    started = time.perf_counter()
    with hidden_for_presentation():
        bpy.ops.render.render(write_still=True)
    render_seconds = time.perf_counter() - started
    verify_png(stage / "still.png", (tier.resolution, tier.resolution))
    (stage / "scene.json").write_text(
        json.dumps(
            {
                "kind": "still",
                "resolution": tier.resolution,
                "engine": tier.engine,
                "blender_version": bpy.app.version_string,
                "camera": "CAM_Iso",
                # The frame alone, without Blender's start-up and file load: what
                # the benchmark divides by megapixels.
                "render_seconds": round(render_seconds, 3),
            },
            indent=2,
        ),
        encoding="utf-8",
    )


def main(argv: list[str] | None = None) -> int:
    return _render.run(list(sys.argv if argv is None else argv), fill)


if __name__ == "__main__":
    raise SystemExit(main())
