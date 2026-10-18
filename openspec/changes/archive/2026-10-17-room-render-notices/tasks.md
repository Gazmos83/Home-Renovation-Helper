## 1. Records and migration

- [x] 1.1 Add the `ThreadRoomRender` model (thread id with cascade on delete, composition slug, version, render key, started-at; unique per thread, slug, version and key) and nullable `composition_slug` and `render_key` on `ThreadNotice`, with one Alembic migration. Verify that `uv run alembic upgrade head` and a downgrade both run on a throwaway database.

## 2. Following the render

- [x] 2.1 In `plugins/render_turntable/tool.py`, record a `room` render with a thread when it is enqueued. In `notices.post`, store the slug, version and render key on a room notice, add "You can also find it on the Rooms page." to a finished one, and delete the thread's record. Verify with tests for the notice text and that the record is removed after posting.
- [x] 2.2 In `app/agent/progress.py`, make `rendering` also true while a record of the thread matches a queued or running job in that composition version's status, and delete records that no longer match. Verify "Room render followed" and "Stale record ignored".

## 3. Links

- [x] 3.1 When the thread history is read, give a finished room notice `links` for the files that exist (viewer for a turntable key, still for a still key). Verify "Turntable ready with a link", "Still ready with a link", "File gone", "Failed room render", and an old notice without a slug carrying no link.
- [x] 3.2 In `Notice.tsx` and `api.ts`, render `links` as new-tab anchors; piece notices are unchanged. Verify with Vitest: a room notice shows "Open the turntable viewer" with `target="_blank"` and no Review button, and a piece notice still shows its Review button.

## 4. Wrap-up

- [x] 4.1 Run `uv run ruff check .` and `uv run pytest -m "not slow"` on a throwaway `TEST_DATABASE_URL` (RunPod and offload files left out), and `pnpm lint`, `pnpm test` and `pnpm build`. All must pass.
  - Run 2026-10-16 on `hra_test_room_render_notices`. The first full run gave 2728 passed, 19 failed, 10 errors. None was in this change's tests. All came from the uncommitted `hardware-catalog` work, which pytest ran here for the first time, plus the migration head this change moves:
    - a top-level `import bmesh` broke the stand-in-`bpy` box tests;
    - two new import-template guide lines were over the 500-character limit, which broke every import test;
    - two new tests had wrong settings and a wrong rail height;
    - two fixed-list tests needed the new rail-support check and head `0028`.
  - After the fixes, every one of those files passes (187 tests), as do the Blender hardware tests and `ruff`. Frontend: `pnpm lint` clean, `pnpm test` 484 passed, `pnpm build` built.
- [x] 4.2 Recorded browser check: in a conversation with a room, ask for a draft still of the room composition (tier `draft`, through the render guard), and see the notice appear without a reload with "Open the still" opening the image.
  - Passed by the owner's browser check, 2026-10-17.
