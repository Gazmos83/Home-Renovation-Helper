## Why

The chat signs every reply as "Foreman", although the Foreman never writes a reply: a specialist does. The owner asked on 2026-10-19 that each agent appear as a member of Little Homey's crew, with its own name, both on the reply it wrote and on the About page.

## What Changes

- Every reply in the conversation view is signed with the persona name of the agent that wrote it, instead of "Foreman":

  | Agent (internal role) | Persona name |
  |---|---|
  | Foreman, and replies written by the application | Little Homey |
  | Intake | Lil' Worm |
  | Designer | Lil' Glitty |
  | Builder | Muscles |
  | Lighting & materials | Bulbs |
  | Reviewer | Mr. Lookback |
  | Researcher | Money Bags |
  | An engineering answer (whichever specialist wrote it) | Little Beam |

- A thread's history records, for each assistant entry, which agent wrote it (a `speaker` role key). A reply saved before this change has no record and is signed "Little Homey".
- The waiting bubble reads "Little Homey is working…" before a specialist is chosen, then "<persona> is working…". The list under a reply names the crew members who ran.
- Short code-written texts the owner reads that name an agent use the persona name, for example "Lil' Glitty can't take this on right now: …", "Lil' Glitty gave no answer…" and "Ask Lil' Glitty to compose …".
- The About page gains a "Meet the crew" section: one entry per persona, each written as a crew member's job description, casual and playful, as a group of friends working together.
- Not changed: internal role keys, agent instructions and prompts (agents keep their role names among themselves, by the owner's choice "screen only"), `/admin` pages, routing, models and the reply tone. The owner asked first for an "Amiable" tone for Little Homey, then said replies keep their tone; the Foreman writes no reply, so no tone setting is added.

Ladder step: none (no spec, generator or Blender change). Agents touched: none in behaviour; the Foreman graph only tags each reply with its writer. Render guard and `bpy` allow-list: not affected.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `homeowner-chat`: a thread's history entry for an assistant reply carries the role that wrote it; owner-visible code texts name agents by persona.
- `design-agents`: the empty-answer reply names the specialist by persona.
- `studio-ui`: the conversation view signs replies, the waiting bubble and the crew list with persona names; the About page gets a Meet the crew section.

## Impact

- Backend: `backend/app/agent/foreman.py` (tag each reply `AIMessage` with its writer; persona names in `EMPTY_REPLY`), `backend/app/agent/budget.py` (refusal text), `backend/app/agent/chat.py` (history entry `speaker`).
- Frontend: new persona table beside `frontend/src/components/chat/roles.ts` (`ROLE_LABELS` stays for `/admin`), `Conversation.tsx`, `WaitingBubble.tsx`, `Rooms.tsx`, `lib/api.ts` (`ChatMessage.speaker`), `routes/About.tsx`, and their tests.
- No migration: the role key lives in the message's `additional_kwargs` in the checkpointer.
