## 0. Owner review

- [ ] 0.1 The owner approves or edits the About and README draft texts in `design.md` before apply. Record the decision here.
  - 2026-10-18: the owner chose "apply with drafts, review later". The drafts are built as written; the owner reviews and edits the wording in the browser pass (5.2). Still open.

## 1. Name and icon

- [x] 1.1 Add `frontend/public/favicon.svg` and a `HouseIcon` component (`stroke="currentColor"`).
  - Set `<title>Little Homey</title>` and the favicon link in `frontend/index.html`.
  - Change the header brand in `frontend/src/App.tsx` to icon + "Little Homey".
  - Set `title="Little Homey"` in `backend/app/main.py`.
  - Update `App.test.tsx` link expectations; add a test for "Tab title and icon" via the brand link's accessible name.
  - Verify with `pnpm test`.

## 2. About page

- [x] 2.1 Add `frontend/src/routes/About.tsx` with the approved text.
  - Add the `/about` route, gated like `/help`, and add `["/about", "About"]` to `links` after Help.
  - Add `About.test.tsx` for "About from the header", "Header links" and "Signed out", plus a check that the page text has none of: model, prompt, token, frame, resolution, Eevee, Cycles.
  - Verify with `pnpm test`.

## 3. Footer

- [x] 3.1 Add `__APP_VERSION__` / `__APP_BUILD__` to `vite.config.ts` (`define`, with git fallback `"dev"`; fixed values under `test`) and declare them in `src/vite-env.d.ts`.
  - Add `frontend/src/components/Footer.tsx` and render it after `<Routes>` in `App.tsx`, with the About link only when signed in.
  - Add `Footer.test.tsx` for "Footer on the Workspace", "Footer on the sign-in page" and "Unknown build".
  - Verify with `pnpm test` and `pnpm build`.

- [x] 3.2 Owner request 2026-10-19: freeze the footer at the bottom and move the header's name to the left, Help/About/Sign out to the right.
  - Footer `fixed bottom-0` with `--footer-h`; body bottom padding; rail, rail fly-out, sub-menu, Workspace panes and tile grid subtract `--footer-h`.
  - Header nav full width; Help, About and Sign out in one `ml-auto` group.
  - `App.test.tsx`: "Header layout" and "Footer frozen at the bottom".
  - Verify with `pnpm lint && pnpm test && pnpm build`.

## 4. README

- [x] 4.1 Replace the README title and opening paragraph with the approved concept section (name, icon, contents, Concept with the three journeys), and move the current intro under "For developers" above the existing sections. Reference the icon as `frontend/public/favicon.svg`. Check that every contents link resolves on GitHub-style anchors.

## 5. Checks

- [x] 5.1 Run `pnpm lint && pnpm test && pnpm build` in `frontend/` and `uv run ruff check .` in `backend/`. pytest is deferred to the batch check after the last change of the 2026-10-18 review batch (skip RunPod/offload tests, throwaway `TEST_DATABASE_URL`).
- [x] 5.2 Browser pass, with **no render tier**, in light and dark mode (passed, owner, 2026-10-19):
  - the tab shows "Little Homey" with the house icon;
  - the header shows the icon and name at the left, and Help, About and Sign out at the right;
  - About opens and reads in plain words;
  - the footer shows "© 2026 Little Homey" with the version and commit on the Workspace (without scrolling), Pieces, Help, About and sign-in;
  - the footer stays at the bottom while Help scrolls, and covers no input, pane, rail fly-out or tile.
