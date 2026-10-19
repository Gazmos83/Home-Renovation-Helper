## Context

See proposal.md and the two delta specs. Current state:

- A composition version's stored document (`compositions.read_document`) holds everything needed:
  - `resolved.rooms[*]`: `corners` and `height_mm`;
  - the placed items: `id`, `room`, `size_mm` (`w`, `d`, `h`), `centre_mm`, `rotation_deg`, `base_mm` for a hung or ceiling-layer item, and `hidden`.
- `compositions.room_dimensions(document)` is the one reader of wall lengths. It labels walls `wall <n>` from the room's corners. `read_room_version_dimensions` (`plugins/room_version_dimensions/tool.py`) wraps it, with the room taken from the thread.
- `room_contract._rotated_footprint` gives an item's four plan corners from its centre, size and rotation. `room_contract.Wall` gives the start, end, direction and outward normal of each wall. `composition_contract._wall_pose` builds a wall-placed footprint.
- The saved place of the bound piece (`packages/placements.read_placement`) holds `wall`, `left_mm`, `offset_mm` and `mount_height_mm`. `foreman.placement_note` turns it into one line that does not name the end walls.
- Corners run counter-clockwise. A wall's end corner is on the left of someone facing it from inside (`ask_placement.offset_from_left`). So wall `i`'s left end meets wall `i+1`, and its right end meets wall `i-1`.

## Goals / Non-Goals

**Goals:**
- Every gap figure the owner hears comes from one function over stored data.
- The same function serves the tool and the saved-place line.

**Non-Goals:**
- Apartment-scope compositions. They are refused in one sentence; their shared-wall labels need their own change.
- Gaps to openings (doors and windows), and LED strips as subjects.
- Changing placement, room fit or validation.
- Exposing gaps in the UI.

## Decisions

1. **Geometry: shortest distance between convex polygons and segments, in plan.**
   - The wall gap is the minimum over the footprint's four edges of the segment-to-segment distance to the wall, or 0 when they intersect.
   - The item gap is the minimum edge-to-edge distance between two footprints, or 0 when one contains a corner of the other.
   - When two footprints overlap in plan and their height ranges do not meet, the gap is the vertical clearance. Height ranges are `[base, base + h]`, with `base` 0 for a standing item.
   - Two helpers, `segment_distance` and `polygon_distance`, live in `room_contract.py` next to the existing polygon helpers. They are pure and dependency-free, so Blender code could reuse them.
   - *Alternative:* the distance along the wall (`left_mm`, and length − left − width). That is exact only when the neighbouring wall is square to this one. Wohnen's wall 3 is not.

2. **One entry point: `compositions.gaps_of(document, item)`.** It returns `{"item", "walls": [{label, gap_mm}], "items": [{id, name, gap_mm, vertical}], "ceiling_mm", "underside_mm"}`, or raises `GapRefused(reason)`.
   - Names are read from the version's `items` (piece `name` or `package_id`, model `name`) next to the resolved entries.
   - The saved-place line builds a one-item document from the room's corners and the stored placement with `_wall_pose`. It reads the gaps from the same function and uses only the two end walls.

3. **Tool in the existing plugin.** `measure_gaps` is added to `plugins/room_version_dimensions/` (manifest `tools`, same role and `also_for`). The scope handling copies `read_room_version_dimensions`: a confirmed room from the thread, any other room refused, an apartment refused.
   - Arguments: `version` (int ≥ 1), `item` (string, 1–120 characters), optional `room` (checked only).
   - The output is one plain block, every figure in mm, ending "Quote these figures; do not recompute them."
   - *Alternative:* a separate plugin. It would duplicate the scope code and the toggle for no gain.

4. **Placement note wording.** The note appends "left end {L} mm from wall {i+2}, right end {R} mm from wall {i}" (owner numbering, wrapping around). L and R come from `gaps_of`. When the room or the piece size cannot be read, the note keeps today's line unchanged rather than guessing.

5. **Instructions.** One sentence each in `designer.md` and `researcher.md`, plus `measure_gaps` in their `tools` headers: "For a distance between a piece or model and a wall, another item or the ceiling, call `measure_gaps` (or use the saved-place note) and quote its figure; never compute one yourself." The prompt guard is unchanged. `foreman.md` gains one routing line sending gap questions to the Designer. The first benchmark run (2026-10-19) showed the Foreman routing one to the Builder, which has no `measure_gaps` and computed wrong figures.

## Risks / Trade-offs

- **The model may still compute instead of calling** → the instruction plus the benchmark case that checks the tool call. A code-forced route is a later change if the benchmark shows the instruction is ignored.
- **Name matching** → an exact case-insensitive match on name, package id or item id only; ambiguity is refused with ids, never guessed.
- **Rounding** → round once at the end, half up to whole millimetres, matching `room_dimensions`.

## Migration Plan

None. Roll back by removing the tool from the manifest and the instruction headers, and reverting `placement_note`.
