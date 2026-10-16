## Context

- The cut-list calculation (`backend/app/blender/custom_build/derive.py`) reads only the version's frozen inputs, `{"data_sheets": {...}, "rules": {...}}`. These are written once per built version by `freeze_inputs` (`backend/app/guidelines/hardware_inputs.py`) and kept as `hardware_inputs.json`.
- Today `freeze_inputs` copies only the rules whose check is one of the two bracket checks, keyed by check name. `derive._rule(inputs, check)` reads them back, and `bracket_plan` takes its count from `shelf_bracket_count_for_length`.
- Shelf pins: `_pin_line(module, shelves, inputs, hardware)` takes a board count only. It reads `pins_per_shelf` from the data sheet or leaves the quantity blank. It is called from five places, one for each shelf layout: plain, dividers, folded, mixed spans and per-bay.
- Hinges: `_hinge_count(sheet, height)` uses the sheet's `count_table`, or `hinges_for_height` (900/1600 mm). Three places use it: `_hinge_lines` for the hardware, `_hinge_entries` for drilling positions and cup borings, and the plate entries.
- Checks live in `CHECKS` (`backend/app/guidelines/checks.py`), each with a Pydantic parameter model and a `run(spec, params)` that returns `Measurement`s. `parse_rules` (`rules.py`) refuses a second rule on either bracket check. The developer panel lists checks straight from `CHECKS`.

## Goals / Non-Goals

**Goals:**
- Pin and hinge counts follow the owner's cited notes through the same path the bracket count already uses: a design rule, frozen per version.
- A derivation without inputs gives exactly the same results as today.

**Non-Goals:**
- Reading free-text notes automatically. A rule is still written by hand, with the clause quoted.
- Checking at startup that an owner note exists for a checked-in rule. That rule is unchanged here.
- Changing shelf-pin hole positions. Those still need a data sheet.
- Any change to the schema, the generator geometry or the frontend.

## Decisions

1. **Two new checks, shaped like the bracket count.** The checks are `shelf_pin_count_for_width` and `hinge_count_for_height`. Their params are `{table: [{max_width_mm | max_height_mm, pins | hinges}], beyond: <count>}`.
   - *Why an explicit `beyond`:* the bracket table reuses its last row beyond the table. Here the owner's notes give a different count past the last limit (5 pins past 36 in, 5 hinges past 203.2 cm). The alternative was a sentinel last row at 10000 mm, but that would state a limit nobody quoted.
   - Validation: counts are whole numbers from 1 to 64, limits are whole millimetres, rows rise strictly. The models use `strict=True`, so `"4-5"` or `4.5` is refused, matching the data-sheet rule on counts.
2. **The run functions return `[]`.** A spec has no pin or hinge count to judge. Making these "checks" lets them reuse rule storage, citation, panel editing, overrides and freezing, with no second rules system.
   - Alternative considered: count fields on data sheets only. Rejected because the owner's guidance is generic, not tied to an item, and a data sheet must cite one product.
3. **One rule per count check.** `BRACKET_CHECKS` in `rules.py` and `hardware_inputs.py` becomes `CALCULATOR_CHECKS`, which holds the bracket checks and the two count checks. It is used both for the "at most one rule" refusal and for freezing. The constants live in `derive.py` next to `BRACKET_COUNT_CHECK`, as the bracket ones do, so `derive` needs no import from `app.guidelines`.
4. **Pin count per board width.** `_pin_line` takes the list of adjustable board cut widths instead of a count, and every call site already has those widths. The order is:
   - sheet `pins_per_shelf` × boards;
   - else, per board, the first row with `width <= max_width_mm`, else `beyond`, summed;
   - else the line is blank.
   
   The note names the source, for example "Rule: 4 per shelf up to 914 mm wide, 5 beyond (shelf-pin-count; owner:7cf8…)". Mixed-width bays therefore count correctly.
5. **Hinge order.** `_hinge_count(sheet, height, rule)` returns `(count, source)`, where source is `"sheet" | "rule" | "fallback"`. All three callers pass `_rule(inputs, HINGE_COUNT_CHECK)`. `hinges_for_height` stays as the fallback, so existing tests and templates derived without inputs don't change.
6. **Inch values converted once, in the YAML.**
   - 36 in = 914.4 mm. Cut widths are whole millimetres, so the limit is 914: a 914 mm board gets 4 pins and a 915 mm board gets 5.
   - The hinge limits are exact: 1016, 1524 and 2032 mm.
   
   A YAML comment states each conversion. The quote keeps the note's own words. The "5 or more" pins becomes `beyond: 5`, the minimum, as the bracket table did with "2 to 3".

## Risks / Trade-offs

- [Hinge counts change for new versions of doors 901–1016 mm and 1525–1600 mm tall.] → This is stated in the proposal and covered by scenarios. Already-built versions keep their frozen inputs. The developer can edit or reset the rule from the panel.
- [A checked-in rule cites a database note id that won't exist on a fresh database.] → The YAML already allows this. The quoted clause carries the limit, so the rule stays traceable. This is noted in the proposal.
- [Owner notes are retailer blog guidance, not official rules.] → Severity is `warn`, and the "Legacy guidance does not establish verified engineering evidence" requirement still applies. These counts are hardware quantities, not load claims.
- [A user-added second count rule breaks the calculator's single lookup.] → It is refused at startup or on the panel, as for brackets.

## Migration Plan

No database migration. Deploy and restart. The shipped rules apply to versions built after the restart. To roll back, remove the two rules from the YAML, or override them from the panel. The fallback and the blank pin line then return.
