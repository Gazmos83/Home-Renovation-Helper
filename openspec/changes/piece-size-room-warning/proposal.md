## Why

The end-to-end review of 2026-10-15 asked whether "Highest the piece may be (mm)" has to be filled in the Brief, and asked instead for a warning when a piece is too big for its room. Today Intake treats the limit as one of "the heights" it must collect (`intake.md`, design-agents "Missing height"), and nothing warns when a version is taller than its room's ceiling or wider than its walls; only `room_fit` and `compose_room` refuse a placement that does not fit. The owner decided on 2026-10-18: keep the field, make it optional, and add the warning.

## What Changes

- **The limit is optional.** The Brief form labels the field "Highest the piece may be (mm, optional)". Intake does not ask for it; it records one only when the owner gives one. Intake still asks for the piece's rough size and height. The API already accepts an empty value.
- **A too-big version is warned about, never refused.** When a piece version is built and the piece has a room, the application compares the version's overall size with that room:
  - taller than the room's ceiling;
  - wider than the room's longest wall.
  Either one adds a warning sentence to the build notice ("Too big for Wohnen: 2600 mm tall, the ceiling is 2500 mm.") and shows the same warning in the inspector for that version.
- **Unchanged:** `room_fit` and `compose_room` keep refusing placements that do not fit; approving a taller version still raises the brief's limit; a piece with no room gets no warning.
- **Assumptions, TODO(user) for review:**
  - "wider than the room" means wider than the room's longest wall (its widest straight run), not the wall the piece is placed on. A piece placed in a composition is already checked against its wall there;
  - depth is not checked.

Ladder: none of the three steps; a code check on the stored spec, no generator change. Agents touched: **Intake** (instruction wording only). The **render guard** and the **bpy allow-list** are **not affected**.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `design-agents`: Intake's brief no longer requires the highest the piece may be.
- `homeowner-chat`: a build notice carries a size warning against the piece's room.
- `studio-ui`: the inspector shows the size warning; the Brief form marks the limit optional.

## Impact

- `backend/app/agent/house_file.py` (or a small new helper beside `describe_room`): `size_warnings(room, overall)` returning plain sentences.
- `backend/app/agent/notices.py`: `build_text` appends the warnings on a succeeded build; `post_build` reads the version's `overall` and the piece's room.
- `backend/app/api/packages.py`: `describe_version` returns `size_warnings` (list of strings).
- `backend/app/agent/instructions/intake.md`: the limit is optional and never asked for.
- `frontend/src/components/chat/BriefPanel.tsx` (label), `frontend/src/components/inspector/InspectorView.tsx` (warning line), `frontend/src/lib/api.ts` (type).
- Tests: notices, the warning helper, packages API, instructions; Vitest for the inspector line and the label.
- Relation: depends on `optional-room-question` (applied, browser pass open), whose wording of the Intake requirement this change edits.
