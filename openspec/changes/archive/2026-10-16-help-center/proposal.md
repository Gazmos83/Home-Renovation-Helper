## Why

The Help page covers only blueprint preparation and file types, its text lives in `Help.tsx` where no agent can read it, and a help question in a fresh conversation gets "Which room is this for?" instead of an answer. The owner also has no guided path from "a photo of a piece I like" to a design in the app, although the import template and the import flow already exist.

## What Changes

- The help text moves to one source, `backend/config/help.yaml`: a list of topics, each with an id, a title and its body. The Help page and the chat read the same file, so they cannot drift apart.
- The Help page shows each topic as its title only, collapsed; expanding a topic reveals the rest. Topics:
  - Preparing a blueprint or a sketch (existing text, unchanged)
  - Files a conversation accepts (existing text, unchanged)
  - Designing from a photo with the design file template: download the template, use it with a photo in another high-end AI chat (one that reads images) together with the default extraction prompt, save its reply as a `.json` file, attach it to a new conversation, confirm the import, then revise the piece in the app
  - Pieces and renders: draft and final renders, the typed "yes" for a final, render times, rating a render, restyle variants
  - Conversations and rooms: one piece per conversation, confirming a room, revising a piece, turning tools on and off
  - How a piece is made: a workflow diagram (wish → Intake confirms → Designer drafts → owner confirms → Builder blockout → draft turntable → Reviewer → revise → optional detail pass → final after a typed "yes"), with the template import as a branch into the Designer
- The template topic offers the import template download (the existing owner-gated route) and shows the default extraction prompt with a Copy button. The prompt is fixed text in the help file, not editable from `/admin`.
- The Pieces page keeps its own template download.
- A new non-toggleable `help` plugin gives Intake a read-only `read_help` tool: with no topic it lists the topic titles; with a topic id it returns that topic's text.
- The Foreman marks a turn as a help question (how to use the app, not a design request). A help question goes to Intake with or without a confirmed room, and is answered from `read_help` without recording a brief, a room or a piece.

## Capabilities

### New Capabilities
- `help-center`: the single help source, its topics, the default extraction prompt, and the `read_help` tool.

### Modified Capabilities
- `studio-ui`: the help page requirement changes to collapsible topics read from the help source, a template download, and the extraction prompt with a Copy button.
- `design-agents`: Foreman routing gains the help-question rule, which goes before the no-room fixed question, and Intake answers help questions from `read_help`.

## Impact

- Ladder step: none. Nothing is built, rendered or written to a spec.
- Agents: the Foreman (routing decision field and instruction) and Intake (new tool, instruction).
- Render guard and bpy allow-list: not affected.
- Backend: `backend/config/help.yaml`; a loader validated at startup (a malformed file is refused by name); an owner-gated `GET /help` route; `backend/plugins/help/` (manifest and `read_help`); `foreman.py` routing; `instructions/foreman.md` and `instructions/intake.md`.
- Frontend: `routes/Help.tsx` renders the topics from `/help` and keeps the example room and the workflow diagram as SVG components; `lib/api.ts` gets a help query. `Help.test.tsx` is updated.
- No database migration and no new dependency.
