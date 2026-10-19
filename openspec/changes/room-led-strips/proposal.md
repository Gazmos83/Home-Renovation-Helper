## Why

The end-to-end review of 2026-10-15 said that the light from LED strips should be defined. A room composition has no way to describe an LED strip today. A strip cannot be a stand-in, because a stand-in stands on the floor or hangs from the ceiling and gives no light (`room-lamp-lights` adds light to lamps only). On 2026-10-18 the owner decided that an LED strip is a new composition item type along a wall or under a cabinet, with a length, lumens per metre and a colour temperature in kelvin. This is a generator-extension request (ladder step 2).

## What Changes

- **A fourth item type, `led-strip`**, with:
  - `name`;
  - `length_mm`: 100–10 000;
  - `lumens_per_m`: 50–3000;
  - `kelvin`: 1800–6500;
  - `mount_height_mm`: the height of the strip above the floor, from 0 up to the room's ceiling height minus 10;
  - `facing`: `"down"` (under a shelf or wall cabinet; the default), `"up"` (cove light on top of a cabinet or a ledge) or `"out"` (into the room);
  - a wall placement `{wall, offset_mm}`. A free-standing placement is refused, because a strip is always fixed to a wall.

  It takes no `layer`, `light`, `colour` or size fields; any of them is refused by name.
- **Checks.**
  - A strip must lie within its wall (`offset_mm + length_mm` up to the wall length) and below the ceiling.
  - It is exempt from the footprint overlap check with standing, floor and ceiling items. It is 10 mm thick and sits on the wall surface, so it may run behind or under furniture placed against that wall.
  - Two strips on the same wall whose lengths and heights overlap are refused.
  - A strip that crosses a door or window on its wall, at a height within that opening, is refused naming the opening.
  - Placement rules do not apply to strips.
- **Under a cabinet.** Today's schema cannot hang a wall cabinet at a height. A strip under the wall cabinets of a kitchen piece is therefore placed by its wall, offset and `mount_height_mm` (the underside of the cabinets) with `facing: "down"`, not attached to the cabinet. Attaching a strip to a placed item, so that it follows when the item moves, is a non-goal for this change. TODO(user): propose it if the owner needs it.
- **Rendering.** Each strip is built as a 10 × 15 mm emissive bar along the wall in its kelvin colour. It also gets one rectangular area light of the same length, facing as stated. The area light's power is `length_m × lumens_per_m × watts_per_lumen`, the factor from `room-lamp-lights`. Strips count towards the composition's `max_lights` cap and towards the room-rig dimming from `room-lamp-lights`.
- **Build report, note and Designer.**
  - The build report lists each strip's length, lumens per metre, kelvin, watts, wall, offset, height and facing.
  - The composition note shows "led-strip: N mm on wall W at H mm, facing F".
  - The `compose_room` tool description and the Designer instructions describe the type.
  - The surface map counts strips under "items".

No breaking change: existing documents carry no `led-strip` items and build as before.

Ladder step 2 (generator extension: schema, checks and composition generator). Agents touched: the **Designer** (`compose_room`). The **Builder** renders unchanged. **Lighting & materials** finds the strips by name (`LGT_Strip_<item id>`) in the detail copy. **Render guard: not affected.** Every render still passes through it with the same tiers, estimates and `final` approval. **bpy allow-list: not affected.** The change is in a checked-in headless generator.

Depends on `room-lamp-lights`, for the lighting helpers, `config/lighting.yaml`, the light cap and the rig factor. That change itself follows `composition-ceiling-layer`, `hidden-room-items` and `room-floor-finish`.

## Capabilities

### New Capabilities

(none)

### Modified Capabilities

- `room-composition`: a new `led-strip` item type with its fields, wall-only placement and its own placement checks; the headless build adds an emissive strip and an area light per strip and reports them.

## Impact

- `backend/app/blender/composition_contract.py`: `led-strip` in `ITEM_TYPES` and `_ITEM_FIELDS`, the wall-only placement, the opening and strip-overlap checks, exemption from the furniture overlap check and the placement rules, and the resolved strip geometry (start and end in plan, height, facing, watts, rgb). Counted in the light cap and the room's rig factor.
- `backend/app/blender/generators/_composition.py`: `_place_led_strip`, an emissive bar mesh plus an `AREA` light with a `RECTANGLE` shape.
- `backend/app/compositions.py` (`rule_outcome`, the proposal summary) and `house_file.placed_items`: strips carry no size fields, so their size-dependent code paths skip them or derive the size from the length.
- `backend/plugins/compose_room/tool.py`, `backend/app/agent/instructions/designer.md`, `backend/app/agent/prompts.py` (`composition_note`, `_item_place`), and `backend/app/agent/instructions/lighting.md`.
- Tests: `test_composition_contract.py`, `test_compose_room.py`, `test_house_file.py`, and the `--blender` suite's `test_composition_blender.py`.
- Frontend: no code change expected. The Rooms page lists items by id, type and name; the apply phase checks that an item without width, depth and height fields does not break the list or the dimensions overlay.
- No migration.
