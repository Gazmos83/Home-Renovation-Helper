No task renders; no render tier is involved.

## 1. Backend: who wrote each reply

- [x] 1.1 In the specialist node of `backend/app/agent/foreman.py`, set `additional_kwargs["speaker"] = name` on every `AIMessage` it returns: the answer (with or without tool calls), the empty-answer replacement and its budget refusal
- [x] 1.2 In the thread history builder in `backend/app/agent/chat.py`, give each assistant entry a `speaker`: `engineering` when `additional_kwargs["engineering"]` is set, else the stored `speaker`, else `foreman`
- [x] 1.3 Tests: a specialist reply reads back with its role, an engineering answer with `engineering`, the room question and a reply without the key with `foreman`; update the existing history assertions (about 12 in `backend/tests`) that compare whole assistant entries

## 2. Backend: persona names in code texts

- [x] 2.1 Replace `ROLE_TITLES` in `backend/app/agent/budget.py` with persona names (Little Homey, Lil' Worm, Lil' Glitty, Muscles, Bulbs, Mr. Lookback, Money Bags) for `refusal_message`
- [x] 2.2 Format `EMPTY_REPLY` in `foreman.py` with the persona name; leave `SPECIALIST_LABELS` and `ROLE_NOTE` (prompt) unchanged
- [x] 2.3 Update `test_budget.py`, `test_foreman.py` and `test_design_loop.py` expectations; add a check that the Designer's prompt still says "the Designer" and contains no persona name

## 3. Frontend: chat signed by the crew

- [x] 3.1 Add `PERSONA_NAMES` and `personaOf()` to `frontend/src/components/chat/roles.ts` (with `engineering` → Little Beam, `foreman`/missing → Little Homey); keep `ROLE_LABELS` for the developer views
- [x] 3.2 Add `speaker?: string` to `ChatMessage` in `frontend/src/lib/api.ts`
- [x] 3.3 `Conversation.tsx`: sign each reply with `personaOf(m.speaker)`, list the turn's specialists by persona, and say "Ask Lil' Glitty to compose …"
- [x] 3.4 `WaitingBubble.tsx`: "Little Homey is working…" before a specialist, then "<persona> is working…"
- [x] 3.5 `Rooms.tsx`: both "Ask the Designer …" lines name Lil' Glitty
- [x] 3.6 Tests: update `Conversation.test.tsx`, `Workspace.test.tsx` and `Rooms.test.tsx`; add a case where replies with speakers `designer`, `engineering` and `foreman` are signed Lil' Glitty, Little Beam and Little Homey; check a developer view still shows "Designer"

## 4. Frontend: Meet the crew

- [x] 4.1 Add the "Meet the crew" section to `frontend/src/routes/About.tsx` with the approved copy from `design.md`, after the three existing points, in the order Little Homey, Lil' Worm, Lil' Glitty, Little Beam, Muscles, Bulbs, Mr. Lookback, Money Bags
- [x] 4.2 `About.test.tsx`: the heading and eight names in order, and no model, prompt, token, frame, resolution or engine word on the page

## 5. Checks

- [x] 5.1 `uv run ruff check .` and `uv run pytest -m "not slow"` (on a throwaway `TEST_DATABASE_URL` if another session is using the test database; offload and pod test files skipped)
- [x] 5.2 `pnpm lint`, `pnpm test`, `pnpm build`
- Note 2026-10-19: the owner moved the Meet the crew section from About to its own page at `/crew` in `marketing-landing-page`, which was archived first; this change's About requirement was removed from its delta as superseded. The browser pass below checks the crew on `/crew`, not on About.
- [x] 5.3 Browser pass: send a message and see Little Homey → Lil' Worm in the waiting bubble and the reply signed Lil' Worm; an engineering question signed Little Beam; the compact layout shows "Lil' Glitty:" inline; `/crew` shows Meet the crew; the owner approves the crew wording
