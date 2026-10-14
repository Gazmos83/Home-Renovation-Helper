## Context

`App.tsx` lists "Pieces" (`/pieces`), "Measured Rooms" (`/rooms`) and "Model Library" (`/models`) as the first three navigation entries, each a signed-in route to its own file in `frontend/src/routes/`. Each file renders `Page` and a heading row with its `h1` (Pieces also holds the "Create A New Piece" button there), an intro and its cards. `Pricing.tsx` and `admin/AgentSettings.tsx` already show the pattern asked for: a left rail built from `railClass`, `railItemClass`, `RailLabelsToggle` and `useRailLabels` (`components/chat/Rail.tsx`), a vertical `role="tablist"` of links, one tab panel, and the page `h1`.

## Goals / Non-Goals

**Goals:** one Design Studio page with three tabs on the shared left rail; each tab linkable; old addresses keep working; no change to any card, form, dialog, 3D view, refusal or query key.

**Non-Goals:** no new API, no backend change, no restyling of the tab bodies, no move of the piece inspector, no change to Pricing Overview or Guidelines.

## Decisions

- **Page and tab names.** Page title and nav label "Design Studio"; tabs "Pieces", "Measured Rooms", "Model Library" as the owner named them. Route `/studio`, tab ids `pieces`, `rooms`, `models` (matching the old paths).
- **Same component shape as Pricing Overview.** `Studio.tsx` copies `Pricing.tsx`: `useParams` tab, unknown tab → `<Navigate replace>` to `/studio/pieces`, rail with tab links (`aria-label`, `aria-selected`, `aria-controls`), lucide icons at 20 px (Armchair for Pieces, Ruler for Measured Rooms, Package for Model Library), the chosen tab on `bg-accent`, `RailLabelsToggle` at the foot, then `Page` with `h1` "Design Studio" and one `role="tabpanel"`. The labels use the AgentSettings wrapping span, since "Measured Rooms" and "Model Library" are as long as the rail is wide. No new shared component: a third copy of a 40-line layout is cheaper than an abstraction the owner did not ask for.
- **Shared label choice.** Same `useRailLabels` browser key, so "Show labels" on any rail shows them on all four.
- **Bodies, not rewrites.** `Pieces`, `Rooms` and `ModelLibrary` keep their default exports and logic; each drops `Page` and its `h1` (the page heading is "Design Studio"). Pieces keeps the "Create A New Piece" button in its heading row; its error and loading states render without `Page`. Only the chosen tab is mounted, so a tab's queries run when it is opened, as today.
- **Old addresses redirect.** `/pieces`, `/rooms`, `/models` become `<Navigate replace>` to `/studio/<tab>`. The internal links to `/pieces` (Login, Conversation, PieceInspector, the catch-all and dev-route fallbacks) are left as they are and pass through the redirect — fewer files touched, same result. `/pieces/:packageId/versions/:version` stays a route of its own, matched before the redirect.
- **Vite proxy.** `/studio` shares no path with the API, so it needs no proxy entry. `/rooms` and `/models` keep their `page` rule so a browser visit to the old address still gets the app (and its redirect) while API calls reach the API.

## Risks / Trade-offs

- [Two existing tests assert the tab body's `h1`] (`Rooms.test.tsx` "Measured Rooms", `ModelLibrary.test.tsx` "Model Library") → the `h1` is gone by design; those assertions move to `Studio.test.tsx`, which checks the page heading and the chosen tab. The rest of those tests render the bodies directly and pass unchanged.
- [A redirect re-runs the session check in `App`] → seen with Pricing Overview: a test that stubs a 401 on an old address may need the new address. Behaviour is unchanged.
- [`split-rooms-page` is uncommitted] → this change edits `Rooms.tsx` and `ModelLibrary.tsx` from that change; apply after it is committed so the two do not mix in one commit.
