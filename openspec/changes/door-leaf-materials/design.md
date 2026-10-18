## Context

See proposal.md (Why). The current state the approach builds on:

- **Front cut-list rows.** `derive._add_front_rows` cuts every door in the carcass slot's material at its thickness `t`. `_group_leaves(prefix, leaves)` gives one row while all leaves share a `_leaf_key` (shape and size), and otherwise one row per leaf, `<prefix>-<n>`, qty 1, left to right. The second case is used by folded modules today.
- **Other rows key on the entry row.** `handle_row_id(module_id, front, index)` is the entry's row (`<module>-door-<i>`). `handle_layout`, `slat_layout` (`row`, `leaf`), the drilling list, `_add_slat_rows` and `slat_handle_warnings` all key on it.
- **The generator.** `_add_front_boxes` builds `pieces[<entry row>]` with one box per leaf. The emit loop then names each box after its cut-list row and colours it from `row["material"]` (the `_COLOURS` keyword match). It raises when a row's qty differs from the boxes placed for it. Slats are `pieces[<entry row>-slat]`.
- **Overrides.** `part_overrides` validation refuses an id that no derived row has.
- **Describing changes.** `revise.describe_front` writes an entry in words. The revise confirmation writes "fronts <before> → <after>" per module (`revise.py`, the `fields == "fronts"` line).
- **door-slats** (applied, not archived) added `SlatsIn.leaves` with the same 1-based numbering and validators this change mirrors.

## Goals / Non-Goals

**Goals:**
- One door of a side-by-side entry can be cut, listed, priced and drawn in its own material.
- Nothing changes for a spec without `leaf_materials`, byte for byte.
- A revision that restructures the fronts is visible in the confirmation, written by code.

**Non-Goals:**
- Doors of different thickness within one entry. The overlay depth, the handle and slat offsets and the hinges all assume `t`, so a different thickness is refused.
- Per-leaf materials on drawers or flaps.
- Side-by-side separate entries, i.e. any change to how `front_layout` stacks entries.
- Edge banding colour per door. The row's material describes the board, and banding stays "all edges".

## Decisions

1. **The field: a map from door numbers to slots.** `DoorIn.leaf_materials: dict[str, SlotName] | None`.
   - Keys are door numbers as strings ("1" to "20"). JSON object keys are strings, and strict mode refuses coercion, so a key pattern `^[1-9][0-9]?$` is validated and checked against `count` in a `DoorIn` validator. Its message is "leaf_materials: the entry has N doors; number them 1 to N".
   - The slot and thickness checks need `materials`, so they live in `CustomBuildSpec._check_fronts` beside the slat slot check: "…fronts[i].leaf_materials: undefined material slot 'x'" and "…: slot 'x' is 12 mm but the carcass is 18 mm; a door must be as thick as the carcass".
   - The folded-module refusal sits beside the slats one.
   - The serializer drops `leaf_materials` when `None`, so existing documents serialise unchanged.
   - Alternative rejected: a list of slots, one per door. It makes every door's slot mandatory and is noisier to revise.

2. **One resolver; split rows only when the materials differ.**
   - `derive.leaf_material(front, leaf_index, materials, carcass_slot) -> slot name` returns the named slot, or the carcass slot.
   - `derive.door_row_ids(module_id, front, index, materials, carcass_slot, leaves) -> list[str]` gives each leaf's row id. When every leaf resolves to the same slot it gives the entry row for all leaves. Otherwise it gives `<entry row>-<n>` per leaf.
   - Folded modules already split by shape. They are refused for `leaf_materials`, so the two causes never combine.
   - `_add_front_rows` uses `door_row_ids` for rectangular doors. A split row takes its leaf's slot material and calls `_hinge_lines` with qty 1, so the hardware totals equal the unsplit pair's (hardware lines aggregate by key).
   - Alternative rejected: one row per material (doors 1 and 3 together). Per-door rows reuse the existing `-<n>` naming and keep the slat and handle row the same as the door's row.

3. **Rows that refer to a door use the door's row id.** `handle_layout` and `slat_layout` set each record's `row` from `door_row_ids` (`leaf` stays the leaf index in the entry). `_add_slat_rows` already groups slat records by `row`, so a split door gets `<door row>-slat`. The slat-handle warning and the drilling list follow because they read `record["row"]`. For unsplit entries `door_row_ids` returns the entry row, so every existing id is unchanged.

4. **The generator mirrors the rows.** In `_add_front_boxes`, door leaves are grouped by `door_row_ids` into `pieces[row] = ("fronts", [panel(rect) …])`. Slat pieces are grouped by `record["row"] + "-slat"`. The handle pieces (`_handle_pieces`) already key on handle records. The emit loop is untouched: it colours each object from its row's material, so the black_paint door is black through the existing `_COLOURS` "black" keyword.

5. **Words.** `describe_front` appends "door <n> <slot>" for each door whose slot differs from the carcass, before the slats text. It is reused by the confirmation, the piece note and both import previews, which already call it.

6. **The front-layout line (code, not model).** `revise.front_layout_change(before_fronts, after_fronts) -> str | None` compares, per module:
   - the entry count;
   - each entry's `(type, count)`.

   It returns nothing when either side has no fronts, since the fronts line already says "→ none". On a difference it returns, for example, "kommode: front layout changes from 1 entry of 2 doors side by side to 2 entries stacked top to bottom (1 door; 1 door)". The revise confirmation appends it beside the existing fronts line. Only structure is compared, so material, handle, slats and height edits never trigger it.

7. **Instruction and template.**
   - `designer.md`, after the slats line: "To give some doors of an entry their own colour or material, set that entry's `leaf_materials` ({"2": "<slot>"}, doors numbered from 1 on the left; the slot must be as thick as the carcass). Never split a pair or row of doors into separate entries for this: separate entries stack top to bottom. If it is refused, say why and keep the layout."
   - The import template gains one guide line of at most 500 characters.

## Risks / Trade-offs

- **[Ids change when a pair is split]** → `kommode-door-1` becomes `-1`/`-2`. An old override on the pair row is refused by name (validation already does this), so the Designer must re-target it. Renders and the inspector read ids from each version's own cut list, so older versions are unaffected.
- **[A thin painted board is refused]** → the refusal gives both thicknesses. The owner or Designer picks an 18 mm painted slot. A thinner door would need an overlay-depth rule, which is a later change if wanted.
- **[Colour depends on the material's name]** → a slot named "black_paint" whose material text lacks a colour word is drawn in the default wood tone. The generator's `_COLOURS` lookup is unchanged; the test uses a material text with "black".
- **[door-slats not yet archived]** → this change only ADDs requirements, so its archive does not overwrite door-slats' MODIFIED requirement blocks. door-slats should be archived first.

## Migration Plan

None. No stored document changes meaning. `lamellen-kommode` v3 (stacked) stays as it is. A revision with `leaf_materials` returns it to a side-by-side pair as v4.
