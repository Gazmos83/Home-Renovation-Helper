## Why

Pieces, Measured Rooms and Model Library are three navigation entries for one job: designing pieces and placing them, with bought models, in the measured rooms. Prices and the developer's agent pages were already combined into tabbed pages with a left rail. The owner asked (2026-10-14) to combine "Pieces", "Measured Rooms" and "Model Library" into one "Design Studio" page with the three as tabs at its left, with the same colour scheme, icon style, font and "Hide labels" switch.

## What Changes

- A new **Design Studio** page at `/studio` with three tabs: **Pieces**, **Measured Rooms** and **Model Library**. Pieces is chosen first. The tabs are a rail at the screen's left edge with the same font, icon style, colours and "Hide labels" switch as the conversation, Pricing Overview and AI & Agent Settings rails; the label choice is shared with them.
- Each tab has its own address (`/studio/pieces`, `/studio/rooms`, `/studio/models`) so a tab can be reloaded and linked; `/studio` opens Pieces.
- The old addresses `/pieces`, `/rooms` and `/models` redirect to their tab, so bookmarks, the sign-in landing and every in-app "All pieces" link keep working. The piece inspector keeps its address `/pieces/<id>/versions/<n>`.
- The Studio navigation shows one "Design Studio" entry, first, in place of "Pieces", "Measured Rooms" and "Model Library".
- Not changed: every API route, card, form, dialog, 3D view, refusal and query key on the three pages. Only where they are shown changes.

Ladder step and agents: none — Studio UI only; no agent, prompt, tool or generator is touched. The render guard and the `bpy` allow-list are not affected.

## Capabilities

### New Capabilities

### Modified Capabilities
- `studio-ui`: the Pieces, Measured Rooms and Model Library pages become tabs of one Design Studio page; the navigation and sign-in landing name Design Studio.

## Impact

Frontend only: a new `frontend/src/routes/Studio.tsx`; `Pieces.tsx`, `Rooms.tsx` and `ModelLibrary.tsx` lose their `Page` wrapper and `h1` and become tab bodies; `frontend/src/App.tsx` (nav entry, routes, redirects); tests in `App.test.tsx`, a new `Studio.test.tsx`, and the two page-heading assertions in `Rooms.test.tsx` and `ModelLibrary.test.tsx`. No backend, schema, migration or API change.
Depends on `split-rooms-page` (archived, its spec delta and code not yet committed or synced at the time of writing): its Measured Rooms and Model Library requirements and code are the tab bodies here, and its specs must be synced before this change is archived.
No task renders; no tier is used.
