## 0. Preconditions

- [x] 0.1 Confirm that `photoreal-detail` is archived and `piece-first-workflow` is applied, and that version approval is readable from code. Verify `openspec list` no longer shows `photoreal-detail` and the approval read used in 4.2 exists. Stop and ask if either is missing.

## 1. Model library (model-assets)

- [x] 1.1 Add the settings `model_max_bytes`, `model_zip_max_entries`, `model_zip_max_unpacked_bytes`, `model_max_triangles` and `composition_max_items` to `app/config.py`, with positive-value validation and the defaults in design.md (decided 2026-10-07). Verify that `tests/test_config.py` covers the defaults and a refusal of 0.
- [x] 1.2 Add an Alembic migration and models for `model_assets`, `compositions` and `composition_versions`. Verify that the migration test upgrades and downgrades on the test database.
- [x] 1.3 Implement `app/assets/models.py`: the streamed upload under the size cap, byte sniffing (GLB magic, zip, `.blend` refused), zip entry checks (absolute paths, `..`, drive letters, symlinks, entry count, unpacked size, extensions, exactly one model file), and the glTF URI, OBJ `mtllib` and MTL map checks. Verify that `tests/test_model_assets.py` covers GLB accepted, `.blend` refused with 415, an oversize file refused with 413 leaving no partial file, a traversal entry, a remote URI, a missing MTL, two model files, and the too-many-entries and unpacked-size caps.
- [x] 1.4 Add owner-gated routes to upload (multipart, with name and size), list, fetch a file by id and exact relative name (fixed content type, `nosniff`), and delete (refused while placed, naming the compositions). Verify that `tests/test_model_assets_api.py` covers 401 without the cookie, each refusal code, and the delete-in-use refusal.
- [x] 1.5 Add `generators/check_model.py` and its runner wiring (semaphore, timeout, no tier). It writes `check.json` with the measured size and triangle count, and the state becomes `ready` or `refused`. Verify that a unit test with a fake launcher covers ready, a crash leading to `refused`, and over-limit leading to `refused`, and that a `--blender` slow test (`tests/test_model_check_blender.py`) imports fixture GLB, glTF-zip and OBJ-zip files and reports their bounds and triangle counts.

## 2. Composition contract and storage

- [x] 2.1 Add `app/blender/composition_contract.py` (standard library only), reusing `room_contract`'s geometry helpers. It covers scope, item types, the two placement forms, unknown fields refused by name, no output fields, max items, footprint inside the room (L-shaped included), ceiling, wall overrun, door and window blocking, and item overlap. Verify that `tests/test_composition_contract.py` covers every scenario in `room-composition` "A composition document describes…" and "Every item is placed validly".
- [x] 2.2 Apply the configured placement design rules to every item through `app/guidelines/rules.evaluate`: `refuse` refuses, `warn` is reported. Verify with tests that use a temporary rules file with one rule of each severity.
- [x] 2.3 Extend `app/blender/storage.py` with the `rooms` reserved id, room and apartment scope slugs (`apt-` prefix), `composition_dir`, `composition_version_dir`, `composition_versions` and `record == "room"` in `record_version_dir`. Verify that `tests/test_storage.py` covers slug collisions, invalid versions and reserved ids.
- [x] 2.4 Add house-file functions to create a composition and its versions, read the latest version and status, and join placed versions with their current approval. Verify that `tests/test_house_file.py` covers the version on `yes` and the "no longer approved" flag after an unapproval.

## 3. Headless build

- [x] 3.1 Add `generators/build_composition.py`, reusing the room-shell, lighting, materials and wall-hiding helpers from `build_room_scene.py` (extract them into `_room.py` only if needed, unchanged) and the shared walls from `build_shell.py` for an apartment scope. It places pieces from `model.glb`, stand-ins as coloured boxes, and models via `import_scene.gltf` / `wm.obj_import` stretched per axis to the stated size with the floor drop, then publishes `model.blend`, a screenshot and a build report with each model's per-axis scale factors. Verify that the existing `test_room_scene` tests still pass.
- [x] 3.2 Wire the composition build into `app/blender/runner.py` (status, staging, atomic publish, one process). A placed piece version without a successful build fails the job naming it. Verify with runner tests using a fake launcher.
- [x] 3.3 Write the `--blender` slow test `tests/test_composition_blender.py`. It builds a fixture room with one built piece, one stand-in and one GLB model, checks the objects, that the model's bounds equal its stated size on each axis (within 1 mm), z = 0, and renders a still at tier `draft`. Verify that it passes with `uv run pytest -m slow --blender -k composition`.

## 4. Agents

- [x] 4.1 Add the `plugins/compose_room/` manifest and tool (Designer, gated, toggleable). The preview validates and summarises the items, the warnings and the added, moved and removed items against the latest version. A `yes` creates the version and starts the build, and `DECLINED["compose_room"]` covers `no`. Verify that `tests/test_compose_room.py` covers confirmed, declined, unapproved piece, model not ready, and an invalid placement returned without a pause.
- [x] 4.2 Extend `render_turntable` with the `composition` target: exactly one target, guard rules unchanged, a refusal when not built, and the "no longer approved" note in the reply. Verify that `tests/test_render_turntable.py` covers a `draft` start with its estimate, a `final` pause, raw `resolution` refused, two targets refused, and an unbuilt version refused.
- [x] 4.3 Add `composition_ready` to the Foreman's `load_house` and `buildable` rule, and list compositions in the Designer's and Builder's house note with names neutralised. Verify that `tests/test_foreman.py` routes a Builder request with only a built composition to the Builder, and that a house-note test shows the unapproved mark.
- [x] 4.4 Extend `photoreal_detail` with an optional `composition` target folder. The pass copies `detail/detail.blend` from the composition's `model.blend`, the detail render stays `final` only, and nothing is written to the composition document. Verify that `tests/test_photoreal_detail.py` covers the room-lighting scenario with a fake socket.
- [x] 4.5 Update the Designer and Builder instruction files to cover composing rooms, approved versions only, and stating refusals plainly. Verify with `tests/test_instructions.py`.

## 4b. Found during the browser check

- [x] 4.6 A compose request in a thread with no piece and no brief reached Intake, and the Designer could not learn a library model's id. Fixed as follows:
  - **Code:** the router lets a Designer choice stand while the house file holds an approved piece version or a composition.
  - **Foreman instructions:** `foreman.md` names composing rooms as the Designer's.
  - **Notes:** the Designer's and Builder's composition note lists the library's ready models (name, id, stated size; names neutralised).
  - **Spec:** the routing requirement is added to this change's `design-agents` delta as MODIFIED.

  Verify that `tests/test_foreman.py` routes a compose request to the Designer only once a piece is approved, and that the note shows ready models and hides models still being checked.

## 5. Studio

- [x] 5.1 Add API client calls and the `routes/Rooms.tsx` page: compositions with their items, approval state, status, still and viewer link, plus the model library with upload, delete, refusal reasons, and a refetch while any model is `checking`. Add the route and a nav link. Verify that `Rooms.test.tsx` covers the unapproved mark, an upload refused, and the `checking` → `ready` change without a reload.

## 6. Docs and verification

- [x] 6.1 Amend CLAUDE.md §8 with the headless importer sentence (design decision 5), and add the Rooms page and model library to the README. Verify that both read correctly.
- [x] 6.2 Browser check against the running backend: upload a GLB, see it become `ready`, compose `Wohnen` with an approved piece, a stand-in and the model in the chat, answer `yes`, see the build in the Rooms page, render a `draft` turntable, then unapprove the piece and see "no longer approved". Record the check in the commit message.
  - Browser pass 2026-10-07: headless Chrome via playwright-core, with the API and Vite on a scratch database. Real routed models through OpenRouter; the real Blender 5.2.1 ran the check, build and renders.
    - The armchair GLB was uploaded on the Rooms page and went from `checking` to `ready` without a reload.
    - The bench v1 was approved on the Pieces page.
    - "compose the Wohnen room…" first reached Intake. That found task 4.6, fixed; after the fix the Designer answered, its words showed above the card, and the summary listed the three items with sizes and placements.
    - On `yes`, Wohnen v1 was built in 2 s and listed on the Rooms page with its items.
    - The Builder rendered a `draft` turntable (12 frames, 600 × 600, Eevee; 64 s against an 11 s estimate from a seeded benchmark) and a `draft` still.
    - The frames showed the room as composed: the bench's doors facing in, and the walls between the camera and the room hidden.
    - The check also found two defects in the build report and colours, both fixed and re-checked: each item is now measured in its own frame (a turned model read its world bounds), and stand-in colours are converted from sRGB to linear (the sofa had rendered pale grey).
    - Unapproving the bench marked it "no longer approved" on the Rooms page.
- [x] 6.3 Run `uv run ruff check .`, `uv run pytest -m "not slow"`, the `--blender` slow tests from 1.5 and 3.3, and `pnpm lint && pnpm test && pnpm build`. Verify that all pass, and record the counts in the commit message.
  - 2026-10-07: ruff clean; `pytest -m "not slow"` 1584 passed, 29 skipped, 16 deselected; `pytest --blender -m blender -k "model_check or composition"` 7 passed; the room and shell Blender tests 13 passed; `pnpm lint` clean, `pnpm test` 69 passed, `pnpm build` ok.
