## Context

- **What a build already writes.** `build_custom_build.py` already builds the three straight-on cameras (`CAM_Front`, `CAM_Side`, `CAM_Top`, orthographic, framed on the piece). It also builds one `MOD_<id>` empty per module (plus `MOD_extras`), parented under `CustomBuild`, and writes `spec.json` with `overall`, `modules` (a dict keyed by module id with `x y z w h d`), `layers`, `parts` and `hardware`. Checked on `murphy-bed` v1: the GLB carries the `MOD_*` empties as nodes.
- **What is used.** Only `CAM_Iso` is used, for the Workbench `screenshot.png` and as the turntable's starting point.
- **Hiding helpers.** `_scene.hidden_for_presentation()` already hides `StudioFloor`, `DIM_*` and `MOD_Dimensions*`. The predecessor's Listening Wall generator made those names, and the custom build never did. The iso screenshot, the turntable, the still and `export_glb` all go through that helper.
- **Build verification.** `storage.BUILD_FILES` is the exact set the runner moves and `verify_build` checks. It has six names, and `SERVED_FILES` includes it.
- **Who runs `render_turntable.py`.** It turns a piece's `model.blend`, a shell's `model.blend` and a detail pass's `detail.blend`. On the render server the input is always copied as `input.blend` (`offload/job.render_command`), so the script cannot tell a piece from a detail copy by file name.
- **Review.** `agent/review.py` caps evidence at `MAX_IMAGES = 6`.
- **Frontend.** It has no 3D dependency and no global store; pages hold their state with `useState` and TanStack Query. The predecessor's Studio used `three`, `@react-three/fiber`, `@react-three/drei` and `zustand`.

## Goals / Non-Goals

**Goals:**
- Dimension lines with figures in `model.blend`, in three straight-on Workbench views, and in every piece turntable.
- One inspector page per piece version: 3D model, camera presets, modes, explode, layers, overlay, grid and shadow, the views, and a Cut list tab. Everything is read from that version's own files.
- Give the Reviewer the views for measurement checks.

**Non-Goals:**
- Shop drawings, assembly, the renders list and the files tab (B8–B11).
- Part selection or highlighting in the 3D view.
- The inspector for shells or compositions.
- Rebuilding old versions to add views. A rebuild happens only through a new version.
- Changing `spec.json` or the spec schema.
- Changing the bundle download.
- Dimension lines in stills, room renders, detail renders, shells or compositions.

## Decisions

1. **The dimension objects follow the predecessor's names.**
   - **What gets built:**
     - `09_Dimensions` holds the empty `MOD_Dimensions`, parented to `CustomBuild`.
     - It holds three bars, `DIM_OverallW`, `DIM_OverallH` and `DIM_OverallD`, each with two end ticks (`DIM_Overall<axis>_tick1/2`). A bar's section is 0.4 % of the largest overall size, at least 6 mm, and it sits 100 mm out from the piece, drawn in a dark `Ink` material.
     - Placement: width along the front's foot, height up the front-left corner, and depth under the left side, below the piece's base. The extra parts are laid flat to the right of the piece, so the depth line is not put there.
     - It also holds three text objects, `DIM_Label_W`, `DIM_Label_H` and `DIM_Label_D` (Blender FONT curves), reading `<n> mm`. Each sits beside its bar and is offset in both of the views that show it, so the figure never overlaps its line. Their size is 4 % of the largest overall dimension, at least 40 mm.
     - Each dimension object carries a `dimension` property (`W`, `H` or `D`).
     - The material sets both the Principled base colour and `diffuse_color`, so Workbench and Eevee/Cycles agree.
   - **Why the old names:** the existing helper already hides them, so `model.glb`, `screenshot.png` and stills stay clean with no new code. The FONT objects are not meshes, so the export's layer-map check is unaffected.
   - **Alternatives considered:**
     - Annotations or grease pencil: they don't render in Eevee or Cycles turntables.
     - Measuring each module: more lines than a turntable frame can read. Per-module figures are in the inspector's cut list.

2. **Three views are written by the build.**
   - `_write_views` in the generator renders a Workbench frame at the same 800 × 500 size as `screenshot.png`, through each camera. It hides `StudioFloor` and the dimension objects that view does not face:
     - front shows W and H;
     - side shows D and H;
     - top shows W and D.
   - Labels get a `COPY_ROTATION` constraint to the active camera (`_scene.face_camera`), so each figure faces the view.
   - The world colour is set to the light studio colour while the views render. Workbench draws its background from it, and the default dark grey hid the dark lines. The iso screenshot keeps its own background.
   - Each orthographic camera is framed on its two sides of the piece plus the lines and figures, at the views' 800 × 500 aspect. These cameras were unused before, and their old scale clipped tall pieces.
   - `BUILD_FILES` gains `front.png`, `side.png` and `top.png`, so the runner publishes nine files at once and `verify_build` checks nine.
   - The names are flat, not `views/…`, because the closed served set and `_move_build_files` work on top-level names.
   - **Rejected alternative:** making the views a render on request. They are progress views like the screenshot, so CLAUDE.md's "viewport screenshots, not renders" applies and no guard ticket is needed.

3. **The turntable shows dimensions only on `--dimensions`.**
   - `render_turntable.py` takes a `--dimensions` flag. With it, the script hides only `StudioFloor` and gives the labels a `COPY_ROTATION` constraint to `CAM_Turntable`, so each figure faces the camera in every frame. Without it, the script hides presentation helpers as now.
   - **Where the flag is passed:**
     - `runner.run_render` passes it only for `record == "piece"`, `source != "detail"`, `kind == "turntable"` and not `room`.
     - `offload/job.render_command` gets the same flag through `RemoteInputs`, so a remote `final` of a piece looks like a local one.
   - `_build_centre()` leaves out the `DIM_*` objects as well as the floor, so the orbit is unchanged.
   - **Why a flag rather than the file name:** the server renames every input to `input.blend`.
   - **Old versions:** a blend without `DIM_*` objects renders exactly as before.
   - **Guard:** the guard does not change. The flag is not a tier value and no raw frame or resolution value is added.

4. **The review shows more images.**
   - `MAX_IMAGES` goes from 6 to 10: screenshot, three views, four frames and two room images.
   - The views come right after the screenshot, labelled `front view (width and height)`, `side view (depth and height)` and `top view (width and depth)`.
   - The existing rule that a measurement claim quotes the spec's number stays as it is. The views let the Reviewer see proportions, not read figures as truth.

5. **The inspector page lives on its own route.**
   - `/pieces/:packageId/versions/:version` uses `routes/PieceInspector.tsx`. It reads `api.version()`, then `spec.json` through the existing file route, and passes `model.glb`'s file route to the canvas.
   - **Why under `/pieces/`:** Vite proxies `/packages` to the API, but `/pieces` is a SPA route, so the page path never collides with an API path.
   - The 3D part is `components/inspector/InspectorCanvas.tsx`, loaded with `React.lazy`. Vitest stubs it (no WebGL in jsdom), and the other pages' bundle does not grow.

6. **The predecessor's code is ported, trimmed to custom builds.**
   - **Pure functions** go to `lib/inspector.ts`, where Vitest can test them:
     - `customBuildExplode(spec)`, the predecessor's function, which handles a `modules` dict and ignores `MOD_extras`;
     - `layerOf(name, layers)`: hidden names, then the layer map, otherwise `keep`;
     - `cameraPresets(overall)`: Iso, Front, Side and Plan framed from the overall size, where the predecessor's were fixed for the Listening Wall. Axes map from Blender to the Y-up glTF as (x, z, −y), so Front looks from +Z.
   - **Components:**
     - `PieceModel`: the predecessor's `CabinetModel`, with Workshop and Blueprint materials, edge lines, explode by moving `MOD_*` nodes, and layer visibility;
     - `DimensionOverlay`;
     - `CutListTables`.
   - **Dropped:** the Listening Wall's `EXPLODE` constants, part selection, attachments and the "uploaded label".
   - **Module filter (added 2026-10-07, owner's request):** the predecessor's `CutListPanel` filtered parts by module. It is restored, with labels taken from the version's own `module_names` rather than the predecessor's compiled `MODULE_LABELS` table, so a module is named as its design names it.
   - **State:** view state (mode, camera, explode, layers) is `useState` in the page, passed down as props. No `zustand`, because the project has no global store pattern.
   - `useGLTF(url, false)` keeps draco off, so no decoder is fetched from a CDN.
   - The overlay's figures are page text (drei's `Html`), not drei's `Text`: `Text` loads its font from a public CDN. The browser check recorded no external request.
   - A version with one module has no explode direction, so Exploded leaves it in place, as the predecessor did.

7. **The links are built in the frontend, with no backend change.**
   - The Pieces page shows "Inspect" when a version's `status` is `succeeded`.
   - The conversation panel shows it when `progress.build_status` is `succeeded`, using the package id and latest version it already has.
   - Both are `<Link>`s inside the Studio, not new tabs.

## Risks / Trade-offs

- **Bundle size.** `three` and `drei` add a few hundred kB. Mitigation: they load only on the inspector route, through the lazy import.
- **Name mismatch.** three.js's GLTFLoader cleans up node names, so a name the layer map lists may differ from the loaded node's. Mitigation: `layerOf` compares through the loader's own `PropertyBinding.sanitizeNodeName`, plus a unit test with an `#2` copy name.
- **Image token cost.** More review images cost more tokens, and a review could hit the Reviewer's context budget. The budget node refuses it with a stated reason, and the limit is set from `/admin`. Accepted.
- **Cluttered frames.** Dimension lines in every piece turntable, including `final`, appear in renders that might be shown to others. The owner chose this (2026-10-07). The detail pass's `final` renders stay clean, so a presentation image remains possible.
- **Text in Eevee and Cycles.** FONT curves render in both, but the labels' readability at 600 × 600 is unproven. The `--blender` suite and the browser check look at a draft frame.
- **Old versions.** They show no views and no dimension lines until a new version is built; the inspector says so by leaving the views out.

## Migration Plan

No data migration is needed. Versions built from now on get the views and dimension objects, and older folders stay valid. The build tests and the fake build launchers that write six files are updated to nine.

## Open Questions

None.
