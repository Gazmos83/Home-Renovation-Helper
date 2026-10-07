## Why

The owner's process is: design a piece, revise it, approve it, then see it in its room with lighting and the rest of the furniture. Today a room render holds exactly one piece. It is placed by `room_fit`, and its furnishings are plain grey boxes. An apartment shell renders empty, and `render_turntable` refuses a shell placed in a room. So the owner cannot put several approved designs, their bought furniture and downloaded models into one room and render that.

## What Changes

- **Room composition.** A new spec document, `room_composition`, holds one room by default, or a whole apartment when the owner asks for it. It lists several placed items. It is versioned like a piece under `docs/renders/rooms/<slug>/v<N>/`, built headless (ladder step 1) and is the source of truth for the room. Nothing at step 3 writes back to it.
- **Three kinds of item:**
  - **piece:** the owner's own design, at an **approved** version only (approval comes from `piece-first-workflow`). Placing an unapproved version is refused. A version unapproved after it was placed stays in the room, marked "no longer approved"; it is never dropped silently.
  - **stand-in:** bought furniture as a named box with width, depth, height and a colour.
  - **model:** an imported 3D model from the owner's model library.
- **Model library.** The owner uploads GLB, glTF (as a zip) or OBJ (as a zip with its `.mtl` and textures), with a name and the real width, depth and height. The type is checked from the file's bytes. Size and zip-safety limits apply: no path traversal, no absolute or remote references, and caps on entry count and unpacked size. `.blend`, FBX and every other type are refused. A headless check job imports each model once, measures it and refuses one that will not load or is over the triangle limit. A model is scaled to the stated size and stood on the floor.
- **Placement validation.** Every item is checked like `room_fit` today: inside the outline (L-shaped rooms included), under the ceiling, not blocking a door or a window below its height, not overlapping another item, and against the placement design rules (`front_clearance_mm`, `door_swing_clear`) when any are configured.
- **Agents.**
  - The Designer gains `compose_room`, which proposes a whole composition, pauses for the owner's `yes`, then creates the version and starts its build.
  - The Builder's `render_turntable` accepts a composition as a third target beside a piece and a shell.
  - The Lighting & materials detail pass may target a composition version, so room lighting and look-dev happen at step 3 on a copy, as for a piece.
- **Render guard: rules unchanged, one new target.** A composition render requires a tier, refuses raw frame, resolution and engine values, states the estimate, and runs `final` only after the owner's `yes`, exactly as for a piece or a shell.
- **bpy allow-list: the live list is not widened.** Model import happens only in the checked-in headless generator, which already calls `bpy.ops.import_scene.gltf` for `model.glb` today. It adds `bpy.ops.wm.obj_import`, verified present in Blender 5.2.1, where the legacy `import_scene.obj` is gone. **CLAUDE.md §8 is amended** to state that the headless generators may call exactly these two importers on validated library files, and that live scripts still may not. The live detail pass never imports models (owner decision 2026-10-07): every model comes in through the build.
- **Studio.** A Rooms page lists each composition with its items and their approval state, the latest still and viewer, and the model library with an upload form.

## Capabilities

### New Capabilities
- `room-composition`: the composition document, its item kinds and placement rules, versions and the headless build, room and apartment scope, approval tracking, guarded renders and the detail pass on a composition.
- `model-assets`: the owner's model library. Upload and type checks, zip safety, the headless import check, storage and serving.

### Modified Capabilities
- `design-agents`: the Designer composes a room and the Builder renders a composition. Added requirements only.
- `house-file`: compositions and their versions are indexed, and every turn's house note lists them. Added requirement only.
- `studio-ui`: a Rooms page for compositions and the model library. Added requirement only.

## Impact

- **Depends on** `piece-first-workflow` (version approval) and on `photoreal-detail` being archived first (the detail pass on a composition extends it).
- **Backend, new:**
  - `app/blender/composition_contract.py`: standard library only, shared with Blender.
  - `app/blender/generators/build_composition.py`: reuses the room-shell, lighting and wall-hiding helpers of `build_room_scene.py` and the apartment walls of `build_shell.py`.
  - `app/blender/generators/check_model.py`.
  - `app/assets/`: the model library.
  - `plugins/compose_room/`, and migrations for the `model_assets`, `compositions` and `composition_versions` tables.
- **Backend, changed:**
  - `app/blender/storage.py`: a `rooms/` and `models` folder, and a `room` record next to `piece` and `shell`.
  - `app/blender/runner.py`, `plugins/render_turntable/tool.py`, `plugins/photoreal_detail/tool.py`, `app/agent/foreman.py` (a composition is renderable), `app/agent/house_file.py`, `app/config.py` (model limits).
- **Frontend:** a `routes/Rooms.tsx` page and new API client calls.
- **Docs:** CLAUDE.md §8 (headless importers), README.
- **No new Python or JS dependency;** the zip and glTF checks use the standard library.
