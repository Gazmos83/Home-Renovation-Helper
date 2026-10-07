## Why

The owner's app check of 2026-10-06 (`docs/App Check 06-10-2023.md`) found the conversation view hard to read and slow to follow: replies are shown as raw text, so the Markdown tables and lists the specialists already write arrive as `|` pipes and asterisks; every message is a left-aligned paragraph; "Waiting for the reply…" is a small line beside the Send button and says nothing about who is working; questions come as free text that is easy to skip; and a conversation cannot be renamed, deleted or started without typing a title first. Long conversations silently lose their oldest exchanges once they pass a model's context budget. This change answers every point of that check that is not a routing fault (those are `foreman-routing-fixes`) and not a workflow change (`piece-first-workflow`, `room-composition`).

## What Changes

- **Readable replies.** Replies are rendered as formatted text (headings, bullet lists, tables, emphasis); raw HTML in a reply is never rendered and images only from the app's own routes. A fenced `calc` block is shown as a framed box separate from the text. Every specialist is told, by a note composed in code, to put its questions in a bullet list, any list of items (a cut list, parts, hardware) in a table, decisions in a table, and arithmetic in a `calc` block.
- **Chat layout.** The Foreman's replies sit in bubbles from the left, the owner's from the right, forms and confirmations centred. Reply text is set in Commissioner and speaker names in Oswald; headings on every Studio page (homeowner and developer) switch to Oswald too (owner decision 2026-10-07). Body text outside the chat keeps the current font. Both fonts are bundled with the app (no request to Google). Line height and paragraph spacing are increased.
- **Tools and Project move to a left icon rail.** Each icon opens its panel as a flyout over the chat; the chat takes the full width.
- **Live turn progress.** The view follows a turn as it runs: the waiting indicator is a left-aligned bubble with a rounded 2 px border and animated dots naming the specialist at work ("Designer is working…"), and the specialists that ran are listed under the reply. The turn and resume routes gain streaming forms (Server-Sent Events: specialist started, tool started, reply, pending, title, error, done); the existing JSON routes stay. Text arrives whole, not token by token.
- **Models stay off the homeowner view** (CLAUDE.md §1 unchanged). A developer page under `/admin` lists one conversation's model calls: time, specialist, model slug, input and output tokens.
- **Questions as a form.** Intake and the Designer gain an `ask_owner` tool: a list of questions, each with optional unit and choices. The turn pauses like a confirmation; the view shows the questions centred, one at a time, each answered before the next; the answers go back in one step and the answered set stays in the conversation as a Question | Answer table.
- **Titles.** A conversation is started without typing a title; after its first turn the Foreman's model writes a 3–6 word title (counted against its token budget); the owner can rename it inline at any time.
- **Delete.** Delivered by `piece-versions-and-chat-delete` (owner's choice, 2026-10-07): any conversation can be deleted after a confirmation; its index entry, conversation memory, tool settings and uploads go, and a delete is refused while a turn runs. This change's spec text keeps the delete sentences so it stays true when it archives; deleting the `threads` row also removes this change's summary columns.
- **Attachments.** An attached file can be removed from the composer before sending. Markdown/plain-text notes are accepted beside PNG and JPEG; a note reaches whichever specialist answers, as untrusted content inside the delimiters, and a specialist that finds a figure in a note disagreeing with the house file or a plan lists the conflicts in a table and asks which wins before proposing numbers.
- **Help page.** `/help` explains how to prepare a blueprint and lists the measurements the Foreman needs.
- **Long conversations are summarised, not silently trimmed.** When a call's history no longer fits its context budget, the dropped exchanges are condensed into a short "decisions so far" note kept with the thread and sent in their place; the stored conversation is unchanged. If the summary cannot be made, the current shortened-history note is used.
- Ladder and agents: Studio and chat plumbing around ladder **step 1**. Touches the Foreman graph's turn runner (streaming, title, summary), Intake and the Designer (`ask_owner`, note conflicts) and the formatting note for every specialist. **The render guard and the bpy allow-list are not affected**; nothing here starts a render or reaches the socket.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `homeowner-chat`: threads are titled by the Foreman's model, renamed and deleted; turns can be streamed; a turn can pause on questions as well as on a confirmation; replies follow the formatting rules. Based on the `studio-conversation` change's delta for this spec, which archives first.
- `studio-ui`: the conversation list and view (bubbles, fonts, spacing, formatted replies, `calc` box, waiting bubble, specialists per turn, question form, remove-before-send, rail and flyouts, rename and delete), the help page, and the developer's conversation calls page. MODIFIED text is based on the `studio-conversation` delta for this spec.
- `plan-uploads`: text notes are accepted beside images; a deleted thread's files go.
- `house-file`: a thread's index entry carries its generated or owner-given title and its summary, and is removed with the thread. Based on the `studio-conversation` delta for this spec.
- `token-budget`: history that does not fit is replaced by the thread's summary before falling back to the shortened-history note.
- `dev-panel`: one conversation's model calls are readable by the developer.
- `design-agents`: Intake and the Designer ask questions through `ask_owner` and list conflicts between a note and the house file before proposing numbers.

## Impact

- Backend: `app/api/chat.py` (streaming turn and resume, `PATCH` thread), `app/agent/chat.py` (stream runner, title step, questions pending), `app/agent/foreman.py` (stream events, summary hook, formatting note), `app/agent/budget.py` (summary in place of the omitted note), `app/agent/uploads.py` and `app/api/uploads.py` (text notes), `app/agent/house_file.py` (title, summary), a new non-toggleable `backend/plugins/ask_owner/`, instruction files for Intake and the Designer, a developer route for a conversation's calls, `app/observability/usage.py` (thread id on usage rows).
- Database: one Alembic migration — `threads.summary`, `threads.summary_through`, `model_usage.thread_id`, `uploads.kind` admitting `text`.
- Frontend: `routes/Conversation.tsx` split into components (messages, bubble, composer, question form, rail), `routes/Conversations.tsx` (start without title, rename), a new `routes/Help.tsx`, a new `routes/admin/ConversationCalls.tsx`, `lib/api.ts` (stream reader, new calls), fonts and spacing in `index.css`.
- New frontend dependencies: `react-markdown`, `remark-gfm`, `@fontsource/oswald`, `@fontsource/commissioner`. No new backend dependency.
- Order: last of the four changes from the app check; assumes `foreman-routing-fixes` (history shows text sent beside a tool call) and archives after `studio-conversation`.
