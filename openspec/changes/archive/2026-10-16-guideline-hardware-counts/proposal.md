## Why

The owner has two guideline notes that give hardware counts. "Shelf Pin Count" says 4 pins for a shelf up to 36 in wide and 5 or more above that. "Hinge Quantity per Door" says 2/3/4/5 hinges up to 101.6/152.4/203.2 cm and above. The cut list uses neither of them. A shelf-pin line has no quantity unless the pin item has a data sheet. The hinge count comes from a fixed rule in code (2/3/4 hinges up to 900/1600 mm and above) that cites nothing and differs from the owner's note. Notes are free text that only the Designer can search, and the cut list reads only data sheets and the closed set of design-rule checks. That set has a count check for wall-shelf brackets, but none for shelf pins or hinges. This came up while importing the Höffner "Kommode Harmony" (2026-10-16): its two adjustable shelves derived a `shelf-pin` line with no quantity, although the owner's note answers it.

## What Changes

- Two new piece checks join the closed set of design-rule checks:
  - `shelf_pin_count_for_width`: a table of shelf widths with the pins per shelf, plus a count for shelves wider than the last row.
  - `hinge_count_for_height`: a table of door heights with the hinges per door, plus a count for doors taller than the last row.
  
  Like the bracket-count check, each one gives the calculator its count. Neither judges anything in a spec, because a spec states no pin or hinge count, so neither ever raises a warning. At most one rule may name each check.
- `config/design_rules.yaml` ships two rules, both `warn`, each citing its owner note as `owner:<note id>` with the note's clause quoted:
  - `shelf-pin-count`: 4 pins per shelf up to 914 mm (36 in) wide, 5 beyond.
  - `hinge-count`: 2 hinges up to 1016 mm, 3 up to 1524 mm, 4 up to 2032 mm, 5 beyond.
- When a version is built, its frozen hardware inputs keep these two rules, as they already keep the bracket rules.
- **Pin count:** taken from the pin item's data sheet when it gives pins per shelf. Otherwise it comes from the pin-count rule, applied to each adjustable shelf board's cut width. With neither, the line has no quantity, as today.
- **Hinge count per door:** taken from the hinge's data-sheet count table when there is one. Otherwise it comes from the hinge-count rule. Without the rule, the built-in 900/1600 mm fallback stays as today. The hardware line, the hinge positions in the drilling list and the hinge cup borings all use the same count. Each hardware note names the rule and its source.
- **Behaviour change (explicit):** a version built with the shipped hinge rule counts differently from today for doors 901–1016 mm tall (2 hinges instead of 3) and 1525–1600 mm tall (4 instead of 3), and gives 5 above 2032 mm. Existing versions keep the inputs frozen with them, so they don't change. A derivation with no frozen inputs (revise diffs, imports checked offline, shipped templates) is unchanged.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `design-guidelines`: two new piece checks that give counts, the two shipped rules citing owner notes, and at most one rule per count check.
- `hardware-drilling`: the hinge calculation's count per door can come from the hinge-count rule. The shelf-pin quantity can come from the pin-count rule.
- `furniture-packages`: the order in which the shelf-pin and hinge hardware quantities are decided (data sheet, then rule, then the fallback), and the notes that name each source.

## Impact

- **Ladder step 1 only.** This changes quantities derived from the spec. Nothing in the schema, the generator geometry, the drawn model or any render changes.
- **Agents:**
  - Designer: `cut_list`, and the hardware in the create and revise previews.
  - Builder: the hardware and drilling list of a built version.
  - Researcher: `price_cut_list` prices the new quantities.
- The render guard and the `bpy` allow-list are not affected.
- **Code:**
  - `backend/app/guidelines/checks.py`: new parameter models and checks.
  - `backend/app/guidelines/rules.py`: one rule per count check.
  - `backend/app/guidelines/hardware_inputs.py`: freeze the count rules.
  - `backend/app/blender/custom_build/derive.py`: `_pin_line`, `_hinge_count`, `_hinge_lines` and the hinge drilling entries.
  - `config/design_rules.yaml`: two rules.
- **Tests:** `tests/test_design_rules*.py`, `tests/test_hardware_drilling*.py`, `tests/test_custom_build_spec.py`, `tests/test_admin_rules*.py`.
- The developer panel lists the new checks from the closed set with no frontend change.
- **Data:** the rules cite owner notes `7cf8c9ef-e98f-4d3d-af6c-f0384a17ffdd` and `a8147011-0f73-4e5e-a5f2-e3a9f8fd9852`, which exist in this database. As with every checked-in rule today, startup checks only the `owner:<uuid>` form, not whether the note exists. The quoted clause in the rule is what makes the limit traceable on another database.
