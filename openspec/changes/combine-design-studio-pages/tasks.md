## 1. Tab bodies

- [x] 1.1 Remove `Page` and the `h1` from `Pieces.tsx`, `Rooms.tsx` and `ModelLibrary.tsx`, keeping their intros, cards, forms, the Pieces "Create A New Piece" button and every query key; move the two `h1` assertions out of `Rooms.test.tsx` and `ModelLibrary.test.tsx`; verify `pnpm test Pieces Rooms ModelLibrary` passes

## 2. Design Studio page

- [x] 2.1 Add `routes/Studio.tsx` like `Pricing.tsx`: rail with tab links Pieces / Measured Rooms / Model Library to `/studio/<tab>` (Armchair, Ruler, Package icons), shared "Hide labels" switch, `h1` "Design Studio", one tab panel; an unknown tab redirects to `/studio/pieces`
- [x] 2.2 Add `Studio.test.tsx` for "Pieces first", "Tab chosen", "Tab address reloaded", "Unknown tab" and the shared labels switch; verify `pnpm test Studio`

## 3. Navigation and routes

- [x] 3.1 In `App.tsx` replace the "Pieces", "Measured Rooms" and "Model Library" links with one "Design Studio" link (`/studio`) first; add signed-in routes `/studio` and `/studio/:tab`; turn `/pieces`, `/rooms`, `/models` into redirects to their tab, keeping `/pieces/:packageId/versions/:version`
- [x] 3.2 Update `App.test.tsx`: nav shows "Design Studio" and none of the three old entries, "Old address" redirects, the inspector address still opens, sign-in lands on the Pieces tab, signed-out `/studio/models` goes to sign-in; verify `pnpm test App`

## 4. Checks

- [x] 4.1 Run `pnpm lint`, `pnpm test` and `pnpm build` in `frontend/`; all pass
  2026-10-14: `pnpm lint` — no findings; `pnpm test` — 329 passed / 37 files; `pnpm build` succeeded.
- [ ] 4.2 Browser check (record it with the date): switch all three tabs, show and hide labels (shared with Pricing Overview), reload on Measured Rooms, open `/models` and land on its tab, create a piece from the Pieces tab, open a piece inspector and come back via "Back to pieces", open a room's 3D view, upload and delete a model
  Browser pass 2026-10-14 (partial): headless Chromium through Python Playwright 1.63, scratch database `home_renovation_studio_ui` (dropped afterwards), backend on 8130 (developer panel on, gateway probe and Langfuse off) and a fixed `vite build` served by `vite preview` on 5210 (`API_PROXY`); the owner's 8000 and 5173 were untouched. 18 checks passed: sign-in lands on `/studio/pieces` with Pieces chosen; the nav reads Design Studio, Pricing Overview, Guidelines, Help (then the developer entries) with no Pieces, Measured Rooms or Model Library item, and Design Studio is current on every tab; the rail sits at the screen's left edge as icons (48 px); all three tabs open at their own address; "Show labels" shows the labels at 144 px, the same width and chosen-tab font, size, weight, background and colour as the Pricing Overview rail, and the choice carries to it; "Hide labels" carries back; a reload on `/studio/rooms` keeps the tab; `/models` and `/rooms` land on their tabs; `/studio/quotes` lands on Pieces; a GLB model uploaded, went checking → ready and was deleted; Create A New Piece opened a conversation; `/pieces/shoe-bench/versions/2` opens the inspector and "Back to pieces" lands on the Pieces tab; no horizontal scroll at 420 px; no page errors. Not checked: a measured room with its composition and 3D view — the scratch house file holds no room (that tab body is unchanged apart from losing its `Page` and `h1`). No model call, render or network fetch outside localhost.
