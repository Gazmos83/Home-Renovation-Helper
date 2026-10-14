## 1. Tab bodies

- [x] 1.1 Remove `Page` and the `h1` from `PriceList.tsx`, `Snapshots.tsx` and `Remnants.tsx`, keeping their intro lines, forms and query keys; verify `pnpm test PriceList Snapshots Remnants` passes unchanged

## 2. Pricing Overview page

- [x] 2.1 Add `routes/Pricing.tsx`: `Page`, `h1` "Pricing Overview", a tab list (Prices, Snapshots, Remnants) of links to `/pricing/<tab>` with `aria-selected`, and one tab panel showing the chosen body; an unknown tab redirects to `/pricing/prices`
- [x] 2.2 Add `Pricing.test.tsx` for "Prices first", "Tab chosen", "Tab address reloaded" and "Unknown tab"; verify `pnpm test Pricing Overview` passes

- [x] 2.3 Move the tabs to a rail at the page's left like the conversation's: extract `railClass`, `railItemClass`, `RailLabelsToggle` and `useRailLabels` from `components/chat/Rail.tsx` (no change to `Rail`'s behaviour), render the Pricing Overview tabs as icon links in that rail with the shared "Hide labels" switch; add tests for showing/hiding labels and the shared choice; verify `pnpm test Rail Conversation Pricing`

## 3. Navigation and routes

- [x] 3.1 In `App.tsx` replace the "Price list", "Snapshots" and "Remnants" links with one "Pricing Overview" link (`/pricing`) where "Price list" stood; add signed-in routes `/pricing` and `/pricing/:tab`; turn `/price-list`, `/snapshots`, `/remnants` into redirects to their tab
- [x] 3.2 Add tests in `App.test.tsx` for the nav ("Pricing Overview" present, the three old entries gone), "Old address" redirects, and keep "without a session the price list is the sign-in page" passing; verify `pnpm test App`

## 4. Checks

- [x] 4.1 Run `pnpm lint`, `pnpm test` and `pnpm build` in `frontend/`; all pass
  2026-10-14: `pnpm lint` — no findings; `pnpm test` — 309 passed / 35 files; `pnpm build` — tsc and Vite succeeded. After 2.3: `pnpm lint` — no findings; `pnpm test` — 318 passed / 36 files (a first run timed out three tests in other in-flight files at 5 s; the rerun passed all); `pnpm build` succeeded. One existing test ("a 401 from any call returns the owner to sign-in") now opens `/pricing/remnants` instead of `/remnants`: the redirect changes the path, which re-runs the session check and races the test's stubbed 401; the behaviour under test is unchanged.
- [x] 4.2 Browser check (record it with the date): switch all three tabs, reload on Snapshots, open `/remnants` and land on its tab, add and override a price, record a snapshot that prefills an entry and see it on Prices, add and remove a remnant, one refusal per form
  Browser pass 2026-10-14, after 2.3 (partial): headless Chromium through Python Playwright, scratch database `home_renovation_pricing_ui` (dropped afterwards), backend on 8110 and a fixed `vite build` served by `vite preview` on 5190 (`API_PROXY`) — the dev server reloaded mid-test while another session edited `frontend/src`; the owner's 8000 and 5173 and the other session's 8100 and 5180 were untouched. 18 checks passed: nav shows "Pricing Overview" and none of the three old items; the page opens on Prices; the left rail shows only icons, "Show labels" shows Prices / Snapshots / Remnants beside them (screenshots compared with the conversation rail: same width, icon size, accent and switch), and the choice is kept when leaving and coming back, then hidden again; Add an entry without a key refused on the form, then added; entry edited; override set and cleared; a bauhaus.info URL refused ("not a permitted source"); Snapshots tab at `/pricing/snapshots` survives a reload; a future-dated snapshot refused next to the date; a snapshot recorded and deleted; `/remnants` lands on the Remnants tab with the nav item current; a zero-length remnant refused; a remnant added and removed; `/price-list` and `/pricing/quotes` land on Prices. Not passed: "record a snapshot that prefills an entry" — the API refuses it ("a panel needs its sheet length, width, thickness") because `Snapshots.tsx` always sends the prefill as category `panel` with no sheet size; this predates the change (same code at HEAD 41158e7). No toom URL was fetched and no captured entry refreshed (no network calls from the check).
  Closed 2026-10-14 by the owner's decision with the prefill step left as a known issue: the snapshot form's "Also create a price-list entry" is refused by the API for want of a panel sheet size. It predates this change and is not fixed here; the "Prefilled entry reaches the Prices tab" scenario is covered by `Pricing.test.tsx` against a stubbed API.
