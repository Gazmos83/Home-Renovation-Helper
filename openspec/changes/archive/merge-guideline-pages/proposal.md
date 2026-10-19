## Why

Guidelines, engineering knowledge and design rules are three developer pages reached from the header, and guidelines are split across two of them: the homeowner page `/guidelines` holds the hand-written guideline notes and the Hardware data section, the developer page `/admin/guidelines` the PDF upload and the source list. Everything the Designer and the Researcher look up should be managed in one place on the Design Studio's rail, beside the AI & Agent Settings tab. The owner decided on 2026-10-15 to merge the guideline pages behind the developer gate and to move all three pages into a Design Studio tab named "Design Knowledge".

## What Changes

- A developer-only **Design Knowledge** tab on the Design Studio rail, below the divider, after AI & Agent Settings. Its sub-menu holds three views, each with its own address on the developer route tree:
  - **Guidelines** (`/admin/design-knowledge/guidelines`): the PDF upload and the source list, the guideline notes (list, add, edit, delete) and the Hardware data section (list, add, edit, delete), on one view.
  - **Engineering Knowledge** (`/admin/design-knowledge/engineering`): what `/admin/knowledge` shows.
  - **Design Rules** (`/admin/design-knowledge/rules`): what `/admin/rules` shows, including its open items.
- `/admin/design-knowledge`, and an address naming no known view, opens Guidelines.
- **BREAKING (navigation):** the homeowner header loses "Guidelines"; the developer header loses "Guidelines", "Knowledge" and "Rules". The homeowner page `/guidelines` is removed.
- The old addresses `/guidelines`, `/admin/guidelines`, `/admin/knowledge` and `/admin/rules` open the matching view for the developer; without the developer gate they open the Pieces tab.
- **Behaviour change, explicit:** without the developer gate (the dev panel switched off, or a session that is not the developer's), notes and data sheets can no longer be managed from the UI. The `/guideline-notes` and `/hardware-data` API routes keep their owner gate, and their data, corpus passages and `search_guidelines` results are unchanged.
- No ladder step, no agent, no prompt and no tool changes. The render guard and the `bpy` allow-list are not affected. Nothing renders.

## Capabilities

### New Capabilities
<!-- none -->

### Modified Capabilities
- `dev-panel`: a new Design Knowledge tab with three views; the AI & Agent Settings requirement no longer keeps "Guidelines", "Knowledge" and "Rules" header entries.
- `studio-ui`: guideline notes and the Hardware data section move from the homeowner page to the Guidelines view of the Design Knowledge tab.

## Impact

- Frontend: `src/routes/Studio.tsx` (rail tab, sub-menu); a new `src/routes/admin/DesignKnowledge.tsx` tab body; `src/routes/admin/{Guidelines,Knowledge,Rules}.tsx` lose their page wrappers; `src/routes/GuidelineNotes.tsx` becomes a section component; `src/App.tsx` (header links, routes, redirects); their tests.
- Backend: none. API gates unchanged (`/guideline-notes` and `/hardware-data` stay `require_owner`; `/admin/guidelines`, `/admin/knowledge` and `/admin/rules` APIs stay `require_dev`).
- Specs: `dev-panel` and `studio-ui`. `design-guidelines` is unchanged.
- Order: `studio-pricing-and-agent-settings-tabs` must be archived first, since this change modifies the requirement it adds. The Engineering Knowledge view carries the page `furniture-engineering-rag-foundation` task 6.2 is still finishing.
