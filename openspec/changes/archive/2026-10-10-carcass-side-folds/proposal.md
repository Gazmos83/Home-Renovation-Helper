## Why

The owner asked in chat for an angled carcass: "The left side of the carcass should have a 26 degree bend from 1100 mm". The Designer can parse that sentence, but the spec has no field for a fold. A module is an axis-aligned box; its sides are full-height rectangles. The request is the same class as a bevelled edge: refused by name, recorded as a generator-extension request, and never modelled. The owner wants that sentence to become a confirmed revision and a truthful cut list.

## What Changes

1. **A side fold on a carcass module.** A module accepts an optional `side_folds` list, at most one fold per `left` or `right` side. Each fold states:
   - `from_mm`: the kink, from the module's bottom face when `along` is `height`, from the front face when `along` is `depth`;
   - `along`: `height` or `depth`;
   - `angle_deg`: a whole degree from 1 to 89;
   - `towards`: `inside` (the named side moves toward the opposite side after the kink) or `outside` (it moves away, and the bounding box grows).
2. **Shop geometry.** The folded side is two rectangular boards joined at the angle. The unfolder side, top, bottom and each fixed shelf stay rectangles sized to the envelope at that height or depth. The back is one board whose net outline follows the profile; the cut list states its grain-aligned bounding rectangle and notes the net shape. Every joining edge's notes name the mitre, so pricing marks those rows for review.
3. **Refusals on a folded module.** Fronts, vertical dividers and adjustable shelves are refused by field name in this change (doors on a trapezoid front, pin holes on a bent side, and bays that change along the fold each need their own later extension). A fold that pinches the inner opening to 0 mm, that sits inside a top or bottom panel, or that rounds to a 0 mm inset is refused naming the fold.
4. **Bounds.** `overall`, envelope fit, module overlap and `room_fit` use the folded bounding box, including an `outside` fold that grows past the module's stated width or depth. The stated `width` / `height` / `depth` stay the unbent box (the part before the kink).
5. **Revisions and chat.** `revise_package` sets or replaces `side_folds`; `[]` clears them. The requested-measurement check treats each fold's `from_mm` like a positions-list value. Degrees are not lengths. The piece summary names each fold. The Designer maps "left side … 26 degree bend from 1100 mm" onto a fold; when the owner omits `along` or `towards`, it restates `along: height` and `towards: inside` in the change list for the owner to confirm.
6. **Unchanged documents.** A module with no `side_folds` derives and builds as today, including the `{id}-side` quantity-2 row.

**Ladder step:** 2 (generator extension). **Agents:** Designer (schema, `revise_package`, piece summary, instructions) and Builder (headless generator draws the bent carcass). Reviewer, Intake, Foreman, Researcher, Lighting & materials are untouched. **Render guard:** not affected; builds stay headless and renders keep their tiers. **bpy allow-list:** not affected; no live script is added.

Out of scope: edge bevels and planar mitres that do not fold the carcass; folds on top, bottom or back; two kinks on one side; kerf-bending one board; doors, dividers or adjustable shelves on a folded module.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `furniture-packages`: a module accepts `side_folds`; the cut list, hardware, assembly steps and headless model follow the bent envelope; folded modules refuse fronts, dividers and adjustable shelves.
- `design-agents`: the piece summary names each fold; the requested-measurement check covers `from_mm`; the Designer maps a bend in the owner's words onto `side_folds`.
- `design-import`: the import template's guide describes `side_folds`.
- `design-guidelines`: shelf span on a folded module is the widest inner width along the fold.
- `cut-list-pricing`: a derived row whose notes name a mitre is marked for review, as for owner-written machining notes.

## Impact

- `backend/app/blender/schemas.py`: `SideFoldIn` on `ModuleIn` / `ModuleChange`, relationship checks (one fold per side, range, pinch, fronts/dividers/adjustable refused, envelope and overlap on the folded bounds).
- `backend/app/blender/custom_build/derive.py`: shared fold profile (inset in whole millimetres), split side rows, top/bottom/shelf sizes, back bounding rectangle and mitre notes, confirmat at each fold joint, `overall()` on the folded bounds, assembly step for the joint. Docstring rule table.
- `backend/app/blender/generators/build_custom_build.py`: two rotated side boxes, remaining parts from the profile, polygonal back; `--blender` suite plus one folded fixture.
- `backend/app/agent/revise.py`, `measurements.py`, `prompts.py` (piece summary), `instructions/designer.md`.
- `backend/app/guidelines/checks.py` (shelf span), `backend/fixtures/packages/templates/import-template.json` (guide line).
- No migration: the field lives in the stored spec JSON. No frontend change: the new boards appear in the existing `carcass` and `backs` layers.
- No render-guard or allow-list change.
