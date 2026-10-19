## Context

See proposal.md (Why). Current state:

- `composition_contract._parse_item` builds the normalised item from fixed per-type keys (`_ITEM_FIELDS`). `layer` is the only optional key, and an unknown key is refused by `_require_keys`. `place_items` resolves each item with its room's geometry. After `composition-ceiling-layer` it records `base_mm` for a ceiling-layer item.
- `generators/_composition._build_shells` calls `build_room_scene._build_lights(state)` once per room. That function adds three area lights (`LGT_Ceiling`, `LGT_Key`, `LGT_Fill`) whose energy scales with floor area. `build_scene` places items and appends one report entry each.
- `render_composition.py` and `render_restyle.py` rebuild the scene with `composition.build_scene` from the stored document. The detail pass opens a copy of `model.blend`. A light added in `build_scene` therefore appears in every downstream use.
- `build_shell.py` and `build_composition.iso_camera` add a sun for shells and apartments.

## Goals / Non-Goals

**Goals:**
- A lamp in a composed room gives light that the owner can state in shop terms (lumens, kelvin), in every render tier.
- Computation that can be tested without Blender: the generator only applies values already resolved by the contract.

**Non-Goals:**
- Lights on built pieces (a lit display cabinet). That needs a spec-JSON change in `furniture-packages`, not a composition change.
- Emissive lampshade materials or glowing bulbs. The lamp's own appearance stays as modelled.
- Dimmers, switching lamps on and off per render, or light scenes. A light is part of the version, so a change means a new version.
- An `area` lamp type. Area lights belong to `room-led-strips`.
- IES profiles, cone angles chosen by the owner, or a per-model shade offset (TODO(user) in the proposal).

## Decisions

1. **`light` is a nested object on stand-in and model items.** It is parsed by `_parse_light(raw, item_id)` with its own `_require_keys` call, so an unknown key inside it is refused by name, consistent with the rest of the contract. A flat set of `light_*` keys was rejected because it scatters one concept across three fields, and a fourth field would be needed for `room-led-strips`.

2. **Two types: point and spot.** `point` is a Blender `POINT` light with a 50 mm radius (soft shadows). `spot` is a `SPOT` light pointing at -Z with a fixed 70° cone and blend 0.3. These cover a pendant, a table lamp, a floor lamp and a downlight. A cone chosen by the owner would need another field and was left out.

3. **Position is computed by the contract.** `place_items` already knows the footprint centre, the item's height and, for a ceiling item, `base_mm`. It records `light: {..., "watts": w, "rgb": [r, g, b], "at_mm": [x, y, z]}` on the resolved item. For a ceiling item z = `base_mm` + 50. For a standing item z = height − 50, clamped to at least half the height for very short items. The generator places the light at `at_mm` with no geometry of its own. Rejected alternative: deriving the position in bpy from the item's mesh bounds, which cannot be unit-tested and repeats the contract's logic.

4. **Lumens to watts by one configured factor.** `watts = lumens × watts_per_lumen`, with a default of 0.05. A physical conversion (1 W of 555 nm light ≈ 683 lm) gives about 1.2 W for an 800 lm bulb. That is invisible next to the rig's 150 W-plus area lights, whose power was tuned for exposure, not physics (`_build_lights` docstring). A single factor that the owner calibrates from one draft is honest about that. It lives in `config/lighting.yaml`, not `render.yaml`, because the tiers loader is strict and the guard owns that file.

5. **Kelvin to RGB in Python.** `lighting.kelvin_to_rgb(k)` uses the Tanner Helland blackbody approximation, normalised so its largest channel is 1.0 and converted to linear. The light's `color` is set from it. This works identically in Eevee and Cycles and needs no shader node. Rejected alternative: a Blackbody node in a light node tree, which Eevee ignores.

6. **The lamp does not shadow itself.** For every mesh of a lit item, the generator sets `visible_shadow = False`. A point light inside a closed stand-in box or a GLB shade would otherwise be fully occluded. The cost is that the lamp casts no shadow on the room. That is acceptable for a draft, and the detail pass can refine it on its copy.

7. **The rig dims per room.** `place_items` records `rig_factor` on each resolved room: `rig_factor_with_lamps` when any item in that room has a light, else 1.0. `_build_lights(state, factor=1.0)` multiplies its three energies by the factor. The default keeps piece room scenes (`build_room_scene` main path) unchanged. The sun, if any, is left alone, so daylight stays.

8. **A light cap of 16.** Eevee in Blender 5.x handles far more lights, but each shadowed light adds shadow-map cost and makes the laptop's draft estimate less reliable. The cap is a config value. `room-led-strips` counts its strips against the same cap.

9. **Naming for the detail pass.** Lights are named `LGT_Lamp_<item id>`. `lighting.md` gains one sentence, so Lighting & materials can adjust a lamp on its detail copy without touching the spec.

## Risks / Trade-offs

- [The default factor 0.05 makes rooms too bright or too dark] → It is a config value. The first `draft` of a lit room calibrates it, and the owner sets it by hand (TODO(user)).
- [Cycles is slower with several shadowed point lights, so the guard's estimate is optimistic] → The estimate formula is unchanged. The first approved `final` of a lit room is compared with its estimate, and the Cycles multiplier is recalibrated as usual.
- [A library model's shade is not at its top (arc lamp, wall sconce)] → The light sits at the footprint centre near the top. The screenshot shows it before any render. An explicit offset is TODO(user).
- [The lamp casting no shadow looks slightly off in a `final`] → Accepted for this step. The detail pass can turn shadows back on for its copy.

## Migration Plan

None. Stored versions have no `light` and no `rig_factor`, so they build with factor 1.0 exactly as before. Rollback is reverting the change, after which documents carrying `light` are refused by name.
