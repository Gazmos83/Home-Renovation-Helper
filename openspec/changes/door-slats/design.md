## Context

See proposal.md (Why). The current state the approach builds on:

- **Fronts are layout rules.** `derive.front_layout(module, t, b)` turns a module's front entries into leaves: rectangles in the module's front-face frame, with `x` from the left face and `z` from the bottom face, and `w`/`h` in whole millimetres for an unfolded module. `CustomBuildSpec._check_fronts` runs that layout at validation time, so a refusal reaches the Designer and the import preview before Blender runs.
- **Handles are the closest precedent.** `HandleIn` hangs off a front entry, `handle_spec` resolves its defaults once, and `handle_layout` gives one record per leaf. That record serves three callers: validation, derive (hardware lines) and the generator (`_handle_pieces`, drawn at `front_y = module y − t`).
- **The generator draws cut-list rows.** `_add_front_boxes` fills `pieces[row_id] = (layer, boxes)`, and `_build_scene` makes one object per cut-list piece, `<id>` then `<id>#<n>`. A count check fails the build when the pieces and the cut list disagree.
- **Fronts sit outside `overall`.** For an unfolded module the fold profile starts at `y0 = 0`, and fronts lie at `y < 0`. So neither fronts nor handles count in `overall` or the envelope check.
- **The confirmations are code-written.**
  - `revise.derived_changes` lists cut-list and hardware changes under the change lines.
  - `create_piece.summarise` appends "Design-rule warnings: …".
  - The two import previews do the same.
  - `prompts.py` builds the Designer's summary of the active build using `describe_front`.
- **The inspector shows `notes`** in `CutListTables.tsx`, from the version's cut list.

## Goals / Non-Goals

**Goals:**
- One `slats` object on a door entry describes all its slats. The positions are derived, never stored.
- One shared layout function, so validation, the cut list, the generator, the handle offset and the warnings cannot disagree.
- A document without `slats` derives and builds byte-for-byte as before.
- The slat-handle warning is written by code from the derived layout, never by a model.

**Non-Goals:**
- Slats on drawers and flaps; slats on folded modules (refused).
- Slats of different widths, uneven spacing, or diagonal or patterned layouts.
- Profiled slats (rounded or fluted). Slats are plain boxes.
- Screws or glue as hardware lines. The note says "glued".
- Moving a handle off the slats automatically, or snapping its posts to a slat. The warning leaves this to the owner.
- Any frontend code change.

## Decisions

1. **`slats` lives on `DoorIn`, not on the module or as extra parts.** The entry already knows its leaves, as for handles. Slats then travel with the fronts through `revise_package`'s `fronts` replacement, and re-space whenever the leaf changes. Extra parts were rejected because their placements are absolute and do not follow the door, which is the owner's complaint.

2. **Fields** (`SlatsIn`, `extra="forbid"`, strict):
   - `count`: 1–40;
   - `width`: `Millimetres`;
   - `material`: `SlotName`;
   - `orientation`: `"vertical" | "horizontal"`, default `"vertical"`;
   - `margin_mm`: 0–500, default 0;
   - `leaves`: a list of 1–20 integers ≥ 1, or `None`.

   Unstated defaults are omitted on serialisation, as in `HandleIn`, so a stored document keeps only what was written. `leaves` is checked against `count` in a `DoorIn` validator; an undefined slot is checked in `CustomBuildSpec`, next to the existing slot checks.

   Leaves are numbered from 1 because the owner speaks of "door 2", while handle records count from 0 internally.

3. **Spacing rule.** Take `across` to be the leaf's width for vertical slats and its height for horizontal ones, and `along` the other dimension.
   - The slat length is `along − 2·margin`.
   - The usable span is `across − 2·margin`.
   - The gap is `(span − count·width) / (count − 1)`, so the outer slats sit on the margins. For `count == 1` the slat is centred and there is no gap.

   A gap under `GAP_MM` (3 mm, the same as between fronts) is refused. The largest count that fits, `floor((span + 3) / (width + 3))`, is named in the refusal. A margin leaving a span or length of 0 or less is refused.

   This was chosen over "count with a fixed gap" and over "fixed width, derived count". It is the only rule where the owner's single style value (`count`) adds or removes slats and the result still fills the door when it is resized.

4. **`derive.slat_layout(module, materials, t, b)`** returns one record per slat:
   - `row`: the door row id, the same as `handle_row_id`;
   - `leaf` (0-based) and `entry`;
   - `orientation` and `gap`;
   - the slat's centre `x`/`z` and size `w`/`h` in the module's front-face frame;
   - `thickness`, from the slot.

   Callers:
   - `_check_fronts` calls it, so refusals carry the entry path `modules[i].fronts[j].slats`.
   - `_add_front_rows` adds one row `<door row id>-slat` after each slatted door row. All slats in a row share one size, because door leaves in a row are equal and folded modules are refused. The row is named "Door slat", has grain "length (vertical)" or "length (left-right)" and banding "all edges". Its note is "Rule: <n> <orientation> slats per door, <gap> mm gap, glued to the door face", with the gap to one decimal.
   - The generator adds `pieces[f"{row}-slat"] = ("fronts", boxes)` in `_add_front_boxes`. Each box is centred `t + slat_t/2` in front of the module's front plane: `y = module y − t − slat_t/2`. Boxes are ordered leaf by leaf, then left to right or top to bottom, so `#n` follows the spec.

5. **The handle offset.** `_handle_pieces` passes `front_y = module y − t − slat_t` when the handle's leaf is slatted. `handle_layout` stays unchanged: placement on the leaf does not depend on slats. The lookup is by `(row, leaf)` from `slat_layout`.

6. **The slat-handle warning.** `derive.slat_handle_warnings(spec)` returns one sentence per leaf that has both slats and a handle, in front-row order.
   - **Cut list:** derive appends " Warning: <sentence>" to that row's slat note; one sentence per leaf, joined with spaces. `cutlist.csv` and the inspector's table show it with no frontend change.
   - **Create and import previews:** these append "Slat-handle warnings: …" after the design-rule warnings.
   - **Revision:** the confirmation lists the warnings after the change lines (it shows no cut-list diffs since `revision-confirm-highlight-cuts`), whenever the revised document carries them, even if they were already there before. The owner should see them before every "yes".
   - **Designer:** `prompts.py` adds a "Warnings:" line to the active-build summary, labelled as application data.

   A design-rule check (`config/design_rules.yaml`) was rejected for this. Those rules cite guideline publications, can be switched off, and do not feed the cut list.

7. **Wording.** `describe_front` appends a slat phrase inside the door's parentheses, after the handle:
   - "8 vertical slats 30 mm";
   - "20 mm margin" when the margin is not 0;
   - "on door 2" or "on doors 1, 3" when `leaves` is set.

   The change lines and the Designer's summary both pick it up. `designer.md` gains one line on `slats`. The import template gains one guide line; the guide has 27 of its 40 notes.

8. **Colour.** `_COLOURS` gains `("anthracite", …)` and `("anthrazit", …)` with a dark grey (0.09, 0.09, 0.1), roughness 0.5. They go before `black`, so an anthracite slot is not caught by a broader keyword. The order of the existing entries is unchanged.

## Risks / Trade-offs

- **The handle lands on a gap or straddles slats.** This is drawn faithfully, not corrected → the slat-handle warning in the cut list and the conversation, which is the owner's chosen mitigation.
- **The slats' thickness is outside `overall`.** Room fit ignores up to the slot thickness in front of the doors → this matches how fronts and handles are treated today. The guide line notes it.
- **Gap rounding.** The note shows one decimal; the geometry uses the exact value → the cut-list sizes are whole millimetres as always; only the spacing is fractional.
- **Many slats in the inspector.** Up to 40 × 20 leaves are possible in theory → they are boxes in an existing layer; the inspector already handles hundreds of objects.
- **Restyle looks.** A separate slat slot takes its own look; slats sharing the carcass slot restyle with it → this is expected behaviour, not a regression.

## Migration Plan

None. The field is optional, and stored versions are not rewritten. Rollback is removing the field; a version that uses `slats` would then be refused by name, as any unknown field is.
