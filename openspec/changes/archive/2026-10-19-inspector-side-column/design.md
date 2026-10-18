## Context

`InspectorView.tsx` (piece) and `RoomView.tsx` (room) each lay out their stage the same way: a row with the `Choice` groups "Camera" and "Mode", a row of toggle buttons ("Layers" or "Surfaces"), then a fixed-height box holding the lazy `InspectorCanvas`. `RoomView` already reuses `CAMERAS` and `Choice` from `InspectorView`. Tests find the controls by the group names (`Camera`, `Mode`, `Layers`, `Surfaces`) and the button names. Both views are used on wide pages and in narrow panes (`Conversation.tsx` split view and Workspace panes).

## Goals / Non-Goals

**Goals:**
- One shared section component so both inspectors fold and look the same.
- Keep every switch's state, starting value and effect exactly as now.

**Non-Goals:**
- No new switches, no saving which sections are folded, no change to the canvas, cameras or the tabs.
- No responsive stacking: the owner chose a column that is always on the right.

## Decisions

- **Native `<details open>` / `<summary>` for each section.** Folding is built into the browser, keyboard-accessible and keeps the children mounted, so React state is untouched and a folded switch keeps its value. A controlled shadcn accordion was considered; it adds a dependency and state for no gain here. A `<select>` per group was rejected by the owner because it allows one choice at a time.
- **A small `StageSection` component** (heading + children) next to `Choice` in `InspectorView.tsx`, exported like `Choice` and `CAMERAS` and used by `RoomView`. No new file is needed for a dozen lines; it follows how `Choice` is shared today.
- **Layout: a two-column flex row with the stage height.** The existing height box (`h-[60vh]`, `h-[50vh]` when compact) becomes the row: the canvas is `flex-1 min-w-0`, the column as wide as its longest button label (`w-max`; owner, 2026-10-19) with `overflow-y-auto`, so a long wall or item list scrolls inside the column and the model keeps its size. Inside each section the buttons are listed one above the other (owner, 2026-10-19): the column's groups are a one-column grid, every button in the column is as thin as it goes (`h-6`, tight padding) and stretches to the column's width, and `Choice` takes a `stacked` flag so the tab rows that also use it stay horizontal.
- **Views holds camera and mode together.** Inside the Views section the existing `Choice` groups stay separate with their labels `Camera` and `Mode`, so the active camera and the active mode are each still shown as pressed and existing tests that query those groups keep working. The explode slider follows the Mode group in the same section.
- **Group labels.** Parts keeps its `Layers` group. The Room section keeps the `Surfaces` group name (walls, floor, ceiling, dimensions) so the conversation and Workspace tests that look it up are unchanged; the `items` / per-item switches and All items move to a new `Furniture` group. The Rooms tests that listed item buttons inside `Surfaces` are updated to the new group, the only test change.

## Risks / Trade-offs

- [The column narrows the 3D view in the Workspace pane and split view] → fixed column width kept small; the owner chose this over stacking.
- [Long wall or part names wrap awkwardly in a narrow column] → the buttons already wrap; names are short (`wall 3`, `carcass`), and item labels use the item's name as today.
- [The dimension overlay labels sit inside the canvas and are positioned against it] → the overlay is a child of `InspectorCanvas`, so it follows the narrower canvas without change; checked in the browser pass.
