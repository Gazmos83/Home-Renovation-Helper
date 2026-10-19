No task renders; no render tier applies.

## 1. Prerequisites

- [ ] 1.1 Archive `studio-pricing-and-agent-settings-tabs` (its tasks 6.1 and 6.3) so `openspec/specs/dev-panel/spec.md` holds "Agent and model pages are views of the Design Studio's AI & Agent Settings tab"; verify with `openspec validate merge-guideline-pages --strict`

## 2. Guidelines view

- [x] 2.1 Move `frontend/src/routes/GuidelineNotes.tsx` to `frontend/src/components/GuidelineNotesSection.tsx` as a `<section aria-label="Guideline notes">` with an `<h2>`, without `<Page>`, `<h1>` or `<HardwareDataSection />`; move its test to `components/GuidelineNotesSection.test.tsx` rendering the section (edit/delete and citation-refusal tests kept); verify both pass under `pnpm test`
- [x] 2.2 In `frontend/src/routes/admin/Guidelines.tsx`, drop `<Page>` and make the `<h1>` an `<h2>`, wrap the upload form and source table in a "Guideline PDFs" section, and render `GuidelineNotesSection` and `HardwareDataSection` below it; verify by an `admin/Guidelines.test.tsx` test that the view shows "Upload a PDF", "Guideline notes" and "Hardware data", with existing tests passing (queries scoped with `within` where "Title" is ambiguous)

## 3. Engineering Knowledge and Design Rules views

- [x] 3.1 In `frontend/src/routes/admin/Knowledge.tsx`, drop `<Page>` and make the `<h1>` an `<h2>`; verify `Knowledge.test.tsx` passes (heading assertions adjusted only if they named the level)
- [x] 3.2 In `frontend/src/routes/admin/Rules.tsx`, drop `<Page>` (including the loading return) and make both `<h1>`s `<h2>`s; verify `Rules.test.tsx` passes

## 4. Design Knowledge tab

- [x] 4.1 Add `frontend/src/routes/admin/DesignKnowledge.tsx` with `KNOWLEDGE_VIEWS` and `DesignKnowledgeTab` (unknown view → `/admin/design-knowledge/guidelines`), mirroring `AgentSettings.tsx`; verify with a `DesignKnowledge.test.tsx` mirroring `AgentSettings.test.tsx` (each view shows its body, unknown view redirects)
- [x] 4.2 In `frontend/src/routes/Studio.tsx`, add the `design-knowledge` developer tab after `agents` and its `useSubMenu` branch; verify by `Studio.test.tsx` that the developer rail shows "Design Knowledge" after "AI & Agent Settings" with one divider, the sub-menu lists the three views in order, and the owner rail has no "Design Knowledge"
- [x] 4.3 In `frontend/src/App.tsx`, serve `/admin/design-knowledge` and `/admin/design-knowledge/:tab` with `<Studio dev fixedTab="design-knowledge" />` behind the developer check; redirect `/guidelines`, `/admin/guidelines`, `/admin/knowledge`, `/admin/rules` to their views for the developer and to `/pieces` otherwise; remove the homeowner "Guidelines" link, the `adminLinks` entries and their divider, and the now-unused imports; verify by `App.test.tsx` tests: developer and owner headers show no "Guidelines", "Knowledge" or "Rules", each old address opens its view for the developer, `/guidelines` without the gate opens Pieces, `/admin/design-knowledge/engineering` reload marks "Design Studio" current

## 5. Verification

- [x] 5.1 Run `pnpm lint`, `pnpm test` and `pnpm build` in `frontend/` and confirm all pass; record the counts here
  Run 2026-10-15: `pnpm lint` clean, `pnpm test` 441 passed in 45 files, `pnpm build` built.
- [x] 5.2 Browser check against the running service at 1280 × 800 and 360 × 780: as developer choose Design Knowledge on the rail, switch the three views, reload a view address, open the four old addresses; on Guidelines upload a PDF, add, edit and delete a note, trigger the missing-citation refusal, add, edit and delete a data sheet and trigger the off-host refusal; open Engineering Knowledge and Design Rules; with the dev panel off confirm no "Design Knowledge" tab, no "Guidelines" header link, and `/guidelines` opens Pieces. Record the date and what was exercised here
  Browser pass 2026-10-15: headless Chromium through Python Playwright 1.63. Scratch database `home_renovation_dk_check` and scratch guideline, upload and render folders, dropped and deleted afterwards. Backend on 8132 (scratch owner login, gateway probe and Langfuse off, a scratch OpenRouter key, RunPod settings blank) and a fresh `vite build` served by `vite preview` on 5212; the owner's 8000 and 5173 were untouched. No model call, no render and no Blender process.
  - **Developer, 1280 × 800 (19 of 19):** header links are exactly "Design Studio" and "Help". The rail ends with "AI & Agent Settings", "Design Knowledge" after one divider. Choosing Design Knowledge opens `/admin/design-knowledge` with the sub-menu "Guidelines", "Engineering Knowledge", "Design Rules", Guidelines current, the h1 "Design Studio", and the "Guideline PDFs", "Upload a PDF", "Guideline notes" and "Hardware data" headings. A one-page PDF was uploaded, listed as ingested and deleted; a non-PDF was refused with "not a PDF". A note without a citation was refused next to the citation field; with "Neufert p. 123" it was added, edited to p. 124 and deleted. A hinge sheet with a toom page on `www.example.com` was refused next to the page URL; with a toom.de page, Cup Ø 35 and end distance 80-120 it was listed with its other values missing, its cup depth edited to 13 and deleted. The sub-menu switched to Engineering Knowledge ("Engineering knowledge") and Design Rules ("Design rules", "Open items for you"). A reload of `/admin/design-knowledge/engineering` kept the view and marked Design Studio current. `/guidelines`, `/admin/guidelines`, `/admin/knowledge`, `/admin/rules` and `/admin/design-knowledge/quotes` landed on the guidelines, guidelines, engineering, rules and guidelines views.
  - **Developer, 360 × 780:** on the rules, guidelines and engineering views only the phone row of views is shown, with the chosen view current, and the page is no wider than 360 px.
  - **Dev panel off (6 of 6):** header links are "Design Studio" and "Help"; the rail has no divider and no Design Knowledge tab; `/guidelines`, `/admin/design-knowledge/guidelines` and `/admin/guidelines` open the Pieces tab with no guideline notes.
  - No page errors. Console errors were only expected statuses: the 401 before sign-in, the three 422 refusals above, and the developer check's 404 with the panel off.
