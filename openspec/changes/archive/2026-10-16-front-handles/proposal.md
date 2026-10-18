## Why

A handle exists today only as a hardware line someone writes by hand: it is listed and priced, but nothing in the spec says which front it belongs to or where it sits, so no build draws it. The model, the inspector, the screenshots and every turntable show bare fronts. Flush drawer fronts are then barely distinguishable from the doors around them. The `amesbury-wardrobe` import (a copy of a Höffner six-door wardrobe with black bar handles) made this visible: its handles are in `hardware.csv` but nowhere in the model.

## What Changes

- A door, drawer or flap entry MAY carry a `handle`:
  - `kind`: `bar` or `knob`.
  - `length`: required for a bar, refused on a knob.
  - `orientation`: `vertical` or `horizontal`, for a bar only. Doors default to vertical; drawers and flaps default to horizontal.
  - `edge`: doors only. `meeting`, `left` or `right` says which edge of each leaf the handle sits on. `meeting` puts each pair's handles on the edge they share and needs an even count. The default is `meeting` for an even count, else `right`.
  - `inset_mm`: the distance from that edge to the handle's centre line.
  - `at_mm`: the handle's centre along that edge.
  - `finish`: `black`, `aluminium`, `steel` or `brass`.
  - `key`: an optional hardware key, used like a hinge key.
  Defaults put a handle where a joiner would. One `handle` serves every leaf of its entry.
- A push-latch door with a handle is refused by name. So are a `meeting` edge on an odd count, a handle that does not fit inside its leaf, and a handle on a module with `side_folds` (not supported yet; refused rather than drawn wrongly).
- Every leaf with a handle draws one handle object in `model.blend`, `model.glb`, the screenshots, the inspector and every render. The object is named `<front row id>-handle` (`#n` for further leaves) and lies in a new `handles` layer, parented to its module. A bar is drawn on two posts; a knob as a short cylinder. It is hardware, not a cut part: it never appears in the cut list, and it does not change `overall` or the envelope check.
- The hardware list gains one line per handle key, with one handle per leaf, priced from the price list like any hardware key. A front without `handle` is drawn and listed exactly as before. Hand-written handle lines are left alone, and the guide says not to write both.
- `revise_package` changes handles through the module's `fronts`, as it changes hinges today. Change lines and the Designer's context describe each front's handle when set.
- The import template's guide describes `handle`.

Ladder step 2 (generator extension): the schema, the derive rules and the headless generator `build_custom_build.py` grow. It touches the **Designer** (revise_package change lines, context summary, instructions) and the **Builder** (headless build). The **render guard** and the **bpy allow-list** are **not affected**. There is no new render path and no live script, and tiers are unchanged. Handle meshes are made by the checked-in headless generator with `bpy.ops.mesh` primitives and `bpy.data`, as boards are today.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `furniture-packages`:
  - new requirement that a front can carry a modelled handle, with its hardware line;
  - the published `spec.json` layers include `handles`.
- `design-agents`: change lines and the Designer's context name a front's handle when set.
- `design-import`: the import template's guide describes `handle` and says not to also list the handle as a hardware line.

## Impact

- `backend/app/blender/schemas.py`: a `HandleIn` model; an optional `handle` on `DoorIn`, `DrawerIn` and `FlapIn`; the push-latch, knob, odd-meeting and folded-module refusals.
- `backend/app/blender/custom_build/derive.py`:
  - a `handles` entry in `LAYER_NAMES`;
  - a `handle_layout(module, t, b)` shared by derive and the generator, giving each handle's placement in the module's front frame and refusing a handle that does not fit its leaf;
  - one hardware line per handle key;
  - the door row note names the handle.
- `backend/app/blender/generators/build_custom_build.py`: draws each handle from `handle_layout` after the cut-list pieces, with a finish material (`brass` added to `_COLOURS`).
- `backend/app/agent/revise.py` (`describe_front`), `backend/app/agent/prompts.py` (the context summary uses `describe_front`), `backend/app/agent/instructions/designer.md`, and `backend/fixtures/packages/templates/import-template.json`.
- Tests: schema, derive, revise and import template; `--blender` build tests.
- Frontend: no code change. The inspector builds its layer switches from `spec.json` layers, so `handles` appears as a switch when a build has handles; a browser pass confirms it.
- Unchanged:
  - drilling (handle screw holes are a later change);
  - restyle looks (these apply per material slot, and handles are not one);
  - room compositions (these import `model.glb`, so handles come along).
