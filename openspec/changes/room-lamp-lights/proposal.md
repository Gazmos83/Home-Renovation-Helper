## Why

The end-to-end review of 2026-10-15 asked how to control the light in renders, and said that the light from lamps should be defined. Today a room is lit only by a fixed rig: three area lights scaled to the floor area (`build_room_scene._build_lights`) and, for a shell or apartment, a sun. A lamp placed in a composition is just geometry, such as the pendant from `composition-ceiling-layer`, and it gives no light. The schema cannot say "this lamp gives 800 lm of warm light". On 2026-10-18 the owner decided that a lamp item, either a library model or a stand-in, gets an optional light with a type, a brightness in lumens and a colour temperature in kelvin, and that the room rig dims when lamps are on. This is a generator-extension request (ladder step 2).

## What Changes

- A `stand-in` or `model` item in a room composition MAY carry `light`:
  - `type`: `"point"` (a bulb that shines all round) or `"spot"` (a downlight or reading lamp that shines down in a cone);
  - `lumens`: a whole number, 10–10 000;
  - `kelvin`: a whole number, 1800–6500.

  Any other key or value is refused by name. A `piece` and a floor-layer item do not take `light`: a piece refuses it as an unknown field, and a floor-layer item refuses it naming the item and `light`.
- **Where the light sits.** It is centred on the item's footprint. On a ceiling-layer item it sits 50 mm above the item's lowest point, inside the shade. On a standing item it sits 50 mm below the item's top. TODO(user): an explicit offset for a library model whose shade is somewhere else (an arc lamp) is left out until the owner needs one.
- **The lamp does not shadow its own light.** The item's own meshes cast no shadow, so a light inside a stand-in box or a closed shade still reaches the room.
- **Brightness.** The build converts lumens to Blender watts with one configured factor, `watts_per_lumen` in a new `config/lighting.yaml`. The default is 0.05, so an 800 lm bulb becomes 40 W. TODO(user): this is calibrated from the first approved draft and can be changed by hand. Colour temperature becomes the light's colour, computed by code from the kelvin value.
- **The room rig dims.** When a room holds at least one item with a light, that room's three rig lights are multiplied by `rig_factor_with_lamps` (same file), default 0.5. TODO(user): the owner checks the factor on the first draft. A room without lamp lights is lit exactly as today.
- **Limit.** A composition holds at most `max_lights` item lights (same file), default 16. More are refused naming the limit. The limit keeps Eevee within its light budget and keeps renders on the laptop predictable.
- **The build report** lists, for each item with a light, its type, lumens, kelvin, watts and the light's position. The report also lists each room's rig factor. The composition note shows the light, for example "(light 800 lm, 2700 K)". The `compose_room` tool description and the Designer instructions say when to add a light and give typical values.
- **Renders.** Draft (Eevee) and final (Cycles) renders, restyle variants and the detail pass's copy all rebuild or open the same scene, so they show the lamp lights. A restyle changes surfaces and the world colour, not lamp lights.

No breaking change: documents without `light` are checked and built exactly as before, and stored versions are not rewritten.

Ladder step 2 (generator extension: schema, checks and composition generator). Agents touched: the **Designer** (`compose_room` description and instructions). The **Builder** renders unchanged. **Lighting & materials** finds the lamp lights by name in the detail-pass copy. **Render guard: not affected.** Every render still passes through it, and tiers, estimates and the `final` approval stay the same. More lights make Cycles slower, which is noted as a risk. **bpy allow-list: not affected.** The change is in a checked-in headless generator, not a live script.

Depends on `composition-ceiling-layer` (in progress, uncommitted), which gives a pendant its `base_mm`. It lands after the sibling changes `hidden-room-items` and `room-floor-finish`, which also touch `composition_contract.py`. `room-led-strips` builds on this change.

## Capabilities

### New Capabilities

(none)

### Modified Capabilities

- `room-composition`: a stand-in or model item may carry a light; the headless build adds that light, keeps the lamp's own meshes from shadowing it, dims the room rig, and reports the lights.

## Impact

- `backend/app/blender/composition_contract.py`: parse and check `light`, refuse it on floor-layer items, enforce `max_lights`, and record on the resolved item the light's position, watts and colour, and on each resolved room its rig factor.
- `backend/app/blender/generators/_composition.py`: add a point or spot light per lit item from the resolved values, turn off shadow casting for the lamp's meshes, add light entries to the report, and pass the rig factor to `build_room_scene._build_lights`.
- `backend/app/blender/generators/build_room_scene.py`: `_build_lights` takes an optional energy factor (default 1.0), so piece room scenes are unchanged.
- `backend/app/blender/lighting.py` (new, pure Python): loads `config/lighting.yaml` and converts kelvin to linear RGB and lumens to watts. The code is shared with `room-led-strips` and testable without Blender.
- `backend/config/lighting.yaml` (new): `watts_per_lumen`, `rig_factor_with_lamps` and `max_lights`, loaded by `app/blender/lighting.py`; a malformed file stops startup by name, as `render.yaml` does. `render.yaml` and the tiers are not touched.
- `backend/plugins/compose_room/tool.py`, `backend/app/agent/instructions/designer.md`, `backend/app/agent/prompts.py` (`composition_note`): describe and show the light.
- `backend/app/agent/instructions/lighting.md`: one line saying that lamp lights are named `LGT_Lamp_<item id>`.
- Tests: `test_composition_contract.py`, `test_compose_room.py`, `test_house_file.py`, a new `test_lighting.py`, and the `--blender` suite's `test_composition_blender.py`.
- Frontend: no change. The Rooms page lists items by id, type and name.
- No migration: compositions are stored as JSON documents, and `light` is optional.
