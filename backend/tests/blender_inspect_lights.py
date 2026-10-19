"""Run inside Blender: open a saved composition and print its lights and which meshes cast shadows.

    blender --background <model.blend> --python blender_inspect_lights.py
"""

import json

import bpy

lights = {
    obj.name: {
        "type": obj.data.type, "energy": round(obj.data.energy, 3),
        "z_mm": round(obj.location.z * 1000, 1), "color": [round(c, 4) for c in obj.data.color],
    }
    for obj in bpy.data.objects if obj.type == "LIGHT"
}
shadows = {obj.name: obj.visible_shadow for obj in bpy.data.objects if obj.type == "MESH" and obj.name.startswith("STAND_")}
print("INSPECT " + json.dumps({"lights": lights, "shadows": shadows}))
