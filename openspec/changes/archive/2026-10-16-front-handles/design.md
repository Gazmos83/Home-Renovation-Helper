## Context

- **Fronts are layout rules.** A front entry is `DoorIn`, `DrawerIn` or `FlapIn` in `schemas.py`. `derive.front_layout(module, t, b)` turns a module's entries into leaves: rectangles in the module's front-face frame, with `x` from the left face and `z` from the bottom face. `CustomBuildSpec._check_fronts` already runs that layout at validation time to refuse fronts that do not fit, so a refusal reaches the Designer and the import preview before Blender runs.
- **The generator draws only cut-list rows.** `_build_scene` builds a `pieces` map from row id to boxes, then makes one object per cut-list piece. Anything placed but not in the cut list fails the count check. Objects are registered in a `LayerRegistry` over `LAYER_NAMES`, and `spec.json` emits only non-empty layers.
- **Hinges are the precedent for front hardware.** A door names a `hinge` key; `_hinge_lines` adds one hardware line under that key; pricing reads the key from the price list. Nothing hardware-like is drawn today ("No hole, pin, hinge cup or plate SHALL be drawn").
- **The inspector builds its layer switches from `Object.keys(spec.layers)`.** A new layer shows up without frontend code.
- **`revise.describe_front` words a front.** Revision change lines and the Designer's context summary use it.

## Goals / Non-Goals

**Goals:**
- A handle is described once per front entry in the spec, which stays the source of truth.
- A handle is drawn on every leaf of its entry by the headless generator, and listed once per key in the hardware.
- A document without handles builds byte-for-byte the same cut list and hardware, and the same objects.
- Bad handles are refused at validation, by field name, before Blender.

**Non-Goals:**
- Handle drilling (screw-hole positions). That is a later hardware-drilling change.
- Handles on folded modules. These are refused for now.
- Edge profiles or grip rails (Griffleiste), recessed grips, and per-leaf different handles.
- A data-sheet catalogue of handle models; the key is just a price-list key.
- Changing `overall`, the envelope rule or room fit for the handle's 30 mm projection.
- Restyle looks for handles.

## Decisions

1. **`handle` is an object on the front entry, not a module- or build-level list.** The entry already knows its leaves, so one object serves them all. A front's handles then travel with the front through `revise_package`'s `fronts` replacement, as hinges do. A separate list keyed by front ids was rejected because row ids change whenever entries are reordered.

2. **Fields and defaults** (`HandleIn`, `extra="forbid"`, strict):
   - `kind`: `"bar" | "knob"`.
   - `length`: mm, 20–2000. Required for a bar, refused for a knob.
   - `orientation`: `"vertical" | "horizontal" | None`. Bar only.
   - `edge`: `"meeting" | "left" | "right" | None`. Door only; checked on `DrawerIn` and `FlapIn` by a validator.
   - `inset_mm`: `0–10000 | None`.
   - `at_mm`: `0–10000 | None`.
   - `finish`: `"black" | "aluminium" | "steel" | "brass"`, default `"black"`.
   - `key`: a hardware-id pattern, or `None`.

   Defaults are resolved in one place, `derive.handle_spec(front, leaf)`, so derive, the generator and the wording agree. A bar's default orientation is vertical on a door and horizontal on a drawer or flap. Inset is 40 mm, but a drawer's default is half the leaf height. `at_mm` defaults to the middle of the edge. The key defaults to `handle-bar-<length>-<finish>` or `handle-knob-<finish>`.

   **Assumption (TODO(user)): the default finish is `black`, matching the import that prompted this.**

3. **One shared layout function.** `derive.handle_layout(module, t, b)` returns one record per leaf with a handle: the front row id, the leaf index within its row, the key, the finish, and the handle's footprint and centre in the module's front-face frame. It is built on `front_layout`. Three callers use it:
   - `_check_fronts` refuses a handle whose footprint is not at least 10 mm inside its leaf, naming `modules[i].fronts[j].handle` and the leaf size;
   - derive adds hardware lines from it;
   - the generator draws from it.

   This avoids two copies of the placement maths, which is how the generator and cut list stay in step today.

4. **Meeting edges pair leaves from the left.** Leaf `2k` takes its right edge and leaf `2k+1` its left edge. Only an even count is accepted. This matches the Amesbury case and avoids guessing hinge sides, which the schema does not state.

5. **The handle edge per front type:**
   - door: the `edge` given;
   - drawer: the top edge;
   - flap: the edge opposite the hinge (top for a bottom-hinged flap, bottom for a top-hinged one).

   `at_mm` runs along that edge: from the leaf's bottom on a door, from its left on a drawer or flap.

6. **Geometry in the generator.** After the cut-list loop, `_build_scene` draws each `handle_layout` record with `_prism`, as one mesh per handle:
   - a bar is a 12 × 12 mm bar of the stated length, 30 mm proud of the front face, on two 12 × 12 mm posts set 15 mm in from each end, all three merged into one vertex list;
   - a knob is a 16-sided cylinder, 30 mm across and 25 mm deep.

   The front face is the leaf's front plane: module `y` minus the front thickness. The mesh is parented to the module's empty, in a `handles` layer added to `LAYER_NAMES`. Its material is `Handle <finish>`; `_COLOURS` gains `brass`, and the `black`, `aluminium` and `steel` keywords already exist. The object gets `hardware_key`, not `part_id`, so nothing reads it as a cut part. The cut-list count check is untouched, because handles are not in `pieces`. A box primitive for the bar was rejected: three objects per handle would clutter the inspector and the layer map.

7. **Hardware lines and notes.** `_add_front_rows` calls a `_handle_lines` helper next to `_hinge_lines`. The helper adds one line per key, quantity being the leaves with that key, with the item text "Bar handle <length> mm, <finish>" or "Knob, <finish>" and the note "Rule: one handle per leaf". The door row note's "; handle as specified" becomes "; handle <key>" when the entry has a handle; it is unchanged otherwise.

8. **Folded modules are refused** in the schema validator when any front carries a `handle` and `side_folds` is non-empty. Warped leaves (`net`) would need the handle placed on a slanted plane. Refusing keeps the result honest, and a later change can lift it.

9. **Wording.** `describe_front` appends the handle inside the existing parentheses:
   - doors: "2 doors (hinge, bar 900 mm vertical, meeting edges, black)";
   - drawers: "5 drawers 850 mm (bar 160 mm horizontal, black)";
   - a flap: its hinge side, then the handle;
   - a non-default key is appended.

   The context summary and change lines both pick this up. `designer.md` gains one line on handles.

10. **The import template.** One guide line describes `handle`. The starter's door stays without a handle, so the template still derives the starter's rows and hardware unchanged, as the existing template scenario requires.

## Risks / Trade-offs

- **The handle projection is outside `overall`.** Room fit and the envelope ignore up to 30 mm in front of the fronts. This is accepted because hardware never counted before, and a handle is clearance, not structure. It is noted in the guide line.
- **Hand-written handle lines can double up with modelled ones** (the existing `amesbury-wardrobe` v1 has `bar-handle-*` lines). The guide and `designer.md` say to drop the hand-written line when adding a `handle`. Code does not merge the two, because keys may legitimately differ.
- **The default black finish** may not suit every piece. It is marked TODO(user) and is easy to change.
- **Workbench screenshots:** a black bar on a light front is clearly visible. A knob seen front-on at 800 px is only a few pixels, which is acceptable.
- **No change to the generator's existing objects.** The `--blender` suite and a byte-compare of a handle-free template guard the "unchanged" requirement.
