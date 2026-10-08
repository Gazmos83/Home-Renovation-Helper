## Why

The cut list says how many hinges a piece needs, but not where to drill them. It has no adjustable shelves, so no shelf-pin holes, and it cannot describe a wall shelf on brackets. The owner wants the workshop's drilling positions in the cut list. Every number must come from a cited source, and missing data must be shown, never guessed.

This change supersedes the untracked change `wall-shelf-brackets`. Its content is folded in here and reworked: bracket positions are now computed, and the owner's positions become a checked override. The owner decides separately whether to delete the old folder.

## What Changes

- **Hardware data sheets (new).** Each hinge or shelf-pin item has one data sheet. It holds the item's drilling values and a cited source. The sheets are managed on the guidelines page and searchable with `search_guidelines`.
  - A toom item cites its toom page, or the maker's data sheet linked from it.
  - An item bought elsewhere carries the values from its own data sheet, entered by hand. Its price is a manual price-list entry, so pricing stays toom-only (§5a).
  - A data sheet may cite a source another item cites only when both are the same maker and model.
  - Each measured value is one number or a min–max range, as its source gives it. Counts, such as pins per shelf, are whole numbers.
- **A calculator registry in `derive.py` (new).** Each calculation is one small function, the cited inputs it reads, and its tests. This change ships three:
  - shelf pins: hole columns, pitch, first and last hole, front and rear setback, hole Ø and depth, and pins per shelf;
  - hinges: number per door, positions from the door ends, cup Ø and depth, cup edge distance, and mounting-plate positions on the side;
  - wall-shelf brackets: count and positions from the bracket rules.
  More calculations, such as drawer runners or cam locks, are added later, each through its own OpenSpec change, without touching these.
- **Drilling list in the cut list.** A version lists its drilling positions per part, beside the cut-list rows. It also lists hardware lines (pins, hinges, plates, brackets) and drilling-work counts (hinge cup borings, shelf-pin holes). Holes, cups, plates and brackets are **not** modelled in Blender.
- **Missing data is not refused.** A position whose input is missing is left blank, with a warning that names the value, for example "drilling positions missing: cup edge distance". The cut list is then marked incomplete, the way an unpriced part marks a pricing incomplete. A value is never guessed or borrowed from another item.
- **Ranges stay ranges** (owner decision). A value its source gives as a range, such as bracket ends 100–200 mm from each end, is stored as that range and never narrowed to a midpoint or a picked value. The drilling list shows it as given, "drill 100–200 mm from each end", and the owner marks the board in the workshop. A position that depends on where the owner marks, such as the inner brackets, is listed as its rule in words ("evenly spaced between them"), never as an invented number. A single value from a source, such as cup Ø 35 mm, stays exact. A range is not missing data.
- **Frozen inputs per version.** When a version is made, the data sheets and bracket rules it uses are copied into the version folder. Its drilling list does not change when a data sheet is edited later.
- **Spec schema (generator extension).** A module gains `adjustable_shelves` and a `shelf_pin` item key. A door entry gains an optional `hinge` item key, and its default is today's `hinge-concealed-110`. A custom build gains `wall_shelves` (from `wall-shelf-brackets`). Each wall shelf has a bracket item key and an optional `bracket_positions_mm` override. `schema_version` stays `1`.
- **Bracket rules (from `wall-shelf-brackets`).** Two `warn` rules go into `config/design_rules.yaml`. They cite `topnotch-shelf-brackets`: the count table (600→2, 1200→2, 1800→3, 2000→4, next row up between rows) and outer brackets 100–200 mm from each end, with inner brackets evenly spaced. The calculator lists the count and the cited end range, and the piece checks judge an owner override against them, with a warning.
- **Pricing.** Hinge cup borings are charged at the home store's captured `topfband_bohrung` price in `per_cut` mode. A hardware line with no quantity, because its data is missing, is unpriced and marks the pricing incomplete.
- **The Researcher gets `search_guidelines`.** It cites the guideline or note it used. The edits are already in the working tree.

Ladder step: a piece that uses these fields is a step 1 spec change. Growing the schema, the derivation and the calculators is step 2 (generator extension), and this change is that step. Agents touched: Designer (spec fields, revisions, previews, `cut_list`), Builder (passes the frozen inputs to the headless generator) and Researcher (`search_guidelines`, hinge-boring line in `price_cut_list`).

The render guard and the `bpy` allow-list are not affected. The headless generator stays a checked-in generator, not a live script. It renders nothing new. It draws only the new boards (adjustable shelves, wall-shelf boards) as plain boxes, because every cut-list row needs its object. No hole, hinge, plate or bracket is drawn.

## Capabilities

### New Capabilities

- `hardware-drilling`: the calculator registry, the per-part drilling list, drilling-work counts, missing-data warnings with the incomplete mark, and the frozen per-version inputs.

### Modified Capabilities

- `furniture-packages`: adjustable shelves, hinge and shelf-pin item keys, and wall shelves with computed or overridden bracket positions; the build gets the frozen inputs and publishes the drilling list in `spec.json`.
- `design-guidelines`: hardware data sheets with cited sources; data sheets in `search_guidelines`; bracket count and spacing checks; the shelf-span check also covers adjustable shelves.
- `cut-list-pricing`: hinge cup borings as a cut-service line; a hardware line with no quantity marks a pricing incomplete.
- `design-agents`: `cut_list` returns the drilling list and says when it is incomplete.
- `studio-ui`: a Hardware data section on the guidelines page; a drilling table and an incomplete banner on the inspector's Cut list tab.

## Impact

- `backend/app/blender/schemas.py`: new module, door and wall-shelf fields; `PackageChanges` fields.
- `backend/app/blender/custom_build/derive.py`: calculator registry, adjustable-shelf and wall-board rows, pin, plate and bracket lines, `drilling` output. It stays standard-library-only.
- `backend/app/blender/generators/build_custom_build.py`, `runner.py`, `storage.py`: the `--hardware-data` argument, the frozen file, and boxes for the new boards. Run the `--blender` suite.
- `backend/app/guidelines/`: data-sheet store, corpus mirror, two bracket checks, span check over adjustable shelves.
- `backend/app/agent/revise.py`, `backend/plugins/cut_list/tool.py`, `backend/app/pricing/pricing.py`, `backend/app/agent/review.py`: read the frozen inputs.
- New migration: table `hardware_data_sheets`. New owner routes `/hardware-data`.
- `backend/config/design_rules.yaml`: two rules.
- Already in the working tree: `backend/plugins/guidelines/manifest.yaml`, `backend/app/agent/instructions/researcher.md`, `backend/config/guideline_sources.yaml`, `backend/tests/test_foreman.py`, `backend/tests/test_instructions.py`.
- Frontend: `GuidelineNotes.tsx` (Hardware data section) and `CutListTables.tsx` (drilling table).
- No new dependency.
