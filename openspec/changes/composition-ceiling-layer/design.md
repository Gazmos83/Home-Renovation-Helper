## Context

See proposal.md (Why). `composition_contract._parse_item` already accepts an optional `layer` on `stand-in` and `model` items (value `"floor"` only) and refuses it on a `piece` as an unknown field. `place_items` checks items in order. For each item it checks the room outline, the openings (`_blocked_opening`, skipped for floor-layer items) and footprint overlap against earlier items in the same room. Two footprints are compared only when both items are on the same layer. Each check reads the item's room geometry, including `height_mm`. Floor-layer items are left out of the rule subjects, so `compositions.rule_outcome` skips them. The generator (`generators/_composition.py`) has two placement paths. `_pose` sets a piece's or model's lowest point at z = 0, and `_place_stand_in` builds its box from z = 0. `_final` reports `lowest_mm`, and `test_composition_blender.py` asserts it is 0 for every item. `house_file.placed_items` already carries `layer`, and `composition_note` already marks the floor layer.

## Goals / Non-Goals

**Goals:**
- Hang a library model or stand-in from its room's ceiling, and let it pass over furniture it clears.

**Non-Goals:**
- Making the lamp emit light in renders. It renders as geometry only; lighting stays with the detail pass at ladder step 3.
- Ceiling-layer `piece` items. Built pieces are furniture, never hung.
- Items at an arbitrary height, such as a wall shelf at 1500 mm or a lamp on a sideboard.
- A UI for the layer. The Designer sets it, as with the floor layer.
- A head-clearance rule for low pendants over walkways. TODO(user): a `warn` design rule could flag a ceiling item hanging lower than about 2000 mm outside any furniture footprint. It is left out until the owner asks.

## Decisions

- **A second value for the existing `layer` field, not a new field.** The floor-layer design kept `layer` as an enum so that it could gain values without breaking the schema. `"ceiling"` is the first new value. Rejected alternative: an `elevation_mm` field, which needs its own validation, and the owner would have to restate the ceiling height for every lamp.
- **Stated height runs from the ceiling to the lowest point.** It matches how a pendant is sold (the "Gesamthöhe" includes the cable and canopy) and how the library model measures, so the library's stated size is used unchanged. The existing "taller than the ceiling" check also covers a pendant longer than the room is high.
- **Height ranges decide overlap between layers.** Each item gets a height range from the floor or the ceiling (`base`, `base + h`). Footprint overlaps involving a ceiling-layer item are refused only when the height ranges also overlap. Ranges that only touch are allowed. Floor and standing items keep today's rule: they may overlap each other, and items on the same layer may not. That keeps the rug behaviour unchanged. Two ceiling items whose footprints overlap both reach the ceiling, so they are refused without a separate rule.
- **Openings by height for ceiling items.** `_blocked_opening` already skips a window when the item's height is at or below the sill. A ceiling item runs the same footprint test only when its lowest point is below the top of the opening (`sill_mm + height_mm`). Otherwise it is skipped, so a short pendant in front of a door passes.
- **No placement rules for ceiling items.** `front_clearance_mm` and `door_swing_clear` describe floor space in front of furniture. Like floor-layer items, ceiling-layer items are left out of the rule subjects, so `rule_outcome` needs no change.
- **`base_mm` on the resolved item, and only for ceiling items.** `place_items` knows each item's room height, while the generator only has the resolved rooms list. Recording `base_mm` (ceiling height minus item height) on the resolved item keeps the generator free of room lookups. An old stored document without the key builds at 0 as before. Rejected alternative: having the generator look up the room's `height_mm` by name, which repeats the contract's logic in bpy code.
- **Generator change is one offset.** `_pose` takes the z offset (`base_mm` in metres) in place of 0.0, and `_place_stand_in` sets `obj.location.z` from it. `_final` already reports the lowest point, so the report states `base_mm` with no change. The blender test asserts `lowest_mm == base_mm`, falling back to 0 when there is no `base_mm`.
- **Prompt and tool text.** One clause in the `ComposeRoomArgs.items` description and in `designer.md` tells the Designer about the ceiling layer: pendant lamps and other hung items use `layer: "ceiling"`, with a height that includes the cable. `composition_note` adds "(ceiling layer)".

## Risks / Trade-offs

- [A library pendant whose GLB has its canopy at the bottom (exported upside down) hangs upside down] → The generator scales and lifts the model but never flips it. The owner sees the screenshot before any render. The Calisto GLB built for this request has its canopy at the top.
- [A pendant over a sofa in an apartment room with a lower ceiling than the rest of the flat] → The ceiling height comes from the item's own room, so a lower room ceiling is respected.
- [A stretched cable looks thick when the stated height differs from the model's own] → The stated size is the library size by default, so the scale is 1. Restating the height stretches the cable, the shade and the canopy along z alike, as it does for any model today.
- [Hidden ceiling clash with a ceiling-mounted object not in the composition (beam, light fitting)] → Out of scope. The room shell holds no ceiling fixtures.

## Migration Plan

None. Stored versions keep building as before: they have no `"ceiling"` layer and no `base_mm`. Rollback is reverting the change, after which documents carrying `layer: "ceiling"` are refused by name.
