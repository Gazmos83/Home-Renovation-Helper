## 1. Warning

- [x] 1.1 Add `size_warnings(room, overall)` in `backend/app/agent/house_file.py` (ceiling and longest wall, 1 mm tolerance). Write unit tests: taller, wider, both, fits, L-shaped room's longest edge (run deferred, see 4.1).
- [x] 1.2 In `backend/app/agent/notices.py`, append the warnings to a succeeded build's notice from `post_build`; a read error posts the plain notice. Write notice tests for "Taller than the ceiling", "Wider than the longest wall", "Fits" and "No room".
- [x] 1.3 In `backend/app/api/packages.py`, return `size_warnings` from `describe_version`. Write an API test for a version taller than its room.

## 2. Intake

- [x] 2.1 Update `backend/app/agent/instructions/intake.md`: the limit is optional and never asked for; the piece's rough size and height are still asked. Extend `tests/test_instructions.py` for "No limit given" (Intake's instruction does not require the limit).

## 3. Frontend

- [x] 3.1 Relabel the field in `frontend/src/components/chat/BriefPanel.tsx` to "Highest the piece may be (mm, optional)"; add `size_warnings` to the version type in `frontend/src/lib/api.ts` and show it in `frontend/src/components/inspector/InspectorView.tsx`. Vitest: the label, saving empty, the warning line shown and not shown. Run `pnpm lint` and `pnpm test` in `frontend/`.

## 4. Checks

- [x] 4.1 Run `uv run ruff check .` in `backend/`. pytest deferred to the batch check after the last change of the 2026-10-18 review batch (skip RunPod/offload tests, throwaway TEST_DATABASE_URL).
- [ ] 4.2 Browser pass, with **no render tier** (builds only, no render): in a conversation in `Wohnen`, give a brief with no height limit and check Intake does not ask for one; revise a piece to 2600 mm tall and check the build notice and the inspector show the warning and Approve still works.
