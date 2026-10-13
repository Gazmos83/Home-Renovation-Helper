## Context

See proposal.md for motivation. Facts the approach rests on, from reading the code:

- The published `spec.json` is a derived file with no `materials`; the validated spec, with its slots, is the version's stored `input.json`.
- The build generator names each Blender material by the spec's material string (`bpy.data.materials.new(name)` in `_material`), and takes its colour and roughness from a keyword table, not from the spec. Appearance is therefore already separate from the spec's slot data (`materials: {slot: {material, thickness_mm}}`).
- A composition build publishes a surface map (walls, floor, ceiling, items → mesh names). Stand-ins are boxes with a `#rrggbb` colour.
- Renders go through the guard; `render_still.py` renders one still at the tier's resolution and engine and takes its tier values from a guard ticket.
- Spec JSON is the source of truth: nothing in this change writes a dimension or material back.

## Goals / Non-Goals

**Goals:**
- One request returns several draft pictures; no rebuild per variant.
- The approved version's files stay byte-identical.
- Presets are data, so adding a style is a config edit.

**Non-Goals:**
- Photoreal quality: Eevee drafts show colour and mood, not realism. No AI image model, no textures from files, no new gateway slot.
- Per-part colours (slot granularity only), changing geometry, or moving furniture (that is a composition revision).
- Final-tier variants and live Blender work.

## Decisions

**1. Override at render time, in memory, on the built `model.blend`.** The restyle script opens `model.blend`, edits material node values, renders one still, and exits without saving. Alternative: rebuild per variant from a spec plus look file. Rejected: a rebuild per variant costs more time and risks writing build files; rendering from the built file is the same cost as an ordinary still.

**2. Piece looks resolve slot → material string → Blender material.** The backend reads the version's stored spec (`input.json`), finds the material string of each named slot, and edits the Blender material of that name. Two slots that share a material string share one Blender material, so a request giving them different looks, or naming only one of them, is refused naming both slots. Alternative: rename materials per slot in the generator. Rejected: it changes the build for approved versions.

**3. A room restyle rebuilds the composition in memory and uses its live surface map.** The script rebuilds the room from the version's stored document, exactly as the composition renderer does, then reads the surface map of that scene (walls, floor, ceiling) and finds stand-ins by item name. Items of type `piece` and `model` are skipped. Each surface kind gets its own new material so no shared material leaks a colour. Alternative: read the published `report.json`. Rejected: the rebuilt scene already holds the map, and the camera, lights and walls are the ones an ordinary room still uses.

**4. Presets in two YAML files, validated at startup like `config/render.yaml`.** Pydantic models with `extra=forbid`, same pattern as the tier config. Free-text looks are composed by the Designer into the same model and used for one request only; nothing is persisted unless the owner adds it to the file.

**5. Guard: a restyle is a third render source, draft and preview only.** One authorisation per variant, bound to the source, the version and that variant's id (single use), all issued together after one batch estimate. Estimate is one frame per variant at the tier's megapixels and engine multiplier, summed. `final` is refused in code, covered by a test. Alternative: allow `final` with the typed yes. Rejected: a restyled final would look like a finished render of a design that does not exist.

**6. Variants are files, not database rows.** `variants/<variant-id>/{still.png,scene.json}` under the version, matching the package-folder rule of no new table. `variant-id` is derived from tier, preset ids and a short counter, never from model text. Cap of 12 per version, oldest replaced.

**7. "Keep this look" hands a request to the Designer.** No new write path: the studio sends the owner's request (slot, look, ask about the real material and its price) into the conversation, and the Designer's ordinary `revise_package` confirmation follows. A room style cannot be kept: a composition has no style field, so room variants are view-only until a separate change adds one.

**8. One tool, `restyle_render`, in the Builder's plugin set.** Arguments: target (package id + version, or composition + version), presets (list or `all`), tier. Session, project and scope come from the conversation, not model arguments.

## Risks / Trade-offs

- [Draft look reads as plastic, not wood] → Optional grain flag uses a simple procedural node; the note says appearance only; realistic wood waits for a later image or texture change.
- [A look is mistaken for a real material] → Fixed note in `scene.json` and UI; keeping a look runs the usual priced-material check.
- [Blender 5.x node API drift] → Look nodes up by type (Principled BSDF), per the repo rule; run the `--blender` suite.
- [Shared material strings couple slots] → Refuse conflicting looks by slot name (decision 2).
- [Batch holds the one Blender process for several stills] → One process at a time as today; each still is seconds at draft; failures reported per variant.
- [Disk growth] → 12-variant cap per version.

## Migration Plan

Additive. New config files with shipped presets; no database migration; existing versions render unchanged. Rollback: remove the plugin and config; variant folders are inert files.

## Open Questions

- Exact shipped preset names and values (colours and roughness) — can be set during implementation and edited later.
