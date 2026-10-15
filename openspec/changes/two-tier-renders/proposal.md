## Why

The `draft` (12 × 600², Eevee) and `preview` (24 × 1000², Eevee) tiers do the same job at two sizes, so the owner asked (2026-10-15) for one sharper draft and no preview. The same conversation set where each render runs. Step 7 should always give a turntable on the laptop. Restyles should be turntables too, because they belong to the build-and-review loop (steps 5–9). The detail pass (step 10) is a lighting loop: a Cycles turntable takes hours on this CPU, so on the laptop it should produce stills only, and a detail turntable should run only on the render server.

## What Changes

- **BREAKING: two tiers.** The render configuration holds exactly `draft` and `final`. `preview` is removed, and a request naming it is refused like any unknown tier.
- **Draft at 800 × 800.** `draft` becomes 12 frames at 800 × 800 on Eevee (was 600 × 600). `final` is unchanged (36 × 1500², Cycles, typed "yes").
- **Step 7 is always a turntable.** The Builder's `render_turntable` refuses a `draft` still of a piece version on its own and says a draft of a piece is a turntable. Draft stills stay available for a piece placed in a room, a shell, a composition and the Studio's render route. Drafts already run only on the laptop; that is unchanged.
- **Restyles become draft turntables.** `restyle_render` accepts `draft` only and renders each variant as a 12-frame turntable, still with one guard ticket per variant. A variant folder holds `frames/`, `viewer.html`, `scene.json` and a `still.png` poster (its first frame), so listings and pictures keep working.
- **Detail renders on the laptop are stills only.** The guard refuses a detail turntable that would run locally and says a detail turntable runs on the render server. When finals go to the render server, a detail turntable is allowed as now. `render_detail` defaults to a still.
- **Stored `preview` becomes `draft`.** A migration relabels `preview` to `draft` in render runs, thread notices (tier and notice wording), and the tier recorded in version and variant `status.json`/`scene.json` files. Variant folder ids are not renamed.
- **A Renders tab in the inspector.** It sits beside Model and Cut list and lists every published render of the version: still, turntable, room, detail and restyle variants. A turntable plays as a frame scrubber (slider, drag, arrow keys) from the frames already published, and every item has the thumbs-up/down and comment controls. This is the only place in the app where a turntable can be watched and rated. That includes the detail turntable rendered on the render server, which today has no view at all. The Pieces page keeps its still cards, and a notice's Review button opens the tab on that render. Images stay files under the render root; nothing new is stored in the database.
- **Piece variants are rateable.** Each restyle variant of a piece is recorded as a render run (`variant:<id>`). It can be rated in the Renders tab or in chat, after a yes as for any render. The rating reaches the Designer's and Lighting's context marked "appearance only, not a priced material", so a liked look informs the next real revision. Composition variants stay viewable only.
- **Docs.** CLAUDE.md §6 tier table, the Builder and Lighting instructions and the tool descriptions name two tiers.

**Ladder step and agents.** Step 1 (spec change → headless render) for the Builder (`render_turntable`, `restyle_render`, `record_render_feedback` for variants). Step 3 for Lighting & materials (`render_detail`). No generator-extension request, and no change to the spec schema.

**Render guard: affected.** The tier set, the restyle rule (turntable, `draft` only) and a new detail rule (no local detail turntable). Estimates, approval, tickets, calibration and offload checks are unchanged.

**bpy allow-list: not affected.** Restyle turntables run in the checked-in headless generator, not over the socket.

## Capabilities

### New Capabilities
<!-- none -->

### Modified Capabilities
- `render-guard`: two tiers, draft at 800²; the detail rule adds "no local detail turntable"; a restyle is a draft turntable.
- `render-offload`: drafts (not "draft and preview") always run locally.
- `restyle-variants`: a variant renders at `draft` only, as a turntable, publishes frames, a viewer and a poster still, serves its frames by index, and is rateable for a piece.
- `scene-rendering`: draft stills and turntables at 800 × 800; a restyle renders a turntable in memory.
- `room-composition`: draft composition renders at 800 × 800.
- `design-agents`: `render_turntable` names two tiers and refuses a draft still of a piece alone.
- `homeowner-chat`: the failed-notice scenario no longer uses `preview`.
- `studio-ui`: the progress step is "draft rendered"; Review buttons name `draft` or `final` and open the inspector's new Renders tab on that render; the Pieces page lists stills only.
- `render-feedback`: restyle variants of a piece are recorded and rateable, and their ratings reach the agents marked appearance only.

## Impact

- Config: `backend/config/render.yaml` (two tiers, `draft.resolution: 800`).
- Backend:
  - `app/render/tiers.py`: `TIER_NAMES` becomes `("draft", "final")`.
  - `app/render/guard.py`: refusal text; restyle and detail rules.
  - `plugins/render_turntable/tool.py`, `plugins/restyle_render/tool.py`, `plugins/photoreal_detail/tool.py`.
  - `app/blender/restyle_runner.py`, `app/blender/generators/render_restyle.py` (turntable via the existing turntable and composition fills).
  - `app/restyle/store.py`.
  - `app/agent/instructions/builder.md`, `lighting.md`.
- Backend for the Renders tab and variant ratings:
  - `app/api/packages.py`: variant frame route.
  - `app/api/feedback.py`: variants in the render list.
  - `app/feedback/ratings.py` and `plugins/render_feedback/tool.py`: accept `variant:<id>`.
  - `app/blender/restyle_runner.py`: record a run per piece variant.
  - `app/agent/prompts.py`: the variant line in the feedback note.
- Data: Alembic migration `0025_relabel_preview_tier` (`render_runs.tier`, `thread_notices.tier` and text; widens `render_runs.render_key` for variant keys). Files under the render root are relabelled by the same migration.
- Frontend: new Renders tab and frame scrubber in `components/inspector/`, the tab and selected render in the inspector URL, the notice's Review button opening the tab, the Pieces page listing stills only, and tests that use the `preview` tier (`Conversation.test.tsx`).
- Tests: `test_render_tiers`, `test_render_guard`, `test_render_estimate`, `test_restyle_tool`, `test_restyle_runner`, `test_photoreal_detail`, `test_builder_tools`, `test_renders_api`, `test_notices`, plus `--blender` generator tests for the restyle turntable.
- Timing on this laptop (5.03 s/MP): a draft turntable goes from about 22 s to about 39 s. A restyle goes from about 2 s to about 39 s per variant, so 12 variants take about 8 minutes. A detail still at `final` is about 6 minutes (uncalibrated ×30).
- Docs: CLAUDE.md §6 table and §5 `restyle_render` row.
