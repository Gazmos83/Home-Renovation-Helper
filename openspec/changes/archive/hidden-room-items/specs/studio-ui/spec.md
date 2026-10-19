## MODIFIED Requirements

### Requirement: The Measured Rooms page shows each room with its composition
The Studio SHALL have a Measured Rooms page for the owner at `/rooms`: a one-line intro, then one tile per room of the house file in the paged tile grid, each named by the room's name, followed by one tile per standalone composition. Choosing a room's tile SHALL open that room's dialog. When the house file holds no room the page SHALL say that no rooms are measured yet and that one is described in a conversation. Wherever another requirement names the Rooms page, it SHALL mean this page.

**The room.** Each room's dialog SHALL show:
- its name, its size (width × depth in millimetres, and the number of corners when it is not four), and its ceiling height;
- its number of openings;
- the apartment it belongs to, or nothing;
- the pieces in it by name, or "No pieces";
- its composition, set out below, or, when it has none, that it has no composition yet and that the Designer can compose it in a conversation.

Each room SHALL have a delete action. Choosing it SHALL open a confirm dialog that names the room and what deleting it does:
- the pieces in it, by name, that become "No room";
- the number of conversations that lose their confirmed room;
- its composition and the number of its versions that are removed, with their renders.

Nothing SHALL be deleted until the owner confirms in the dialog. Cancelling SHALL send nothing. After a delete the room's dialog SHALL close, the room's tile and its composition SHALL be gone, and the pieces' rooms SHALL be shown updated without a reload, on this page and on the Pieces page. A room that belongs to an apartment SHALL show why it cannot be deleted here instead of a working delete action. A refused delete SHALL show its reason in the room's dialog, and the room SHALL stay listed.

**The composition.** A room's composition SHALL be shown inside that room's dialog. An apartment composition, and a room composition whose room is not in the house file, SHALL each have a tile of its own after the room tiles, marked "Apartment" or "Room", opening a dialog titled with its name. For each composition the page SHALL offer a version dropdown listing its newest five versions, newest first, with the latest chosen. Older versions SHALL be kept and SHALL NOT be listed. Everything below SHALL show the chosen version. For the chosen version the page SHALL show:
- its version number and that version's build status;
- its items by name and type, with each piece's version and approval state ("no longer approved" shown plainly), each hidden item marked "hidden", or "The room only, no furniture" when it has no items;
- its screenshot or still. The dialog SHALL NOT show a link to the turntable viewer outside the 3D view;
- when the version has `model.glb`, a 3D view of the composition, loaded only when the owner opens it; choosing another version in the dropdown SHALL show that version in the open view. It SHALL use the piece inspector's camera controls (free rotate and zoom, Iso, Front, Side and Plan) and its Workshop and Blueprint modes. It SHALL offer one switch per surface of the version's surface map: each wall, the floor and the ceiling, plus "All walls". When the version's build report lists each item's meshes, the view SHALL offer one switch per built item, labelled with the item's name, plus "All items", in place of a single items switch; a version whose report does not list them SHALL keep the single items switch. Switching a surface or an item off SHALL hide exactly the meshes listed under it, and a mesh the map does not name stays visible. The item switches SHALL NOT be saved: they create no version, start no build and start switched on whenever the view is opened. A hidden item is not built and SHALL have no switch. All surfaces and items SHALL start switched on, except the ceiling, which starts off so the room can be seen from above. The view SHALL offer a "dimensions" switch, off at first. Switched on, it SHALL label every unique wall of the version's room plan with its length in millimetres, on that wall (a wall two rooms of an apartment share is labelled once), and each room's ceiling height in millimetres once per room (so an apartment whose rooms differ shows each height). The figures SHALL be the chosen version's own. While the 3D view is open and the chosen version has a turntable, the view SHALL offer "Open the turntable viewer of <name>", opening the viewer in a new tab; this is the only place on the page that offers it. A version without `model.glb` SHALL show its screenshot or still and say that composing the room again adds the 3D view.

The page SHALL NOT show the model library, model names of language models, prompts, token counts or costs. The page SHALL pass a recorded browser check before it counts as done.

#### Scenario: Measured room listed
- **WHEN** the house file holds `Hall` with `shoe-bench` in it and no composition
- **THEN** the Measured Rooms page shows a tile `Hall` with its size and ceiling height, and its dialog shows its openings and `shoe-bench` and says it has no composition yet

#### Scenario: Composition inside its room
- **WHEN** the house file holds `Wohnen` and composition `Wohnen` has versions 1 and 2
- **THEN** the `Wohnen` dialog shows the composition's version dropdown with version 2 chosen, its items and its picture, and no separate `Wohnen` composition tile is shown

#### Scenario: Apartment composition on its own card
- **WHEN** apartment `Wohnung` has a composition
- **THEN** a tile `Wohnung` marked "Apartment" is shown after the room tiles

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
- **THEN** the `Hall` dialog closes, the `Hall` tile is no longer shown without a reload, and the Pieces page shows `shoe-bench` with "No room"

#### Scenario: Room in an apartment
- **WHEN** `Küche` belongs to apartment `Wohnung`
- **THEN** the `Küche` dialog shows that it cannot be deleted here because it belongs to `Wohnung`

#### Scenario: Delete refused
- **WHEN** the delete route refuses because the room's composition is building
- **THEN** the reason is shown in the room's dialog and the room is still listed

#### Scenario: Empty composition shown
- **WHEN** composition `Hall` v1 has no items and its build succeeded
- **THEN** the `Hall` dialog shows "The room only, no furniture" and its screenshot

#### Scenario: Unapproved piece shown
- **WHEN** a composition places a piece version that has since been unapproved
- **THEN** the dialog lists that item with "no longer approved" beside it

#### Scenario: Room shown in 3D
- **WHEN** composition `Wohnen` v2 has `model.glb` and the owner opens its 3D view
- **THEN** the composition is shown from the Iso camera with switches for each wall, the floor, the ceiling, each item by name, "All walls" and "All items", and the ceiling is off

#### Scenario: Wall switched off
- **WHEN** the owner switches wall 2 off
- **THEN** every mesh the surface map lists under wall 2 is hidden and the pieces behind it can be seen, and all other surfaces stay as they were

#### Scenario: Older composition without a model
- **WHEN** composition `Hall` v1 was built before the 3D view existed and has no `model.glb`
- **THEN** the `Hall` dialog shows its screenshot and says that composing `Hall` again adds the 3D view

#### Scenario: Newest five versions offered
- **WHEN** composition `Wohnen` has versions 1 to 7
- **THEN** its version dropdown lists versions 7, 6, 5, 4 and 3, version 7 is shown, and versions 1 and 2 are still kept

#### Scenario: Older version chosen
- **WHEN** the owner chooses version 5 of `Wohnen` in the dropdown while its 3D view is open
- **THEN** the dialog shows version 5's status, items and picture, and the 3D view shows version 5's model

#### Scenario: Wall and ceiling dimensions
- **WHEN** the owner switches dimensions on in the 3D view of a five-walled room `Wohnen` with a 2500 mm ceiling
- **THEN** each of the five walls is labelled with its own length in mm and the ceiling height reads 2500 mm once

#### Scenario: Apartment heights differ
- **WHEN** the owner switches dimensions on in the 3D view of an apartment whose `Bad` is 2400 mm high and whose other rooms are 2550 mm, with one wall shared by `Bad` and `Flur`
- **THEN** `Bad` shows 2400 mm, each other room shows 2550 mm, and the shared wall carries one length label

#### Scenario: Turntable viewer only in the 3D view
- **WHEN** composition `Wohnen` version 11 has a turntable and the owner opens the `Wohnen` dialog
- **THEN** no "Open the turntable viewer of Wohnen" link is shown until the owner opens the 3D view, and the open 3D view offers it

#### Scenario: One item switched off
- **WHEN** the 3D view of `Wohnen` v3 shows the stand-in `sofa` and the model `armchair`, and the owner switches `sofa` off
- **THEN** only the sofa's meshes are hidden, the armchair stays visible, and no new version or build is started

#### Scenario: Item switches start on again
- **WHEN** the owner switched `sofa` off, closes the 3D view and opens it again
- **THEN** every item switch is on

#### Scenario: All items
- **WHEN** the owner switches "All items" off
- **THEN** every item's meshes are hidden and the walls, floor and ceiling stay as they were

#### Scenario: Older report keeps one items switch
- **WHEN** composition `Hall` v1 was built before item meshes were listed in its report
- **THEN** its 3D view offers the single items switch and no per-item switch

#### Scenario: Hidden item listed, not switched
- **WHEN** composition `Wohnen` v4 holds the hidden stand-in `sofa`
- **THEN** the dialog lists `sofa` marked "hidden", and its 3D view has no `sofa` switch

