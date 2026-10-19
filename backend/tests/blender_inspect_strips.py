"""Run inside Blender: open a saved composition and print each LED strip's bar and light.

    blender --background <model.blend> --python blender_inspect_strips.py
"""

import json

import bpy
from mathutils import Vector

found = {}
for obj in bpy.data.objects:
    if obj.type == "MESH" and obj.name.startswith("STRIP_"):
        points = [obj.matrix_world @ Vector(c) for c in obj.bound_box]
        found[obj.name] = {
            "low_mm": round(min(p.z for p in points) * 1000, 1),
            "length_mm": round(max((points[i] - points[j]).length for i in range(8) for j in range(8)) * 1000, 1),
            "shadow": obj.visible_shadow,
        }
    elif obj.type == "LIGHT" and obj.name.startswith("LGT_Strip_"):
        shine = obj.matrix_world.to_3x3() @ Vector((0, 0, -1))
        found[obj.name] = {
            "type": obj.data.type, "shape": obj.data.shape, "energy": round(obj.data.energy, 3),
            "size_mm": round(obj.data.size * 1000, 1), "shine": [round(c, 4) for c in shine],
        }
print("INSPECT " + json.dumps(found))
