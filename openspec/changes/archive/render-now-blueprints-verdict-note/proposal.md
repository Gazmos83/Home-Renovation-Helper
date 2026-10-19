## Why

The 2026-10-15 end-to-end review raised three small gaps, all in places where the owner looks at a result.

- **No render action in the Renders tab.** It says "No renders of this version yet." but offers no way to make one. A render can only be asked for in the chat.
- **Blueprints are not kept.** A room read from a blueprint keeps the measurements but not the blueprint itself. The image stays an attachment in the conversation it was sent to and is deleted with that conversation. The Measured Rooms page cannot download it.
- **The verdict note looks unsaved.** The optional note on "Matches what I confirmed" seems not to save on Enter. It does save, but shows no sign of it and offers no Save button for a thumbs up. It can also be sent twice (Enter, then leaving the field). The owner wants to see that a note is saved and to edit it.

## What Changes

**Revised 2026-10-18 after the owner's check:** "Render version N now" is for **room versions**, not pieces. The piece inspector's 3D view is enough for a piece, so its Renders tab is removed and every existing piece render was deleted (files and their `render_runs` / `render_feedback` rows; backed up outside the repository). The Renders tab moves to the room inspector. Making renders of rooms only, everywhere (the Builder's render tool, restyle variants, the Reviewer, the Pieces page), is proposed separately in `rooms-only-renders`.

- **The piece inspector has no Renders tab.** A piece render's notice shows its text with no Review button. An old `?tab=renders` address opens the Model tab.
- **"Render version N now"** in the room inspector's new Renders tab (the Workspace room pane gains "3D view" and "Renders" tabs), for a built room version with no renders.
  - Pressing it shows one plain sentence first, with no frame, resolution or engine wording: "This makes a quick turn-around preview of the room on this computer, so you can look at it from every side. It takes about <estimate>." It also shows **Start** and **Cancel**.
  - Start runs a `draft` turntable through the render guard. While it runs the tab says "Rendering version N… about <estimate>". When it finishes, the turntable appears selected.
  - A refusal (no benchmark yet, Blender busy, not built) is shown in plain words.
  - It is never `final`.
  - A `final` of a room stays a request in the conversation, where the owner approves it.
- **Room render routes.** `GET /compositions/{slug}/versions/{n}/render-estimate?kind=turntable&tier=draft` returns the guard's human estimate without starting anything or issuing a ticket. `POST /compositions/{slug}/versions/{n}/renders` starts a `draft` through the guard (a `final` is refused: it is asked for in a conversation). `GET /compositions/{slug}/versions/{n}/renders` lists the version's turntable and still and the queued or running render (`render_job`), which the tab polls.
- **Blueprints are kept with the apartment.** When the owner confirms a plan read (`record_plan`), the PNG and JPEG files attached in that conversation up to that turn are copied into the house file as the apartment's blueprints (a new `blueprints` table and files under `<upload_root>/blueprints/`). They outlive the conversation. Replacing the apartment with a new plan read adds the new images and keeps the old ones, newest first.
- **Blueprints download on the Measured Rooms page.** The page shows each room's apartment blueprints as "Download blueprint <original name>". This uses `GET /rooms/{name}/blueprints` (list) and `GET /blueprints/{id}` (an attachment download, `nosniff`).
- **The verdict note saves visibly.**
  - A **Save** button is shown for either thumb while the note differs from the saved one.
  - Enter or Save saves once: a save in flight blocks another, and leaving the field no longer saves.
  - A saved note is shown as text with "Saved" and an **Edit** button, which reopens the field with the note.
  - Escape cancels an edit.
  - The thumbs-down rules (a note is required) stay.
- **Assumptions, TODO(user) for review:**
  - every image attached in the conversation before the plan was confirmed counts as a blueprint, including room photos sent alongside;
  - photos confirmed with a single room (`record_room`, not a plan) are not kept as blueprints;
  - the draft turntable is the piece alone, not placed in its room.

Ladder: none of the three steps. No schema or generator change; the render uses the existing headless turntable. Agents touched: none. `record_plan` (Intake's tool) also stores the blueprint copies, in code after the owner's yes. The **render guard is used, not changed**: the new estimate route only quotes, and every run still needs a ticket from `authorise`. A `final` stays approval-only and is not offered here. The **bpy allow-list** is **not affected**.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `studio-ui`: the Renders tab offers "Render version N now" when there are no renders; the verdict row's note saves visibly and can be edited; the Measured Rooms page offers blueprint downloads.
- `render-guard`: an estimate can be read without starting a render.
- `plan-uploads`: a confirmed plan's images are kept as the apartment's blueprints and can be downloaded.

## Impact

- **Backend:**
  - `backend/app/api/renders.py` or `packages.py`: the estimate route, built from `_price_args` + `_with_target` + `quote`, approving nothing;
  - `read_version` gains `render_job` from `storage.read_status(folder)["renders"]`;
  - `backend/app/db/models.py` plus an Alembic migration: a `blueprints` table (`id`, `apartment_id` FK cascade, `kind`, `original_name`, `size_bytes`, `created_at`);
  - `backend/app/agent/uploads.py` or `house_file.py`: copy the thread's image uploads on a confirmed plan;
  - `backend/plugins/intake/tool.py` `run_plan`: call that copy;
  - `backend/app/api/rooms.py`: the list route; a `GET /blueprints/{id}` route.
- **Frontend:**
  - `frontend/src/lib/api.ts`: `renderEstimate`, `startRender`, `roomBlueprints`, `VersionInfo.render_job`;
  - `frontend/src/components/inspector/RendersTab.tsx` and `InspectorView.tsx` (the poll);
  - `frontend/src/components/inspector/VersionVerdict.tsx`;
  - `frontend/src/routes/Rooms.tsx` (`MeasuredRoom`).
- **Tests:** render-route and estimate tests, a blueprints copy and route test, Vitest for the three UI parts.
- **Relation to the review's tidy-up change**, which removes the turntable-viewer link from the Measured Rooms page: both touch `Rooms.tsx`, in different blocks.
