## Context

See proposal.md for the why. The current state:

- `custom_build/derive.py` turns a normalised spec into cut-list rows, hardware lines and assembly steps, using a fixed rule table. It is standard-library-only, because the headless generator imports it inside Blender.
- Shelves are fixed only (`shelves: int`). Hinges are one line, `hinge-concealed-110`, with 2, 3 or 4 per door by height (`hinges_for_height`). There are no positions, cup values or plates.
- The generator draws one object per cut-list row. It raises when a row has no placed object.
- Pricing prices a hardware line by the price-list entry whose key equals the line id. A row whose notes name machining is marked for review. `CutGeometry.HINGE_BORING` → `topfband_bohrung` exists in `pricing/store.py`, but nothing uses it.
- `config/design_rules.yaml` ships `rules: []`. Checks read the normalised document. Guideline notes (title, body, citation, value, unit) are mirrored into the corpus. `search_guidelines` only retrieves.
- The untracked change `wall-shelf-brackets` proposed wall shelves with explicit bracket positions, drawn brackets and two `warn` checks. Its quotes were checked against the saved PDF on 2026-10-08.
- Uncommitted working-tree edits already give the Researcher `search_guidelines` (`also_for: [researcher]`, the instruction rule, two tests) and list `topnotch-shelf-brackets`.

## Goals / Non-Goals

**Goals:**
- Workshop drilling positions per part, from cited data, in the cut list.
- One registry where each calculation is small, isolated and tested.
- Hardware quantities and drilling lists that are the same in the backend and in Blender, and stable per version.

**Non-Goals:**
- Modelling holes, cups, plates, pins or brackets in Blender.
- Reading drilling values from toom pages automatically. The owner enters them from the cited page. The Researcher can find the page text with `search_catalog_knowledge` and quote it.
- Hinge side (left or right) in the spec. The list says "hinge edge", and for a pair of doors that means the outer edges.
- Bracket screw-hole patterns, wall fixings and load checks. The source gives no numbers.
- Drawer runners, cam locks and other calculations. Each comes later through its own change.
- Re-deriving an existing version after a data sheet edit. A new version picks the edit up.

## Decisions

**1. Guidelines hold the values; a calculator in `derive` applies them** (owner decision). These are the options the owner was shown.
- *Guidelines only*: the values sit in notes, and the Designer reads and applies them in its reply.
  - Pros: no schema, no code.
  - Cons: the model does the arithmetic, so it is not reproducible or testable. Positions are not in the cut list. A missing value can be silently guessed.
- *Calculator* (chosen): the cited values sit on data sheets and rules, and a deterministic function computes positions.
  - Pros: tested, the same every time, missing values are shown by name, and it fits derive's rule-table style.
  - Cons: a schema, a table and code to maintain, and each new calculation needs a change.

**2. A registry in `derive.py`, not a plugin system.**
- `CALCULATIONS: Final` is a tuple of `Calculation(name, kind, inputs, run)`.
- `run(spec, inputs) -> list[DrillEntry]` is pure, and each `DrillEntry` carries `part`, `what`, `positions`, `values` (each with its source), `missing` and `counts`.
- Each position is one of three forms (decision 12): an exact mm value, a range, or a rule in words.
- `drilling(spec, inputs)` runs every entry in order and merges the warnings.
- Each calculation has its own test module.
- To add one, append an entry, add its data-sheet kind and add its tests. Nothing else changes.
- Alternative: one function per hardware type called by hand. It is rejected because adding one means editing the shared flow.

**3. Data sheets are a table, keyed by hardware key.**
- The table `hardware_data_sheets` holds:
  - `key` (unique, the same as the price-list and hardware-line key), `kind`, `maker` and `model`;
  - `values` as JSON, validated per kind by a Pydantic model whose fields are all optional. A measured field is either one value or a range (decision 12). A count field is one whole number;
  - `source_kind` (`toom` or `manual`), `page_url`, `datasheet_url` and `citation`;
  - `updated_at`.
- The kinds are `hinge` and `shelf_pin`. Brackets need no sheet, because their numbers come from the rules.
- The reuse rule: a new or edited sheet whose `page_url`, `datasheet_url` or `citation` matches another sheet's must have the same `maker` and `model`. Otherwise it is refused, naming the other item.
- A `toom` source's `page_url` host must be a configured retail source host. The maker URL is the owner's statement and is not fetched.
- Each sheet is mirrored into the corpus like a guideline note, with `owner-datasheet:<key>` as its URL.
- Alternative: drilling fields on `supplier_prices`. It is rejected because prices and drilling data have different sources and life cycles, and §5a keeps the price list price-only.

**4. Frozen inputs per version: `hardware_inputs.json`.**
- The file is written next to `input.json` whenever a version folder is made. It holds:
  - `{"data_sheets": {key: {...values, source, updated_at}}, "rules": {check: {rule_id, params, source}}}`, each value kept in its own form, exact or range;
  - only the keys the spec names, and the two bracket checks.
- The runner passes `--hardware-data <path>` to `build_custom_build.py`, and the generator hands it to `derive`.
- `derive(spec, inputs=None)` keeps its signature for old callers. `None` means "not calculated": rows and hardware come out exactly as today, and there is no `drilling` key.
- `cut_list`, `review.py`, `pricing.py` and the inspector read the version's own file through one helper in `storage.py`.
- The file is not in the served closed set. Its content reaches the owner through `spec.json` `drilling`.
- Alternatives:
  - The backend computes drilling at read time from the live table. It is rejected because hardware quantities (pins, brackets) would differ between `hardware.csv` and pricing, and a version's list would drift.
  - Write the values into the spec. It is rejected because it mixes data from a source into the owner's design.

**5. Hardware quantities stay in the rule rows.** Hardware lines are still made in `_rule_rows`, now with the inputs:
- the shelf-pin line is `pins_per_shelf × adjustable_shelves`, or no quantity (`""` plus a note naming the value) when that value is missing;
- the bracket line is keyed by the bracket item and merged across shelves;
- the plate line is added only when the hinge sheet names `plate_item`;
- the hinge count per door comes from the sheet's `count_table` when given. Otherwise it is `hinges_for_height`, so a document with no new fields derives exactly as before.
The `<shelf-id>-bracket` line id from `wall-shelf-brackets` is replaced by the item key, so that pricing can find a price-list entry.

**6. The calculations.** All values are in mm. Positions on a side are measured from the side's bottom end, and on a door from its bottom end. The formulas below are for exact values. A ranged value follows decision 12.
- *Shelf pins*:
  - holes run from `t + first_hole_mm` to `height − t − last_hole_mm`, in steps of `pitch_mm`;
  - there are two columns, at `front_setback_mm` from the side's front edge and at `rear_setback_mm` from the back-reduced rear edge;
  - the list is given per side row, inner face, mirrored on the second side;
  - when the pitch or the first or last hole is a range, the hole heights are a rule in words ("first hole 50–60 mm above the bottom shelf face, then every 32 mm, last hole at least 50 mm below the top"), and the hole count is left out with the note "counted when the holes are marked";
  - a ranged setback is listed as its range, for example "37–40 mm from the front edge".
- *Hinges*:
  - with n hinges, the outer two sit at `end_distance_mm` from each end and the rest are evenly spaced between them;
  - with a ranged end distance, the outer two are listed as "80–120 mm from each end" and the rest as "evenly spaced between them";
  - the cup centre sits `cup_edge_distance_mm + cup_diameter_mm / 2` from the hinge edge;
  - the plate height on the side is the hinge height plus the door's bottom offset in the module, at `plate_setback_mm` from the front edge, with its holes `plate_hole_spacing_mm` apart. An inner plate under a hinge listed in words is listed as "level with its hinge".
- *Brackets*:
  - the count is the count rule's minimum for the length (next row up, last row beyond the table);
  - the outer two are listed at the spacing rule's end-distance range from each end, as cited: "drill 100–200 mm from each end". No value inside the range is picked;
  - the inner brackets are listed as "evenly spaced between the outer brackets", in words, because their centres depend on where the owner marks the outer two;
  - when `2 × shortest end distance ≥ length`, the positions are blank with the warning "board too short for the bracket end distance";
  - owner positions are taken as given and marked `set by the owner`. The spacing check judges them against the range and warns.
- A missing value blanks only the positions that need it. For example, hinge heights need only `end_distance_mm`, while the cup offset needs the cup values.

**7. Incompleteness mirrors pricing.**
- `drilling.complete` is false when any entry has `missing`.
- The warning text has the form `drilling positions missing: <value name>` and names the part.
- No row notes are changed, so the pricing machining-review mark is not triggered by drilling.
- A version is never refused for missing data.

**8. New spec fields (strict, `extra="forbid"`).**
- `ModuleIn.adjustable_shelves: int` (0–20, default 0) and `ModuleIn.shelf_pin: Slug = "shelf-pin"`.
- `DoorIn.hinge: Slug = "hinge-concealed-110"`.
- `CustomBuildSpec.wall_shelves`. Each entry holds `id`, `name`, `x`, `y=0`, `z`, `length`, `depth`, `material`, `bracket: Slug` and `bracket_positions_mm: list[int] | None` (1–20 entries).
- Ids are unique across modules, extra parts and wall shelves.
- The `wall-shelf-brackets` fields `arm_mm` and `drop_mm` are dropped, because brackets are not drawn.
- The adjustable-shelf row is cut `(inner_w − ADJUSTABLE_SHELF_CLEARANCE_MM) × inner_d`, a derive constant (`TODO(user)`, no value shipped). Implementation is blocked until the owner states it.

**9. The generator draws boards only.** Adjustable-shelf boards are spread evenly with the fixed shelves, in the `shelves` layer. Wall-shelf boards are drawn at their position, under `MOD_<shelf-id>`, also in the `shelves` layer, so the closed layer set is unchanged. The generator refuses a cut-list row without an object, so the new boards must be drawn. Nothing else is drawn. The `--blender` suite must pass on 5.2.1.

**10. Pricing of drilling work.** In `per_cut` mode, hinge cup borings are priced through `find_service(..., SERVICE_FOR_GEOMETRY[CutGeometry.HINGE_BORING])`. They are added to `cut_service_cents` as their own listed line, so no migration is needed. `shared` mode lists the count with no fee. Shelf-pin holes are listed only. Tying borings to the cut-charge mode is `TODO(user)` to confirm.

**11. Bracket rules shared by check and calculator.** `checks.py` gets `shelf_bracket_count_for_length` and `shelf_bracket_spacing_mm`, as in `wall-shelf-brackets` decision 6. `rules.load_rules` refuses two rules on the same bracket check. The version-creation code copies the two rules into `hardware_inputs.json`. The span check also counts `adjustable_shelves`. The spacing rule holds the end distance as a range (`min: 100`, `max: 200`, `unit: mm`, its source). The count check applies to calculated brackets. The spacing check applies to owner positions only, because calculated positions are the cited range itself.

**12. A ranged value stays a range** (owner decision, option a).
- A value is exact (`value`) or a range (`min`, `max`), with its unit and source. A range needs `min < max`, or it is refused naming the field. One number is entered as an exact value.
- A range is never narrowed to a midpoint or any picked value. The owner marks the board in the workshop.
- A position computed from one ranged value and exact numbers only is listed as that range, moved by the exact numbers. Examples: the outer brackets "100–200 mm from each end"; an outer hinge's plate height.
- A position that depends on where the owner marks inside a range, or on two ranged values, is listed as its rule in words, naming each value. Examples: inner brackets "evenly spaced between them"; shelf-pin holes from a ranged first hole. No number is invented for it.
- A range is not a missing value. It adds no warning and does not make the list incomplete.
- Counts are whole numbers and are never ranges: pins per shelf, the hinge count table and the bracket count table. A range on a count is refused naming the field. Hinges per door, brackets per board, pins and borings are counted as before.
- Which values may be ranges:

| Value | Kind | Range allowed | When it is a range |
|---|---|---|---|
| hole Ø, hole depth | shelf pin | yes | listed as the range |
| pitch, first hole, last hole | shelf pin | yes | hole heights in words, no hole count |
| front and rear setback | shelf pin | yes | column listed as the range |
| pins per shelf | shelf pin | no, a count | — |
| cup Ø, cup depth | hinge | yes | listed as the range |
| cup edge distance | hinge | yes | cup centre as a range when the cup Ø is exact, in words when both are ranges |
| end distance from the door ends | hinge | yes | outer hinges and their plates as ranges, inner ones in words |
| count table | hinge | no, a count | — |
| plate setback, plate hole spacing | hinge | yes | listed as the range |
| bracket count table | rule | no, a count | — |
| bracket end distance | rule | yes, shipped as 100–200 mm | outer brackets as the range, inner ones in words |
| evenness tolerance | rule | no | it is the owner's measuring tolerance that the check compares against, not a cited position |
| adjustable-shelf clearance | derive constant | no | it sets a cut dimension, and a cut-list dimension is one number |

- A single value from a source stays exact. A data sheet that states cup Ø 35 gives "cup Ø 35 mm".
- The drilling list has one line per part and position, in this form:
  - `side-l, inner face: front column 37 mm from the front edge; holes at 66, 98, … 642 mm (shelf-pin-5mm data sheet)`
  - `door-1: hinges 1 and 3 at 80–120 mm from each end; hinge 2 evenly spaced between them; cup Ø 35 mm, 13 mm deep, centre 21.5 mm from the hinge edge (hinge-concealed-110 data sheet)`
  - `wall-shelf-1: brackets 1 and 3: drill 100–200 mm from each end; bracket 2 evenly spaced between them (topnotch-shelf-brackets)`
  - `wall-shelf-2: brackets at 150, 600 and 1050 mm, set by the owner`
- The same three forms reach `spec.json` `drilling`, `cut_list` and the inspector as data: `{"mm": 37}`, `{"min_mm": 100, "max_mm": 200}` or `{"rule": "evenly spaced between the outer brackets"}`.

## Risks / Trade-offs

- [A frozen file per version adds a path every derivation must read.] → One helper in `storage.py` reads it, and a parity test compares the backend with Blender.
- [No data ships, so every list starts incomplete.] → This is intended. The banner names each value, and the owner fills in the data sheets from the cited pages.
- [A retailer blog is weak evidence.] → The bracket rules are `warn`, and the source entry labels the guide as retailer guidance.
- [Drawing new boards touches the generator.] → It draws only boxes of the existing kind. The `--blender` suite runs before merging.
- [A ranged value leaves marking to the owner, and a hole count can be missing when the holes are a rule in words.] → This is the owner's decision. The list says how to mark each position, and shelf-pin holes carry no fee, so pricing is not affected.
- [A hinge pair's hinge edge is assumed to be the outer edges.] → The drilling list says so in words. Hinge side is a non-goal.

## Migration Plan

- One Alembic migration adds `hardware_data_sheets`, with upgrade and downgrade.
- No stored version changes. A version without `hardware_inputs.json` derives as before.
- To roll back, revert the commit and downgrade the migration. Versions made with the new fields would then be refused by name on revision, which is the existing generator-extension path.

## Open Questions

These only change config values or constants, not the approach:
- `TODO(user)`: the adjustable-shelf clearance in mm, one value (it sets a cut dimension). No value is shipped.
- `TODO(user)`: the bracket evenness tolerance. 10 mm is proposed (from `wall-shelf-brackets`). It is a measuring tolerance, not a quoted limit, so it is one value, not a range.
- `TODO(user)`: the year of `topnotch-shelf-brackets`. The page shows "Jul 24", and 2026 is assumed in the working tree.
- `TODO(user)`: confirm that hinge borings follow the cut-charge mode.
- `TODO(user)`: the default shelf-pin key `shelf-pin`. Rename it if the price list uses another key.
- `TODO(user)`: every data-sheet value, entered by the owner from its cited source.
