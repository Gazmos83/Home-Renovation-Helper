## Context

- **Tiers.** `config/render.yaml` defines three tiers, and `app/render/tiers.py` requires exactly `TIER_NAMES = ("draft", "preview", "final")`.
- **Guard.** One function, `quote()` in `app/render/guard.py`, validates every render request: tier, kind, source, target, restyle and detail rules. It is called by the Builder tools, the Studio routes (`api/renders.py`, `api/apartments.py`), `restyle_render` and `render_detail`.
- **Where renders run.** `target_for` (`app/render/offload/runtime.py`) already sends only a `final` to the render server, so drafts are laptop-only today.
- **Restyles.** A restyle is a still. `render_restyle.py` calls `render_still.fill` for a piece and `render_composition._still` for a room. `restyle_runner` verifies `still.png`. `restyle/store.list_variants` lists only folders that contain `still.png`. The variant id is `<base>-<tier>`.
- **Detail renders.** `render_detail` defaults to `kind="turntable"`. The guard only requires `final` for a detail render.
- **Where `preview` is stored.**
  - Database: `render_runs.tier` and `thread_notices.tier`, plus the notice text, for example "The preview turntable of … is ready."
  - Files: each version's `status.json` render entries and `scene.json`, and each variant's `scene.json`.
  - The latest migration is `0024_render_pod_sessions`, from the in-flight `render-pod-lifecycle` change.
- **Alembic.** The Alembic env resolves only the database URL; it does not load the render root.
- **Viewing renders.**
  - The inspector (`components/inspector/InspectorView.tsx`) has two tabs, Model and Cut list.
  - The Pieces page hides every turntable card (`isTurntableRender`, `routes/Pieces.tsx:289`), so no turntable can be watched or rated in the app.
  - The files route (`api/packages.py`) already serves frames by index for `frames/`, `room/frames/` and `detail/frames/`, and the version payload reports each frame count. Variants are served only as `variants/<id>/still.png`.
- **Ratings.**
  - `render_runs.render_key` is `String(32)`, and rating validation, the render list (`api/feedback.py`) and the chat tool (`plugins/render_feedback`) accept only the six fixed `RENDER_KEYS`.
  - Restyles record no render run.
  - `ratings.recent_for_piece` feeds the newest ratings to the Designer and Lighting through `render_feedback_note`.

## Goals / Non-Goals

**Goals:**
- Two tiers, `draft` (12 × 800², Eevee) and `final` (unchanged), loaded and refused exactly as tiers are today.
- A step-7 draft of a piece version on its own is always a turntable.
- Restyles are draft turntables, and the Variants pictures keep working.
- On the laptop, a detail render is a still. A detail turntable runs only on the render server.
- No stored render names `preview` after the upgrade.
- Every published render of a piece version, turntables included, can be watched and rated inside the app.
- Piece variants are rateable, and the agents read those ratings as look preferences, never as materials.

**Non-Goals:**
- Changing `final`, the estimate formula, calibration, approvals, tickets or the offload checks.
- Removing draft stills for placed pieces, shells, compositions or the Studio render route (owner's choice, 2026-10-15).
- Renaming variant folders such as `walnut-preview`.
- Rewriting Langfuse history. Past traces keep the tier they were sent with.
- A link to `viewer.html` anywhere in the UI. The Renders tab plays the frames itself.
- Renders of shells and compositions in the Renders tab, and ratings for composition variants. The tab belongs to the piece inspector.
- Storing images in the database.

## Decisions

1. **The tier list shrinks in code and config together.** `TIER_NAMES = ("draft", "final")`, and `render.yaml` drops `preview` and sets `draft.resolution: 800`. The loader's "unknown tier" check then refuses a leftover `preview` in the config, and `Tiers.get` refuses it in a request, both naming the allowed tiers. The guard's "a tier is required" message lists the tiers from `tiers.items()` instead of a literal string. *Alternative:* keep `preview` in config but hide it from agents. Rejected because the owner asked for its removal.

2. **The step-7 rule lives in the Builder tool, not the guard.** `render_turntable` refuses `kind == "still"` at `draft` when the target is a piece version with no room. The refusal says a draft of a piece is a turntable. The guard stays shared with the Studio route, which keeps draft stills. *Alternative:* a guard rule keyed on record and room. Rejected because the HTTP route uses the same guard and must keep stills.

3. **Restyle and detail rules live in the guard.**
   - **Restyle:** `kind != "turntable"` → "a restyle is a draft turntable". Since `final` is already refused and `preview` no longer exists, a restyle is `draft` only.
   - **Detail:** `source == "detail" and kind == "turntable" and target == "local"` → refused before quoting. The reason says that on the laptop a detail render is a still and a detail turntable runs only on the render server.
   - Both rules follow the existing source rules. The ticket match is unchanged.
   - `render_detail`'s `kind` default becomes `"still"`, and the Lighting instructions say a turntable is available only when finals go to the render server.

4. **The restyle turntable reuses the existing turntable fills.**
   - In `render_restyle.py`, `_piece` calls `render_turntable.fill(stage, tier)` after `apply_piece`.
   - `_room` calls `render_composition._turntable(scene, stage, tier.frames)` after `apply_room`, which keeps the per-frame wall hiding.
   - Both then copy `frames/frame_000.png` to `still.png` as the poster, and `_write_scene` records `frames`.
   - `restyle_runner` verifies the frames with `verify_frames` and the poster with `verify_png`. The guard ticket's kind is `turntable`.
   - `store.list_variants` stays keyed on `still.png`, so the API and `Variants.tsx` need no change.
   - *Alternative:* a new restyle turntable generator. Rejected because it would add code that duplicates the camera orbit.

5. **The relabel is split by where the data lives.**
   - Migration `0025_relabel_preview_tier` runs `UPDATE render_runs SET tier='draft' WHERE tier='preview'` and the same for `thread_notices.tier`. It also rewrites notice text that starts with "The preview " to "The draft ". Notices are written by code in that fixed form. A downgrade does nothing, because the old split cannot be recovered.
   - Files are relabelled by an idempotent `relabel_preview_files(render_root)` in `app/blender/storage.py`, called once from the app lifespan at startup. It walks every version folder under the render root (pieces at `<id>/v<n>`, shells under `shells/`, compositions under `rooms/`), including each folder's `status.json`, any `scene.json` beneath it (`room/`, `detail/`) and `variants/*/scene.json`, and rewrites only a `tier` value of `"preview"`, through the existing atomic write helpers. It logs a count.
   - *Alternative:* do the files in the migration. Rejected because the Alembic env does not load settings or the render root.
   - *Alternative:* map `preview`→`draft` whenever data is read. Rejected because the owner chose a relabel, and read-time mapping leaves `preview` in storage forever.

6. **Dependency on `render-pod-lifecycle`.** That change owns migration `0024`. This change's migration revises `0024`. If this change is applied first, its `down_revision` is set to the head at that time, and the task says so.

7. **The Renders tab reads the existing render list.**
   - `describe_renders` already returns each published render with its label, tier, rating and first-frame route. It gains `frames` (the count, from the published folder) and the piece's variants, keyed `variant:<id>` and labelled from their `scene.json`. The tab uses that one query.
   - The scrubber is a small component in `components/inspector/`. It requests `…/files/<prefix>frames/<n>` for the frame on screen and prefetches the neighbouring frames, so a 36-frame 1500² turntable is not downloaded all at once. The browser cache keeps frames already seen.
   - It reuses the Pieces page's rating calls and controls (`api.rateRender`, `api.clearRating`). The rating card is moved to a shared component, so both views behave alike.
   - The tab and the selected render are search parameters (`tab=renders&render=<key>`), on the inspector page and in the split view's `inspect` address.
   - *Alternative:* embed `viewer.html` in an iframe. Rejected because the specs keep viewer links out of the homeowner UI, and the iframe could not show the rating controls or follow the app's theme.

8. **How Review picks a render.** A notice records its tier, package and version but not the render key. The Review button opens the Renders tab with `render` unset and a `tier` hint, and the tab selects the most recently finished render of that tier using the `finished_at` the render list returns. This needs no notice schema change. *Alternative:* add a render key column to `thread_notices`. Rejected as a schema change for a choice the data already allows.

9. **Variant ratings use the existing tables.**
   - `restyle_runner` calls `feedback_runs.record_run` for each piece variant with `render_key = "variant:<id>"` and the Builder's origin, and marks it succeeded or failed like any run.
   - Migration `0025` widens `render_runs.render_key` from 32 to 96 characters. `restyle.store` refuses an id that would exceed the limit.
   - Rating validation and the chat tool accept a fixed key, or `variant:<id>` when that variant is published in the version.
   - `render_feedback_note` writes a variant line as `v2 · restyle walnut-draft (appearance only, not a priced material) · draft · up`.
   - Composition variants are not recorded, because ratings belong to a piece.
   - *Alternative:* a separate variant-rating table. Rejected because it would duplicate the rating, tracing and summary paths that already work per run.

## Risks / Trade-offs

- **Slower loop pictures.** On the 5.03 s/MP laptop, a draft turntable goes from about 22 s to about 39 s, and a restyle from about 2 s to about 39 s per variant (12 variants ≈ 8 min). The batch estimate is still stated once before running, so the owner sees the cost and can ask for fewer looks.
- **No local detail turntable.** Without a configured render server, a detail turntable cannot be made at all. The refusal says so, and the owner can still render the built model's `final` turntable locally.
- **The relabel merges history.** Feedback statistics per tier fold old `preview` ratings into `draft`, so a 1000² rating now counts with 800² ones. The owner accepted this when choosing the relabel.
- **Notice text rewrite.** Only notices that start with "The preview " are changed. A notice worded differently would keep its old word, but its tier field and Review button still read `draft`.
- **Startup file walk.** The walk runs on every start but only reads small JSON files. It does nothing once relabelled, and a failure is logged, never fatal.
- **Large frames on the tab.** A 36-frame 1500² turntable is roughly 100–200 MB of PNGs. Fetching the frame on screen plus its neighbours keeps the first view fast. Scrubbing quickly through an unseen turntable can still stall briefly.
- **Variant ratings steer the Designer.** A liked look reaches the Designer as a preference. The note says it is appearance only, and a real change still goes through a confirmed revision. Ten variant ratings can still push older render ratings out of the recent list (5 by default). The memory setting's 0–10 range is the control.
- **Pieces page loses turntable cards for good.** This matches the current code, and the spec now says so. Turntables are rated only in the inspector.
