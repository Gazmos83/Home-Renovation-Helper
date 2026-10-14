## Why

`studio-tile-grid` gave the Pieces and Measured Rooms tabs a sub column holding a single view ("All pieces", "All rooms"), which takes space and leads nowhere new. The owner asked (2026-10-14) for that column to list the pieces and rooms by name instead, so any item can be opened directly from it without paging through the grid.

## What Changes

- **Pieces sub column:** lists every piece by name (its id), in the grid's order. "All pieces" is removed.
- **Measured Rooms sub column:** lists every measured room by name, then each composition that has no room of its own (apartment, or a room no longer in the house file), in the grid's order. "All rooms" is removed.
- **Selecting a name** opens that item's popup over the grid, at the same address as choosing its tile (`/studio/pieces/<id>`, `/studio/rooms/<room>`, `/studio/rooms/compositions/<slug>`), keeping `?page`. The name is highlighted while its popup is open. Back, Esc or Close returns to the grid.
- **Nothing selected:** the tab shows the tile grid as defined in `studio-tile-grid`. No sub-column entry is highlighted.
- **Phone (below 768 px):** the names are one row of name chips above the grid that scrolls sideways.
- **Long lists:** the column scrolls on its own, and long names are cut short with an ellipsis and shown in full on hover.
- **Unchanged:** Model Library keeps "Uploaded models" and "Upload model". Tiles, popups, paging and the left rail are as `studio-tile-grid` defines them.

This change touches no ladder step and no agent. It is Studio UI only. **The render guard and the bpy allow-list are not affected.**

**Order:** this change builds on `studio-tile-grid` and modifies the requirement text that change introduces. Archive `studio-tile-grid` first.

## Capabilities

### New Capabilities
<!-- none -->

### Modified Capabilities
- `studio-ui`: the Design Studio sub-menu for Pieces and Measured Rooms becomes a list of item names that open their popups. The Model Library sub-menu stays as it is.

## Impact

- **Frontend:** `routes/Studio.tsx` builds the Pieces and Rooms sub-menus from the list queries the tabs already use (same query keys, no extra request). `components/studio/SubMenu.tsx` gains a scrolling column, truncated labels, an optional empty text, and the link state used when opening a popup. Tests: `Studio.test.tsx`, `SubMenu.test.tsx`, `App.test.tsx`.
- **No backend, API, dependency or data change.**
- **Specs:** `openspec/specs/studio-ui/spec.md`, the Design Studio tabs requirement.
