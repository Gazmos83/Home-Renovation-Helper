## 1. Close the flyout

- [x] 1.1 In `Conversation.tsx` pass `ProjectPanel` handlers that call `inspect` / `inspectRoom` and then close the flyout (`setPanel(null)`), leaving those two functions as they are. Verify with Vitest: "Inspect version 1" and "Inspect Hall" in the panel close it and show the inspector or room view; approve keeps it open; a build notice's Inspect button still works.
- [x] 1.2 Update the existing tests that click a second Inspect button in the same open panel so they reopen the Project icon first, with no other change to them.

## 2. Checks

- [x] 2.1 Run `pnpm lint`, `pnpm test` and `pnpm build`, and record the results here. Result 2026-10-13: lint clean, tsc clean, 268 tests passed, build green.
- [x] 2.2 Browser check: open Project, press Inspect version N, and see the flyout close with the inspector shown; same for the room. No render is needed (no tier). Browser pass 2026-10-13, headless Chrome (Playwright) on a scratch stack: scratch database `home_renovation_check_flyout`, a copy of listening-wall v17 in a scratch render root, backend on 8100 and Vite on 5180, with the owner's 8000 and 5173 servers untouched. (1) Project flyout opened with "Inspect version 17" and a Project heading. (2) Pressing it closed the flyout and showed the Inspector beside the chat (URL `?inspect=listening-wall/17`, "Overall: W 2206 mm × H 2238 mm × D 400 mm"). (3) Reopening the Project icon opened the flyout with the inspector still shown. (4) Approve version 17 in the flyout left it open. (5) The Tools flyout still opens on its own. Not exercised in the browser: "Inspect <room>", which needs a composed room; it is covered by the Vitest case. No render, no tier.
