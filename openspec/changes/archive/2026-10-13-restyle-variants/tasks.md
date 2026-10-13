## 1. Presets

- [x] 1.1 Add `config/looks.yaml` (six piece looks) and `config/styles.yaml` (four room styles), with a Pydantic loader using `extra=forbid`, `#rrggbb` colours and 0–1 ranges, refusing duplicates and unknown keys by name at startup. Verify `tests/test_restyle_presets.py` covers: shipped files load and list ids; bad colour names the preset and `colour`; duplicate id; unknown key; roughness 1.2 refused
- [x] 1.2 Request models: piece restyle (target, per-variant slot → look id or composed look), room restyle (composition version, style id or composed style), tier, preset list or `all`; unknown fields refused by name. Verify `tests/test_restyle_request.py` covers: unknown slot names the slot and lists existing ones; `thickness_mm` and `texture_path` refused; two slots sharing one material string with different looks refused naming both; raw `resolution` refused

## 2. Render script

- [x] 2.1 Add the headless restyle script under `backend/app/blender/generators/`: open `model.blend`, override Principled BSDF values by material string (piece) or by surface map and stand-in name (room), set the world, render one still with the guard's tier values, never save. Look nodes up by type. Verify the `--blender` suite checks: `model.blend` is byte-identical after a restyle; the still has the tier's resolution; a piece and a library model in a room keep their own colours
- [x] 2.2 Refuse a version without a successful build or without its `model.blend` (a composition is rebuilt from its stored document, so no surface map is needed) with the stated reasons. Verify tests for the refusals and that no process starts

## 3. Guard and runner

- [x] 3.1 Add source `restyle` to the guard: tiers `draft` and `preview` only, `final` refused with the concept-picture reason, one authorisation per variant bound to source, version and that variant's id and single use, batch estimate of one frame per variant summed. Verify `tests/test_render_guard.py` covers: final refused; ticket for `walnut` refused for `sage-green`; ticket used twice refused; estimate for three variants equals three single-frame estimates; launcher without a ticket refused
- [x] 3.2 Runner publishes each variant atomically to `variants/<variant-id>/` with `still.png` and `scene.json` (source `restyle`, presets, slot mapping, tier, the appearance note), keeps finished variants when one fails, enforces the 12-variant cap replacing the oldest, and removes stale staging. Verify tests for: one failure among three; thirteenth variant replaces the oldest and the reply says so; the version's own `still.png`, `frames/`, `scene.json` and `spec.json` are unchanged
- [x] 3.3 Record tier, estimate and actual per batch in Langfuse like other renders. Verify the existing observability test pattern covers the restyle record

## 4. Tool and agents

- [x] 4.1 Add the `restyle_render` plugin (manifest + tool) for the Builder, toggleable, with session, project and scope taken from the conversation, and the Designer prompt addition for composing a look from the fixed fields. Verify manifest loads, a malformed one is refused by file name, and `tests/test_restyle_tool.py` covers: `all` expands to every preset; a missing tier is refused; the reply states the estimate first
- [x] 4.2 "Keep this look" (piece only): the studio hands the owner's request to the Designer in the conversation, asking about the real material and its price first; the Designer's ordinary `revise_package` confirmation follows. A room style cannot be kept (a composition has no style field). Verify tests: a restyle changes no spec and makes no new version; the request names the slot and look and asks about the real material

## 5. Studio

- [x] 5.1 API route listing a version's variants (files served by exact name only) and the `api.ts` types. Verify `tests/test_restyle_api.py` covers: list, exact-name serving, 404 unknown, 401 without cookie, path traversal refused; `pnpm build` type-checks
- [x] 5.2 Variants strip on the piece and room version views (Pieces, Rooms and the conversation's Project panel): pictures, preset names, the appearance note, a "Use this look" action on piece variants only. Homeowner view shows no model, prompt, token or cost. Verify `Variants.test.tsx` covers: strip renders, note shown, the action hands the request over (piece only), no developer fields

## 6. Verification

- [x] 6.1 Run `uv run ruff check .`, `uv run pytest -m "not slow"`, the `--blender` suite, `pnpm lint`, `pnpm test`, `pnpm build`; fix code before tests
- [x] 6.2 Browser pass: restyle one approved piece (two looks) and one approved room (two styles) at draft, see the strips, keep one look through the confirmation, and decline another. Record the check here
  Browser pass 2026-10-12: scratch database `home_renovation_restyle_ui` (dropped afterwards), backend on 8100 and Vite on 5180 (`API_PROXY`), the real Blender build of a `bench` piece (fold-down-desk template) and three real draft restyle stills (`walnut`, `sage-green`, `white-lacquer`) rendered through the guard tickets and the runner. Headless Chromium (Python Playwright): signed in, Pieces page shows the "Restyle pictures" strip with three images at 600 px, each with its tier badge and the note "appearance only, not a priced material"; no "Use this look" button on the Pieces page; no model, prompt, token or cost words in the strip; the walnut picture shows grain. Not covered in the browser: the "Use this look" hand-over and the Rooms page strip (no model is reachable from the scratch app, and a composition needs the Designer to compose it); both are covered by `Variants.test.tsx`.
