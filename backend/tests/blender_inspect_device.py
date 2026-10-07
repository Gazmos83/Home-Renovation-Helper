"""Run inside Blender: apply the generators' Cycles setup for one device and print the result.

    blender --background --python blender_inspect_device.py -- DEVICE
"""

import json
import sys
from pathlib import Path

import bpy

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.blender.cli import TierArguments
from app.blender.generators import _render

device = sys.argv[sys.argv.index("--") + 1]
_render.configure_render(TierArguments(1, 600, "CYCLES", device))
preferences = bpy.context.preferences.addons["cycles"].preferences
print(
    "INSPECT "
    + json.dumps(
        {
            "engine": bpy.context.scene.render.engine,
            "device": bpy.context.scene.cycles.device,
            "compute": preferences.compute_device_type,
        }
    )
)
