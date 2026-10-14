## Context

`App.tsx` lists "Price list" (`/price-list`), "Snapshots" (`/snapshots`) and "Remnants" (`/remnants`) as three navigation entries, each a signed-in route to its own file in `frontend/src/routes/`. Each file renders `Page`, an `h1`, a one-line intro (Snapshots, Remnants) and its lists and forms. The Studio has no tab component: the conversation's panels use the `Rail` flyout, which is not a page-level tab bar.

## Goals / Non-Goals

**Goals:** one Pricing Overview page with three tabs; each tab linkable; old addresses keep working; no change to any form, list, refusal or query key.

**Non-Goals:** no new API, no backend change, no restyling of the forms or the price-list table, no move of the Guidelines page.

## Decisions

- **Page and tab names.** Page title and nav label "Pricing Overview"; tabs "Prices", "Snapshots", "Remnants" as the owner named them. The owner chose "Pricing Overview" (2026-10-14); the route stays `/pricing`.
- **Tab in the path.** Route `/pricing/:tab` with `tab` one of `prices`, `snapshots`, `remnants`; `/pricing` and an unknown tab go to `/pricing/prices`. The `NavLink` for `/pricing` stays active on every tab without extra code. Alternative — `?tab=` query — rejected: a path segment matches how the rest of the Studio addresses pages (`/pieces/:packageId/versions/:version`).
- **Old addresses redirect.** `/price-list`, `/snapshots`, `/remnants` become `<Navigate replace>` to their tab, so bookmarks and the existing "price list without a session" scenario keep working (the redirect lands on the signed-in guard).
- **Tabs on a left rail like the conversation's.** The owner asked (2026-10-14) for the tabs at the page's left with the conversation rail's font, icon style, colour scheme and "Hide labels" switch. The rail's look and switch are extracted from `components/chat/Rail.tsx` — `railClass`, `railItemClass`, `RailLabelsToggle` and `useRailLabels` — and `Rail` uses them unchanged in behaviour. `Pricing.tsx` renders the same column with a vertical `role="tablist"` labelled "Pricing Overview" of three `role="tab"` links (`aria-label`, `aria-selected`, `aria-controls`) with lucide icons (Tag, Camera, Layers), the chosen tab on `bg-accent`, and the switch at the foot outside the tab list. Links, not buttons, so a tab is a real address and the browser's back button works. `Rail` itself is not reused: it opens flyouts, while these tabs choose the page body. The label choice uses the same browser key (`studio.rail.expanded`), so showing labels on one rail shows them on the other — one feature, one setting.
- **Bodies, not rewrites.** `PriceList`, `Snapshots` and `Remnants` keep their default exports and logic; each drops `Page` and its `h1` (the page heading is "Pricing Overview") and keeps its intro line. Only the chosen tab is mounted, so a tab's queries run when it is opened, as today when its page is opened. Their existing tests render the components directly and keep passing unchanged.

## Risks / Trade-offs

- [An existing test may look for a tab body's `h1`] → none do today (checked); new tests look for the tab and the page heading.
- [A snapshot that prefills an entry updates the Prices tab] → it already invalidates `["price-list"]`, so the Prices tab shows the entry when opened.
- [Known issue, not fixed here (owner, 2026-10-14)] The snapshot form always sends its prefill as category `panel` with no sheet size, which the API refuses ("a panel needs its sheet length, width, thickness"), so "Also create a price-list entry" fails in the running app. It predates this change; the tab refresh after a successful prefill is covered by a stubbed test.
