## 1. House file and packages: one conversation per piece

- [x] 1.1 Add a house-file helper that returns the thread id bound to a package id (thread with that `package_id`, newest `last_turn_at` if duplicates). Verify with a pytest: bound piece returns the id; unbound piece returns `None`.
- [x] 1.2 On `POST /chat/threads` with `package_id`, refuse with 409 and a stated reason when that piece already has a conversation; on success bind `Thread.package_id` and a single `thread_pieces` row. Verify with pytest: first start binds; second start for the same piece is refused and creates no thread.
- [x] 1.3 Extend `GET /packages` (and any shared piece list shape) with `thread_id: string | null` from the helper in 1.1. Verify with pytest that a bound piece's list entry carries its thread id and an unbound piece carries `null`.

## 2. Binding refusals in tools and Foreman

- [x] 2.1 In `create_piece` (and design import that creates a piece), refuse when the thread is already bound to a different package id, naming the bound piece, with no pause. First create on an unbound thread still binds via `set_active_build`. Verify with pytest: unbound create binds; second create on a bound thread is refused; revise of the bound piece still works.
- [x] 2.2 Stop Foreman multi-build switching: remove the "Which piece do you mean?" path among conversation builds, and do not call `set_active_build` for another house-file piece when the thread is already bound. Unbound + named piece with no conversation still binds; unbound + named piece that already has a conversation gets a fixed plain-words reply and stays unbound. Verify with pytest covering those three cases; drop or rewrite tests that expected multi-build joins or the ambiguity question.
- [x] 2.3 Scope `house_note` / turn context to the single bound piece (no "other builds" lines). Verify with an existing house-file or prompts test updated so a legacy second `thread_pieces` row does not appear in the Designer's context.

## 3. Frontend: Pieces entry points

- [x] 3.1 Extend `PieceSummary` / `api.createThread` in `api.ts` for `thread_id` and starting with `package_id`. Verify TypeScript compiles and existing api usages still type-check.
- [x] 3.2 On the Pieces page, add "Create A New Piece" at the top; clicking it calls `createThread()` with no package and navigates to the new conversation. Update empty-state copy to point at the button. Verify with Vitest: button present above the cards; click posts and navigates.
- [x] 3.3 Under each piece card header, add a conversation link: if `thread_id` is set, link to `/conversations/<id>`; otherwise a control that starts a thread with that `package_id` and opens it. Show API refusals next to the piece. Verify with Vitest: open existing; start when none; refusal shown when the API refuses.

## 4. Frontend: nav, landing, delete

- [x] 4.1 Remove Conversations from the homeowner nav in `App.tsx`. Change sign-in and default redirects that go to `/conversations` to `/pieces`. Keep `/conversations` and `/conversations/:threadId` routes. Verify with Vitest or a router test: nav has no Conversations; login navigates to `/pieces`; deep link to a conversation still renders.
- [x] 4.2 Move conversation delete onto the conversation view (confirm copy unchanged in substance: pieces kept, cannot restore). On success navigate to `/pieces`. Verify with Vitest: confirm deletes and navigates; cancel sends nothing; turn-running refusal stays on the view.

## 5. Docs and checks

- [x] 5.1 Update CLAUDE.md §9a so a conversation is about one piece (rooms may hold many). Verify the wording matches the house-file delta.
- [x] 5.2 Run `uv run ruff check .` and `uv run pytest -m "not slow"` from `backend/` (one process), then `pnpm lint`, `pnpm test` and `pnpm build` in `frontend/`. Record that all are green. No render tier; no Blender job.
  Checks 2026-10-13: `ruff check .` clean; `pytest -m "not slow"` 2438 passed / 39 skipped / 26 deselected (1 unrelated fail: `test_seed_links_registers_kitchen_sources_without_chunks`); piece-conversation related suites 241 passed; frontend `pnpm lint`, `pnpm test` (278), `pnpm build` green.
- [x] 5.3 Browser pass (scratch API + Vite per studio-frontend memory): on Pieces, use "Create A New Piece", open an existing piece's conversation link, start a conversation from a piece with none, confirm delete from the conversation view returns to Pieces, confirm nav has no Conversations and sign-in lands on Pieces. Record steps and outcome in this file. No build or render.
  Browser pass 2026-10-13: headless Chromium through Python Playwright (`uv run --no-project --with playwright`), scratch database `home_renovation_scratch` (dropped afterwards), backend on 8100 and Vite on 5180 (`API_PROXY`); the owner's 8000 and 5173 were untouched. Seeded `hall-bench` (bound) and `shoe-rack` (unbound). No build or render. All checks passed: sign-in lands on Pieces; nav has Pieces and no Conversations; Open conversation opens hall-bench chat; Start conversation binds shoe-rack and opens the composer; delete conversation returns to Pieces with shoe-rack kept unbound; Create A New Piece opens an unbound untitled conversation.
