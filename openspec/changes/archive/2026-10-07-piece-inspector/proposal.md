## Why

A built piece can be reviewed today only as a picture: the iso screenshot and the turntable. Its measurements, layers, parts and module layout are written into every build (`spec.json`, the module empties, the straight-on cameras) but nothing shows them, so the owner cannot check a size or a part against what they told the Foreman without opening downloaded files. The predecessor's Studio had this inspection view and the Listening Wall generator drew dimension lines; the owner asked (2026-10-07) for those elements back: A1–A4 on the Blender side and B1–B7 in the Studio.

## What Changes

- **Dimension lines in the build (A1).** A custom build adds overall width, height and depth lines with their figures in mm (`DIM_*` objects under `MOD_Dimensions`, collection `09_Dimensions`), from `spec.json` `overall`. They are kept out of `model.glb`, the iso screenshot, stills, room renders and the detail pass.
- **Straight-on views (A2).** Each build also writes three Workbench screenshots from the existing `CAM_Front`, `CAM_Side` and `CAM_Top`: `front.png`, `side.png`, `top.png`, with the dimension lines showing. They are viewport screenshots, not renders, and need no tier. A build now publishes nine files instead of six.
- **Dimension lines in piece turntables (owner decision 2026-10-07).** A turntable of a piece at any tier shows the dimension lines, their figures turned to face the camera. A version built before this change has none and turns as before.
- **The Reviewer sees the views.** `revision_review` adds the three straight-on views to its evidence, so a measurement can be checked against the brief.
- **Piece inspector page (A3, A4, B1–B7).** A new Studio page per piece version shows its `model.glb` in 3D: orbit and zoom (B1), Iso / Front / Side / Plan buttons (B2), Workshop / Blueprint / Exploded modes with an explode slider driven by the module empties (B3, A4), layer switches from the version's own layer map plus `dimensions` (B4, A3), an overall W / H / D overlay in mm (B5), a floor grid and contact shadow (B6), and the straight-on views. A Cut list tab shows the parts and hardware tables from `spec.json` (B7). Ported from the predecessor's `Model.tsx`, `StudioCanvas.tsx`, `Dimensions.tsx` and `CutListPanel.tsx`; nothing Listening-Wall-specific is carried over.
- **Links to it.** Each version on the Pieces page and the conversation panel's bound piece link to the inspector.
- Not included (owner's choice): shop drawings (B8), assembly steps (B9), the renders list (B10) and the files tab (B11). The bundle download is unchanged.

## Capabilities

### New Capabilities
- None.

### Modified Capabilities
- `furniture-packages`: a build also publishes `front.png`, `side.png` and `top.png` and carries dimension objects in `model.blend`; the three views are served by exact name.
- `scene-rendering`: a piece turntable shows the dimension lines; stills, room renders and detail renders do not.
- `render-review`: the review's evidence includes the straight-on views when the version has them.
- `studio-ui`: the piece inspector page, and links to it from the Pieces page and the conversation panel.

## Impact

- **Ladder and agents.** Step 1 (headless generator and render scripts). A generator extension made through this change, not a spec-schema change: `spec.json` is unchanged. Agents: the Builder's build publishes more files; the Reviewer receives more images; the Foreman, Designer and Intake are untouched.
- **Render guard.** Unchanged. The straight-on views are Workbench viewport screenshots made by the build, like `screenshot.png`; turntables still run only on a guard ticket and keep their tiers. What a turntable frame shows changes (the dimension lines), not how it is authorised.
- **bpy allow-list.** Unaffected: only the checked-in headless generators change. The detail pass's live scripts are unchanged; its renders hide the dimension objects in the headless render script.
- **Backend:**
  - `generators/build_custom_build.py`, `_scene.py` and `render_turntable.py`;
  - `runner.py` and the render-server job, which pass `--dimensions` only for a piece's own turntable;
  - `storage.BUILD_FILES` and `verify.verify_build`, which go from six files to nine;
  - `agent/review.py`, with a higher image cap.
- **Frontend.** A new route `/pieces/:packageId/versions/:version`. New dependencies: `three`, `@react-three/fiber`, `@react-three/drei` and `@types/three`, loaded only on that page. Links are added on the Pieces page and in `Conversation.tsx`.
- **Existing data.** Versions built before this change have no views and no dimension objects. The inspector still shows their model, overlay and cut list, and they can be rebuilt by revising the piece.
- **Tests.**
  - The `--blender` suite gains dimension-object and view checks.
  - Build-file tests go from six names to nine.
  - The review evidence tests change.
  - The frontend gets tests for the inspector with the canvas stubbed (no WebGL in jsdom).
  - The inspector needs a browser check.
