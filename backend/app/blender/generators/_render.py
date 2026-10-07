"""The skeleton the still and turntable generators share (inside Blender).

Parse the guard-issued tier arguments, open the built `model.blend`, fill a
staging directory, verify it, and publish it with one rename — or print one
concise diagnostic to stderr, remove the staging directory and exit non-zero.
"""

from __future__ import annotations

import os
import shutil
import sys
import uuid
from collections.abc import Callable
from pathlib import Path

import bpy

BACKEND_ROOT = Path(__file__).resolve().parents[3]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.blender.cli import (
    InputError,
    TierArguments,
    parse_render_arguments,
)
from app.blender.generators._scene import GeneratorError, set_engine
from app.blender.verify import VerificationError

Fill = Callable[[Path, TierArguments], None]


def configure_render(tier: TierArguments) -> None:
    """Engine and square resolution from the tier — nothing else is chosen."""
    set_engine(tier.engine)
    scene = bpy.context.scene
    scene.render.resolution_x = tier.resolution
    scene.render.resolution_y = tier.resolution
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.render.film_transparent = False
    if tier.engine == "CYCLES":
        use_cycles_device(tier.device)


def use_cycles_device(device: str) -> None:
    """Cycles on the CPU, or on a GPU back end (OPTIX, CUDA or HIP) when the
    render server asks for one. The default leaves the laptop's behaviour as it was."""
    scene = bpy.context.scene
    if device == "CPU":
        scene.cycles.device = "CPU"
        return
    preferences = bpy.context.preferences.addons["cycles"].preferences
    preferences.compute_device_type = device
    preferences.get_devices()
    for entry in preferences.devices:
        entry.use = entry.type == device
    scene.cycles.device = "GPU"


def run(argv: list[str], fill: Fill) -> int:
    stage: Path | None = None
    try:
        blend, output, tier = parse_render_arguments(argv)
        bpy.ops.wm.open_mainfile(filepath=str(blend))
        stage = output.parent / f".{output.name}.tmp-{uuid.uuid4().hex}"
        stage.mkdir()
        fill(stage, tier)
        os.replace(stage, output)
        stage = None
        print(f"WROTE {output}")
        return 0
    except (GeneratorError, InputError, VerificationError) as error:
        print(str(error), file=sys.stderr)
    except Exception as error:  # noqa: BLE001 - Blender errors need a short operator-safe diagnostic
        print(f"render: {type(error).__name__}: {error}", file=sys.stderr)
    if stage is not None and stage.exists():
        shutil.rmtree(stage)
    return 1
