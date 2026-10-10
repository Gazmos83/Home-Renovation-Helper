## Context

See proposal.md for the motivation. Today a divider is a count plus optional left-face positions (`bays()` in `custom_build/derive.py`); every divider runs from the bottom panel to the top panel, every shelf level is split into the same bays, and `_check_folds` refuses dividers on a folded module. Folded modules derive in their own path (`_folded_module_rows`, `_folded_module_pieces`) from `fold_profile`, which already gives inner left/right x at any (y, z) and the smallest inner width over a board's range.

## Goals / Non-Goals

**Goals:**
- One shared model of "which boards cross which heights" used by validation, the cut list, drilling, the guideline and the generator.
- Documents with full-height dividers on unfolded modules, and folded modules without dividers, keep row ids, quantities and drawn objects byte-for-byte.

**Non-Goals:**
- Dividers anchored on adjustable shelves, dividers that do not run the full back-reduced depth, or angled dividers that follow a fold. These stay unexpressible.
- Per-bay shelf counts or heights (shelves stay at one set of heights for the module).
- Horizontal partial shelves (a shelf in one bay only).

## Decisions

1. **`divider_spans` names boards, not millimetres.** `{from_board: "bottom" | n, to_board: "top" | n}` with n a shelf number counting every shelf (fixed and adjustable) from the lowest, so "the top shelf" is always the highest number whatever its kind. The owner's words ("from the top shelf to the top") name boards, and boards keep the divider attached when shelf heights change through `shelf_spacing_mm`. Millimetre ranges were rejected: they would let a divider end in mid-air and would need re-validation on every spacing change. Field names avoid `from`, a Python keyword. Only fixed shelves anchor: an adjustable shelf has no fixed height to screw into.

2. **A derived divider list is the single source.** A new `dividers_of(module, t, profile | None)` returns, per divider left to right, its left-face x in the module frame, its bottom z and top z. Bottom z is the top face of its `from_board` (t for the bottom panel); top z is the underside of its `to_board` (height − t for the top panel). Length = floor(top − bottom). `bays()` and `bay_cut_widths()` keep their current results for full-height dividers on an unfolded module, so the old path and its row naming stay untouched; the new path is used when spans are set or the module is folded.

3. **Shelf segments per level.** For each shelf centre, the dividers whose `bottom < centre < top` split the board; the segment edges are the inner side faces and the crossing dividers' faces. On a folded module, an edge on a folded side is that side's inner x at the narrowest point along the board's thickness and the full depth (the same sampling as `min_inner_width`), so a segment next to a fold is cut like a fixed shelf on a fold today. Segment cut width is floored; adjustable segments subtract the clearance, then floor.

4. **Row grouping in the new path.** Boards of one kind grouped by cut width, numbered by first appearance (lowest level, then left to right), with notes naming levels and bays. Chosen over one row per board (too many qty-1 rows for the shop) and over width-in-the-id (unstable when sizes change). The old `-bay-<n>` naming stays for full-height dividers on unfolded modules, so existing packages and part overrides keep their ids.

5. **Equal bays on a fold use the narrowest opening.** Without positions on a folded module, find the (y, z) along the union of the dividers' spans and the full depth where the inner width is smallest, and split that opening's inner-left to inner-right range into equal bays, as today's formula does for the unbent width. That is the only place every bay is guaranteed to exist; splitting the unbent width put the owner's own example inside the folded side. The computed left faces are then validated like stated positions. On the 26° cabinet this gives a left face 588 mm from the unbent inner face (606 mm in the module frame) and 158 mm bays at the top.

6. **Fold fit is checked by sampling.** For each divider, sample the inner left and right x at its bottom and top z, at the fold's `from_mm` when that lies inside the span (height folds), and at y = 0, the fold's `from_mm` and the back-reduced depth (depth folds). Refuse when `left_face < inner_left` or `left_face + t > inner_right` at any sample, or a bay is 0 mm or less. Insets are linear past the kink, so the extremes are at these samples.

7. **Drilling.** Shelf-pin holes are one continuous row per board (data sheet first hole, last hole, pitch), not one set per shelf. Divider entries move from one per module to one per divider row (one row today, so the entry is unchanged for full-height dividers). The row is computed over the divider's own length from its bottom z, exactly as the sides use their length; for a full-height divider that gives today's `heights − t`. The hole count multiplies by the dividers in that row. A divider whose span holds no adjustable shelf gets no entry. Fixing a shelf changes only the pin count, not the side boards' hole row.

8. **`shelf_kinds` replaces the "fixed lowest" slicing.** A helper `shelf_levels(module, t)` returns each shelf's centre and kind, lowest first: `shelf_kinds` when stated, else `fixed` for the first `shelves` and `adjustable` for the rest. Every place that slices `shelf_centres(...)[: shelves]` / `[shelves :]` (derive rows, folded widths, both generator paths) uses it instead. Heights do not depend on kinds, so fixing a shelf never moves it. A stored per-shelf list was chosen over "fix from the bottom up", which would have fixed every shelf below the one the owner named.

9. **Questions come from tool answers, not prompts alone.** Two code paths return a question instead of a confirmation, so the Designer cannot skip them:
    - *Adjustable anchor*: schema validation refuses a span on an adjustable shelf. `revise_package` / `create_piece` turn that refusal into an answer naming the shelf and the hardware effect, computed by deriving the module with that shelf fixed: confirmat +4, pins per shelf fewer, or "pins: no quantity" when the pin data sheet lacks the value.
    - *Missing position*: a helper `divider_recommendation(module, materials, rules)` compares the latest and revised documents. A new divider without `divider_positions_mm` gets the centred left faces (decision 5 on a fold), the compartment widths at each split shelf, and the `shelf_span_mm_for_thickness` rule's limit and source, or "no shelf-span limit configured".

    `import_design` does not use either path; its documents keep the equal-bay default. The Designer instructions tell it to relay both answers as questions and to call `search_guidelines` for passages to cite. The Foreman relays specialist questions as today and needs no change.

10. **Preview diff.** `preview` derives the cut list and hardware of the latest version and of the revised document (`custom_derive.base_parts` and the hardware list, without hardware inputs) and lists changed hardware quantities and added, removed or resized rows after the change lines. Derivation is pure and fast, so this costs no build.

11. **Generator.** `_module_boxes` (unfolded) and `_folded_module_pieces` (folded) both take divider boxes and shelf segments from the shared derivation, so drawn objects and cut-list rows cannot disagree. The new path is only reached when spans are set or the module is folded.

## Risks / Trade-offs

- [The Designer proposes a position without asking] → The tool refuses a new unpositioned divider, so no version can be proposed without a stated position.
- [No shelf-span limit exists today] → The recommendation says so; a TODO(user) task asks the owner for a cited limit.

- [Row ids shift for a folded module with shelves when a divider is added] → Expected: adding a divider is a new version; revisions already rename rows. Part overrides naming a removed id are reported as before.
- [Two open changes underneath (`carcass-side-folds`, `folded-fronts-and-shelves`)] → This change's furniture-packages, design-guidelines, design-agents and design-import deltas MODIFY requirements those changes add or change. Archive them first, then this one.
- [Equal-bay placement on a fold moves the divider when a span changes] → It is restated in the change list; the owner can pin it with `divider_positions_mm`.
- [Narrowest-opening sampling misses a non-linear profile] → Profiles are piecewise linear with at most one kink per side; the samples cover every vertex.

## Migration Plan

No migration. Stored documents without `divider_spans` validate and derive as before; a stored folded document with dividers cannot exist (it was refused). Rollback is reverting the change; documents that used `divider_spans` would then be refused by name, as any unknown field.
