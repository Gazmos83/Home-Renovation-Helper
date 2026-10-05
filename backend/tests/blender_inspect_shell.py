"""Run inside Blender: print one JSON line describing a shell .blend for the tests.

    blender --background FILE.blend --python blender_inspect_shell.py
"""

import json

import bpy
from mathutils import Vector

objects = []
for obj in bpy.data.objects:
    if obj.type != "MESH":
        objects.append({"name": obj.name, "type": obj.type})
        continue
    corners = [obj.matrix_world @ Vector(c) for c in obj.bound_box]
    top_area = 0.0
    for polygon in obj.data.polygons:
        if polygon.normal.z > 0.99:
            top_area += polygon.area
    objects.append(
        {
            "name": obj.name,
            "type": obj.type,
            "min": [min(c[i] for c in corners) for i in range(3)],
            "max": [max(c[i] for c in corners) for i in range(3)],
            "top_area_m2": top_area,
        }
    )
print("INSPECT " + json.dumps({"objects": objects}))
