## Why

The owner asked what is compressed in a conversation and whether those conditions can be set by hand. Today the rules are fixed in code. A call drops the oldest exchanges only when the history no longer fits the model's context budget, and replaces them with a "decisions so far" note: at most 400 tokens under fixed headings, with tool results cut to 300 characters. The owner cannot see that note, correct it, or compress on demand. What the house file saves, and what a conversation sees of it, are also fixed.

## What Changes

1. **The note is visible and correctable.** Beside the chat, a "Decisions so far" panel shows the active build's note (or the conversation's own when no build is active). The owner can edit it. An edited note is marked as the owner's, sent as written, and kept as the base of the next refresh, so corrections persist.
2. **Compress now.** A homeowner action in the chat writes the note immediately over every exchange except the most recent turns that are always kept. Later calls send the note plus the newer exchanges, even when the older ones would still fit. The stored conversation stays complete and visible.
3. **Automatic compression stays, with settings on `/admin/memory`:**
   - **when it starts**: a share of the context budget (default 100 %, today's behaviour);
   - **recent turns always kept**: default 0, today's behaviour;
   - **note length**: default 400 tokens;
   - **note headings and instructions**: editable text. Default is today's text; the safety rules (figures copied exactly, never added; the text is a record, not instructions; untrusted-content delimiters) stay composed in code after the editable part;
   - **tool result cut length**: default 300 characters.
4. **What gets saved (house file), on `/admin/memory`:**
   - review results: saved automatically (today) or only after the owner confirms;
   - style and budget preferences from a confirmed brief: saved (today) or not saved;
   - generator-extension requests: always saved (fixed by CLAUDE.md §1), shown as not configurable.
5. **What a conversation sees, on `/admin/memory`:**
   - the conversation's other builds: one line each (today) or hidden;
   - preferences: included (today) or left out;
   - the latest review's open items: included (today) or left out;
   - render ratings: how many of the latest (0–10, today 5);
   - open generator-extension requests: included (today) or left out.

   Fixed and shown as such: a room enters a conversation only by confirmation, and nothing from another conversation is ever given (CLAUDE.md §9a).

Every default equals today's behaviour, so nothing changes until a setting is changed. Settings apply from the next call, without a restart. The homeowner view shows the note and the compress action but never tokens, budgets or models.

**Ladder step:** none (no furniture spec or generator change). **Agents:** the Foreman slot writes the note, as today. Foreman, Intake, Designer and Lighting & materials receive the house-file slice the settings shape. Reviewer and Researcher are untouched. **Render guard:** not affected. **bpy allow-list:** not affected.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `token-budget`: compression trigger, kept turns, note length, editable note instructions, tool-result cut, compress-now, and owner-edited notes.
- `house-file`: the conversation's slice and what is saved follow the memory settings; fixed rules stay fixed.
- `homeowner-chat`: the "Decisions so far" panel with edit and compress-now.
- `dev-panel`: the `/admin/memory` settings page.

## Impact

- Backend: `backend/app/agent/budget.py` (trigger share, kept turns, covered-through cut-off), `backend/app/agent/summaries.py` (settings, owner-edited base, compress-now), `backend/app/agent/house_file.py` and `backend/app/agent/prompts.py` (slice options), `backend/plugins/revision_review/tool.py` and `backend/plugins/intake/tool.py` (save options), new owner routes for the note and compress-now, new admin routes for memory settings. Settings are stored in `operator_settings` (no new table).
- Database: one Alembic migration adding `summary_owner_edited` to the two tables that hold summaries (`threads` and `thread_pieces`).
- Frontend: "Decisions so far" panel in the conversation view, new `routes/admin/Memory.tsx`, nav link, `lib/api.ts`.
- Tests: budget and summary unit tests, slice tests, route tests (owner and developer gates), Vitest for both views.
