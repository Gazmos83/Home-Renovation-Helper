"""Run inside Blender: build a composition, restyle it in memory, print before and after colours.

    RESTYLE_SPEC=… RESTYLE_PIECES=… RESTYLE_MODELS=… RESTYLE_STYLE=… blender --background --python blender_inspect_restyle.py
"""

import json
import os
import sys
from pathlib import Path

import bpy

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.blender.generators import _composition as composition
from app.blender.generators import render_restyle


def colours() -> dict:
    found = {}
    for obj in bpy.data.objects:
        if obj.type != "MESH" or not obj.data.materials:
            continue
        shader = next((n for n in obj.data.materials[0].node_tree.nodes if n.type == "BSDF_PRINCIPLED"), None)
        found[obj.name] = [round(c, 4) for c in shader.inputs["Base Color"].default_value] if shader else None
    return found


document = json.loads(Path(os.environ["RESTYLE_SPEC"]).read_text(encoding="utf-8"))
scene = composition.build_scene(
    document, pieces_root=Path(os.environ["RESTYLE_PIECES"]), models_root=Path(os.environ["RESTYLE_MODELS"])
)
before = colours()
render_restyle.apply_room(scene, json.loads(os.environ["RESTYLE_STYLE"])["style"])
materials = {obj.name: obj.data.materials[0].name for obj in bpy.data.objects if obj.type == "MESH" and obj.data.materials}
print("INSPECT " + json.dumps({"before": before, "after": colours(), "items": [o.name for o in scene.item_meshes],
                               "materials": materials}))
