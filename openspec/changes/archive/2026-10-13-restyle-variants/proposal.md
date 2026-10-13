## Why

Seeing a custom piece in other colours and finishes, or an approved room in another style, today takes a long conversation: the Designer revises the spec (a new version, a new cut list, a new price) just to look at a colour. Appearance is separate from the spec, so previewing it should not need a spec change. A restyle should be one short request that returns a few draft pictures to choose from, and only the chosen look becomes a real revision.

This is ladder step 1 for the Builder (headless, draft tier). The Designer chooses presets; no live Blender, no bpy from a model.

## What Changes

- **Look presets** (`config/looks.yaml`): named appearance entries for a piece (colour, roughness, metallic, optional simple wood-grain flag), applied **per material slot name** of the piece's spec.
- **Style presets** (`config/styles.yaml`): named room appearances (wall, ceiling and floor colour and roughness, world colour and strength, a colour map for stand-ins by name, and a fallback tint).
- **A restyle render path.** The render script opens a built version's `model.blend` in memory, overrides material values by slot (piece) or by the build report's surface map (room), renders a still, and never saves. No rebuild, no spec write, no change to the version's own `still.png`, `frames/` or `scene.json`.
- **Variants** publish beside the version in `variants/<variant-id>/` with `still.png` and `scene.json` (source `restyle`, preset ids, tier). A variant is marked "appearance only, not a priced material".
- **One tool** `restyle_render` (Builder): takes a target (piece version or composition version), a list of preset ids (or "all"), and a tier of `draft` or `preview`. It states the total estimate once, then renders one still per preset. `final` is refused for a variant.
- **Keeping a look** goes through the existing `revise_package` confirmation as a normal spec change; a style is saved on a composition only through a normal composition revision. Nothing is written back silently.
- The Designer may compose a look from the fixed fields when the owner gives free text; it is validated and anything outside the fields is refused by name.

Render guard: **affected** (variant stills pass the guard at `draft` or `preview`; no raw values; estimate before the run; one single-use authorisation per variant, issued after one batch estimate). bpy allow-list: **not affected** (headless checked-in script, not a live script; the model supplies preset ids and validated data only). Ladder step 1; agents touched: Builder (tool), Designer (picks or composes a look).

## Capabilities

### New Capabilities
- `restyle-variants`: look and style presets, validation of look and style data, the in-memory override render, the variants folder and the `restyle_render` tool.

### Modified Capabilities
- `render-guard`: a restyle render names its source (`restyle`), is limited to `draft` and `preview`, and a batch estimate is the sum of one frame per variant, each variant having its own authorisation.
- `scene-rendering`: variants publish beside the version without replacing its own render files.

## Impact

- New: `config/looks.yaml`, `config/styles.yaml`, a `restyle_render` plugin under `backend/plugins/`, a render script in `backend/app/blender/generators/`, a validation module for look and style data, tests (validation, in-memory override leaves the `.blend` byte-identical, guard refusal of `final`, estimate maths for a batch).
- Changed: the runner and guard accept a `restyle` source; the Blender suite gains a restyle render check (run `--blender` before merging).
- Frontend: a variants strip on the version view (images, preset names, the "appearance only" note, a "use this look" action that starts the usual revision). Homeowner view shows no models, prompts or costs.
- Not touched: the spec schema and `materials` list, cut list, pricing, approved versions, `photoreal-detail`, the allow-list.
- Assumptions to confirm (`TODO(user)`): variants are draft or preview only; the first presets are four room styles and about six piece looks; per-slot override only (no per-part colours).
