## 1. Tools and agents

- [x] 1.1 In `backend/plugins/render_turntable/tool.py`, refuse a `package_id` target and `in_room` in plain words (renders are made of rooms; offer to compose and render the room). Update the manifest description and tool text. Tests for "Draft still of a piece refused" and "Draft still of a placed piece"; existing piece render tool tests become refusals.
- [x] 1.2 In `backend/plugins/restyle_render/tool.py`, refuse `slots` (piece looks) in plain words; room styles unchanged. Update tests.
- [x] 1.3 Update `backend/app/agent/instructions/builder.md` and `foreman.md`: a piece is built and inspected, renders are of composed rooms and shells; "render it" for a piece is answered by offering its room. Update `tests/test_instructions.py`.

## 2. Frontend

- [x] 2.1 Remove `PieceVariants` and "Use this look" from the piece pane (`frontend/src/routes/Conversation.tsx`) and `keepLookRequest` from `frontend/src/components/Variants.tsx` if unused. Update Conversation and Variants tests.
- [x] 2.2 Remove the stills, ratings and piece variants from the Pieces page (`frontend/src/routes/Pieces.tsx`). Update `Pieces.test.tsx`.

## 3. Checks

- [x] 3.1 Run `uv run ruff check .` in `backend/` and `pnpm lint && pnpm test && pnpm build` in `frontend/`. pytest in the batch check (skip RunPod/offload tests, throwaway `TEST_DATABASE_URL`).
- [x] 3.2 Folded 2026-10-19 into `place-piece-from-owner-words` task 5.2 (owner's decision). Browser pass, **no render tier**: ask the Builder to render a piece and see the plain refusal offering the room; the piece pane and the Pieces page show no renders or looks.
