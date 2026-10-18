"""Run inside Blender: print one JSON line describing a .blend for the tests.

    blender --background FILE.blend --python blender_inspect.py
"""

import json
import math

import bpy
from mathutils import Vector

scene = bpy.context.scene
print(
    "INSPECT "
    + json.dumps(
        {
            "engine": scene.render.engine,
            "resolution": [scene.render.resolution_x, scene.render.resolution_y],
            "objects": [
                {
                    "name": obj.name,
                    "type": obj.type,
                    "parent": obj.parent.name if obj.parent else None,
                    "part_id": obj.get("part_id"),
                    "hardware_key": obj.get("hardware_key"),
                    "materials": [m.name for m in obj.data.materials] if obj.type == "MESH" else [],
                    "metallic": [m.metallic for m in obj.data.materials] if obj.type == "MESH" else [],
                    "colours": (
                        [[round(c, 4) for c in list(m.diffuse_color)[:3]] for m in obj.data.materials]
                        if obj.type == "MESH"
                        else []
                    ),
                    "modifiers": [m.type for m in obj.modifiers],
                    "location": list(obj.matrix_world.translation),
                    "rotation_deg": [round(math.degrees(angle), 4) for angle in obj.rotation_euler],
                    "bound_box": [
                        [round(coord, 6) for coord in obj.matrix_world @ Vector(corner)]
                        for corner in obj.bound_box
                    ],
                    "vertices": (
                        sorted(
                            [list(point) for point in {
                                (
                                    round((obj.matrix_world @ vertex.co).x, 5),
                                    round((obj.matrix_world @ vertex.co).y, 5),
                                    round((obj.matrix_world @ vertex.co).z, 5),
                                )
                                for vertex in obj.data.vertices
                            }]
                        )
                        if obj.type == "MESH"
                        else []
                    ),
                    "dimension": obj.get("dimension"),
                    "text": obj.data.body if obj.type == "FONT" else None,
                    "faces": next(
                        (c.target.name for c in obj.constraints if c.type == "COPY_ROTATION" and c.target),
                        None,
                    ),
                }
                for obj in bpy.data.objects
            ],
        }
    )
)
