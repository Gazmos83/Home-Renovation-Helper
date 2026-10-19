"""Build one room-composition version headless (room-composition); never renders.

Usage (the arguments after ``--`` belong to this script)::

    blender --background --python build_composition.py -- \
      --spec <version>/input.json --pieces <render root> --models <upload root>/models \
      --out /absolute/new-dir

Publishes `model.blend`, `model.glb` (for the Rooms page's 3D view), a Workbench
`screenshot.png` and `report.json`, which lists each item's stated and final size and,
for a library model, its per-axis scale factors, and holds the surface map: each
wall, floor and ceiling and the items, with the mesh names in `model.glb`. A still or turntable of the composition is `render_composition.py`'s job,
behind the render guard.
"""

from __future__ import annotations

import json
import math
import os
import shutil
import sys
import uuid
from pathlib import Path

import bpy
from mathutils import Vector

BACKEND_ROOT = Path(__file__).resolve().parents[3]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.blender.generators import _composition as composition
from app.blender.generators import build_shell as shell_gen
from app.blender.generators._scene import GeneratorError, export_glb
from app.blender.generators._scene import add_camera as _add_camera
from app.blender.generators._scene import aim_at as _aim_at
from app.blender.verify import VerificationError, verify_composition


def arguments(argv: list[str], names: tuple[str, ...]) -> dict[str, str]:
    args = argv[argv.index("--") + 1:] if "--" in argv else []
    values = dict(zip(args[::2], args[1::2], strict=False))
    missing = [name for name in names if name not in values]
    if missing:
        raise GeneratorError(f"arguments: missing {missing[0]}")
    return values


def iso_camera(scene: composition.CompositionScene) -> None:
    """The overview camera the screenshot uses (an apartment's shell build already made one)."""
    if bpy.data.objects.get("CAM_Iso") is not None:
        return
    m = composition.m
    centre = (m(scene.centre_mm[0]), m(scene.centre_mm[1]), m(scene.ceiling_mm / 2))
    distance = max(6.0, m(scene.radius_mm) * 4.6)
    direction = Vector((0.4, -0.6, 1.0)).normalized()
    camera = _add_camera("CAM_Iso", tuple(Vector(centre) + direction * distance), (0, 0, 0))
    camera.data.clip_end = max(20.0, distance * 4)
    _aim_at(camera, centre)
    bpy.context.scene.camera = camera
    if bpy.data.objects.get("LGT_Sun") is None:
        sun_data = bpy.data.lights.new("LGT_Sun", "SUN")
        sun_data.energy = 3.0
        sun = bpy.data.objects.new("LGT_Sun", sun_data)
        bpy.context.scene.collection.objects.link(sun)
        sun.rotation_euler = (math.radians(50), math.radians(10), math.radians(35))


def build(document: dict, pieces: Path, models: Path, output_dir: Path) -> None:
    try:
        scene = composition.build_scene(document, pieces_root=pieces, models_root=models)
        iso_camera(scene)
    except GeneratorError:
        raise
    except Exception as error:
        raise GeneratorError(f"build: {type(error).__name__}: {error}") from error
    try:
        surfaces = composition.surfaces(scene)
        report = {
            "kind": "room_composition_build",
            "scope": document["scope"],
            "blender_version": bpy.app.version_string,
            "items": scene.report,
            "surfaces": surfaces,
            "extent_mm": composition.extent_mm(scene),
            "rig_factors": composition.rig_factors(scene),
            **({"floor": document["floor"]} if document.get("floor") else {}),
        }
        (output_dir / "report.json").write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        # A tiled floor shows its plain colour in the screenshot and the 3D view; `model.blend`
        # is saved with the tile material back on (room-floor-finish).
        with composition.flat_floor(scene):
            shell_gen._write_screenshot(output_dir / "screenshot.png")
            # Every mesh, ceilings included: the 3D view switches each surface itself.
            export_glb({name for names in surfaces.values() for name in names}, output_dir / "model.glb", hide_helpers=False)
        bpy.ops.wm.save_as_mainfile(filepath=str(output_dir / "model.blend"), check_existing=False)
    except GeneratorError:
        raise
    except Exception as error:
        raise GeneratorError(f"export: {type(error).__name__}: {error}") from error
    for leftover in output_dir.glob("*.blend1"):
        leftover.unlink()
    try:
        verify_composition(output_dir)
    except VerificationError as error:
        raise GeneratorError(f"publish: {error}") from error


def main(argv: list[str] | None = None) -> int:
    stage: Path | None = None
    try:
        values = arguments(list(sys.argv if argv is None else argv), ("--spec", "--pieces", "--models", "--out"))
        document = json.loads(Path(values["--spec"]).read_text(encoding="utf-8"))
        output_path = Path(values["--out"])
        stage = output_path.parent / f".{output_path.name}.tmp-{uuid.uuid4().hex}"
        stage.mkdir()
        build(document, Path(values["--pieces"]), Path(values["--models"]), stage)
        os.replace(stage, output_path)
        stage = None
        print(f"WROTE {output_path}")
        return 0
    except GeneratorError as error:
        print(str(error), file=sys.stderr)
    except Exception as error:  # noqa: BLE001 - Blender errors need a short operator-safe diagnostic
        print(f"build: {type(error).__name__}: {error}", file=sys.stderr)
    if stage is not None and stage.exists():
        shutil.rmtree(stage)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
