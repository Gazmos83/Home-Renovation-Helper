## 0. Order and owner input

- [x] 0.1 Archive `carcass-side-folds` and `folded-fronts-and-shelves` (after the owner test 5.2 there) before archiving this change, because this change's deltas modify their requirements. Verify `openspec validate partial-and-folded-dividers` passes.

  2026-10-10: both archived. One validate error remains by design: the main furniture-packages spec still has "Dividers refused on a folded module", which this change reverses. Remove that scenario from `openspec/specs/furniture-packages/spec.md` just before archiving this change (after owner test 5.2), as was done for the two refusals dropped by `folded-fronts-and-shelves`.

- [x] 0.2 TODO(user): give a cited shelf-span limit per board thickness (e.g. "18 mm chipboard: at most N mm"), as a guideline note at `/guidelines` citing its source. Then add a `shelf_span_mm_for_thickness` rule to `backend/config/design_rules.yaml` quoting that note (`owner:<note id>`), severity `warn` unless the owner says `refuse`. Verify the backend starts and the design-agents scenario "Position asked with a limit configured" passes with the real rule. Not blocking: every other task works without it.

  Skipped 2026-10-10 by the owner: the guidelines are being rebuilt (in development). No shelf-span rule is configured, so the position question gives the recommendation without a limit.

## 1. Schema

- [x] 1.1 Add `DividerSpanIn` (`from_board`: `"bottom"` or int ≥ 1; `to_board`: `"top"` or int ≥ 1; strict, extra forbidden) and optional `divider_spans` on `ModuleIn` (omitted when empty) and `ModuleChange` (`[]` clears). Check in `_check_interior`: count equals `dividers`, not without dividers, shelf numbers ≤ every shelf, `from_board` below `to_board`, a named shelf must be fixed. Verify with schema tests: the `cabinet` span from shelf 4 to the top is accepted; "Span on a missing shelf", "Span on an adjustable shelf", a count mismatch, spans without dividers and `from_board` 3 / `to_board` 2 are each refused naming `modules[0].divider_spans`; `divider_material` is still refused by name.

- [x] 1.2 Add optional `shelf_kinds` on `ModuleIn` (omitted when empty) and `ModuleChange` (`[]` clears); refuse when its length or kind counts disagree with `shelves` and `adjustable_shelves`. Verify "Kinds disagree with the counts" and that a document without the field serialises as before.

- [x] 1.3 Drop the dividers refusal in `_check_folds`; add the fold-fit check (design decision 6) refusing `divider_positions_mm` (or `dividers` when unpositioned) naming the folded side. Verify "Divider cuts into a folded side" is refused and "Divider on a folded module" is accepted.

## 2. Derivation

- [x] 2.1 Add `shelf_levels` (decision 8) and replace every `shelf_centres(...)[: shelves]` / `[shelves :]` slice in `derive.py` and the generator with it. Verify "Top shelf fixed, the rest adjustable" (cut list and hardware) and "No kinds, unchanged" over every shipped template and fixture.

- [x] 2.2 Add `dividers_of` (left-face x, bottom z, top z per divider; equal bays on the narrowest folded opening, decision 5) and per-level shelf segments (decision 3). Keep `bays()` / `bay_cut_widths()` results for full-height unfolded dividers. Verify unit tests: 383 mm length for shelf 4 to the top on the starter; 588 mm left face and 158 mm bays on the folded cabinet; the 1000 × 1200 mm module splits only shelf 1.

- [x] 2.3 Cut-list rows: new path for spans or folds with dividers (grouped by width, `-<n>` numbering, notes naming levels and bays; divider rows by length); confirmat 8 + 4 per fold joint + 4 per fixed shelf board + 4 per divider; shelf pins per adjustable board; assembly step names the span. Update the docstring rule table. Verify the furniture-packages scenarios "Divider from the top shelf to the top", "Divider crosses only the shelf below it", "Divider on a folded module", and that "Two dividers, equal bays", "Positioned divider, unequal bays" and every shipped template and fixture still derive row-for-row.

- [x] 2.4 Drilling (decision 7): one divider entry per divider row; the hole row over the divider's own length from its bottom z; no entry when the span holds no adjustable shelf; side rows unchanged by `shelf_kinds`. Verify the hardware-drilling scenarios "Partial divider drills only its span", "Divider with no adjustable shelf in its span", "Fixing a shelf keeps the side holes", and that "Holes on a divider listed" is unchanged.

- [x] 2.5 `widest_shelf_span` and `guidelines/checks.shelf_span`: widest board across levels and bays, naming the bay when that level is split. Verify the design-guidelines scenarios "Partial divider leaves a whole shelf", "Unequal bays" and "Outside fold widens the span".

- [x] 2.6 `divider_recommendation` (decision 9): centred left faces, compartment widths per split shelf, and the shelf-span rule's limit and source or "no shelf-span limit configured". Verify the 800 mm `cabinet` gives 373 mm and two 373 mm compartments with the no-limit statement, and a test rule of 800 mm for 18 mm gives two 573 mm compartments within the limit for a 1164 mm inner width.

## 3. Generator

- [x] 3.1 Draw divider boxes from `dividers_of`, shelf segments from the shared derivation and each shelf by its kind, in `_module_boxes` and `_folded_module_pieces`, named by cut-list id. Verify with a headless `--blender` test (no render, no tier) for "Partial divider drawn in the model", for the folded cabinet with the divider from shelf 4 to the top (divider object between the fourth shelf's top face and the top panel's underside, clear of the left upper side board), and for the top shelf drawn as the fixed board. Verify the existing `--blender` suite, including "Shelves split by dividers in the model", still passes.

## 4. Tools, Designer, revisions, import

- [x] 4.1 `revise._apply_module_change`: `divider_spans` and `shelf_kinds` replace their lists, `[]` clears, `dividers` 0 also clears spans, with change lines naming each span and kind. Verify "Spans cleared in a revision".

- [x] 4.2 `revise_package` and `create_piece`: return the position question (from 2.6) for a new divider without positions, and the fix-shelf question (shelf named, confirmat +4, that shelf's pins fewer or "no quantity") for a span on an adjustable shelf, instead of a confirmation. `import_design` is unchanged. Verify "Position asked with no limit configured", "Owner gives the position", "Import not asked", and that an adjustable-anchor revision returns the fix-shelf question.

- [x] 4.3 Preview diff (decision 10): changed hardware quantities and added, removed or resized cut-list rows after the change lines. Verify the furniture-packages scenarios "Fixing a shelf in the preview" and "Divider in the preview", and that a revision changing only a name shows no diff lines.

- [x] 4.4 Piece summary in `prompts.py`: spans ("1 divider (equal bays) from shelf 4 to the top", or with its position) and shelf kinds when set. Verify "Span visible in the summary", "Shelf kinds visible in the summary" and "Full-height summary unchanged" in `test_piece_note.py`.

- [x] 4.5 `instructions/designer.md`: describe `divider_spans` with the top-shelf-to-top example; shelf numbers count every shelf; only fixed shelves anchor; relay the tool's position recommendation and fix-shelf question to the owner and wait; call `search_guidelines` for shelf-span or divider passages and cite them; never change a shelf's kind without the owner's yes; dividers allowed on a fold; never say a partial-height divider cannot be made. Add short field descriptions for `divider_spans` and `shelf_kinds` on the schema. Verify `test_instructions.py` for "Instructions name divider spans", "Instructions name the rule" and "Instructions allow fronts on a fold".

- [x] 4.6 Import template guide: describe `divider_spans` and `shelf_kinds`; drop "A folded module cannot carry dividers". Verify the design-import scenarios "Guide names divider spans" and "Guide allows fronts on a fold", and that the template still derives the starter's rows.

## 5. Checks and owner test

- [x] 5.1 Run `uv run ruff check .`, `uv run pytest -m "not slow"` and the `--blender` suite in `backend/`. All must pass.

- [x] 5.2 Owner test in the chat on the folded cabinet: "add a vertical wall from the top shelf to the top of the cabinet". The Designer asks for the position with the recommendation (and the shelf-span limit or its absence); the owner accepts or gives a position; the revision preview lists the divider row and the confirmat change; the headless build's viewport screenshot shows the divider in the upper compartment. Then on a carcass with adjustable shelves only: the Designer explains that only fixed shelves hold a divider and asks to fix the top shelf; on yes, the preview shows +4 confirmat and fewer pins. One optional `draft` turntable through the guard. Record the owner's verdict in this change.

  Done 2026-10-10: the owner reports the chat test passed.
