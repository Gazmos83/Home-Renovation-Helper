## Why

Version 4 of the Amesbury Wardrobe does not match what the owner confirmed, and there is nowhere to say so that lasts. Render ratings attach only to a finished render, and v4 has only its blockout screenshots, so it cannot be rated. The Reviewer also needs a render. The "Decisions so far" note is a rewritable summary of the conversation: it is refreshed, owner rows are dropped when a newer version is approved, and it stays in one conversation. So a version that came out wrong leaves no trace for the Designer's next revision and no count against the model that produced it.

## What Changes

- The owner can give a **version verdict** on any piece version, built or not and rendered or not: "Matches what I confirmed" or "Doesn't match", with a note of at most 1 000 characters. A "Doesn't match" verdict needs a note. Giving a verdict again replaces it, and clearing removes it. One current verdict per version.
- A "Doesn't match" verdict stays **open** until the owner marks it resolved or dismissed. Deleting a version deletes its verdict. Approving a version is not blocked by an open verdict.
- **Each new version records which agent slot and model produced it** (create, revise, import). Versions made before this change, or outside an agent turn, record none.
- The **conversation's house-file slice** lists the piece's open "Doesn't match" verdicts (newest first, at most 5, each naming its version and marked as the owner's verdict), so the Designer sees what went wrong before revising. A new memory setting includes or leaves them out (default included).
- **In chat**, when the owner says a version is right or wrong, the Designer proposes the verdict, naming the version and the note it read. Nothing is stored before "yes". The piece comes from the conversation, never from a model argument. When no version is named, the latest is used. New plugin `version_verdict`, toggleable.
- The **piece inspector** (page and split view) shows the version's verdict on every tab, with controls to give, edit, clear, resolve or dismiss it. It never shows a model, prompt, token count or cost.
- The **developer Feedback page** gains verdict counts grouped by slot and model (matches, doesn't match, latest note time) and the notes of one group, newest first. Verdicts never change routing.
- When tracing is configured, each stored or changed verdict is recorded as a feedback trace tagged with the verdict, slot and model. Tracing failures are logged and change nothing.

Ladder: none. A verdict is a house-file record. It writes no spec value, dimension, figure or price, and builds and renders nothing. Agents touched: the Designer (new tool, reads verdicts in its context), and the Foreman and Intake through the shared house-file slice. Neither the render guard nor the `bpy` allow-list is affected: nothing renders and no Blender script runs.

## Capabilities

### New Capabilities
- `version-verdict`: the owner's "matches / doesn't match" verdict on a piece version, its open/resolved/dismissed lifecycle, the producing slot and model recorded on each version, the chat proposal behind a "yes", and tracing.

### Modified Capabilities
- `house-file`: the conversation's slice carries the piece's open "Doesn't match" verdicts.
- `dev-panel`: the Feedback page shows verdict counts per slot and model and a group's notes; memory settings gain the verdict slice switch.
- `studio-ui`: the piece inspector shows and sets the version's verdict.

## Impact

- Database: Alembic migration `0027` adds `version_verdicts` (cascade with `piece_versions`) and nullable `slot` and `model` columns on `piece_versions`.
- Backend: `app/db/models.py`, `app/agent/house_file.py` (`record_version` takes the origin), new `app/feedback/verdicts.py`, `plugins/create_piece`, `plugins/revise_package` and `plugins/design_import` (pass `ctx.slot` and `ctx.model`), new `plugins/version_verdict/`, `app/agent/foreman.py` and `app/agent/prompts.py` (slice), `app/agent/memory_settings.py`, `app/api/feedback.py` or a new `app/api/verdicts.py` (owner and admin routes), `app/observability/langfuse.py` (`record_verdict`).
- Frontend: `lib/api.ts`, `components/inspector/InspectorView.tsx` (new `VersionVerdict` component), `routes/admin/Feedback.tsx`, `routes/admin/Memory.tsx`.
- No new dependency. No change to the spec schema, generators, render guard or allow-list.
