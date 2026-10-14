No task in this change renders, so no render tier applies. Apply after `studio-tile-grid` is archived.

## 1. Shared order

- [x] 1.1 Extract the Measured Rooms grid order (rooms, then compositions no room claims) from `routes/Rooms.tsx` into `lib/rooms.ts` as `roomEntries(rooms, compositions, roomsRead)` returning `{ kind, name, segments }`, with `segments` being `[<room>]` or `["compositions", <slug>]`, plus `isOpen(entry, segments)`, which matches an entry to a dialog address. Use it for the Rooms tiles. Add `lib/rooms.test.ts` covering rooms first, apartment after, and a room's own composition not listed twice; verify `pnpm test rooms Rooms`

## 2. Sub-menu

- [x] 2.1 In `components/studio/SubMenu.tsx` add a per-item `title`, truncated labels (`min-w-0`, `truncate`), an optional `empty` text, and `overflow-y-auto` on the column. Extend `SubMenu.test.tsx` for the title, the empty text and the scrolling classes; verify `pnpm test SubMenu`
- [x] 2.2 In `routes/Studio.tsx` build the Pieces sub-menu from `["pieces"]` (each name links to `/studio/pieces/<id>` + `?page`, with `state.fromGrid`) and the Rooms sub-menu from `["rooms"]` + `["compositions"]` via `roomEntries`. Highlight the open item from the address, and show "No pieces yet" / "No rooms yet" when empty. Remove "All pieces" and "All rooms", and leave Model Library's two views unchanged. Extend `Studio.test.tsx` with "Pieces first", "Pieces listed by name", "Rooms and apartment listed", "Name opens the dialog", "Dialog closed", "Composition name opens its dialog", "No pieces", "Deleted room leaves the sub-menu" and "Names on a phone" (row markup); update the existing sub-menu tests that named "All pieces" / "All rooms"; verify `pnpm test Studio App`

## 3. Checks

- [x] 3.1 Run `pnpm lint`, `pnpm test` and `pnpm build` in `frontend/`; all pass, with counts recorded here
  2026-10-14: `pnpm lint` no findings; `pnpm test` 383 passed / 43 files; `pnpm build` succeeded. `Pieces.test.tsx` "Unknown item" now waits for the address change, as the Rooms and Models tests already did: the grid's dismiss runs in an effect after the tiles render.
- [x] 3.2 Browser check, recorded with the date, at 1280 × 800 and 360 × 780, on a scratch database and ports (the owner's 8000 / 5173 untouched, no model call, no render). Exercise: names listed in grid order with no "All" entry; a name opens its dialog and is highlighted; closing returns to the grid with none highlighted; a composition name; a long name truncated with its full name on hover; a sub-menu longer than the screen scrolls on its own; the phone name row scrolls sideways with no page scroll sideways; deleting a room removes its name; no page errors
  Browser pass 2026-10-14: headless Chromium through Python Playwright 1.63; scratch database `home_renovation_tile_grid` and scratch render and upload folders, all removed afterwards; backend on 8131 and a fresh `vite build` served by `vite preview` on 5211. The owner's 8000 and 5173 were untouched; no model call and no render. Seeded with the app's own house-file code: 26 pieces (one with a 60-character id), rooms Bad, Hall and Wohnen, a Wohnen composition and an apartment composition Wohnung. Checked at 1280 × 800 and at 360 × 780:
  - The "Pieces" sub-menu lists all 26 names in the grid's order (checked against the tiles' names across pages), with no "All" entry. "Measured Rooms" lists Bad, Hall, Wohnen, then Wohnung, matching the tiles.
  - Choosing piece-20 opens `/studio/pieces/piece-20?page=2` with its name `aria-current`; Escape returns to `/studio/pieces?page=2` with no name highlighted.
  - The Wohnung name opens `/studio/rooms/compositions/apt-wohnung`, highlighted.
  - The 60-character name is cut short (span 350 px of content in 135 px on the laptop, 168 px on the phone), with its full name as its title.
  - The laptop column scrolls on its own (scrollHeight 948 against clientHeight 748; scrollTop 200 while `window.scrollY` stays 0).
  - The phone name row scrolls sideways (2184 px of content in 288 px) while the page stays 360 px wide.
  - Deleting Bad from its dialog removes its name.
  - No page errors.
- [x] 3.3 At archive time sync the delta into `openspec/specs/studio-ui/spec.md`; verify `openspec validate studio-submenu-names --strict`
