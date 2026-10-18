## Why

The piece and room inspectors put their camera, mode, layer and surface buttons in rows above the 3D view. In a room with many walls and items the rows wrap into a block of unlabelled buttons that pushes the model down and mixes views with things to show or hide. The owner asked (2026-10-19) for the clickable controls to sit in a column to the right of the view, grouped under clear headings.

## What Changes

- The 3D stage of both inspectors gets a column on its right that holds every clickable control of the stage. The canvas takes the remaining width. The column is always to the right, also in the conversation's split view and the Workspace panes (owner's choice).
- The controls are grouped into collapsible sections, each a heading the owner clicks to fold or unfold. Every section starts open.
- **Room inspector** sections:
  1. **Views**: Iso, Front, Side, Plan, Workshop, Blueprint.
  2. **Room**: All walls, each wall, the floor, the ceiling, and dimensions.
  3. **Furniture**: All items and each built piece and model (or the single `items` switch when the build report does not list item meshes).
- **Piece inspector** sections:
  1. **Views**: Iso, Front, Side, Plan, Workshop, Blueprint, Exploded, and the explode slider while Exploded is chosen.
  2. **Parts**: one switch per layer of `spec.json` and `dimensions`.
- The switches keep their names, their starting state (ceiling off, room dimensions off, all piece layers on) and what they do. Only where they sit changes. The Overall line, tabs, version switcher, verdict, straight-on views and turntable link stay where they are.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `studio-ui`: a new requirement places the inspectors' stage controls in a grouped, collapsible column to the right of the 3D view, for pieces and rooms.

## Impact

- Frontend only: `frontend/src/components/inspector/InspectorView.tsx` (piece stage), `frontend/src/components/inspector/RoomView.tsx` (room stage), one small shared section component, and their tests (`PieceInspector.test.tsx`, `Rooms.test.tsx`, `Conversation.test.tsx` keep finding the same named buttons).
- No backend, API, spec JSON or Blender change. Ladder step: none (no spec change, generator or live Blender). Agents: none. The render guard and the `bpy` allow-list are not affected; nothing renders.
- The open browser passes of `hidden-room-items`, `render-now-blueprints-verdict-note` and `piece-size-room-warning` look at the same inspectors; their switches still exist under the new headings.
