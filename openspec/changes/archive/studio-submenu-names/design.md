## Context

After `studio-tile-grid`, `routes/Studio.tsx` builds each tab's sub-menu from a static `views` list (`all` for Pieces and Rooms; `all` and `upload` for Models) and renders `components/studio/SubMenu.tsx` twice: once as a column (`hidden md:flex`) and once as a row (`md:hidden`). `useStudioDialog(tab)` reads the dialog from the path and gives `open`, `close`, `dismiss` and `grid`. The tab bodies load `["pieces"]` (`api.pieces`), `["rooms"]` (`api.rooms`), `["compositions"]` (`api.compositions`) and `["model-library"]`. Rooms derives its tile order and its standalone ("unclaimed") compositions inline in `Rooms.tsx`. Radix's modal dialog blocks pointer events outside itself, so while a dialog is open the sub-menu can be seen but not clicked.

## Goals / Non-Goals

**Goals:** Pieces and Rooms sub-menus list item names in grid order. A name opens the item's dialog through the same address as its tile. The current item is highlighted. The column scrolls, and a phone gets a scrolling row.

**Non-Goals:** no change to the Model Library sub-menu, tiles, dialogs, paging or the rail; no search or filter in the sub-menu; no backend change; no jumping the grid to the page that holds the chosen item.

## Decisions

- **Names come from the same queries.** `Studio` calls `useQuery` with the tabs' own keys and query functions (`["pieces"]`; `["rooms"]` + `["compositions"]`). TanStack Query shares one request and one cache entry with the tab body, so there is no extra request, and a create or delete updates the sub-menu with the grid. Queries run only for the chosen tab (`enabled: tab === …`), as the bodies do today. *Alternative:* the tab body pushes its names up through a context. Rejected: it couples the bodies to the shell for no gain.
- **One order, defined once.** The Rooms grid order (rooms, then compositions that no room claims) moves from `Rooms.tsx` into `lib/rooms.ts` as `roomEntries(rooms, compositions, roomsRead)`, returning `{ kind, name, segments }` entries, with `isOpen(entry, segments)` to match an entry to the dialog address. `Rooms.tsx` builds its tiles from it and `Studio.tsx` builds its sub-menu from it, so the two can't drift apart. This is a small extraction, needed so the order is shared. Pieces needs no helper: both use the `api.pieces` order.
- **Links, not buttons.** Each name is a `Link` to the item's dialog address, plus the current `?page`, with `state: { fromGrid: true }`. This is exactly what `useStudioDialog.open` does, so Back and Close behave as they do for a tile. Names are encoded per path segment, as `open` encodes them.
- **Highlight from the address.** For Pieces the current entry is `dialog.segments[0]`. For Rooms it is the entry for which `isOpen(entry, dialog.segments)` holds (`[<room>]` or `["compositions", <slug>]`), the same match `Rooms.tsx` uses to pick its dialog. An unknown address highlights nothing, and the tab's existing `dismiss` takes the address back to the grid.
- **SubMenu grows three small options, no new component.** Each item gets `title` (full name on hover), the label is wrapped in `truncate` (the column link becomes `min-w-0 justify-start`), and an optional `empty` text is shown when `items` is empty. The column adds `overflow-y-auto`. It is already `sticky` with a fixed `h-[calc(100vh-var(--header-h))]`, so it scrolls on its own. The row is already `overflow-x-auto`; its links are `shrink-0` chips, so names stay whole and the row scrolls.
- **Model Library unchanged.** Its `views` stay static. `Studio` keeps a per-tab builder: Pieces → names, Rooms → names, Models → the two views.
- **Clicking a name while a dialog is open.** The modal blocks it, so the owner closes the current dialog first. This matches how tiles behave under an open dialog. The highlight still shows which item is open.

## Risks / Trade-offs

- [Many pieces make the phone row long] → It scrolls sideways inside its own box (`overflow-x-auto`), and the page width is unchanged. This is checked in the browser pass at 360 px with 18 pieces.
- [Rooms grid order logic moves] → `Rooms.test.tsx` keeps covering the order ("apartment after rooms"). A unit test of `roomEntries` covers it directly.
- [Studio tests now need the list stubs] → `Studio.test.tsx` already stubs `/packages`, `/rooms`, `/compositions` and `/models`. The new scenarios add pieces and rooms to those stubs.
- [Depends on `studio-tile-grid`] → apply after `studio-tile-grid` is archived, so the main spec holds the requirement this delta modifies.

## Migration Plan

UI only. Deploy with the frontend build. Rollback: revert the commit.
