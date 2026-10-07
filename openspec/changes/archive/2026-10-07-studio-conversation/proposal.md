## Why

The homeowner cannot talk to the Foreman from the Studio. The Conversations page starts a thread and lists its tool toggles, and that is all: sending a message, reading the reply and answering a confirmation exist only as API routes (`/chat/threads/…/turns`, `/resume`), so today a project is started with `curl`. A thread also says nothing about the project it is for: not which piece it is about, not which version exists, not how far along the brief → piece → build → render → review → detail → final flow it has come.

## What Changes

- **Conversation view.** A thread opens on its own route and shows the owner's messages and the replies, a composer that sends one turn, and the pending confirmation as a card with `yes`, `no` and an optional reason. Blueprints and photos are uploaded from the same view and attached to the next turn. The tool toggles stay on the thread.
- **Project panel.** The thread shows its bound piece, the latest version with its build status, and the piece's progress: brief confirmed, piece created, built (screenshot), draft or preview rendered, reviewed (with the count of open items), detail pass done, final rendered. The panel names the next step the owner can ask for and lists open generator-extension requests of the piece. Everything in it is derived server-side from the house file, the version folder and the thread's conversation state, and is read through one homeowner-safe route on the thread.
- **Thread binding (specified, already implemented).** `create_piece` and `revise_package` already bind the thread to the piece they create or revise, and the Foreman prefers that binding. This change records the behaviour in the specs and pins it with tests; no code changes. (An earlier draft of this proposal wrongly called it a bug.)
- **Thread list.** The list shows each conversation's title, the piece it is about, and when it last had a turn, newest first, and opens a conversation on click.
- Ladder and agents: this is Studio and chat plumbing around ladder **step 1** (spec change) and the Foreman's routing. The Intake, Designer, Builder, Reviewer and Lighting specialists are untouched; the Foreman gains nothing but a shared progress derivation it already computes privately. **The render guard and the bpy allow-list are not affected**; the view never starts a render except by asking the Foreman in words, which goes through the Builder and the guard as before.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `homeowner-chat`: a thread exposes its piece's progress through an owner-gated read that shows no internals; a turn binds the thread to the piece it creates or revises.
- `house-file`: the thread index's bound piece follows the piece the latest turn created or revised, not only the piece the thread was started with.
- `studio-ui`: the Conversations page becomes a list that opens a conversation; the conversation view carries the messages, composer, confirmation, uploads, tool toggles and the project panel.

## Impact

- Backend: `app/api/chat.py` (progress route), a small shared progress module used by both the Foreman's facts and the route (extraction of `_review_ready` / `_detail_ready` from `app/agent/foreman.py`), `app/agent/house_file.py` unchanged in schema (no migration).
- Frontend: `src/routes/Conversations.tsx` split into a list and a conversation view, new API client calls for thread detail, turns, resume, uploads and progress, a new route in `App.tsx`.
- Tests: backend route tests for progress and binding; Vitest for the list, the view, the confirmation and the upload attach; the recorded browser check the Studio spec asks for.
- No new dependencies, no migration, no change to `config/`.
