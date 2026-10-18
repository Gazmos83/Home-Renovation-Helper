## Why

`hardware-catalog` draws common hardware from parametric shapes. Two needs remain that a shape table cannot meet.
- **Realism.** Some items, like a specific knob, a pull or a hinge, look right only as a real model. The owner wants every model to come from what they import themselves: their JSON designs and the items in their model library, not manufacturer CAD (decided 2026-10-16).
- **The mechanism.** The `murphy-bed` design came from an LLM, not from a real product, and its folding mechanism is only a hardware line ("No hardware model selected"). The owner wants every component of such a mechanism shown, so a carpenter can analyse and replace each part. Showing the folded and unfolded positions would be nice, but only if building the inspector model gets no more than 90 s slower.

## What Changes

- **A library model can stand for a hardware key.** From the model library, the owner assigns a `ready` model to a hardware key (for example `cabinet-knob-brass` or `hinge-concealed-110`). Where that key is drawn, the generator then uses the model instead of the catalog shape.
  - The model is placed at its stated real size, with its bounding box anchored on the catalog shape's mounting face.
  - It is refused, naming both sizes, when its stated size differs from the catalog shape's by more than the configured tolerance (default 25 %).
  - It is imported once per build and instanced at each position.
  - Removing the assignment or the model brings back the catalog shape at the next build.
- **Mechanism assemblies.** A catalog entry can be an `assembly`: named components, each a catalog shape or a cut part, with pivot axes and limits. A build can carry one `fold_bed`, the first assembly kind. It names the module that houses the bed and the mattress size. The app then derives an **illustrative** fold-down mechanism. Every component is its own object and its own cut-list row or hardware line:
  - two pivot brackets, two side arms and two lift struts (gas struts or springs);
  - a wall mounting rail and its anchors;
  - the platform frame (cut parts) and two folding legs.

  Each line says it is illustrative and must be replaced by a selected product's parts before building. Nothing is engineered: there are no load, spring-force or anchor calculations (engineering-safety: no evidence is implied).
- **Poses.** A piece with an assembly is built in its stored pose (`closed`, the default) and exported a second time in `open`.
  - The inspector gets a Folded / Unfolded switch that loads `model.glb` or `model-open.glb`.
  - A render request may name the pose; the default is the stored one. Each pose is its own render, with its own guard ticket and estimate.
  - The second export must add no more than 90 s to the build. It is measured, and the build reports the time.
- **Import.** The import corrections from `hardware-catalog` recognise mechanism lines ("murphy bed mechanism", "fold-down bed mechanism") and warn that they can be written as a `fold_bed`. They are not converted automatically. The template guide describes `fold_bed`.

Ladder step 2 (generator extension). Agents touched:
- **Designer:** `fold_bed` in create, revise and import, and the context summary.
- **Builder:** imports library models into piece builds, the assembly, and the second pose export.
- **Owner UI:** model-library assignment, and the inspector pose switch.

The **render guard is affected only by the pose parameter**. A render still needs its tier and the typed "yes" for `final`. The estimate is per pose, and no render is added without a request. The **bpy allow-list is not affected for live scripts**. **CLAUDE.md §8 is extended for checked-in headless generators:** `build_custom_build.py` may call `bpy.ops.import_scene.gltf` / `bpy.ops.wm.obj_import` on a `ready` model-library file assigned to a hardware key, as the room-composition generator already may. A live script still may not import a file.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `hardware-catalog` (from `hardware-catalog`): library models assigned to keys, and assembly entries.
- `model-assets`: assigning a model to a hardware key.
- `furniture-packages`: `fold_bed`, components as rows and lines, poses and `model-open.glb`.
- `studio-ui`: the inspector pose switch, and the assignment control on the model library page.
- `scene-rendering`: a render names its pose.
- `design-import`: the mechanism warning and the `fold_bed` guide.

## Impact

- **Depends on `hardware-catalog`** being applied and archived.
- **Backend:**
  - `config/hardware.yaml` (assemblies), `app/blender/hardware_catalog.py`;
  - a `hardware_models` table (key → model id) with an Alembic migration, and model-library routes;
  - `schemas.py` (`FoldBedIn`), `derive.py` (assembly layout, rows and lines), `build_custom_build.py` (model import and instancing, assembly, pose export);
  - `runner.py` (passes assigned model paths; timing);
  - render tools (pose argument);
  - `import_corrections.py`, `import-template.json`, `designer.md`.
- **Frontend:**
  - the inspector (pose switch, `PieceModel.tsx` loads by pose);
  - the model library page (assign to a key);
  - the render request (pose).
- **CLAUDE.md §8:** one sentence extended (headless generator imports for pieces).
- **Tests:** catalog assembly loading, size tolerance, the `--blender` suite (import and instancing, assembly objects, both poses, timing), render-guard tests for the pose, Vitest, and a recorded browser check.
