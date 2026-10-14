## ADDED Requirements

### Requirement: The Measured Rooms page shows each room with its composition
The Studio SHALL have a Measured Rooms page for the owner at `/rooms`, laid out like the Pieces page: a heading row with the page title "Measured Rooms", a one-line intro, then one card per room of the house file, each titled with the room's name. When the house file holds no room the page SHALL say that no rooms are measured yet and that one is described in a conversation. Wherever another requirement names the Rooms page, it SHALL mean this page.

**The room.** Each room card SHALL show:
- its name, its size (width × depth in millimetres, and the number of corners when it is not four), and its ceiling height;
- its number of openings;
- the apartment it belongs to, or nothing;
- the pieces in it by name, or "No pieces";
- its composition, set out below, or, when it has none, that it has no composition yet and that the Designer can compose it in a conversation.

Each room SHALL have a delete action. Choosing it SHALL open a confirm dialog that names the room and what deleting it does:
- the pieces in it, by name, that become "No room";
- the number of conversations that lose their confirmed room;
- its composition and the number of its versions that are removed, with their renders.

Nothing SHALL be deleted until the owner confirms in the dialog. Cancelling SHALL send nothing. After a delete the room and its composition SHALL be gone and the pieces' rooms SHALL be shown updated without a reload, on this page and on the Pieces page. A room that belongs to an apartment SHALL show why it cannot be deleted here instead of a working delete action. A refused delete SHALL show its reason next to the room, and the room SHALL stay listed.

**The composition.** A room's composition SHALL be shown inside that room's card. An apartment composition, and a room composition whose room is not in the house file, SHALL each be shown in a card of its own below the room cards, titled with its name and marked "Apartment" or "Room". For each composition the page SHALL offer a version dropdown listing its newest five versions, newest first, with the latest chosen. Older versions SHALL be kept and SHALL NOT be listed. Everything below SHALL show the chosen version. For the chosen version the page SHALL show:
- its version number and that version's build status;
- its items by name and type, with each piece's version and approval state ("no longer approved" shown plainly), or "The room only, no furniture" when it has no items;
- its screenshot or still, and a link to the viewer when a turntable exists;
- when the version has `model.glb`, a 3D view of the composition, loaded only when the owner opens it; choosing another version in the dropdown SHALL show that version in the open view. It SHALL use the piece inspector's camera controls (free rotate and zoom, Iso, Front, Side and Plan) and its Workshop and Blueprint modes. It SHALL offer one switch per surface of the version's surface map: each wall, the floor, the ceiling and the items, plus "All walls". Switching a surface off SHALL hide exactly the meshes the map lists under it, and a mesh the map does not name stays visible. All surfaces SHALL start switched on, except the ceiling, which starts off so the room can be seen from above. The view SHALL offer a "dimensions" switch, off at first. Switched on, it SHALL label every unique wall of the version's room plan with its length in millimetres, on that wall (a wall two rooms of an apartment share is labelled once), and each room's ceiling height in millimetres once per room (so an apartment whose rooms differ shows each height). The figures SHALL be the chosen version's own. A version without `model.glb` SHALL show its screenshot or still and say that composing the room again adds the 3D view.

The page SHALL NOT show the model library, model names of language models, prompts, token counts or costs. The page SHALL pass a recorded browser check before it counts as done.

#### Scenario: Measured room listed
- **WHEN** the house file holds `Hall` with `shoe-bench` in it and no composition
- **THEN** the Measured Rooms page shows a card `Hall` with its size, ceiling height, openings and `shoe-bench`, and says it has no composition yet

#### Scenario: Composition inside its room
- **WHEN** the house file holds `Wohnen` and composition `Wohnen` has versions 1 and 2
- **THEN** the `Wohnen` card shows the composition's version dropdown with version 2 chosen, its items and its picture, and no separate `Wohnen` composition card is shown

#### Scenario: Apartment composition on its own card
- **WHEN** apartment `Wohnung` has a composition
- **THEN** a card `Wohnung` marked "Apartment" is shown below the room cards

#### Scenario: No rooms
- **WHEN** the house file holds no room
- **THEN** the page says that no rooms are measured yet and that one is described in a conversation

#### Scenario: Delete warns first
- **WHEN** the owner chooses delete on `Hall`, which holds `shoe-bench`, was confirmed in one conversation and has composition `Hall` with two versions
- **THEN** a dialog names `shoe-bench` as becoming "No room", one conversation losing its confirmed room, and composition `Hall` with two versions removed, and nothing has been deleted

#### Scenario: Delete cancelled
- **WHEN** the owner cancels that dialog
- **THEN** no request is sent and `Hall` is still listed

#### Scenario: Delete confirmed
- **WHEN** the owner confirms that dialog
- **THEN** the `Hall` card, with its composition, is no longer shown without a reload, and the Pieces page shows `shoe-bench` with "No room"

#### Scenario: Room in an apartment
- **WHEN** `Küche` belongs to apartment `Wohnung`
- **THEN** the `Küche` card shows that it cannot be deleted here because it belongs to `Wohnung`

#### Scenario: Delete refused
- **WHEN** the delete route refuses because the room's composition is building
- **THEN** the reason is shown in the room's card and the room is still listed

#### Scenario: Empty composition shown
- **WHEN** composition `Hall` v1 has no items and its build succeeded
- **THEN** the `Hall` card shows "The room only, no furniture" and its screenshot

#### Scenario: Unapproved piece shown
- **WHEN** a composition places a piece version that has since been unapproved
- **THEN** the card lists that item with "no longer approved" beside it

#### Scenario: Room shown in 3D
- **WHEN** composition `Wohnen` v2 has `model.glb` and the owner opens its 3D view
- **THEN** the composition is shown from the Iso camera with switches for each wall, the floor, the ceiling, the items and "All walls", and the ceiling is off

#### Scenario: Wall switched off
- **WHEN** the owner switches wall 2 off
- **THEN** every mesh the surface map lists under wall 2 is hidden and the pieces behind it can be seen, and all other surfaces stay as they were

#### Scenario: Older composition without a model
- **WHEN** composition `Hall` v1 was built before the 3D view existed and has no `model.glb`
- **THEN** the `Hall` card shows its screenshot and says that composing `Hall` again adds the 3D view

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

### Requirement: The Model Library page lists, uploads and deletes models
The Studio SHALL have a Model Library page for the owner at `/models`, laid out like the Pieces page: a heading row with the page title "Model Library", a one-line intro saying the library holds bought furniture and decor as 3D models (a GLB file, or a zip with one glTF or OBJ model and its files), then one card per model. Each card SHALL show the model's name, its stated size and its check state (`checking`, `ready`, or `refused` with its reason), and a delete action. When the library is empty the page SHALL say so. The page SHALL offer an upload form taking a file, a name and the three dimensions. A refused upload or delete SHALL show its reason next to the form. A model being checked SHALL change state without a reload.

The page SHALL NOT show measured rooms, compositions, model names of language models, prompts, token counts or costs. The page SHALL pass a recorded browser check before it counts as done.

#### Scenario: Models listed
- **WHEN** the library holds `Sofa` (2200 × 950 × 800 mm, ready)
- **THEN** the Model Library page shows a card `Sofa` with its size, "ready" and a delete action

#### Scenario: Upload refused
- **WHEN** the owner uploads a `.blend` file
- **THEN** the page shows the refusal reason and the library is unchanged

#### Scenario: Check finishes
- **WHEN** an uploaded model's check finishes while the page is open
- **THEN** its state changes from `checking` to `ready` without a reload

### Requirement: The Studio navigation offers Measured Rooms and Model Library
The Studio navigation SHALL show "Measured Rooms" (to `/rooms`) and "Model Library" (to `/models`) directly after "Pieces", and SHALL NOT show a "Rooms" item. Both routes SHALL require sign-in, and a signed-out visit SHALL go to the sign-in page.

#### Scenario: Navigation entries
- **WHEN** the signed-in owner opens the Studio
- **THEN** the navigation reads "Pieces", "Measured Rooms", "Model Library" in that order, and each opens its page

#### Scenario: Signed out
- **WHEN** a signed-out visitor opens `/models`
- **THEN** they are sent to the sign-in page

## REMOVED Requirements

### Requirement: The Rooms page shows compositions and the model library
**Reason**: The page is split in two on the owner's request (2026-10-14): measured rooms now hold their compositions, and the model library has a page of its own.
**Migration**: See "The Measured Rooms page shows each room with its composition" and "The Model Library page lists, uploads and deletes models". The `/rooms` address stays; the library moves to `/models`. No API changes.
