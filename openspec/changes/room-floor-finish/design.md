## Context

See proposal.md (Why). The current state the approach builds on:

- `parse_composition` requires exactly `kind`, `schema_version`, `units`, `scope`, `items` (`_TOP_REQUIRED`) with no optional top-level key, so `floor` is refused by name today and recorded as a generator-extension request by `compose_room`.
- `compose_room` passes `room`, `apartment` and `items` to `compositions.propose`, which builds the document itself. A new top-level field has to be a tool argument.
- The room floor is `_prism(state, "Floor", corners, -20, 0, …, "Floor")` in `build_room_scene._build_floor_ceiling`, one concave n-gon per room built from the outline. An apartment floor is `Floor_<room>` in `build_shell`. Both use a material named `Floor` from their module's material table.
- `export_glb` exports through the glTF exporter. A Principled BSDF whose Base Color is driven by a procedural texture node does not export as a colour, so the GLB would show white or the node default.
- The surface map labels `Floor` (room) and `Floor_<room>` (apartment) as floor surfaces. `render_restyle.apply_room` gives every floor surface `Restyle_floor`.
- Shader nodes must be looked up by type (CLAUDE.md §2), and the material code must run in Blender 5.2.

## Goals / Non-Goals

**Goals:**
- One field tiles the whole floor of any outline shape, with real joints visible in renders.
- The finish is versioned and approved with the room.

**Non-Goals:**
- Image textures, photo-scanned materials or wood grain. TODO(user): a later change could add an uploaded texture like the model library's files.
- Herringbone, chevron, diagonal or mixed-size patterns.
- A per-room finish inside an apartment composition. The single finish covers all the apartment's floors. TODO(user): a `rooms` list on the finish could narrow it later.
- Rotating the tile grid. The width runs along plan x and the length along plan y. Swapping the two values turns planks by 90°.
- Wall tiles (splashbacks, bathroom walls).
- Real tile thickness or bevelled edges in the geometry.

## Decisions

1. **Top-level `floor`, not an item and not a house-file room field.**
   - An item would need a placement and a footprint, and the floor-layer limits (one rectangle, inside the outline, no overlaps) are exactly what failed for the L-shaped case.
   - A house-file room field would not be versioned and would change every composition of the room at once.
   - On the composition document it is part of the confirmed, approved room version.
   - `_require_keys(document, _TOP_REQUIRED, frozenset({"floor"}), "composition")`, and `_parse_floor` normalises it with `pattern` filled in. The stored document keeps it top-level. `resolved` does not repeat it.

2. **Procedural material from the Brick Texture node.**
   - `ShaderNodeTexBrick` gives a joint (mortar) between bricks of a set width and row height, with a row offset: offset 0 for the grid, 0.5 with frequency 2 for staggered.
   - It is driven by Texture Coordinate → Object, with a Scale of 1, so its units are metres in the floor object's space. The floor prisms are built in plan coordinates with the object at the origin, so the joint lines are on multiples of the tile size from the plan origin.
   - Mortar size = grout width / 1000. Brick width = tile width + grout. Row height = tile length + grout, so a tile's visible face is its stated size.
   - Colour1 = Colour2 = tile colour (no brick variation), and Mortar = grout colour.
   - Roughness is 0.35 for tiles. TODO(user): a matt/gloss option could follow.
   - With `grout_width_mm: 0` the mortar size is 0, which shows a plain floor in the tile colour. For planks that is accepted as the look, and with no grout there is nothing to draw between them.
   - Nodes are created and linked by type, never looked up by localised name.
   - Rejected alternative: real tile geometry, cut at the outline. It adds thousands of faces to a 30 m² room, slows the CPU-only draft, and needs polygon clipping in bpy.

3. **A flat colour in the GLB and the screenshot.** In `build_composition.build`, before `export_glb`, the floor meshes get a plain Principled material of the tile colour (`material.diffuse_color` set as well, for Workbench). After export the tile material goes back on, and only then is `model.blend` saved, so the detail pass and renders see the tiles. Rendering stays out of the build. The screenshot is taken while the flat material is on, which keeps the Workbench look honest. Rejected alternative: baking a texture image during the build, which renders inside the build process and writes a file the verify step does not expect.

4. **The finish applies in `build_scene`, after `_build_shells`.** `_apply_floor_finish(scene)` finds the floor meshes from `surfaces(scene)` (labels `floor` or `<room>: floor`), so the room and apartment paths share one lookup. `render_composition.py` and `render_restyle.py` call `build_scene`, so stills and turntables get the tiles with no change to the render scripts. The report gains `floor: {…finish…}`.

5. **Restyle leaves a finished floor alone.** In `apply_room`, the floor kind is skipped when `scene.document.get("floor")`. This is the recommended reading of "appearance only" (the owner asked for the tiles explicitly). It is marked TODO(user) in the proposal. Reversing it later changes only that branch and the restyle scenario.

6. **Designer surface.** `ComposeRoomArgs` gains `floor: dict | None` with a description of the fields and an example ("600 × 600 mm light grey tiles with 3 mm grout → …"). `designer.md` gets one paragraph. The composition note adds a "floor: 600 × 600 mm grid, tile #e8e4dc, grout 3 mm #9a958c" line per composition. `_changes` emits "floor: <summary>" when added or changed and "floor finish removed" when dropped. Restating a composition without `floor` removes the finish, which the change line makes visible in the confirmation.

## Risks / Trade-offs

- [Eevee draft at 800 px shows moiré on 3 mm joints far from the camera] → Accepted for a draft. The `final` Cycles render resolves them. The browser pass looks at a draft frame.
- [The Brick node's row offset applies to every other row only (frequency 2), not a random stagger] → Matches a running-bond plank floor, which is what "staggered" promises.
- [The plan origin can be outside the room, so a tile is cut at a wall] → Real floors are cut at walls too. Centring the grid is a non-goal (TODO(user) if wanted).
- [The Designer forgets to restate the finish when moving furniture, removing it] → The confirmation's change list says "floor finish removed" before yes. The composition note shows the current finish so the Designer can copy it.
- [Material swap around export leaves the wrong material on save if export raises] → The swap back is in a `finally` block, and `model.blend` is saved after it.

## Migration Plan

None. Stored documents have no `floor`. Rollback: revert the change. Documents with `floor` are then refused by name as a generator-extension request.
