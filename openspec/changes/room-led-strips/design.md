## Context

See proposal.md (Why). The state this builds on, after `room-lamp-lights`:

- `composition_contract` has `ITEM_TYPES = ("piece", "stand-in", "model")` and the per-type `_ITEM_FIELDS`. Every type has a width, depth and height, either stated or taken from the piece. `place_items` checks the outline, the wall end, the ceiling, openings (`_blocked_opening`) and footprint overlap, and returns rule subjects for standing items.
- `app/blender/lighting.py` provides `lumens_to_watts`, `kelvin_to_rgb` and the `config/lighting.yaml` values (`watts_per_lumen`, `rig_factor_with_lamps`, `max_lights`). The contract records `rig_factor` on each resolved room and enforces the light cap.
- `_composition.build_scene` dispatches on the item type to `_place_piece`, `_place_model` and `_place_stand_in`. Each returns meshes for the report and the "items" surface.

## Goals / Non-Goals

**Goals:**
- An LED strip described in shop terms (length, lm/m, K) and placed with the same wall and offset language as every other item.
- The strip's light and glow both render in Eevee drafts and Cycles finals.

**Non-Goals:**
- Attaching a strip to a placed item or a piece's part (under a shelf inside a cabinet). See the TODO(user) in the proposal.
- Strips that bend round a corner, or that run on the floor or the ceiling. One strip lies along one wall. A corner run is two strips.
- RGB or colour-changing strips, dimmers or diffuser profiles.
- Strips inside built pieces. That is a spec-JSON change in `furniture-packages`.

## Decisions

1. **A new item type, not a stand-in with a light.** A strip has no footprint worth checking, a height that is a mounting position rather than a size, and a length along the wall. Expressing it as a stand-in would mean a 10 mm-deep box that clashes with every cabinet against the same wall. A separate type keeps the stand-in rules intact. The type name is `led-strip`, hyphenated like `stand-in`.

2. **Size derived, not stated.** The resolved strip gets `size_mm = {width: length_mm, depth: 15, height: 10}` and `base_mm = mount_height_mm`, so the outline and wall-end checks run unchanged. The ceiling check becomes `mount_height_mm + 10 ≤ ceiling`.

3. **Overlap only with strips.** In `place_items`, a strip skips the footprint overlap loop against non-strip items. Against another strip on the same wall it is refused when both the along-wall intervals `[offset, offset + length]` and the height intervals `[h, h + 10]` overlap. Strips on different walls never clash, even at a corner.

4. **Openings by height.** For each opening on the strip's wall, the strip is refused when the along-wall intervals overlap and its height interval meets `[sill_mm, sill_mm + height_mm]` (a door's sill is 0). This reuses the ceiling layer's height-aware idea. It does not use `_blocked_opening`, because that function tests floor footprints in front of the opening, not the wall surface.

5. **No rule subjects.** Strips are left out of the subjects returned for `rule_outcome`, as floor-layer and ceiling-layer items are. `front_clearance_mm` and `door_swing_clear` describe floor space.

6. **Geometry and light in bpy.** `_place_led_strip` builds:
   - a box mesh `<id>` of length × 15 × 10 mm, with its back on the wall's inner face. Its material uses an Emission shader in the kelvin colour (strength 5) mixed over a white diffuse;
   - an `AREA` light `LGT_Strip_<id>`, shape `RECTANGLE`, size = length and size_y = 15 mm, placed at the strip's face, 2 mm off it. It is rotated so that −Z points down, up or along the wall's inward normal for `facing` `down`, `up` and `out`. Its energy is the resolved watts.

   The wall's direction and inward normal come from the resolved placement, which `place_items` already computes for wall-placed items (rotation and centre). The emission alone does not light the room in Eevee, which is why the area light is added. The bar does not shadow its own light (`visible_shadow = False`), as with lamps.

7. **Cap and dimming shared with lamps.** A strip counts as one light in `max_lights` and marks its room as lit for `rig_factor`, using the same counters `room-lamp-lights` adds.

## Risks / Trade-offs

- [A strip under wall cabinets is placed by height, not attached, so it is left behind when the kitchen piece moves] → The Designer instructions say to re-place strips when moving a piece on that wall. Attachment is TODO(user).
- [A strip "behind" a tall cabinet against the same wall is accepted but invisible in the render] → The confirmation summary lists the strip with its wall and height. The owner sees the screenshot before any render.
- [Size-dependent code elsewhere (summary, dimensions route, Rooms page) expects width, depth and height] → The resolved derived size covers it. Task 3.2 checks these paths.
- [Eevee's soft area light looks weaker than Cycles' for very long thin strips] → The same watts are used in both engines. The first `draft` and an optional `final` are compared in the browser pass.

## Migration Plan

None. Rollback is reverting the change, after which documents holding `led-strip` items are refused (unknown type).
