## 1. Backend

- [x] 1.1 Add `notices.post_revision` and `revision_text` (never raises; no-op without a thread); allow kind `revision` in `house_file.add_notice` and the thread read. Verify a unit test: one notice with package, version and `succeeded`, no internals.
- [x] 1.2 Call it from `record_next` after the version is recorded, so `revise_package` and `rebuild_piece` both post. Verify: a confirmed revision posts it before the build ends; a Studio-route version posts none; a failed post is logged and the version stands; `create_piece` posts none.
- [x] 1.3 Verify the notice is never in a model call's messages.

## 2. Frontend

- [x] 2.1 Render `kind === "revision"` in `Notice.tsx` with a centered "Open version N" button calling `onReview`. Verify a Vitest test: button present, container centered, press opens the inspector for that piece and version.
- [ ] 2.2 Confirm the inspector opens on a version still building. Verify in the browser.

## 3. Wrap-up

- [x] 3.1 Run `uv run pytest -m "not slow"`, `uv run ruff check .`, `pnpm test`, `pnpm lint`, `pnpm build`.
