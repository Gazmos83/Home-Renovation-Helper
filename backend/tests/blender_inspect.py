"""Run inside Blender: print one JSON line describing a .blend for the tests.

    blender --background FILE.blend --python blender_inspect.py
"""

import json

import bpy

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
