## Why

The owner's app check of 2026-10-09 (`docs/App Check 09-10-2026.md`, kept out of git) lists ten findings. They were checked against the code the same day. Nine are in scope here. The tenth ("always ask whether more changes are needed before a revision") already landed with `designer-revision-clarity`, so the owner dropped it.

What the code showed:

- **Rooms come back silently.** Rooms and apartments are stored house-wide by name, and deleting a conversation keeps them. A new conversation that reads the same blueprint produces the same names. `record_plan` then merges into the stored apartment and keeps every stored room the new read does not name. `record_brief` with a stored room name and no figures quietly takes the stored ones.
- **A room cannot be designed without a piece.** The Foreman's compose route needs the confirmed room's name to appear in the owner's latest message. Otherwise the turn goes to Intake, whose role, hand-off and required `purpose` field are all about a piece.
- **Rooms have no 3D view.** A composition build publishes `model.blend` and a screenshot, but no `model.glb`. The Rooms page shows a PNG, and a link to `viewer.html` only after a turntable render. Walls are hidden only in turntable frames, automatically, with no owner control.
- **A turn cannot be stopped or corrected.** A streamed turn always runs to the end and is stored in the checkpointer. There is no cancel route, no abort in the client and no way to edit a message.
- **The inspector does not move between versions.** It is pinned to the version in its URL, offers no version switcher, and keeps showing the old version after a revision creates a new one.
- **Revisions drift from what was asked.** Every Designer turn carries three full template JSONs full of concrete millimetre values, even when the Designer is only revising an existing piece. The piece summary leaves out the envelope, which a width change usually needs. No code checks that a measurement the owner asked for actually reaches the change lines.
- **Prices are not visible anywhere.** Pricing a version works (`/packages/{id}/versions/{v}/pricings`, `price_cut_list`), but no homeowner page shows a pricing. The checklist says "Models page". `/admin/models` is the developer's model-routing page, so the owner chose the Pieces page instead.

## What Changes

1. **Stored rooms are never reused silently.**
   - A stored room or apartment enters a conversation only through a confirmation that shows its stored measurements.
   - When a plan is read again for an apartment the house file already holds, the `record_plan` card shows each room stored and as read now.
   - On `yes`, the new read replaces the apartment. Stored rooms the read does not name are listed on the card as removed, and are deleted. Pieces in a removed room become "No room".
   - **This changes behaviour:** today unnamed rooms are kept.
   - Deleting a conversation still keeps its rooms.
   - Side fix: correcting an apartment room through `record_brief` no longer detaches it from its apartment.
2. **Room-first design.**
   - When the owner wants to design a room rather than a piece, Intake confirms the room and asks what the room should hold: approved pieces, stand-ins or library models. It never asks which piece to design or what a piece is for.
   - Once the room is confirmed, the Foreman sends a compose request to the Designer without needing the room's name in the message.
3. **Rooms in 3D.**
   - A composition build also publishes `model.glb` and a surface map that names every wall (per room for an apartment), the floor and the ceiling.
   - The Rooms page shows the latest built version in the same three.js view the piece inspector uses: camera, Workshop/Blueprint modes, and one switch per surface, like the inspector's layer switches.
   - The still and the turntable link stay.
4. **Stop and edit in the chat.**
   - While a turn runs, a Stop button aborts it. The turn is discarded from the conversation's history.
   - The owner's latest message can be edited and sent again. The conversation is rewound to just before it.
   - Builds, versions, renders and house-file writes already confirmed are not undone, and the edit dialog says so.
   - Earlier messages cannot be edited.
5. **Inspector follows versions.**
   - The inspector (page and split view) gets a version switcher that lists every version of the piece and updates the URL.
   - When a newer version of the piece is created while it is open, it switches to that version by itself.
6. **Revision accuracy.**
   - The Designer gets the template JSONs only while the conversation has no active build. They are not sent on revision turns.
   - The piece summary adds the envelope.
   - `revise_package` gains a required list of the owner's requested measurements. Each entry gives the owner's words, the module and field, and the target value.
   - Code checks four things:
     - each quote is in the owner's messages since the last created revision;
     - its number and unit give the target, either as an absolute value or as a relative value applied to the current spec;
     - the change sets that field to the target;
     - every length with a unit in those messages is covered by an entry.
   - A mismatch or a measurement left out is refused back to the Designer by name, before any card is shown.
7. **Pricing on the Pieces page.**
   - Each approved version has a "Pricing" dropdown. It lists the version's stored pricings, newest first, and shows the selected pricing's sheets, cut lines, hardware, total and unpriced parts. It also has a "Price this version" action.
   - An unapproved version says that it must be approved first.
   - Prices are not added to `/admin/models`.

Ladder step: everything is step 1 or the application layer.
- The composition generator adds a GLB export to a checked-in headless generator. This is not a schema change, and the export needs no new import.
- No spec schema field changes.
- Agents touched:
  - the Foreman (compose routing);
  - Intake (room reuse, room-first flow, `record_plan` replace);
  - the Designer (template context, envelope, `revise_package` measurement list).

The render guard is not affected: the GLB comes from the build, not from a render, and wall hiding in renders is unchanged. The `bpy` allow-list is not affected: no live script changes.

## Capabilities

### New Capabilities

(none)

### Modified Capabilities

- `house-file`: a stored room is reused only through a confirmation; a plan re-read replaces its apartment and removes rooms it does not name.
- `apartment-shell`: the `record_plan` summary compares the stored apartment with the new read and lists removed rooms.
- `design-agents`:
  - Intake runs a room-first flow;
  - the Foreman routes a compose request once a room is confirmed;
  - template JSONs are sent only with no active build;
  - the piece summary includes the envelope;
  - `revise_package` carries the owner's requested measurements and code checks them.
- `room-composition`: a composition build also publishes `model.glb` and a surface map.
- `homeowner-chat`: a running turn can be stopped and discarded; the latest owner message can be edited and resent.
- `studio-ui`:
  - the Rooms page shows the composition in 3D with surface switches;
  - the inspector has a version switcher and follows a new version;
  - the chat has Stop and Edit;
  - the Pieces page shows pricings per approved version.

## Impact

- Backend:
  - `app/agent/house_file.py`: `upsert_apartment` replaces and removes, and `upsert_room` keeps the apartment;
  - `plugins/intake/tool.py`: `record_plan` preview compares with the stored apartment, and `record_brief` keeps `apartment_id`;
  - `app/agent/instructions/intake.md`, `designer.md`, `foreman.md`;
  - `app/agent/foreman.py`: `compose_ready`, the Foreman decision, and `_designer_note` gating;
  - `app/agent/prompts.py`: envelope in `piece_note`;
  - `app/agent/revise.py` plus a new `app/agent/measurements.py`, and `plugins/revise_package/tool.py`;
  - `app/blender/generators/build_composition.py` and `_composition.py`: GLB export and surface map;
  - `app/api/compositions.py`: model and surface URLs;
  - `app/api/chat.py` and `app/agent/chat.py`: cancel and rewind routes.
- Frontend:
  - `routes/Rooms.tsx` with a room 3D view built from the inspector components;
  - `components/inspector/InspectorView.tsx` and `routes/PieceInspector.tsx`;
  - `routes/Conversation.tsx` and `components/chat/Composer.tsx`;
  - `routes/Pieces.tsx`;
  - `lib/api.ts`.
- Tests: house-file and intake tool tests, Foreman routing, the instruction tests, `test_piece_note.py`, `test_revise_package.py`, a new measurement test, composition build tests (`--blender` for the GLB), chat API tests, and the Vitest suites of the touched pages. Every touched page gets a browser pass.
- No migration is expected: rooms delete through the existing paths, and pricings are already stored. No new dependency.
- Existing composition versions have no `model.glb`. The Rooms page shows the still for them until the room is composed again.
