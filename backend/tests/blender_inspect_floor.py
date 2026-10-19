"""Run inside Blender: open a saved composition and print its floors' materials and tile nodes.

    blender --background <model.blend> --python blender_inspect_floor.py
"""

import json

import bpy

floors = {}
for obj in bpy.data.objects:
    if obj.type != "MESH" or not (obj.name == "Floor" or obj.name.startswith("Floor_")):
        continue
    used = sorted({obj.data.materials[p.material_index].name for p in obj.data.polygons if obj.data.materials})
    brick = None
    for material in obj.data.materials:
        node = next((n for n in material.node_tree.nodes if n.type == "TEX_BRICK"), None) if material.node_tree else None
        if node is not None:
            brick = {
                "brick_width": node.inputs["Brick Width"].default_value,
                "row_height": node.inputs["Row Height"].default_value,
                "mortar_size": node.inputs["Mortar Size"].default_value,
                "offset": node.offset,
            }
    floors[obj.name] = {"materials": used, "polygons": len(obj.data.polygons), "brick": brick}
print("INSPECT " + json.dumps(floors))
