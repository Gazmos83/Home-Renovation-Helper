## Context

See proposal.md (Why). The current state:

- **Renders.** `POST /packages/{id}/versions/{n}/renders` (`backend/app/api/renders.py:175`) validates the request with `_price_args` → `_with_target` → `quote`.
  - A `draft` is then authorised and started at once; its 202 body carries `estimate`.
  - A `final` returns 409 `approval_required` with a token.
  - There is no way to read an estimate before a draft starts.
  - Render progress lives in the version folder's status file under `renders` (`runner.mark_render_queued`).
  - `GET /packages/{id}/versions/{n}` (`packages.py:303`) does not expose it.
  - `InspectorView` polls that route every 3 s while `status` is queued or running (`InspectorView.tsx:147-151`).
  - `RendersTab` lists published renders only (`describe_renders`, `backend/app/api/feedback.py:76`).
- **Uploads.** `Upload` rows (`backend/app/db/models.py:646`) belong to a thread with `ondelete=CASCADE`. Their files are at `uploads.upload_path(root, thread_id, id, kind)`.
  - `run_plan` (`backend/plugins/intake/tool.py:342`) calls `house_file.upsert_apartment` after the owner's yes.
  - Nothing links an apartment or room to the image that was read.
- **Verdict.** `VersionVerdict.tsx` saves the note on Enter and on blur (`:123-126`). It shows Save only for an unsaved thumbs down, has no in-flight guard and no saved state. `PUT` upserts (`backend/app/api/feedback.py:240`).

## Goals / Non-Goals

**Goals:**
- One button from "no renders" to a draft turntable, with the estimate shown before anything starts (CLAUDE.md §6).
- Blueprints that survive the conversation that carried them.
- A note save the owner can see, done exactly once.

**Non-Goals:**
- Renders of rooms or apartment shells from the inspector.
- A `final` from this button.
- PDF blueprints (PDF is not an upload kind).
- Linking blueprints to single-room `record_room` confirmations.
- Showing blueprints in the room's 3D view.

## Decisions

0. **Renders belong to room versions (owner, 2026-10-18).** "Render version N now" and the Renders tab are on the room inspector (the Workspace room pane, beside its 3D view); the piece inspector has no Renders tab. The estimate, start and progress routes live under `/compositions/{slug}/versions/{n}/`. Decisions 1–3 below were first written for pieces and apply to rooms in the same way, with `render_job` read from the room version's renders list instead of the piece version route.


1. **The estimate route sits beside the renders routes, outside their path.** It is `GET /packages/{package_id}/versions/{version}/render-estimate?kind=&tier=`, which avoids clashing with `/renders/{render}/…`.
   - It reuses `_price_args` (with `raw_fields` from the query keys, so `frames=` is refused like on POST), `_with_target` and `quote`.
   - It returns `{tier, kind, estimate, estimate_seconds, warning}`.
   - It checks `_require_built`.
   - It never calls `authorise`, `mark_render_queued` or `record_run`.
   - A refusal goes through `_refusal`, so the messages match a POST.

2. **The button posts the normal route.** Start sends `POST …/renders {"kind": "turntable", "tier": "draft"}`, so the guard runs in full on the real request. The estimate shown before is informational. The 202 body's estimate replaces it in the "rendering" line.

3. **Progress through the version poll.** `read_version` adds `render_job` when a renders entry has status queued or running: `{tier, status, estimate}`, where `estimate` is human text formatted with the guard's `estimate_text` helper from the stored seconds.
   - `InspectorView`'s `refetchInterval` also polls while `render_job` is present.
   - When it disappears, the tab invalidates `["renders", id, n]` and selects the newest turntable through `onSelect`.
   - A separate poll route was rejected: the inspector already polls this one.

4. **Blueprints are copies, not links.** Uploads cascade away with their thread, so `run_plan` copies them after `upsert_apartment` succeeds, in the same session.
   - New table `blueprints`: `id` UUID, `apartment_id` FK `apartments.id` `ondelete=CASCADE`, `source_upload_id` UUID (no FK), `kind` (`png`/`jpeg`), `original_name`, `size_bytes`, `created_at`; unique (`apartment_id`, `source_upload_id`).
   - Files go to `<upload_root>/blueprints/<id>.<ext>` and are written before commit. A failed copy logs and does not undo the plan (the plan is the owner-confirmed fact).
   - Images taken: `uploads.list_uploads(session, thread_id)` with kind png or jpeg. The tool has `ctx.thread_id`.
   - Deleting an apartment cascades the rows. File clean-up on that path is added where the apartment is deleted, if such a path exists (`upsert_apartment` replaces rooms, not the apartment row).

5. **Routes.**
   - `GET /rooms/{name}/blueprints` returns `[{id, original_name, kind, created_at, href}]` for the room's apartment, newest first, and `[]` for a room with no apartment.
   - `GET /blueprints/{id}` returns `FileResponse` with `media_type` from `uploads.MEDIA_TYPES`, `Content-Disposition: attachment; filename=<original_name>` and `X-Content-Type-Options: nosniff`.
   - Both are owner-gated like the other `/rooms` routes.

6. **Verdict row states.**
   - A `saving` flag comes from `give.isPending`; `saveNote` returns early while it is set.
   - `onBlur` saving is removed.
   - `editing` is true while the field is open: after choosing a thumb, after Edit, or while a thumbs down waits for its note. Otherwise a saved note shows as text with a "Saved" mark and Edit.
   - Save shows while `editing` and the trimmed text differs from the saved note, or while a thumbs down is pending. Escape restores the saved note and closes the field.

## Risks / Trade-offs

- A room photo sent before the plan was confirmed is also kept as a blueprint. This is accepted, and marked TODO(user) in the proposal.
- Copying doubles disk use for blueprints. The images are small (upload cap).
- The draft estimate before Start can differ from the 202 estimate if the benchmark is re-run in between. The 202 value is the one shown while rendering.
