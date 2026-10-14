## 1. Tab bodies

- [x] 1.1 Remove `Page` and the page `h1` from `Memory.tsx`, `Workflow.tsx`, `ConversationCalls.tsx`, `Offload.tsx`, `Feedback.tsx`, `Usage.tsx`, `Plugins.tsx` and `Models.tsx`; turn their loading and error `Page`s into fragments; make Models' "Generation and budgets" an `h2`; keep every form, table, graph and query key; verify `pnpm test admin/` passes unchanged

## 2. AI & Agent Settings page

- [x] 2.1 Add `routes/admin/AgentSettings.tsx`: `Page`, `h1` "AI & Agent Settings", a wrapping tab list (Agent Memory, Agent Workflow, Agent Calls, Render Offload, Agent Score, Token Usage, Plugins, Models and Routing) of links to `/admin/agents/<tab>` with `aria-selected`, and one tab panel showing the chosen body; an unknown tab redirects to `/admin/agents/memory`
- [x] 2.2 Add `AgentSettings.test.tsx` for "Agent Memory first", "Tab chosen", "Tab address reloaded" and an unknown tab; verify `pnpm test AgentSettings` passes
- [x] 2.3 Move the tabs to a rail at the page's left like Pricing Overview's: render them as icon links (Brain, Workflow, Activity, Server, ThumbsUp, Gauge, Puzzle, Route) with `railClass`, `railItemClass`, `RailLabelsToggle` and `useRailLabels` from `components/chat/Rail.tsx`; add tests for showing/hiding labels and the shared choice; verify `pnpm test AgentSettings Pricing Rail`

## 3. Navigation and routes

- [x] 3.1 In `App.tsx` replace the eight admin links with one "AI & Agent Settings" link (`/admin/agents`) where "Models" stood; add dev-gated routes `/admin/agents` and `/admin/agents/:tab`; turn the eight old routes into dev-gated redirects to their tab
- [x] 3.2 Add tests in `App.test.tsx` for the developer nav (new entry present, eight old entries gone, Guidelines/Knowledge/Rules kept), "Old address" and "Not a developer"; verify `pnpm test App`

- [x] 3.3 Keep a reloaded developer page: `App.tsx` held `dev` at `false` until `/admin/models` answered, so the dev-gated route sent a reload of any developer page to `/pieces` (true of the old admin pages too). `dev` is now `null` until the check answers and the app shows Loading meanwhile; test "a reloaded developer tab waits for the developer check" fails without it

## 4. Checks

- [x] 4.1 Run `pnpm lint`, `pnpm test` and `pnpm build` in `frontend/`; all pass
- [x] 4.2 Browser check (record it with the date): open every tab, reload on Render Offload, open `/admin/conversations` and land on Agent Calls, change and reset one memory setting, toggle a plugin off and on, narrow the window and see the tab bar wrap; after 2.3: show and hide the rail's labels, compare it with the Pricing Overview rail, and see the label choice kept when leaving and coming back
  Browser pass 2026-10-14: headless Chromium through Python Playwright 1.63, scratch database `home_renovation_agents_ui` (dropped afterwards), backend on 8100 with the developer panel on and the gateway probe off, Vite on 5180 (`API_PROXY`); the owner's 8000 and 5173 were untouched. 16 checks passed: the nav shows "AI & Agent Settings", Guidelines, Knowledge, Rules and none of the eight former entries; the entry opens Agent Memory; all eight tabs open at their own address with content and the nav item current; a reload on `/admin/agents/offload` stays on Render Offload (failed before 3.3); `/admin/conversations` lands on Agent Calls; "Start compressing at" saved as 75 and reset to 100; `room_fit` toggled off and on; at 420 px the tab bar wraps to three rows with no horizontal page scroll; no page errors. No model call, render or network fetch outside localhost.
  Browser pass 2026-10-14, after 2.3: headless Chromium through Python Playwright 1.63, scratch database `home_renovation_agents_rail_ui` (dropped afterwards), backend on 8120 (developer panel on, gateway probe off) and a fixed `vite build` served by `vite preview` on 5200 (`API_PROXY`), so edits by another session could not reload the page mid-test; the owner's 8000 and 5173 were untouched. 20 checks passed: the 16 above again, plus the rail sits at the screen's left edge as icons only (48 px); "Show labels" shows all eight labels at 144 px; the chosen tab's font, size, weight, accent background, text colour and 20 px icon match the Pricing Overview rail exactly and the label choice carries between the two pages; "Hide labels" hides them on both; no horizontal scroll at 420 px. Found and fixed during the pass: "Models and Routing" ran past the rail's edge with labels shown — the labels on this rail now wrap within their 40 px row instead of widening the shared rail, which the conversation's flyouts are placed against.
