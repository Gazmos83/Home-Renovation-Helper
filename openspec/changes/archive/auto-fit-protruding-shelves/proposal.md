## Why

A module whose shelf sticks out the front (`shelf_depths_mm` with `shelf_depth_align: "back"`) puts the board at a negative y in the module's frame. A build with an envelope refuses any module that starts before y = 0, so the revision is refused with "module 'cabinet' lies outside the envelope" and growing the envelope's depth cannot help (400 mm cabinet, 550 mm shelf, 12 mm back: envelope 724 mm refused at module y 0, accepted at y 162 with depth 562). The Designer cannot know to move the module back, so it told the owner the only form was to deepen the whole module, which changes more than the owner asked for. On a module with a folded side the same shelf is refused against the folded inner depth, and in Listening wall v18 the Designer cleared the left fold (1100 mm, 26°, inside) to get past that refusal, which the owner never asked for.

## What Changes

- When a revision gives a module a shelf that reaches in front of the build's y = 0 plane, the app **fits the build automatically**: every module and wall shelf moves back (larger `y`) by the overhang, and the envelope's depth grows by the overhang when the build has an envelope, so every part stays inside and the backs stay flush on the same wall. The owner is not asked to restate any of it.
- The owner still confirms. The adjustment appears as its own lines in the usual `revise_package` confirmation (the new y of each moved module and wall shelf, the new envelope depth, and the reason), so the piece's changed dimensions are shown before anything is saved.
- On confirmation, one row is appended to the conversation's "decisions so far" note, naming the shelf, the overhang and the envelope and position changes. A declined revision writes nothing.
- **A folded module may carry a protruding shelf.** A back-aligned shelf deeper than the folded inner depth is no longer refused against that depth: the part in front of the carcass is outside the folds, and only the part inside the carcass must fit them. A front-aligned shelf (it would stick out the back) is still refused against the folded inner depth.
- **The Designer cannot change a side fold on its own.** A revision that sets, changes or clears `side_folds` is refused, naming the field, unless the owner's own messages since the last version ask for it: the Designer must give a `requested` entry for that module and field whose quote appears in those messages and names a fold or bend. This is the guard the measurement check already is for lengths.
- The refusal "lies outside the envelope" stays for every other cause. A shelf that still collides with another module after the fit is refused as today.
- The Designer's instructions say that a protruding shelf needs no separate envelope or position change; the app makes it.
- Revisions that already set `y` or the envelope explicitly are respected: the fit adds only the shortfall.

Ladder step: 1 (spec change; the app edits spec JSON fields that already exist). No schema field is added, so no generator extension and no Blender change. Agents touched: Designer (instructions, `revise_package`). The render guard and the bpy allow-list are not affected.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `furniture-packages`: a revision with a front-protruding shelf fits the build's module and wall-shelf positions and envelope depth instead of being refused.
- `design-agents`: the fit is shown in the revision confirmation and the Designer is told not to request it.
- `homeowner-chat`: a confirmed fit adds a decisions row to the conversation's note.

## Impact

- Backend: `app/blender/schemas.py` (`_check_shelf_depths`), `app/blender/custom_build/derive.py` (shelf width of a board that reaches in front of a fold), `app/agent/measurements.py` (fold entries), `app/agent/revise.py` (fit step after the module changes), `plugins/revise_package/tool.py` (confirmation lines, row on `run`), `app/agent/decisions_note.py` (reused, not changed), `app/agent/instructions/designer.md`, `app/blender/custom_build/derive.py` (reuse `module_bounds`; no change expected).
- Tests in `backend/tests/` (revise, revise_package confirmation and run, decisions row, instructions).
- No migration, no frontend change, no new dependency.
