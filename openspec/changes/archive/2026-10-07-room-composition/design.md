## Context

See proposal.md for the motivation. Current state:
- **Room renders.** `room_contract.py` (standard library only) validates a `room_scene` document: one placed piece (`placement: {wall, offset_mm}`) and `furnishings`, which are named boxes with `x_mm`/`y_mm`/`rotation_deg`. `room_fit` builds that document from a house-file room plus one piece version. `build_room_scene.py` builds the room shell, imports the package's `model.glb` with `bpy.ops.import_scene.gltf`, and renders through `_render`.
- **Shells.** `build_shell.py` generates an apartment's walls once per shared edge. Shell versions live under `docs/renders/shells/<slug>/v<N>/`. `storage.record_version_dir` knows the records `piece` and `shell`, and the guard's quote carries `record`.
- **Allow-list.** `app/live/allowlist.py` is applied only to scripts sent over the live socket (`detail_pass.py`). The checked-in headless generators are fixed code that the runner launches; no allow-list check runs on them, and `build_room_scene.py` already calls `import_scene.gltf` and `wm.read_factory_settings`.
- **Detail pass.** `photoreal_detail` resolves its target from the thread's bound piece. The photoreal-detail delta refuses a detail render "placed in a room", meaning a piece with a `room_fit` document.
- **Uploads.** Images only (PNG/JPEG sniffed from bytes), per thread, under `upload_root`, capped by `upload_max_bytes` (10 MB).
- **Design rules.** `config/design_rules.yaml` holds the placement checks `front_clearance_mm` and `door_swing_clear`. No rule is configured yet.
- **Approval.** Version approval is defined by `piece-first-workflow`, which this change depends on.

## Goals / Non-Goals

**Goals:**
- One document places many items, validated by code, then built and rendered with the existing guard, storage and publish machinery.
- Imported models are treated as untrusted input until a byte-level check and a headless import check pass.
- One room is the default scope, so a render only builds what it shows.

**Non-Goals:**
- Downloading models from online libraries (Poly Haven, Sketchfab). The owner uploads files only.
- Converting models between formats, or editing them.
- Camera matching against photos (still step 3, unchanged).
- Rewriting the single-piece `room_fit` path. It stays as it is for a quick look at one piece in its room.
- A per-scene render estimate. The guard formula stays frames × megapixels × engine multiplier × benchmark.

## Decisions

1. **A new document kind, not an extended `room_scene`.** `room_composition` gets its own standard-library contract, `composition_contract.py`. It reuses `room_contract`'s geometry helpers (simple polygon, footprint inside the polygon, rotated-rectangle overlap, the wall list, the opening rules) by importing them, not by copying them.
   - *Alternative:* widen `room_scene` to many pieces. Rejected: it would change a spec'd contract that `room_fit` and existing renders rely on, and the single-piece path keeps working unchanged.

2. **Placement in the plan frame.** A wall placement `{wall, offset_mm}` puts the item's back against that wall, as `_normalise_placement` does today. A free placement `{x_mm, y_mm, rotation_deg}` puts its footprint centre there, as for furnishings. Rooms inside an apartment already share the apartment's plan frame, so an apartment scope needs no per-room transform.
   - Door and window blocking reuses `room_fit.opening_in_the_way` for wall placements. For free placements the footprint is tested against each opening's span along its wall, projected `max(item depth, 1 mm)` into the room. That is the strictest reading available without inventing a clearance figure. Clearance distances come only from configured design rules.

3. **Storage layout.** Versions live under `docs/renders/rooms/<scope-slug>/v<N>/`. `rooms` joins `RESERVED_IDS`, and `record_version_dir` gains `record == "room"`. An apartment scope is slugged with an `apt-` prefix so a room and an apartment with the same name cannot collide. The guard, the runner's staging and publish, `status.json` and `render_key` are reused as they are; only the record name is new.

4. **One generator, `build_composition.py`.**
   - It imports the room-shell, lighting, materials and per-frame wall-hiding helpers from `build_room_scene.py`, and for an apartment scope the shared-wall builder from `build_shell.py`. The shared functions move into `generators/_room.py` only if a direct import proves awkward; any such move is a pure extraction.
   - Pieces come in from each version's `model.glb` (`import_scene.gltf`), as today. Stand-ins are a box with a material in the item's colour.
   - Library models use `import_scene.gltf` or `wm.obj_import`, are joined under one empty named `ITEM_<id>`, are stretched to exactly the stated size by a per-axis scale `stated / measured` (owner decision 2026-10-07: stretch, not fit), and are dropped so the lowest point sits at z = 0.
   - The build report lists each item's final size and, for a library model, its per-axis scale factors.

5. **Allow-list: live unchanged, headless importers named.** Importing is done only by checked-in generator code on files that passed `model-assets` checks. The live allow-list (`OPERATOR_NAMESPACES`, the `wm` exceptions) does not change. CLAUDE.md §8 gains one sentence: headless generators may call `bpy.ops.import_scene.gltf` and `bpy.ops.wm.obj_import` on validated library files and package `model.glb` files, and live scripts may not import files.
   - *Alternative:* widen the live allow-list as well. Not needed for any spec'd behaviour, because placement happens at step 1, and it would let a model-written script import arbitrary paths.

6. **Model library outside threads.** A new `model_assets` table holds the id, name, stated size, kind (`glb`/`gltf`/`obj`), state (`checking`/`ready`/`refused`), reason, measured size and triangle count. Files live under `<upload_root>/models/<id>/`.
   - Upload streams to a temporary file under the cap, sniffs the bytes (`glTF` magic for GLB, `PK\x03\x04` for a zip), and for a zip validates every entry with `zipfile` before extracting anything.
   - It then parses `.gltf` JSON for `buffers[].uri`/`images[].uri`, and reads OBJ `mtllib` and MTL `map_*`/`bump`/`disp`/`norm` lines, checking every reference against the extracted set.
   - A `.blend` is refused by its `BLENDER` magic, and anything else by not matching an accepted form.
   - Limits are settings with these defaults (owner decision 2026-10-07): `model_max_bytes` 50 MB, `model_zip_max_entries` 200, `model_zip_max_unpacked_bytes` 200 MB, `model_max_triangles` 500 000, `composition_max_items` 30.

7. **Headless check job.** `check_model.py` runs after upload through the runner's semaphore and timeout. It is not a render, so no tier applies. It imports the model with factory settings, measures the evaluated mesh bounds and triangle count, and writes `check.json`; the service reads that file and sets the state. Library routes poll the state, which the Rooms page refetches while any model is `checking`.

8. **Approval check at proposal time, flag at read time.** `compose_room` refuses unapproved versions when it previews. Reads (house note, Studio, `render_turntable` reply) join each placed version with its current approval and mark it "no longer approved"; nothing is stored about the unapproval on the composition. Builds and renders are **not** blocked by an unapproved placed version; they only warn.

9. **Agents.**
   - `compose_room` is a Designer plugin (manifest, gated, toggleable). Its preview returns a `Confirmation` with subject `compose_room`, and a declined answer adds `DECLINED["compose_room"]`.
   - `render_turntable` gains `composition: str | None` and refuses when not exactly one of `package_id`, `shell` or `composition` is set.
   - The Foreman's `buildable` rule gains `composition_ready`, computed in `load_house` like `shell_ready`.
   - `photoreal_detail` gains an optional `composition` argument; when it is given, the target folder is the composition version folder instead of the bound piece's. The photoreal-detail "not placed in a room" refusal still applies to `room_fit` documents, not to a composition, whose `model.blend` already is the room.

## Risks / Trade-offs

- [A malformed model crashes or hangs Blender] → It is caught by the check job under the timeout, before any composition can use it. A crash marks the model `refused`.
- [A huge model makes every room render slow] → The triangle cap at check time. A room scope by default keeps scenes small.
- [A stretched model looks distorted when the stated proportions differ a lot from the model's own] → The build report states the per-axis scale factors, so a wrong stated size is easy to spot and correct with a new stated size.
- [The guard estimate ignores scene complexity] → A room with many items may run longer than quoted. Actual times are logged and calibrated as today; a per-scene multiplier is out of scope.
- [Two changes touch `render_turntable` and `photoreal_detail`] → This change applies after `photoreal-detail` is archived and `piece-first-workflow` is applied. Tasks start by checking that.
- [glTF importer behaviour on odd files] → It is the Blender-bundled add-on, pinned with Blender 5.2.1. The `--blender` slow test imports fixtures of each form.

## Migration Plan

- An Alembic migration adds `model_assets`, `compositions` and `composition_versions`. Downgrade drops them; the folders under `docs/renders/rooms/` and `<upload_root>/models/` are left on disk.
- No existing document, folder or route changes shape. `room_fit` and single-piece room renders behave as before.
- Rollback: revert the code and downgrade the migration. Composition folders stay readable as plain files.

## Open Questions

Decided by the owner on 2026-10-07:
- Library models are stretched to exactly the stated size (decision 4).
- A no-longer-approved placed version warns only, at every tier including `final` (decision 8).
- The limits stay at 50 MB per file, 200 zip entries, 200 MB unpacked, 500 000 triangles and 30 items (decision 6).
- The live detail pass never imports library models. Every model enters a room as a placed item in the composition and comes in through the headless build, so the composition stays the source of truth and a rebuild never loses a model. The live allow-list is not widened.

None open.
