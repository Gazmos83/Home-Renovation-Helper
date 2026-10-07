## 1. Dimension objects and straight-on views in the build

- [x] 1.1 In `build_custom_build.py`, add `09_Dimensions` / `MOD_Dimensions` with the three bars `DIM_OverallW/H/D`, the three labels `DIM_Label_W/H/D` (`<n> mm` from `overall`), and an `Ink` material (design decision 1). Check: a `--blender` test builds the fold-down-desk template; `model.blend` holds the six `DIM_*` objects with the template's figures, and `model.glb` holds no `DIM_` node.
- [x] 1.2 Add `_write_views` (with `_scene.face_camera` and `_scene.is_dimension`) and write `front.png`, `side.png` and `top.png` from `CAM_Front`, `CAM_Side` and `CAM_Top`. Each is a Workbench frame at 800 × 500 with the floor hidden, only the dimensions it faces shown, and labels facing the camera. This is not a render and has no tier. Check: the `--blender` test asserts the three PNGs, their size, and that `screenshot.png` stays free of dimensions (no ink-coloured pixels in the label area, or a hidden-state assertion before the iso shot).
- [x] 1.3 `storage.BUILD_FILES` gains the three views. Update `verify_build` and every test helper or fake launcher that writes the six build files. Check: `uv run pytest -m "not slow"`, where the build-file tests expect nine names, and `front.png` of a fresh version is served while `front.png` of a six-file version answers 404.

## 2. Dimension lines in piece turntables

- [x] 2.1 `render_turntable.py` takes `--dimensions`. With it, only the floor is hidden and the labels get `COPY_ROTATION` to `CAM_Turntable`. `_build_centre` leaves out `DIM_*`. Check: a `--blender` test renders a **draft** turntable (tier `draft`, 12 frames, 600 × 600, Eevee) of a fresh build with the flag and one without, and asserts the dimension objects' render visibility in each case. A blend with no `DIM_*` renders unchanged.
- [x] 2.2 `runner.run_render` passes `--dimensions` only for a piece's own turntable: not a still, not a room render, not detail, not a shell or composition. `offload/job.render_command` passes it through `RemoteInputs` for the same case. Check: runner and offload unit tests assert the argv for a piece `draft` turntable (flag present), a piece `draft` still, a detail `final` turntable, a shell `draft` turntable (flag absent in all three), and a remote piece `final` turntable (flag present).

## 3. Reviewer evidence

- [x] 3.1 In `agent/review.py`, raise `MAX_IMAGES` to 10 and add `front.png`, `side.png` and `top.png` after the screenshot with the labels from design decision 4. Check: `test_review*` asserts the order and labels for a version with the views and a 12-frame **draft** turntable, and that a version without views is unchanged.

## 4. Inspector page

- [x] 4.1 Add `three`, `@react-three/fiber`, `@react-three/drei` and `@types/three` with `pnpm add`. Commit `pnpm-lock.yaml`. Check: `pnpm build` passes, and the inspector chunk is separate from the main chunk in the build output.
- [x] 4.2 Add `lib/inspector.ts` with `customBuildExplode`, `layerOf` (using `sanitizeNodeName`) and `cameraPresets`, ported from the predecessor's `Model.tsx` and `StudioCanvas.tsx`. Check: Vitest unit tests cover:
  - offsets for two side-by-side modules, with `MOD_extras` absent;
  - a `#2` copy name found in its layer, and an unlisted mesh kept;
  - the Front preset looking along −Z at the piece's centre.
- [x] 4.3 Add `components/inspector/InspectorCanvas.tsx`, `PieceModel.tsx`, `DimensionOverlay.tsx` and `CutListTables.tsx`, ported from the predecessor's `StudioCanvas.tsx`, `Model.tsx`, `Dimensions.tsx` and `CutListPanel.tsx`, without Listening Wall constants, selection or attachments. Covers:
  - B1: orbit and zoom;
  - B2: the four camera presets;
  - B3: Workshop, Blueprint, and Exploded with its slider;
  - B4: the layer switches;
  - B5: the overlay;
  - B6: grid and contact shadow.

  Check: `pnpm lint`; component tests with the canvas stubbed.
- [x] 4.4 Add `routes/PieceInspector.tsx` at `/pieces/:packageId/versions/:version` in `App.tsx`. It has a Model tab (the lazy canvas, controls, the straight-on views when present) and a Cut list tab. A version that is not built shows its build state; a missing version or file shows a plain sentence. Check: Vitest tests:
  - a built version shows the overlay figures from `spec.json` and the layer switches from its `layers` plus `dimensions`;
  - switching a mode, camera or layer reaches the stubbed canvas's props;
  - the Cut list lists every `parts` and `hardware` row;
  - a version without `front.png` leaves the views out;
  - a building version shows no canvas.
- [x] 4.5 Add the "Inspect" link on the Pieces page for each built version, and in the conversation panel when `build_status` is `succeeded`. Check: `Pieces.test.tsx` and `Conversation.test.tsx` assert the link and its target, and that it is absent for a building version.
- [x] 4.6 Filter the Cut list by module (owner's request, 2026-10-07): "All" plus one choice per module, labelled from `module_names`, "Extra parts" for `extras` and otherwise the id. Show the chosen module's rows and pieces, and name each row's module by its label. Check: `PieceInspector.test.tsx` covers choosing a module (only its rows, its counts), "All" restoring every row, the labels, and no filter for a single-module version. Then a browser look at a copy of `murphy-bed` v2 on scratch servers.
  Done 2026-10-07. Vitest covers it (frontend 98 tests). The browser look used a copy of `docs/renders/murphy-bed` in a scratch render root with a scratch DB, backend on 8100 and Vite on 5180, with the owner's servers untouched:
  - the filter showed "All", the six modules by their `module_names` labels, and "Extra parts";
  - "Left lower cabinet" listed 4 rows / 7 pieces, "Bridge above bed" 3 / 5 and "Extra parts" 14 / 49, each matching `spec.json`;
  - "All" restored the 35 rows.

## 5. Verification

- [x] 5.1 Full suites. Check: in `backend/`, `uv run ruff check .`, `uv run pytest -m "not slow"` and `uv run pytest --blender -k "custom_build or turntable"`, never two pytest processes at once; in `frontend/`, `pnpm lint`, `pnpm test` and `pnpm build`.
- [x] 5.2 Browser check on a scratch database and render root, with the owner's servers on 8000 and 5173 untouched. Steps:
  1. Build a piece in a conversation and open "Inspect" from the panel.
  2. Check the Iso, Front, Side and Plan presets, Workshop and Blueprint, and Exploded with the slider.
  3. Switch `fronts` and `dimensions` off and on, read W / H / D against `spec.json`, and open the Cut list tab.
  4. Look at the three views.
  5. Ask for a **draft** turntable and confirm in its viewer that the dimension figures face the camera in every frame.
  6. Ask for a **draft** still and confirm it has no dimension lines.

  Record the steps and results under this task.

  Browser pass 2026-10-07, with real OpenRouter models. Scratch DB `home_renovation_check`, with the render benchmark copied read-only from `home_renovation`. Backend on 8100 and Vite on 5180, with the render and upload roots in the scratchpad. Headless Chrome through Playwright; the owner's 8000 and 5173 servers were not touched.
  1. Conversation "Hall shoe bench": brief recorded on Yes. The Designer asked to change two drawers to one, because the drawer fronts did not fit in 450 mm; I said yes, then Yes on `create_piece`. Version 1 was built with nine files. The panel showed "Inspect version 1", which opened `/pieces/hall-shoe-bench/versions/1`.
  2. Iso, Front, Side and Plan each moved the camera; Front looked straight at the drawer front and the open shelf. Blueprint drew cream parts with edges on the grid. Exploded hid the overlay; this piece has one module, so nothing moved (design decision 6).
  3. Switching `fronts` off hid only the drawer front, and `dimensions` off hid the overlay. Both came back on. The overlay read 1000 mm, 450 mm and 350 mm, matching `spec.json` `overall`. The Cut list tab showed 8 part rows and 3 hardware rows, the same as `cutlist.csv`.
  4. The three views loaded at 800 × 500: front (W, H), side (D, H) and top (W, D), with figures beside their lines.
  5. Asked for a draft turntable in words. `scene.json` recorded `"dimensions": true`. The viewer, opened from the reply's link, showed the lines, and each frame's figures faced the camera.
  6. Asked for a draft still; `still.png` shows no dimension line. In the same turn the Builder also started a second draft turntable that was not asked for. That is the agent's tool choice, not part of this change.

  No request left 127.0.0.1. The page had no errors; one 404 in the console came from the conversation page before the inspector opened.

