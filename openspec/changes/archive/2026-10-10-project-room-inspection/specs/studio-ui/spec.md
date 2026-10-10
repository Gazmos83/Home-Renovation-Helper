## ADDED Requirements

### Requirement: The Project panel opens the conversation's room in 3D beside the chat
The Project panel SHALL show, under the piece, a "Selected room" heading and below it the conversation's confirmed room or apartment by name. When its composition has a 3D model the panel SHALL offer a button to inspect it. Pressing it SHALL show the room's 3D view beside the chat in the same split screen as the piece inspector: on a wide screen the chat on one side and the room on the other, on a narrow screen the room below the chat. The view SHALL be the Rooms page's 3D view of the composition, with the same cameras, modes, surface switches and dimensions switch, the ceiling starting off. The pane SHALL offer the same version dropdown as the Rooms page (the newest five versions, the latest chosen); choosing a version SHALL show it, and a version without a 3D model SHALL be named in plain words. Opening it SHALL NOT start a turn, and the owner SHALL still be able to read, scroll and send messages. The pane SHALL show the room's name and a control to close it, after which the chat takes the width again. The open room view and its chosen version SHALL be part of the page's address, so a reload shows them again.

When the room or apartment has no composition, the panel SHALL say in plain words that it has no 3D view yet and that the Designer can compose it. When the composition's latest version has no 3D model, the panel SHALL say that composing it again adds the 3D view. When the conversation has confirmed no room or apartment, the panel SHALL show no room section. An address naming a room view that is not the conversation's current room SHALL show no room pane.

Only one side pane SHALL be shown at a time: opening the room view SHALL close an open piece inspector, and opening a piece version (from the panel or a notice) SHALL close an open room view.

The panel and the pane SHALL NOT show model names of language models, prompts, token counts or costs. The room section SHALL pass a recorded browser check before it counts as done.

#### Scenario: Inspect the room
- **WHEN** the conversation has confirmed `Hall`, composition `Hall` has a 3D model, and the owner presses "Inspect Hall" in the Project panel under "Selected room"
- **THEN** the 3D view of `Hall` is shown beside the chat with its surface switches and the ceiling off, and the composer is still usable

#### Scenario: Another version beside the chat
- **WHEN** the room view of `Hall` shows version 3 and the owner chooses version 2 in its dropdown
- **THEN** version 2's model is shown, and a reload shows version 2 again

#### Scenario: Dimensions beside the chat
- **WHEN** the owner switches dimensions on in the room view of `Hall`
- **THEN** each wall of `Hall` is labelled with its length and the ceiling height is shown once

#### Scenario: No 3D view yet
- **WHEN** the conversation has confirmed `Hall` and `Hall` has no composition
- **THEN** the Project panel says `Hall` has no 3D view yet and that the Designer can compose the room, and offers no inspect button

#### Scenario: No room confirmed
- **WHEN** the conversation has confirmed no room or apartment
- **THEN** the Project panel shows no room section

#### Scenario: Close the room view
- **WHEN** the owner closes the room pane
- **THEN** the chat takes the full width beside the rail again

#### Scenario: Reload
- **WHEN** the owner reloads the conversation while the room view of `Hall` is shown
- **THEN** the conversation and the room view of `Hall` are shown again

#### Scenario: One pane at a time
- **WHEN** the room view of `Hall` is shown and the owner presses "Inspect version 2" in the Project panel
- **THEN** the piece inspector for version 2 is shown beside the chat and the room view is closed; pressing "Inspect Hall" then shows the room and closes the inspector

## MODIFIED Requirements

### Requirement: The Rooms page shows compositions and the model library
The Studio SHALL have a Rooms page for the owner, with three parts.

**Measured rooms.** For each room of the house file the page SHALL show:
- its name, its size (width × depth in millimetres, and the number of corners when it is not four), and its ceiling height;
- its number of openings;
- the apartment it belongs to, or nothing;
- the pieces in it by name, or "No pieces";
- whether it has a composition.

Each room SHALL have a delete action. Choosing it SHALL open a confirm dialog that names the room and what deleting it does:
- the pieces in it, by name, that become "No room";
- the number of conversations that lose their confirmed room;
- its composition and the number of its versions that are removed, with their renders.

Nothing SHALL be deleted until the owner confirms in the dialog. Cancelling SHALL send nothing. After a delete the room, its composition and the pieces' rooms SHALL be shown updated without a reload, on this page and on the Pieces page. A room that belongs to an apartment SHALL show why it cannot be deleted here instead of a working delete action. A refused delete SHALL show its reason next to the room, and the room SHALL stay listed.

**Compositions.** For each composition the page SHALL offer a version dropdown listing its newest five versions, newest first, with the latest chosen. Older versions SHALL be kept and SHALL NOT be listed. Everything below SHALL show the chosen version. For the chosen version the page SHALL show:
- its scope, its version number and that version's build status;
- its items by name and type, with each piece's version and approval state ("no longer approved" shown plainly), or "The room only, no furniture" when it has no items;
- its screenshot or still, and a link to the viewer when a turntable exists;
- when the version has `model.glb`, a 3D view of the composition, loaded only when the owner opens it; choosing another version in the dropdown SHALL show that version in the open view. It SHALL use the piece inspector's camera controls (free rotate and zoom, Iso, Front, Side and Plan) and its Workshop and Blueprint modes. It SHALL offer one switch per surface of the version's surface map: each wall, the floor, the ceiling and the items, plus "All walls". Switching a surface off SHALL hide exactly the meshes the map lists under it, and a mesh the map does not name stays visible. All surfaces SHALL start switched on, except the ceiling, which starts off so the room can be seen from above. The view SHALL offer a "dimensions" switch, off at first. Switched on, it SHALL label every unique wall of the version's room plan with its length in millimetres, on that wall (a wall two rooms of an apartment share is labelled once), and each room's ceiling height in millimetres once per room (so an apartment whose rooms differ shows each height). The figures SHALL be the chosen version's own. A version without `model.glb` SHALL show its screenshot or still and say that composing the room again adds the 3D view.

**Model library.** The page SHALL show the library with each model's name, stated size and check state (`checking`, `ready`, or `refused` with its reason). It SHALL offer an upload form taking a file, a name and the three dimensions, and a delete action. A refused upload or delete SHALL show its reason next to the form.

The page SHALL NOT show model names of language models, prompts, token counts or costs. The page SHALL pass a recorded browser check before it counts as done.

#### Scenario: Measured room listed
- **WHEN** the house file holds `Hall` with `shoe-bench` in it and no composition
- **THEN** the Rooms page lists `Hall` with its size, ceiling height, openings and `shoe-bench`, and says it has no composition

#### Scenario: Delete warns first
- **WHEN** the owner chooses delete on `Hall`, which holds `shoe-bench`, was confirmed in one conversation and has composition `Hall` with two versions
- **THEN** a dialog names `shoe-bench` as becoming "No room", one conversation losing its confirmed room, and composition `Hall` with two versions removed, and nothing has been deleted

#### Scenario: Delete cancelled
- **WHEN** the owner cancels that dialog
- **THEN** no request is sent and `Hall` is still listed

#### Scenario: Delete confirmed
- **WHEN** the owner confirms that dialog
- **THEN** `Hall` and composition `Hall` are no longer listed without a reload, and the Pieces page shows `shoe-bench` with "No room"

#### Scenario: Room in an apartment
- **WHEN** `Küche` belongs to apartment `Wohnung`
- **THEN** the Rooms page shows that `Küche` cannot be deleted here because it belongs to `Wohnung`

#### Scenario: Delete refused
- **WHEN** the delete route refuses because the room's composition is building
- **THEN** the reason is shown next to the room and the room is still listed

#### Scenario: Empty composition shown
- **WHEN** composition `Hall` v1 has no items and its build succeeded
- **THEN** the Rooms page lists `Hall` with "The room only, no furniture" and its screenshot

#### Scenario: Unapproved piece shown
- **WHEN** a composition places a piece version that has since been unapproved
- **THEN** the Rooms page lists that item with "no longer approved" beside it

#### Scenario: Upload refused
- **WHEN** the owner uploads a `.blend` file
- **THEN** the page shows the refusal reason and the library is unchanged

#### Scenario: Check finishes
- **WHEN** an uploaded model's check finishes while the page is open
- **THEN** its state changes from `checking` to `ready` without a reload

#### Scenario: Room shown in 3D
- **WHEN** composition `Wohnen` v2 has `model.glb` and the owner opens its 3D view
- **THEN** the composition is shown from the Iso camera with switches for each wall, the floor, the ceiling, the items and "All walls", and the ceiling is off

#### Scenario: Wall switched off
- **WHEN** the owner switches wall 2 off
- **THEN** every mesh the surface map lists under wall 2 is hidden and the pieces behind it can be seen, and all other surfaces stay as they were

#### Scenario: Older composition without a model
- **WHEN** composition `Hall` v1 was built before this change and has no `model.glb`
- **THEN** the Rooms page shows its screenshot and says that composing `Hall` again adds the 3D view

#### Scenario: Newest five versions offered
- **WHEN** composition `Wohnen` has versions 1 to 7
- **THEN** its version dropdown lists versions 7, 6, 5, 4 and 3, version 7 is shown, and versions 1 and 2 are still kept

#### Scenario: Older version chosen
- **WHEN** the owner chooses version 5 of `Wohnen` in the dropdown while its 3D view is open
- **THEN** the card shows version 5's status, items and picture, and the 3D view shows version 5's model

#### Scenario: Wall and ceiling dimensions
- **WHEN** the owner switches dimensions on in the 3D view of a five-walled room `Wohnen` with a 2500 mm ceiling
- **THEN** each of the five walls is labelled with its own length in mm and the ceiling height reads 2500 mm once

#### Scenario: Apartment heights differ
- **WHEN** the owner switches dimensions on in the 3D view of an apartment whose `Bad` is 2400 mm high and whose other rooms are 2550 mm, with one wall shared by `Bad` and `Flur`
- **THEN** `Bad` shows 2400 mm, each other room shows 2550 mm, and the shared wall carries one length label
