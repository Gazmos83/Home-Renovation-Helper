## Why

The owner asked to "add a vertical wall from the top shelf to the top of the cabinet" on the folded carcass and got two refusals: the `dividers` field only makes full-height boards splitting the whole module into equal bays, and a folded module refuses dividers outright (`folded-fronts-and-shelves` kept that v1 refusal). A divider that only closes off one compartment is ordinary cabinetry, and a non-rectangular carcass needs it as much as a rectangular one.

Two follow-ups from the owner (2026-10-10): a divider must not be placed silently when no position is given, so the Designer asks and recommends one using structural guidelines where they exist; and a divider can only stand on a fixed shelf, so when the shelf is adjustable the owner is told and asked whether to fix it, with the cut list and hardware following that choice.

## What Changes

1. **Divider spans.** A module accepts an optional `divider_spans` list, one entry per divider, left to right. Each entry names the board the divider stands on (`from_board`: `"bottom"` or a shelf number) and the board it reaches (`to_board`: `"top"` or a shelf number). Shelf numbers count **every** shelf, fixed and adjustable, from the lowest. Without `divider_spans`, every divider runs from the bottom panel to the top panel, as today.
2. **Only fixed shelves anchor a divider.** A span naming an adjustable shelf is refused, naming `divider_spans` and that shelf.
3. **Each shelf's kind can be stated.** A module accepts an optional `shelf_kinds` list (`"fixed"` / `"adjustable"`, lowest first) that must agree with `shelves` and `adjustable_shelves`. Without it, fixed shelves take the lowest heights, as today. This lets one shelf, e.g. the top one, be fixed while the others stay adjustable.
4. **Asking before fixing a shelf.** When the owner asks for a divider on an adjustable shelf, the Designer (relayed by the Foreman) explains that only fixed shelves can hold a divider and asks whether to fix that shelf. It states what that changes: 4 more confirmat screws, and that shelf's pins fewer. If the owner agrees, the revision sets `shelf_kinds` and the counts; the cut list and hardware follow from the document. If the owner declines, no divider is added.
5. **Asking for a position.** When a new divider has no `divider_positions_mm`, `create_piece` and `revise_package` do not propose the version. They return a recommendation computed by code, which the Designer relays (through the Foreman) as a question:
   - the centred position (equal compartments) in millimetres from the left side's inner face;
   - the compartment widths at each shelf it splits;
   - the configured shelf-span limit with its cited source and whether each compartment is within it, or a statement that no shelf-span limit is configured yet.

   The Designer also searches the guideline passages and cites any that apply. Once the owner accepts the recommendation or gives a position, the revision carries that position explicitly. Import is not affected.
6. **Shelves are split only where a divider crosses them.** A shelf board (fixed or adjustable) is split into bays only by the dividers whose span crosses that shelf's height; the board a divider stands on or reaches stays whole. Divider length is the clear gap between its two boards, rounded down to a whole millimetre.
7. **Cut-list rows for mixed shelves.** With full-height dividers and no fold, rows stay as today (`-bay-<n>` when bays differ). Otherwise shelf boards of one kind are grouped by cut width: one width keeps `{id}-shelf` / `{id}-adjustable-shelf` with quantity; several widths become `{id}-shelf-<n>`, numbered from the lowest level and then left to right, with notes naming the shelf levels and bays. Dividers of different lengths become `{id}-divider-<n>`, left to right.
8. **Dividers on a folded module.** The `_check_folds` refusal is lifted. A divider stays a vertical rectangle at the back-reduced depth. `divider_positions_mm` is measured from the unbent left side's inner face. The centred recommendation (and a document without positions, e.g. an import) splits the narrowest inner opening along the spans into equal bays. A shelf segment next to a folded side is cut to the smallest width along its board. A divider that would cut into a folded side, or leave a bay 0 mm wide or less anywhere along its span, is refused, naming the field.
9. **The preview shows what changes.** The `revise_package` confirmation lists the hardware lines and cut-list rows whose quantity or size changes, e.g. "Confirmat screw 7×50 mm: 28 → 32", "Shelf pin: 16 → 12".
10. **Drilling.** A divider's shelf-pin row is the data sheet's first hole, last hole and pitch applied to the divider's own length, from its bottom end (the top face of the board it stands on); one drilling entry per divider row, none when no adjustable shelf lies within its span. Fixing a shelf leaves the side boards' hole row as it is.
11. **Shelf span guideline** measures the widest shelf board, across levels and bays, naming the bay when the level is split.
12. **Designer, piece summary, revisions and import guide.** The Designer maps "from the top shelf to the top" onto `divider_spans`, restates it and waits for confirmation. The piece summary names each divider's span and states fixed shelves by position. `revise_package` sets `divider_spans` and `shelf_kinds`: `[]` clears either, and `dividers` 0 clears the spans. The import guide describes both fields and drops "a folded module cannot carry dividers".
13. **TODO(user): a shelf-span limit.** No shelf-span limit is configured in `config/design_rules.yaml`. The owner is asked for a cited limit: a guideline note plus a `shelf_span_mm_for_thickness` rule. Until then the recommendation says plainly that no limit is set.

Depends on `carcass-side-folds` and `folded-fronts-and-shelves` (both still open). Not **BREAKING**: a document without `divider_spans` or `shelf_kinds`, and without dividers on a folded module, derives and is drawn exactly as before.

**Ladder step:** 2 (generator extension). **Agents:** Designer (schema, instructions, summary, import guide, the two questions) and Builder (headless generator draws partial dividers, split shelves and mixed shelf kinds on folded and unfolded modules). The Foreman relays the Designer's questions as it does today, with no new instructions. Intake, Reviewer, Researcher and Lighting & materials are untouched. **Render guard:** not affected. **bpy allow-list:** not affected; no live script is added.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `furniture-packages`: dividers may span between named boards; only fixed shelves anchor; shelf kinds per shelf; shelves split only where crossed; a folded module may carry dividers; the revision preview lists hardware and cut-list changes.
- `hardware-drilling`: a divider's shelf-pin row follows its own length and is listed per divider row.
- `design-guidelines`: the shelf span is the widest shelf board across levels and bays.
- `design-agents`: the Designer expresses partial-height dividers, asks for a divider position with a code-computed recommendation, and asks before fixing a shelf; the piece summary names spans and shelf kinds.
- `design-import`: the import guide describes `divider_spans` and `shelf_kinds`, and no longer forbids dividers on a fold.

## Impact

- `backend/app/blender/schemas.py`: `DividerSpanIn`, `divider_spans` and `shelf_kinds` on `ModuleIn` and `ModuleChange`, span and kind checks, fold-aware divider fit; drop the dividers refusal in `_check_folds`.
- `backend/app/blender/custom_build/derive.py`: shelf kinds per level (replacing the "fixed lowest" slicing), divider spans and lengths, per-level shelf segments, folded bays, row grouping, confirmat count, divider pin-hole rows, `widest_shelf_span`, a divider recommendation helper, docstring rule table.
- `backend/app/blender/generators/build_custom_build.py`: partial divider boxes; split shelves and per-level kinds on unfolded and folded modules.
- `backend/plugins/revise_package/tool.py`, `backend/plugins/create_piece/tool.py`: position-needed and fix-shelf answers; hardware and cut-list changes in the preview.
- `backend/app/guidelines/checks.py`, `backend/app/agent/prompts.py`, `backend/app/agent/revise.py`, `backend/app/agent/instructions/designer.md`, `backend/fixtures/packages/templates/import-template.json`.
- Tests in `backend/tests/` (schema, derivation, drilling, guidelines, revise, create, piece note, instructions, design import, `--blender`).
- No migration, no frontend change, no new dependency.
