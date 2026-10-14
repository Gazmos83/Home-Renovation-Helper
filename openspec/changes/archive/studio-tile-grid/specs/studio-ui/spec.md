## ADDED Requirements

### Requirement: Design Studio tabs show a paged grid of picture tiles
The Pieces, Measured Rooms and Uploaded models views SHALL each show their items as a grid of tiles in place of one card per item. Each tile SHALL show:
- a picture filling the tile's top, kept whole (not cropped);
- below it, the item's name on one line (cut short with an ellipsis when too long), and one line of detail in smaller, muted text;
- a state badge in the picture's top-right corner when the item has a state to show.

The tile's content per view is:
- a piece: the picture is the one the piece-picture requirement chooses; the detail line is that picture's caption ("Version 9 (approved)"); the badge reads "Approved" when a version is approved.
- a measured room: the picture is its composition's latest picture; the detail line is width × depth in mm and the ceiling height; the badge names its apartment, if it has one.
- a standalone composition (apartment, or a room no longer in the house file): its latest picture, its name, and an "Apartment" or "Room" badge.
- an uploaded model: its preview picture; its stated width × depth × height in mm; its check state (`checking`, `ready` or `refused`), with `refused` marked as an error.

An item with no picture SHALL show a placeholder icon of its kind in place of the picture, and no error. Each tile SHALL be one control that can be reached by keyboard and named by the item's name. It SHALL show a visible ring on hover and keyboard focus.

**Grid size.** On a screen 1024 CSS px wide or wider, the grid SHALL be 4 tiles across and 4 down. Below 1024 px it SHALL be 2 across and 3 down. The rows SHALL share the height left below the header, the tab heading and the paging controls, so one page of tiles fills the screen without scrolling at 1280 × 800 and at 360 × 780 (Samsung Galaxy S25). On a screen too short for readable tiles, the rows SHALL keep a minimum height and the page SHALL scroll rather than squash them.

**Pages.** A view holding more items than one grid SHALL split them into pages of 16 (4 × 4) or 6 (2 × 3), in the order the view lists them today. Previous and Next buttons and "Page N of M" SHALL show below the grid only when there is more than one page. Previous SHALL be disabled on the first page and Next on the last. The page number SHALL be in the address as `?page=N`. Reloading SHALL show the same page, and a page past the last SHALL show the last page. When the screen width crosses 1024 px, the page SHALL change to the one holding the first tile that was shown. An empty view SHALL keep its existing empty-state message and show no grid or paging controls.

#### Scenario: Laptop grid
- **WHEN** the owner opens Uploaded models with 20 models in a 1280 × 800 window
- **THEN** 16 tiles are shown, 4 across and 4 down, with no vertical scroll, and "Page 1 of 2" with Next enabled and Previous disabled

#### Scenario: Phone grid
- **WHEN** the owner opens Pieces with 8 pieces on a 360 × 780 screen
- **THEN** 6 tiles are shown, 2 across and 3 down, and "Page 1 of 2"

#### Scenario: Page in the address
- **WHEN** the owner chooses Next and then reloads
- **THEN** the address ends in `?page=2` and page 2 is shown again

#### Scenario: One page only
- **WHEN** Measured Rooms holds 3 rooms
- **THEN** 3 tiles are shown and no paging controls

#### Scenario: Width crosses the breakpoint
- **WHEN** the owner is on page 2 of 16-tile pages (tiles 17 to 32) and narrows the window below 1024 px
- **THEN** page 3 of 6-tile pages is shown, holding tile 17

#### Scenario: No picture
- **WHEN** piece `hall-bench` has only version 1, still building
- **THEN** its tile shows a placeholder icon, the name `hall-bench` and no error

#### Scenario: Refused model
- **WHEN** model `Lamp` reads `refused`
- **THEN** its tile shows a `refused` badge marked as an error

### Requirement: A tile opens its detail in an addressable dialog
Choosing a tile SHALL open a dialog over the grid that shows everything the item's card showed before this change, with the same controls, refusals and live updates. Its title SHALL be the item's name. Wherever another requirement gives content to a piece card, a room card or a composition card, it SHALL mean that item's dialog. The "Create A New Piece" button and the import-template link ("Import template") SHALL stay above the Pieces grid, on one row so the grid still fills the screen. Beside the link, an information button SHALL show, until it is pressed again, Escape is pressed or focus leaves it, the Pieces intro and the line on how to use the template (give it to another AI chat, then attach the returned file in a new conversation), without moving the grid.

Each dialog SHALL have its own address under its tab:
- `/studio/pieces/<piece-id>`;
- `/studio/rooms/<room-name>`;
- `/studio/rooms/compositions/<slug>` for a standalone composition;
- `/studio/models/<model-id>`.

The grid's page number SHALL be kept in the address while the dialog is open. Opening a dialog's address directly SHALL show the grid with that dialog open. Browser Back, Esc, the dialog's close button and a click outside the dialog SHALL each close it and return to the grid address, with the grid not reloaded. An address naming an item that does not exist (or no longer exists, for example after a delete from inside the dialog) SHALL show the grid with no dialog. A deleted item's tile SHALL be gone without a reload.

The dialog SHALL keep keyboard focus inside it while open, return focus to the tile that opened it when it closes, and be named by its title. On a screen narrower than 640 CSS px it SHALL fill the screen. Wider, it SHALL be centred, at most 90 % of the screen high, and scroll its own content. Hovering over or focusing a tile SHALL start loading that item's detail, so the dialog usually opens with its content ready. The dialog SHALL NOT show model names of language models, prompts, token counts or costs.

#### Scenario: Pieces header fits
- **WHEN** the owner opens Pieces with 20 pieces on a 360 × 780 screen
- **THEN** "Create A New Piece" and "Import template" share one row above a 2 × 3 grid, and the page does not scroll

#### Scenario: Template how-to
- **WHEN** the owner presses the information button beside "Import template"
- **THEN** the line on giving the template to another AI chat and attaching the returned file is shown over the grid

#### Scenario: Open a piece
- **WHEN** the owner chooses the `listening-wall` tile on page 2 of Pieces
- **THEN** the address is `/studio/pieces/listening-wall?page=2` and a dialog titled `listening-wall` shows its conversation link, picture, room, version dropdown, approval, downloads, pricing, renders and variants

#### Scenario: Back closes
- **WHEN** that dialog is open and the owner presses browser Back
- **THEN** the dialog closes, the address is `/studio/pieces?page=2`, and page 2 of the grid is shown

#### Scenario: Link reopens
- **WHEN** the owner reloads `/studio/rooms/Wohnen`
- **THEN** the Measured Rooms grid is shown with the `Wohnen` dialog open, holding its size, openings, pieces, delete action and composition

#### Scenario: Unknown item
- **WHEN** the owner opens `/studio/models/` followed by the id of a deleted model
- **THEN** the Uploaded models grid is shown and no dialog

#### Scenario: Delete from the dialog
- **WHEN** the owner confirms the delete of `Hall` in its dialog
- **THEN** the dialog closes and the `Hall` tile is gone without a reload

#### Scenario: Phone dialog
- **WHEN** the owner opens a model's dialog on a 360 × 780 screen
- **THEN** the dialog fills the screen and has a close button

#### Scenario: Focus returns
- **WHEN** the owner opens the `Sofa` tile with the keyboard and presses Esc
- **THEN** the dialog closes and the `Sofa` tile has focus

## MODIFIED Requirements

### Requirement: Each piece card shows a picture of the piece
The picture of each piece, on its tile and at the top of its dialog, SHALL be the build screenshot of one version:
- the approved version, when it has a screenshot;
- otherwise the newest version that has a screenshot.

A caption under the picture SHALL name the version, followed by "(approved)" when it is the approved one, e.g. "Version 14 (approved)". On the tile, this caption SHALL be the tile's detail line. The picture SHALL NOT follow the dialog's version dropdown. It SHALL be the build screenshot only, never a render. A piece with no screenshot in any version SHALL show no picture in its dialog, a placeholder icon on its tile, and no error. After an approval changes or a version is deleted, the tile and the dialog SHALL show the version these rules now choose, without a reload.

#### Scenario: Approved version shown
- **WHEN** `listening-wall` has versions 1 to 14, all built, and version 9 is approved
- **THEN** its tile and its dialog show version 9's screenshot captioned "Version 9 (approved)", whichever version the dropdown shows

#### Scenario: None approved
- **WHEN** no version of `murphy-bed` is approved and versions 1 to 4 are built
- **THEN** its tile shows version 4's screenshot captioned "Version 4"

#### Scenario: Newest has not built
- **WHEN** no version of `murphy-bed` is approved, version 5 failed and version 4 is built
- **THEN** its tile shows version 4's screenshot captioned "Version 4"

#### Scenario: No screenshot at all
- **WHEN** `hall-bench` has only version 1 and it is still building
- **THEN** its tile shows a placeholder icon, its dialog shows no picture, and there is no error

#### Scenario: Render not used
- **WHEN** the approved version has a rendered still and a build screenshot
- **THEN** the tile shows the build screenshot

#### Scenario: Approval changes the tile
- **WHEN** the owner approves version 12 of `listening-wall` in its dialog and closes it
- **THEN** the tile shows version 12's screenshot captioned "Version 12 (approved)" without a reload

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
- its items by name and type, with each piece's version and approval state ("no longer approved" shown plainly), or "The room only, no furniture" when it has no items;
- its screenshot or still, and a link to the viewer when a turntable exists;
- when the version has `model.glb`, a 3D view of the composition, loaded only when the owner opens it; choosing another version in the dropdown SHALL show that version in the open view. It SHALL use the piece inspector's camera controls (free rotate and zoom, Iso, Front, Side and Plan) and its Workshop and Blueprint modes. It SHALL offer one switch per surface of the version's surface map: each wall, the floor, the ceiling and the items, plus "All walls". Switching a surface off SHALL hide exactly the meshes the map lists under it, and a mesh the map does not name stays visible. All surfaces SHALL start switched on, except the ceiling, which starts off so the room can be seen from above. The view SHALL offer a "dimensions" switch, off at first. Switched on, it SHALL label every unique wall of the version's room plan with its length in millimetres, on that wall (a wall two rooms of an apartment share is labelled once), and each room's ceiling height in millimetres once per room (so an apartment whose rooms differ shows each height). The figures SHALL be the chosen version's own. A version without `model.glb` SHALL show its screenshot or still and say that composing the room again adds the 3D view.

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
- **THEN** the composition is shown from the Iso camera with switches for each wall, the floor, the ceiling, the items and "All walls", and the ceiling is off

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

### Requirement: The Model Library page lists, uploads and deletes models
The Studio SHALL have a Model Library for the owner at `/models` with two views, chosen from the Design Studio sub-menu: "Uploaded models" and "Upload model".

**Uploaded models** SHALL show a one-line intro saying the library holds bought furniture and decor as 3D models (a GLB file, or a zip with one glTF or OBJ model and its files), then one tile per model in the paged tile grid, each with the model's preview picture, its name, its stated size and its check state. When the library is empty the view SHALL say so and point to "Upload model". Choosing a tile SHALL open the model's dialog showing its name, a larger preview picture, its stated size, its measured size and triangle count once checked, its check state (`checking`, `ready`, or `refused` with its reason), and a delete action. A refused delete SHALL show its reason in the dialog. A model being checked SHALL change state on its tile and in its dialog without a reload.

**Preview pictures.** When a model reads `ready` and has no preview picture, the Uploaded models view SHALL draw the model once in the owner's browser from its own stored files, from a fixed three-quarter view on a plain background, and store the picture with the model. Until a picture exists, and when drawing fails, the tile SHALL show a placeholder icon. A failed drawing SHALL NOT show an error on the tile and SHALL NOT be retried until the view is opened again. No Blender process and no render SHALL be started to make a preview picture.

**Upload model** SHALL open, over the Uploaded models grid, a dialog holding the upload form: a file, a name and the three dimensions. A refused upload SHALL show its reason in the dialog, next to the field it names, and keep what the owner typed. A successful upload SHALL close the dialog and show the page of the grid that holds the new model, as a `checking` tile (the library lists models oldest first, so it is the last page). Closing the dialog without uploading SHALL send nothing. The dialog's address SHALL be `/studio/models/upload`.

The views SHALL NOT show measured rooms, compositions, model names of language models, prompts, token counts or costs. The page SHALL pass a recorded browser check before it counts as done.

#### Scenario: Models listed
- **WHEN** the library holds `Sofa` (2200 × 950 × 800 mm, ready, with a preview picture)
- **THEN** Uploaded models shows a tile `Sofa` with its picture, "2200 × 950 × 800 mm" and "ready", and its dialog has a delete action

#### Scenario: Upload in a dialog
- **WHEN** the owner chooses "Upload model"
- **THEN** the address is `/studio/models/upload` and the upload form is shown in a dialog over the Uploaded models grid

#### Scenario: Upload refused
- **WHEN** the owner uploads a `.blend` file
- **THEN** the dialog stays open showing the refusal reason, and the library is unchanged

#### Scenario: Upload succeeds
- **WHEN** the owner uploads a GLB armchair named `armchair` at 800 × 700 × 900 mm
- **THEN** the dialog closes and an `armchair` tile reading `checking` is shown with a placeholder icon

#### Scenario: Check finishes
- **WHEN** an uploaded model's check finishes while the view is open
- **THEN** its state changes from `checking` to `ready` without a reload, and its placeholder is replaced by its preview picture

#### Scenario: Preview cannot be drawn
- **WHEN** the browser cannot draw a ready OBJ model
- **THEN** its tile keeps the placeholder icon and shows no error

### Requirement: Pieces, measured rooms and the model library are tabs of one Design Studio page
The Studio SHALL have a Design Studio page for the owner at `/studio` with the page title "Design Studio" and three tabs, in this order: "Pieces", "Measured Rooms" and "Model Library". Each tab SHALL have its own address — `/studio/pieces`, `/studio/rooms`, `/studio/models` — and opening that address SHALL show the page with that tab chosen. `/studio`, and a `/studio/` address naming no known tab, SHALL show the Pieces tab. The tabs SHALL be a rail at the screen's left edge below the header, with the same font, icon style, colour scheme and "Hide labels" switch as the conversation page's panel rail: each tab an icon, with its label beside it while labels are shown, the chosen tab highlighted, and the switch at the rail's foot. The label choice SHALL be remembered in the browser and shared with the other rails; a browser that cannot store it SHALL show the labels hidden. The tabs SHALL be exposed as a vertical tab list with the chosen tab marked selected, and only the chosen tab's content SHALL be shown.

**Sub-menu.** Beside the rail, the chosen tab SHALL show a sub-menu of its views, each with its label always shown and the chosen one highlighted:
- Pieces: "All pieces";
- Measured Rooms: "All rooms";
- Model Library: "Uploaded models" and "Upload model".

"All pieces", "All rooms" and "Uploaded models" SHALL be each tab's first view and its address (`/studio/pieces`, `/studio/rooms`, `/studio/models`). "Upload model" SHALL open the upload dialog of the Model Library requirement over Uploaded models, and SHALL be highlighted while that dialog is open. On a screen 768 CSS px wide or wider the sub-menu SHALL be a column between the rail and the content. Narrower, it SHALL be a row of tabs across the top of the content, below the page title, and the rail SHALL stay at the left edge as it is.

Each tab SHALL show what its page showed: wherever another requirement names the Pieces page, the Measured Rooms page (or the Rooms page) or the Model Library page, it SHALL mean that tab, and where it gives that page a heading row with its page title, the page title is "Design Studio" and the tab keeps the rest of its heading row. The old addresses `/pieces`, `/rooms` and `/models` SHALL open the matching tab; a piece version's inspector SHALL keep its address `/pieces/<id>/versions/<n>`. The Studio navigation SHALL show one "Design Studio" entry, first, marked current on every tab, and SHALL NOT show "Pieces", "Measured Rooms" or "Model Library" entries. The routes SHALL require sign-in, and a signed-out visit SHALL go to the sign-in page. The page SHALL NOT show model names, prompts, token counts or costs of model calls. The page SHALL pass a recorded browser check, at 1280 × 800 and at 360 × 780, before it counts as done.

#### Scenario: Pieces first
- **WHEN** the owner chooses "Design Studio" in the navigation
- **THEN** the Design Studio page opens with the Pieces tab and its "All pieces" view chosen and the piece tiles shown

#### Scenario: Labels shown and hidden
- **WHEN** the owner chooses "Show labels" on the Design Studio rail
- **THEN** each tab shows its label beside its icon, and the Pricing Overview and conversation rails show their labels too until the owner hides them

#### Scenario: Tab chosen
- **WHEN** the owner chooses the Model Library tab
- **THEN** the address is `/studio/models`, the sub-menu shows "Uploaded models" (chosen) and "Upload model", the model tiles are shown, and the pieces and measured rooms are not

#### Scenario: Sub-menu on a phone
- **WHEN** the owner opens `/studio/models` on a 360 × 780 screen
- **THEN** "Uploaded models" and "Upload model" are a row of tabs above the tiles, and the rail is still at the left edge

#### Scenario: Tab address reloaded
- **WHEN** the owner reloads `/studio/rooms`
- **THEN** the Design Studio page opens with the Measured Rooms tab chosen

#### Scenario: Old address
- **WHEN** the owner opens a bookmark to `/rooms`
- **THEN** the Design Studio page opens with the Measured Rooms tab chosen

#### Scenario: Inspector address kept
- **WHEN** the owner opens `/pieces/shoe-bench/versions/2`
- **THEN** the inspector for `shoe-bench` version 2 opens, and its "Back to pieces" link opens the Pieces tab

#### Scenario: Navigation
- **WHEN** the owner is signed in and looks at the Studio navigation
- **THEN** it shows "Design Studio" first and no "Pieces", "Measured Rooms" or "Model Library" entry

#### Scenario: Signed out
- **WHEN** a signed-out visitor opens `/studio/models`
- **THEN** they are sent to the sign-in page
