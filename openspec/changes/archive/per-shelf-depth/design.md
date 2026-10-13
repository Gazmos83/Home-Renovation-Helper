## Context

Shelf boards today all share one depth: `inner_d = module["depth"] - back_thickness`. That value is used in `derive.py` for cut-list `w` (depth of the board) and in `build_custom_build.py` for every shelf box's size and y-centre (`y + inner_d / 2`). `ShelfBoard` already carries per-board width and level/kind/bay; it has no depth or y0. `module_bounds` / `overall` use the carcass AABB only, so a protruding shelf would not grow overall depth today.

Per-shelf lists already exist (`shelf_positions_mm`, `shelf_kinds`) with the same lowest-first indexing. Revisions clear list fields with `[]` via `revise.py`; `measurements.py` treats list membership for `LIST_FIELDS`.

See proposal.md for motivation and the owner's align choice (both front-flush and back-flush).

## Goals / Non-Goals

**Goals:**
- One place that resolves each shelf's cut depth and y-span from `shelf_depths_mm` + `shelf_depth_align`, used by cut list, generator, overall/overlap and the pin-coverage check.
- Documents without the new fields keep identical rows, ids and boxes.
- The model states the owner's depths; code places the boards.

**Non-Goals:**
- Per-shelf align (one align for the whole module is enough for v1).
- Moving pin columns with the shelf; pins stay on the sides at carcass setbacks.
- Changing divider, side, top or bottom depth.
- Auto-deepening the module when one shelf is deeper (the owner asked for one shelf; the carcass stays).
- Drawing a cantilever support or bracket for a protruding shelf.
- Frontend inspector changes.

## Decisions

1. **Extend `ShelfBoard` with `depth` and `y0`.** Cut depth (int mm) and the board's front face in the module frame (float). Helpers `shelf_depth_of(module, level, inner_d)` and `shelf_y0(align, inner_d, depth)` keep placement in one place. `shelf_rows` groups by `(board_cut_width, depth)` instead of width alone.
   - *Alternative:* keep depth only in the generator. Rejected: cut list and overall would drift.

2. **Align semantics in the module frame.** Carcass interior depth runs from `y = 0` (side fronts) to `y = inner_d` (inner rear, before the back panel). Back-flush: `y0 = inner_d - depth` (may be negative when protruding). Front-flush: `y0 = 0` (rear at `depth`, may exceed `inner_d`). Absolute world y is `module["y"] + y0`.

3. **`null` in the list means default.** Unlike `shelf_positions_mm` (every entry required), depths allow `null` so "only the second shelf is 500" is one list. Schema: `list[Millimetres | None]` with length = shelf count. Minimum stated depth 50 mm (separate from `Millimetres` which is `gt=0`).

4. **`shelf_depth_align` only with depths.** Validator refuses align alone. Serialize omits both when unset; omit align when depths are set and align is the default `"back"` (or always emit align when depths are set — prefer always emit when depths are set so the document is explicit). On revise, `shelf_depths_mm: []` clears depths and align; setting depths without align stores `"back"`.

5. **Bounds and envelope.** `module_bounds` expands `y0`/`d` to include every shelf board's `[y0, y0+depth]` unioned with the carcass. Envelope fit reuses the existing wall-shelf style check against each placed shelf box. Overlap uses the same expanded boxes.

6. **Pin coverage is a schema/derive check when inputs are available.** Exact front setback `F` and rear setback `R` from the sheet: a back-flush board covers both iff `inner_d - depth <= F` and `depth >= R`; front-flush iff `depth >= F` is automatic for front and `depth >= inner_d - R`. Implement as one helper `shelf_covers_pin_columns(y0, depth, inner_d, F, R)`. When setbacks are missing or ranged, skip. Wire the check where hardware inputs are already loaded for create/revise (same path as other drilling-aware refusals), or in derive when inputs are passed; if create_piece validates without sheets, the refusal runs on the first cut_list/build that has inputs — prefer validating in `revise_package`/`create_piece` when `hardware_inputs` are present, and always in derive when `inputs` is non-empty, so a bad import is caught before Blender.

7. **Folded modules.** Stated depth must be `<=` the smallest inner depth along that shelf's thickness samples (same sampling spirit as `min_inner_width`). Placement still uses the unbent `inner_d` for y0 math; the cut depth is the stated value. A depth that exceeds the available inner depth at that height is refused.

8. **Designer surfacing.** Punchy `designer.md` paragraph + Field descriptions on `ModuleChange`, plus a short constant note on every Designer turn (same pattern as `DESIGNER_SIDE_FOLDS_NOTE`) so the model does not claim "no field" again. Piece summary lists depths with `null` shown as the default depth figure or as "default".

9. **Measurement check.** Add `shelf_depths_mm` to `LIST_FIELDS` / `OPTIONAL_FIELDS`. Membership matches a non-null entry equal to the requested millimetres.

## Risks / Trade-offs

- [Protruding shelf collides with an overlay door] → Accepted for v1; the owner sees it in the screenshot. A later change can refuse overlap between a protruding board and a front that covers its height.
- [Cantilevered shelf has no extra support in the model] → Spec states boards only; workshop notes can mention support later.
- [Pin-coverage refusal needs data sheets] → Without exact setbacks the check is skipped; a very shallow adjustable shelf could still validate until sheets exist — document that in the drilling spec scenarios.
- [Grouping by width and depth renames rows when depths differ] → Same pattern as mixed bay widths; part overrides naming the old single row are refused with the existing "rows that exist" message.
- [`--blender` suite] → One fixture with mixed depths is enough.

## Migration Plan

No database migration: fields live in stored spec JSON. Documents without them are unchanged. Rollback is a revert; a stored document with the new fields would then be refused by name (generator-extension behaviour).

## Open Questions

None. Align (module-level front/back) and fixed+adjustable indexing were decided with the owner.
