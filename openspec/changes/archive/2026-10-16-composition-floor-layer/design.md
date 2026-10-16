## Context

`composition_contract.place_items` checks each item in order: room outline, opening (`_blocked_opening`), then footprint overlap against every earlier item in the same room. It returns the stored document and one `ItemSubject` per item; `compositions.rule_outcome` is the only consumer of those subjects and runs the configured placement rules (`front_clearance_mm`, `door_swing_clear`) over them. Item keys are checked with `_require_keys(raw, required, optional, label)`, which already supports optional fields and refuses unknown ones by name. The generator builds a stand-in as a box from z = 0 to its height and scales a model to its stated size, so a 10 mm rug already renders correctly once the contract lets it through.

## Goals / Non-Goals

**Goals:**
- Express a flat item (rug, runner, mat) that lies under standing furniture, with the smallest change to the contract.

**Non-Goals:**
- Layering on furniture tops (a lamp on a sideboard) or any stacking in z.
- Floor-layer `piece` items: built pieces are furniture, never flat floor coverings.
- Changing the generator, the render path or the UI.

## Decisions

- **Explicit `layer: "floor"` field, not inferred from height.** Chosen by the owner (2026-10-16). It stays visible in the document and in the composition note, and a single-value enum leaves room for later values without a schema break. Alternative: treat any item ≤ 30 mm as flat. Rejected as implicit.
- **Optional key on `stand-in` and `model` only.** Add `layer` to those two types' optional set in `_parse_item`, so a `piece` carrying it is refused by the existing unknown-field message. The value check and the 30 mm cap live in `_parse_item` next to the size checks, because the stated height is known there.
- **30 mm height cap.** Thick enough for a high-pile rug, too thin for anything a person would trip over or that would need a door clearance. A fixed constant (`FLOOR_LAYER_MAX_MM`) in the contract, not a setting.
- **Overlap rule: refuse only when both items are on the same layer.** The footprint list carries each item's layer, and the existing overlap test runs only when the layers match. Two rugs overlapping is still refused, which keeps the check simple and avoids z-fighting in the render.
- **Openings and rules skipped for floor-layer items.** `_blocked_opening` is not called for them, and they are left out of the returned subjects so `rule_outcome` needs no change. The outline, wall-end and ceiling checks still run.
- **Prompt and tool text.** The `compose_room` argument description and one line in `designer.md` tell the Designer to use `layer: "floor"` for rugs and mats, and the composition note marks a floor-layer item with "(floor layer)", so a later revision keeps the field.

## Risks / Trade-offs

- [A rug under a door swing can jam a door with little undercut] → Accepted by the owner's decision that the door rule is for standing items; the 30 mm cap limits it.
- [A standing item's base sits inside the rug's box in the render] → The rug is at most 30 mm and the sofa's legs or base hide the intersection; no generator change.
- [The Designer forgets `layer` and gets the old overlap refusal] → The refusal is unchanged and the tool description names the field, so the next call can add it.
