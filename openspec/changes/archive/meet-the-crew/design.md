## Context

- `frontend/src/components/chat/roles.ts` holds `ROLE_LABELS`, used by the conversation view (`Conversation.tsx:767`, the crew list under a reply), `WaitingBubble.tsx` and three developer views (`UsageCharts.tsx`, `admin/ConversationCalls.tsx`, `admin/Workflow.tsx`).
- `Conversation.tsx:759` signs every reply `speaker="Foreman"`; `WaitingBubble.tsx:6` falls back to "The Foreman is working".
- A thread's history is built in `backend/app/agent/chat.py` (~line 641): an assistant entry is `{"role": "assistant", "text": …}` with no writer. The writer is known only while the turn runs (`specialists` on the stream's `reply` event).
- Specialist replies are created in the specialist node of `backend/app/agent/foreman.py` (~line 1297–1350). An engineering answer already gets `additional_kwargs["engineering"] = True` (lines 1350, 1492). The Foreman's own code replies (`ROOM_QUESTION`, `HEIGHT_REPLY`, foreman refusals) are plain `AIMessage`s.
- Owner-visible code texts naming a role: `budget.refusal_message` via `ROLE_TITLES` (`budget.py:43`), `EMPTY_REPLY` via `SPECIALIST_LABELS` (`foreman.py:99`, which also feeds `ROLE_NOTE` in the prompt), and `Rooms.tsx:339`, `Rooms.tsx:379`, `Conversation.tsx:972` ("Ask the Designer …").
- After a streamed turn the view calls `refresh()` and shows the reply from the re-read thread, so the history is the only place the speaker is needed.

## Goals / Non-Goals

**Goals:** sign each reply with the persona of the agent that wrote it; persona names in the waiting bubble, the crew list and owner-visible code texts; a Meet the crew section on About.

**Non-Goals:** renaming role keys, slots or plugins; changing agent instructions or the notes composed into prompts (owner chose "screen only"); changing `/admin`; adding a tone setting (owner: "replies should keep the same tone"); a separate engineering agent (Little Beam is the label of an engineering answer, decided 2026-10-19).

## Decisions

1. **Speaker stored on the message.** The specialist node sets `additional_kwargs["speaker"] = name` on every `AIMessage` it returns (answers, the empty-answer replacement, its budget refusal). The history builder derives the entry's `speaker`: `engineering` when `additional_kwargs["engineering"]` is set, else `additional_kwargs["speaker"]`, else `foreman`. Messages already in checkpoints have neither key and read as `foreman`, so no migration. *Alternative:* infer the writer from the routing state per turn — rejected, the checkpoint does not keep it per message.
2. **Persona table in the frontend, separate from `ROLE_LABELS`.** Add `PERSONA_NAMES` (with `engineering` and `foreman`) next to `ROLE_LABELS` in `roles.ts`, and a `personaOf(speaker?)` helper returning "Little Homey" for an unknown or missing key. Homeowner views use it; developer views keep `ROLE_LABELS`.
3. **Persona table in the backend for code texts only.** One `PERSONA_NAMES` mapping in `budget.py` replaces `ROLE_TITLES` in `refusal_message`; `EMPTY_REPLY` formats with it instead of `SPECIALIST_LABELS`. `SPECIALIST_LABELS` stays for `ROLE_NOTE` and the prompt, so models still see role names.
4. **Crew list under a reply.** It keeps listing the specialists that ran, by persona. An engineering turn lists the specialist that ran (for example "Money Bags"), while the reply is signed "Little Beam"; the stream reports no engineering role and this change adds none.
5. **About copy as data in the page.** A small array of `{ name, job }` rendered as a list under a "Meet the crew" `<h2>`, matching the page's plain markup. No pictures. The drafts below need the owner's approval at the browser pass.

### Draft copy: Meet the crew

> **Meet the crew**
> Little Homey doesn't work alone. It's a crew of friends who each have one job, and they love it. You chat, they get to work.
>
> - **Little Homey**: the friendly face of the crew. Listens to what you want, then shouts for the right friend to take it on. If it's not sure who, it asks you.
> - **Lil' Worm**: wriggles into every corner of your home with a tape measure. Reads your floor plans and room photos, writes down every wall, window and ceiling height, and won't let anyone start until the numbers are right.
> - **Lil' Glitty**: the designer with the sparkle. Turns your wish into a real piece (sizes, shelves, drawers, wood) and makes the list of boards to cut. Checks that it fits your room, and happily redoes it as often as you like.
> - **Little Beam**: the crew's strength checker. Tells you how much a shelf can hold, whether it will sag and how it should hang on the wall. If Beam isn't sure, Beam says so.
> - **Muscles**: does the heavy lifting. Builds your piece in 3D from Glitty's plans and spins it round so you can see it from every side.
> - **Bulbs**: the bright spark. Adds real-looking wood, fabric and light for the extra-pretty pictures.
> - **Mr. Lookback**: never lets anything slide. Holds every picture up next to what you asked for and points out anything that doesn't match. He only looks, he never touches.
> - **Money Bags**: knows what everything costs. Looks up prices at toom, adds up the boards and keeps an eye on the offcuts you already have.

*TODO(user):* the draft gives Mr. Lookback "he" from his title and calls Little Beam "Beam" rather than using a pronoun; confirm or change the pronouns and the copy when you approve the wording.

## Risks / Trade-offs

- [Older replies are signed "Little Homey" although a specialist wrote them] → accepted and stated in the spec; the checkpoint holds no writer for them.
- [An engineering reply signed "Little Beam" while the crew list names the specialist] → kept on purpose: it shows who actually worked, as before; the owner can ask to hide it later.
- [Persona names are new strings in owner-facing code texts that existing tests quote] → update those test expectations in the same change (`test_budget*`, empty-answer and Conversation/Workspace tests).

## Migration Plan

None. The new key is written on new messages only; rollback leaves an unused key in `additional_kwargs`.
