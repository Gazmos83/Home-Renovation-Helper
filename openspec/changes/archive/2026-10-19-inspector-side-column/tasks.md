## 1. Shared section

- [x] 1.1 Add an exported `StageSection` (a `<details open>` with a `<summary>` heading and its children) beside `Choice` in `frontend/src/components/inspector/InspectorView.tsx`; verify with a Vitest case that it starts open, folds on a click of its heading and keeps its children mounted.

## 2. Piece inspector

- [x] 2.1 In `InspectorView.tsx`, turn the stage into a row: canvas on the left (`flex-1 min-w-0`, same heights as now), column on the right with a Views section (Camera and Mode groups, explode slider while Exploded) and a Parts section (the `Layers` group). Overall line, tabs, straight-on views, verdict and switcher stay outside. Verify in `PieceInspector.test.tsx` that both sections are present and open with the named buttons, that the slider shows only in Exploded, and that the existing tests still pass.

## 3. Room inspector

- [x] 3.1 In `RoomView.tsx`, build the same row with sections Views (Camera, Mode), Room (All walls, walls, floor, ceiling, `dimensions`, as a `Room` group) and Furniture (All items and the item switches, or the single `items` switch, as a `Furniture` group; no section when there are no items). Starting state unchanged (ceiling off, dimensions off). Verify in `Rooms.test.tsx`: the three sections and their buttons, no Furniture section for a room without items, and a wall switched off stays off after folding and unfolding Room. Update the tests that looked item buttons up in the `Surfaces` group. Done with the `Surfaces` group name kept inside the Room section, as design.md decided, so the conversation and Workspace tests stay unchanged.
- [x] 3.2 Run `pnpm test`, `pnpm lint` and `pnpm build` in `frontend/`; all pass, including `Conversation.test.tsx`. Result 2026-10-19: 56 files, 542 tests passed; oxlint clean; build succeeded.

## 4. Browser pass

- [x] 4.1 Browser pass, with **no render tier** (nothing renders): open `/pieces/<id>/versions/<n>` and check the column right of the model, folding each section, Exploded with the slider; open a room in 3D on Measured Rooms, switch a wall and an item off, fold and unfold, switch dimensions on and check the labels sit on the walls; open a piece in a conversation's split view and a room in the Workspace pane and check the column stays to the right and scrolls when long. Passed by the owner 2026-10-19.
