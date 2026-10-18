## 1. Placement store and fit

- [x] 1.1 Factor `fit(...)` out of `backend/plugins/room_fit/tool.py`. It writes `placements/<room-slug>.json` in the version folder on success, and `room_fit`'s result says "Placement saved" without the document. Verify with room-fit tests for the existing scenarios plus: the stored file holds the placement and scene document, and it is deleted with its version.
- [x] 1.2 Add `backend/plugins/ask_placement/` (manifest: Designer, not toggleable; tool). It covers the fixed question texts, the wall choices "Wall N (L mm)" (at most eight, free answer for more), `layout: "room"`, the left-end-to-offset conversion pinned to the room contract's corner order, and `fit` on the answers. Verify with tool tests for:
  - "First view in the room" (question texts and choices for `Wohnen`'s five walls);
  - "Placed and shown" (stored placement);
  - "Does not fit" (plain refusal, nothing stored);
  - a declined set.

## 2. Render tool

- [x] 2.1 In `backend/plugins/render_turntable/tool.py`, replace `room` with `in_room`, reading the stored placement for the confirmed room from `ctx`, re-checking it with `fit`, and giving the plain refusal when it is missing. Verify with tests:
  - "No placement, Builder call refused";
  - `in_room` with a composition refused;
  - a fake-Blender **draft** still in the room is queued through the guard with the stored scene.

## 3. Routing

- [x] 3.1 In `backend/app/agent/foreman.py`, add `views_in_room` to the router decision, the Designer/Builder choice by stored placement, the declined-room case, and the hand-off to the Builder after "Placement saved" on a `views_in_room` turn. Verify with foreman tests for:
  - "First view in the room" (Designer, no render);
  - "Placed and shown" (the Builder starts a **draft** still in the same turn);
  - "Shown again" (Builder, no questions);
  - "Room declined".

## 4. Instructions and the no-internals rule

- [x] 4.1 Add the "ask, don't explain; never name tools, documents or fields" line to `designer.md`, `builder.md` and `intake.md`. Remove any mention of passing a room document. Verify with `tests/test_instructions.py`.
- [x] 4.2 Rewrite `render_turntable`'s owner-resolvable refusal texts in plain words. Verify with a test that no refusal returned to the model contains `schema_version`, `kind:` or "room document".

## 5. Frontend

- [x] 5.1 Add `layout` to the question-set type in `frontend/src/lib/api.ts` and a "Room layout" button in the question set (`frontend/src/routes/Conversation.tsx`) that switches to the "Chat and room" layout and keeps the answers. Verify with Vitest for "Room layout from the question" and "Other question sets".

## 6. Checks

- [x] 6.1 Run `uv run ruff check .` and `uv run pytest -m "not slow"` in `backend/`, skipping the RunPod/offload test files and using a throwaway `TEST_DATABASE_URL` if needed. Run `pnpm lint`, `pnpm test` and `pnpm build` in `frontend/`. All must pass.
- [ ] 6.2 Browser pass in the `lamellen-kommode` conversation:
  - "I would like to view this in the room" shows the two questions and the Room layout button;
  - answering wall 2 and 300 mm starts a **draft** still in `Wohnen` (through the render guard) with no internal names in any reply;
  - asking again renders with no questions.
