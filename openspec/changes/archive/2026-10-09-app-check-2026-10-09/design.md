## Context

The proposal's Why gives the motivation and the code findings. This section only covers the parts of the current code that shape the approach.

- **Rooms.** `rooms.name` is unique house-wide. `upsert_apartment` (`app/agent/house_file.py`) keeps stored rooms the new read does not name. `run_brief` calls `upsert_room` without `apartment_id`, and `upsert_room` assigns it unconditionally. The measured-room delete (`house-file` spec, "The owner reads and deletes a measured room") already clears pieces, conversations and the room composition in one step. It refuses a room that belongs to an apartment.
- **Routing.** `compose_ready` in `foreman.py` `load_house` is true only when the confirmed room's name is in the latest message, a composition exists, or an approved piece is in scope. The Foreman's structured `Decision` has `specialist` and `reason` only.
- **Designer context.** `_designer_note()` appends three full template JSONs every Designer turn. `piece_note` (`prompts.py`) has no envelope line.
- **Chat.** `_stream` (`app/api/chat.py`) runs a turn on a daemon thread over `run_events` (`app/agent/chat.py`). `_forget_unanswered` already removes a failed turn's messages with `RemoveMessage` from the owner's message onwards. The client has no `AbortController`.
- **Compositions.** `build_composition.py` publishes `model.blend`, `screenshot.png` and `report.json`. Walls are named `Wall_<i>_<n>`, `Wall_<i>_lintel_<n>` and `Wall_<i>_sill_<n>`; floor and ceiling are `Floor` and `Ceiling`. Apartment shells come from `build_shell.py`. Piece builds already export `model.glb` from a checked-in headless generator.
- **Inspector.** `InspectorView` takes a fixed package and version. It has layer switches driven by `spec.json` `layers` (layer → mesh names) through `PieceModel` and `lib/inspector.ts`.
- **Pricing.** The `pricings` routes exist. `describe_pricing` returns totals in cents, counts, `complete` and a `result` holding the lines. `POST` refuses an unapproved version with 409 `not_approved`.

## Goals / Non-Goals

**Goals:**
- Every rule the owner relies on is enforced in code: room reuse, measurement check, compose routing.
- The inspector components are reused for rooms instead of building a second viewer.
- Each behaviour stays independently testable without a live model.

**Non-Goals:**
- Changing the Designer's model. The owner changes slots by hand in `/admin`.
- Code routing for revisions, which bypasses the Foreman model. The owner did not choose it.
- Editing any message other than the latest one, or undoing house-file writes, builds or renders on a rewind.
- Hiding walls in renders. Turntable auto-hiding stays as it is.
- A 3D view for the older piece-in-room scene (`build_room_scene.py`). Only compositions get one.
- Pricing on `/admin/models`.
- Changing the "ask whether anything else should change" rule. It shipped with `designer-revision-clarity`.

## Decisions

1. **Room reuse is enforced where rooms enter a conversation, not by scoping rooms to conversations.**
   - Rooms stay house-wide, as the owner chose ("ask before reusing").
   - The code paths that put a room into a conversation already pause (`confirm_room`, `record_brief`, `record_plan`). The gaps are elsewhere:
     - `record_plan` merges silently;
     - `room_named` routing lets an unconfirmed stored room shape a turn;
     - `intake.md` says "Never ask for what it already says".
   - Fixes:
     - The `intake.md` rule is reworded to "the conversation's confirmed room".
     - A new rule says a stored room or apartment is offered through `confirm_room`, never assumed.
     - `record_plan` gains the replace summary (decision 2).
   - The house-file note already carries only the conversation's confirmed room, so no other stored figures reach the prompt.
   - Alternative rejected: conversation-owned rooms. It breaks pieces placed from other conversations, and the owner did not choose it.

2. **A plan re-read replaces the apartment through the existing room delete.**
   - `upsert_apartment` gains `replace=True`, used by `record_plan`. It computes three lists: kept-and-changed, new and removed. The preview shows them before `yes`.
   - On `yes`, each removed room goes through a shared helper extracted from the measured-room delete. The helper skips the "belongs to an apartment" refusal for this caller only. That way pieces, conversations and room compositions are cleared exactly as a delete does.
   - Overlap is checked among the read's rooms only.
   - The busy check refuses the re-read while a composition of a removed room, or of the apartment, is queued or running.
   - An apartment composition whose latest version places an item in a removed room is not changed. Its next compose is validated against the new rooms.
   - Alternative rejected: a soft "archived" state for rooms. It needs a migration, and the owner chose removal.

3. **Compose routing comes from the Foreman's decision, bounded by code.**
   - `Decision` gains `composes_room: bool`, described as "the owner wants a room furnished or composed, not a piece designed".
   - `compose_ready` becomes:
     - a confirmed room or apartment exists and `composes_room` is true; or
     - the existing conditions.
   - The literal name match stays as one of the existing conditions.
   - Code still enforces the rest: a room must be confirmed, and a piece wish with no brief still goes to Intake.
   - Intake's instructions gain the room-first path: confirm the room, ask what it holds, hand off to compose, never call `record_brief` for a room-only wish.
   - Alternative rejected: keyword matching on "room" or "furnish". It is brittle in German and English mixed messages.

4. **Templates only without an active build.** `_designer_note()` is added to the Designer's notes only when `package_id` is falsy. The template note is the one source of competing figures, and a revision never needs it. `piece_note` gains an `envelope W × H × D mm` line first.

5. **The measurement check is a pure module that `revise_package` calls before its preview.**
   - `RevisePackageSchema` gains `requested: list[RequestedMeasure]`. Each entry is `{quote: str, target: str, field: str, value_mm: int}`, where `target` is a module id, `envelope` or a wall-shelf id. The list is required but may be empty.
   - `app/agent/measurements.py` provides:
     - `lengths(text) -> list[Length]`: a regex for a number (comma or dot decimal) followed by `mm|cm|m`, normalised to mm, with the relative words from the spec;
     - `check(requested, owner_texts, current_doc, changes) -> list[str]`, which returns refusals.
   - The tool needs the owner's messages since the last created revision. They come through `ToolContext`: the specialist loop passes the thread's `HumanMessage` texts after the last `revise_package` ToolMessage that created a version, or after the thread's start. This is code-composed, never a model argument.
   - Lengths without a unit (for example "3 shelves") are not checked.
   - Alternative rejected: the model echoes values and the card shows them. That is already the case today, and it failed.

6. **The composition GLB is exported by the generator, and the surface map is computed from object names.**
   - After `save_as_mainfile`, `build_composition.py` calls `bpy.ops.export_scene.gltf` with Y-up and applied modifiers, as the piece build does. This is a checked-in headless generator, outside the live allow-list (CLAUDE.md §8). Export is not an import, so the room-composition import rule is unaffected.
   - The surface map is built from object names:
     - `Wall_<i>_*` → `wall <i+1>`;
     - `Floor` → `floor`; `Ceiling` → `ceiling`;
     - item objects → `items`.
   - For an apartment, the shell generator's per-room names are prefixed `<room>: `. `build_shell.py` naming is read during task 4.1, and objects are renamed there only if needed.
   - `verify_composition` checks that every mesh is mapped exactly once.
   - `app/api/compositions.py` returns `model` and `surfaces` URLs for the latest version when the files exist.

7. **The Rooms 3D view reuses the inspector's canvas.**
   - `InspectorCanvas` and `PieceModel` already take a `layerMap` and `layers`. The room view passes the surface map as the layer map.
   - Room-specific parts:
     - default layers: ceiling off;
     - an "All walls" switch that toggles every `wall*` key;
     - no explode, no dimensions overlay, no cut list.
   - It is loaded lazily, like the inspector.

8. **Stop is cooperative. Edit is a rewind plus a new turn.**
   - A process-local registry `{thread_id: threading.Event}` is set when a streamed turn starts and cleared when it ends. A single process serves the app.
   - `POST /threads/{id}/turns/stop` sets the event, or answers 409 when no turn is registered.
   - `run_events` checks the event after each graph event and stops. The graph is not interrupted mid-call, so a model call already in flight finishes and is discarded.
   - The turn's messages are removed with the existing `_forget_unanswered`. Tool completions seen in the turn's events are collected into the `stopped` event's plain text.
   - `POST /threads/{id}/turns/latest` with `{message, uploads}`:
     - refuses (409) while a turn runs or a confirmation is pending, or when the message id given is not the latest `HumanMessage`;
     - removes the latest `HumanMessage` and everything after it, with the same `RemoveMessage` mechanism;
     - collects the versions, compositions and renders that the rewound tool messages created, and reports them;
     - streams the new turn through `_stream`.
   - Graph channels other than messages (brief, package_id) are left as they are. They mirror house-file writes that stay.

9. **The inspector follows versions by polling the piece.**
   - A new query `["piece-versions", pkg]` polls `api.piece(pkg)` every 3 s while the inspector is mounted.
   - The newest version number seen at mount (or at the last manual choice) is remembered. When a larger number appears, the view navigates, or sets `inspect`, to it.
   - The switcher is a select fed by the same query.
   - This needs no backend change: the pieces list already carries the versions.

10. **Pricing UI reads the existing routes.**
    - `lib/api.ts` gains `pricings(pkg, v)` and `createPricing(pkg, v)`, with an empty body that uses the defaults.
    - The dropdown renders `result`'s sheet, cut and hardware lines, the cents totals as EUR, and the unpriced lines.
    - The field names of `result` are read from `app/pricing/pricing.py` in task 7.1.

## Risks / Trade-offs

- [The Designer fills `requested` with an empty list and skips the check] → The coverage rule refuses any unit length in the owner's messages that is not covered, so an empty list fails whenever the owner gave a length.
- [Owner texts quote lengths that are not about the piece, for example "the room is 4 m wide"] → The Designer marks them with a `none` entry (spec), accepted only when the quote is present.
- [A stop lands between a tool's completion and its ToolMessage] → The tool's write stays (spec), and the `stopped` text names it from the tool-start events. At worst the owner is told "a build may have been started".
- [The process-local stop registry breaks with several workers] → The app runs one process (single user). Noted in a code comment.
- [A re-read removes a room the owner still wanted] → The card lists each removed room with its pieces and composition before `yes`.
- [The GLB of a large apartment is heavy in the browser] → It is loaded only when the 3D view is opened. Same approach as the inspector.
- [`composes_room` misclassifies] → Code still requires a confirmed room, and `compose_room` always pauses with a summary.

## Migration Plan

No schema migration. Existing composition versions keep working without `model.glb`. Rollback is a revert: the new files are additive, and `record_plan`'s replace only applies to new reads.
