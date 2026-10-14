## Why

Prices, snapshots and remnants are three navigation entries for one job: the material figures that price a cut list. A snapshot can prefill a price-list entry and pricing uses remnants first, yet the owner has to move between three pages to follow that. The owner asked (2026-10-14) to combine "Prices", "Snapshots" and "Remnants" into one page with three tabs.

## What Changes

- A new **Pricing Overview** page at `/pricing` with three tabs: **Prices** (the current price-list page), **Snapshots** and **Remnants**. Prices is chosen first. The tabs are a rail at the screen's left edge with the same font, icon style, colours and "Hide labels" switch as the conversation page's panel rail; the label choice is shared with that rail.
- Each tab has its own address (`/pricing/prices`, `/pricing/snapshots`, `/pricing/remnants`) so a tab can be reloaded and linked; `/pricing` opens Prices.
- The old addresses `/price-list`, `/snapshots` and `/remnants` redirect to their tab, so bookmarks keep working.
- The Studio navigation shows one "Pricing Overview" entry in place of "Price list", "Snapshots" and "Remnants".
- Not changed: every API route, every form, list, refusal and query key on the three pages. Only where they are shown changes.

Ladder step and agents: none — Studio UI only; no agent, prompt, tool or generator is touched. The render guard and the `bpy` allow-list are not affected.

## Capabilities

### New Capabilities

### Modified Capabilities
- `studio-ui`: the price list, snapshots and remnants requirements now describe tabs of one Pricing Overview page; guideline notes keep their own page.

## Impact

Frontend only: a new `frontend/src/routes/Pricing.tsx`; `PriceList.tsx`, `Snapshots.tsx` and `Remnants.tsx` lose their `Page` wrapper and `h1` and become tab bodies; `frontend/src/App.tsx` (nav entry, routes, redirects); tests in `App.test.tsx` and a new `Pricing.test.tsx`. No backend, schema, migration or API change.
No task renders; no tier is used.
