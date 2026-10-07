"""Import one library model headless and measure it (model-assets); never renders.

Run as `blender --background --factory-startup --python check_model.py --
--model <file> --kind glb|gltf|obj --out <folder>`. Writes `check.json` with the
model's evaluated mesh bounds in millimetres (x width, y depth, z height, Blender's
Z-up frame) and its triangle count. Only the two bundled importers are used, on a
file that already passed the upload checks; nothing else is read or written.
"""

from __future__ import annotations

import json
import os
import sys
import uuid
from pathlib import Path

import bpy
from mathutils import Vector


def _arguments(argv: list[str]) -> tuple[Path, str, Path]:
    args = argv[argv.index("--") + 1:] if "--" in argv else []
    values = dict(zip(args[::2], args[1::2], strict=False))
    try:
        return Path(values["--model"]), values["--kind"], Path(values["--out"])
    except KeyError as missing:
        raise SystemExit(f"check: missing {missing.args[0]}") from None


def import_objects(path: Path, kind: str) -> list[bpy.types.Object]:
    """Import with the bundled importer for `kind`; return every new object."""
    before = set(bpy.data.objects)
    if kind in ("glb", "gltf"):
        bpy.ops.import_scene.gltf(filepath=str(path))
    elif kind == "obj":
        bpy.ops.wm.obj_import(filepath=str(path))
    else:
        raise ValueError(f"unknown model kind {kind!r}")
    return [obj for obj in bpy.data.objects if obj not in before]


def import_model(path: Path, kind: str) -> list[bpy.types.Object]:
    """Import with the bundled importer for `kind`; return the new mesh objects."""
    return [obj for obj in import_objects(path, kind) if obj.type == "MESH"]


def measure(meshes: list[bpy.types.Object]) -> tuple[dict[str, float], int, list[float]]:
    """The evaluated world bounds' size in mm, the triangle count and the minimum corner (m)."""
    depsgraph = bpy.context.evaluated_depsgraph_get()
    low = Vector((float("inf"),) * 3)
    high = Vector((float("-inf"),) * 3)
    triangles = 0
    for obj in meshes:
        evaluated = obj.evaluated_get(depsgraph)
        mesh = evaluated.to_mesh()
        try:
            mesh.calc_loop_triangles()
            triangles += len(mesh.loop_triangles)
            for vertex in mesh.vertices:
                point = evaluated.matrix_world @ vertex.co
                low = Vector(map(min, low, point))
                high = Vector(map(max, high, point))
        finally:
            evaluated.to_mesh_clear()
    if triangles == 0:
        return {"x": 0.0, "y": 0.0, "z": 0.0}, 0, [0.0, 0.0, 0.0]
    size = high - low
    return {"x": size.x * 1000, "y": size.y * 1000, "z": size.z * 1000}, triangles, list(low)


def main(argv: list[str] | None = None) -> int:
    try:
        model, kind, out = _arguments(list(sys.argv if argv is None else argv))
        meshes = import_model(model, kind)
        size, triangles, _low = measure(meshes)
        stage = out.parent / f".{out.name}.tmp-{uuid.uuid4().hex}"
        stage.mkdir(parents=True)
        (stage / "check.json").write_text(
            json.dumps({"size_mm": size, "triangles": triangles, "meshes": len(meshes)}), encoding="utf-8"
        )
        os.replace(stage, out)
        print(f"WROTE {out}")
        return 0
    except Exception as error:  # noqa: BLE001 - Blender errors need a short operator-safe diagnostic
        print(f"check: {type(error).__name__}: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
