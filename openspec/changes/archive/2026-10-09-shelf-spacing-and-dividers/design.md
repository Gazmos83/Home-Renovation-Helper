## Context

A module's interior is derived in two places that must agree, both from the same normalised spec:
- `custom_build/derive.py` produces the cut-list rows, the hardware and the drilling list;
- `generators/build_custom_build.py` draws the boxes inside Blender, and imports `derive` as `rules`.

Today the shelves are counts (`shelves`, `adjustable_shelves`). Both files compute an even step, `(height − 2t) / (n + 1)`, and the fixed shelves take the lowest slots. Nothing models a divider.

Revisions pass through `revise.py` (`_apply_module_change`), and the owner's lengths are checked in `measurements.py`. That check resolves a field with `field_value`, which returns `None` for a field the module has not set, and it then refuses. The Designer reads a summary written by `prompts.py`.

See proposal.md for the motivation and the owner's test gate.

## Goals / Non-Goals

**Goals:**
- One calculation of shelf heights and bay widths, used by both the cut list and the generator.
- No change for documents that use none of the new fields: same rows, same ids, same model.
- The model states what the owner said (355); code turns it into heights.

**Non-Goals:**
- Per-bay shelf counts or spacing (rejected by the owner for now).
- Partial-height dividers, horizontal sub-dividers, or dividers in another material.
- Drawing holes or pins.
- The "Inspect version N" chat button and exploded-view module sizes. They are deferred until after the owner's test.
- Any relaxation of the spec-only rule. That is a separate decision after the test.

## Decisions

1. **One shared geometry helper in `derive.py`.** A pure function, `interior(module, t, b)`, returns the bay x-ranges (left inner face → right inner face per bay) and the shelf underside heights, lowest first, fixed shelves before adjustable ones. `_module_rows`, `_shelf_pin_entries`, `guidelines.checks.shelf_span` and the generator's `_module_boxes` all call it.
   - *Alternative:* compute in each place. Rejected: the even step is already duplicated, and two copies of the bay arithmetic would drift.
2. **Heights are measured from the top face of the bottom panel to the shelf's underside.** This matches the owner's "clear gap" reading: 355 mm of open space, then the 18 mm board, so the step is 373 mm. Divider positions are measured from the inner face of the left side to the divider's left face, so the first bay's width equals the first position.
3. **Even spacing stays the default and keeps its float step.** Without the new fields, the generator keeps placing centres at `t + step·(k+1)`, so existing models stay byte-for-byte equal. Stated spacing and positions are whole millimetres. Even-split bay widths are rounded down (`floor`), like front sizes, and any remainder goes to the last bay in the drawing only. The cut list states one rounded width.
4. **Row ids stay stable unless bays differ.** Equal bays keep `<id>-shelf` and `<id>-adjustable-shelf` with the quantity multiplied, so existing part overrides still match. Unequal bays use `<id>-shelf-bay-<n>` and `<id>-adjustable-shelf-bay-<n>`. A part override naming a row that disappears is refused by the existing check, which tells the Designer which rows exist.
   - *Alternative:* always split per bay. Rejected: it would rename rows of every divided module and break overrides needlessly.
5. **Spacing and positions exclude each other; revise clears the other.**
   - The validator refuses both fields together.
   - So that a revision can switch from one to the other in one step, `_apply_module_change` drops the other field when one is set, and adds a change line for it.
   - In `ModuleChange` only, `shelf_spacing_mm: 0`, `shelf_positions_mm: []` and `divider_positions_mm: []` clear the field. Without spacing or positions, the shelves go back to even spacing; without divider positions, the bays go back to equal widths. This mirrors `bracket_positions_mm: []`.
   - `ModuleIn` never accepts 0 or an empty list.
6. **The shelf-pin drilling gets a second entry for dividers.** It adds an entry on the `<id>-divider` row with "both faces" and the same heights, instead of folding the divider holes into the side entry. The holes are counted separately, so the pricing count stays traceable. No new calculation is added to `CALCULATIONS`; this extends the existing one under its own spec requirement, which hardware-drilling allows only through a change, and this is that change.
7. **Confirmat rule.** 4 per divider: 2 through the bottom and 2 through the top. Fixed-shelf screws count per board, so 4 × shelves × bays. This is stated in the rule table and the docstring.
8. **Measurement check.** `field_value` gains a list mode: for a list field, the check matches against membership in the revised list. A module field that is not set gives `before = None`; that is accepted only when every candidate is absolute. A relative length on an unset field is refused with a clear reason.
9. **Designer instructions.** One paragraph, plus one example each: `"shelves": 4, "shelf_spacing_mm": 355` and `"dividers": 2`. Plus the rule: "never compute heights from a spacing; state the spacing".

## Risks / Trade-offs

- [The model still writes positions where a spacing was said] → The instructions prefer spacing for "X apart", and the measurement check refuses a position list whose values the owner never wrote.
- [Rounding a bay leaves the drawing up to 2 mm off the cut list] → The drawing places the remainder in the last bay, and the cut list states the rounded width. This is the same convention as the fronts.
- [The divider changes how adjustable shelves are made in the real build] → The pin holes are listed on the divider faces, and the clearance applies per bay.
- [`--blender` suite runtime] → Only one new fixture build is needed: a module with dividers and spacing.

## Migration Plan

No database or file migration: existing specs omit the new fields and derive as before. Rollback is a revert. A spec stored with the new fields would then be refused by name, which is the documented generator-extension behaviour.
