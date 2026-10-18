## MODIFIED Requirements

### Requirement: Tools and Project open from a rail
In the Workspace, the chat pane SHALL show one header row with, from the left, the conversation's title, its rename button, its delete action ("Delete <title>") directly to the right of the title, and at the right end a row of panel icons followed by the "Layout" button: "Decisions so far", "Brief", "Project", "Piece" and "Room", each with an accessible name and a tooltip naming it. The header SHALL NOT offer a "Tools" icon, and no conversation view SHALL offer per-conversation tool switches. While the Design Studio rail shows its labels, each icon SHALL show its label beside it. Choosing the Decisions so far, Brief or Project icon SHALL open its panel as a flyout over the chat pane. Choosing it again, choosing another flyout icon, pressing Escape or closing the flyout SHALL close it or switch to the other panel. The Piece and Room icons SHALL NOT open a flyout: choosing one SHALL close any open flyout and show the Workspace's piece pane or room pane, as the requirement "The Workspace's Piece and Room icons open their panes" sets out. The messages SHALL NOT reflow when a flyout opens. The header row SHALL stay visible while the messages scroll. Asking to delete SHALL show the confirmation on its own line below the header row. The Project flyout SHALL show the progress steps, the next step and the open review items, and SHALL refresh while a build or render is queued or running.

#### Scenario: Open and close
- **WHEN** the owner clicks the Project icon in the chat pane header and then presses Escape
- **THEN** the project panel opens over the chat and then closes, and the messages were not reflowed

#### Scenario: Switch
- **WHEN** the Brief flyout is open and the owner clicks the Project icon
- **THEN** the Brief flyout closes and the project panel opens

#### Scenario: No Tools icon
- **WHEN** the owner opens a conversation in the Workspace
- **THEN** the chat pane header shows no "Tools" icon and no tool switches are offered anywhere in the conversation view

#### Scenario: Piece icon opens no flyout
- **WHEN** the Brief flyout is open and the owner clicks the Piece icon
- **THEN** the Brief flyout closes, no flyout opens, and the piece pane is shown beside the chat

#### Scenario: Scrolled conversation
- **WHEN** the owner scrolls a long conversation to its end
- **THEN** the chat pane header and its icons are still shown, and the icons still open their panels or panes

#### Scenario: Icons named
- **WHEN** the owner rests the pointer on the Brief icon
- **THEN** a tooltip shows "Brief"

#### Scenario: Expanded
- **WHEN** the owner chooses "Show labels" on the Design Studio rail
- **THEN** the chat pane header shows each panel's label beside its icon, and choosing "Hide labels" shows the icons only

#### Scenario: Delete beside the title
- **WHEN** the owner opens the conversation "Murphy bed" in the Workspace
- **THEN** "Delete Murphy bed" is on the header row directly right of the title and its rename button, and no separate line holds it

### Requirement: The workspace, pieces, measured rooms, the model library, pricing and agent settings are tabs of one Design Studio page
The Studio SHALL have a Design Studio page for the owner at `/studio` with no visible page title on any tab (its level-1 heading "Design Studio" is for screen readers only, so the space goes to the tab's content), and five owner tabs, in this order: "Workspace", "Pieces", "Measured Rooms", "Model Library" and "Pricing". When the developer gate answers, a sixth tab, "AI & Agent Settings", SHALL follow them below a divider. Without the developer gate, that tab and the divider SHALL NOT be shown. Each owner tab SHALL have its own address (`/studio/workspace`, `/studio/pieces`, `/studio/rooms`, `/studio/models`, `/studio/pricing`), and opening that address SHALL show the page with that tab chosen. The AI & Agent Settings tab SHALL keep the developer route tree's addresses, as its requirement states. `/studio`, and a `/studio/` address naming no known tab, SHALL show the Workspace tab. The tabs SHALL be a rail at the screen's left edge below the header, with the same font, icon style, colour scheme and "Hide labels" switch as the conversation page's panel rail: each tab an icon, with its label beside it while labels are shown, the chosen tab highlighted, and the switch at the rail's foot. The label choice SHALL be remembered in the browser and shared with the other rails; a browser that cannot store it SHALL show the labels hidden. The tabs SHALL be exposed as a vertical tab list with the chosen tab marked selected, and only the chosen tab's content SHALL be shown.

**Sub-menu.** Beside the rail, the chosen tab SHALL show a sub-menu, each entry with its label always shown:
- Workspace: "New conversation", then the conversations by title, newest first;
- Pieces: the name (id) of every piece, in the order of the Pieces grid;
- Measured Rooms: the name of every measured room, then the name of every composition that has a tile of its own (an apartment composition, or a room composition whose room is not in the house file), in the order of the Measured Rooms grid;
- Model Library: "Uploaded models" and "Upload model";
- Pricing: "Prices", "Snapshots" and "Remnants";
- AI & Agent Settings: "Agent Memory", "Agent Workflow", "Agent Calls", "Render Offload", "Agent Score", "Token Usage", "Plugins" and "Models and Routing".

There SHALL be no "All pieces" or "All rooms" entry. With no dialog open, each tab's address (`/studio/pieces`, `/studio/rooms`) SHALL show its tile grid, and no Pieces or Measured Rooms entry SHALL be highlighted. Choosing a piece's, room's or composition's name SHALL open that item's dialog over the grid, at the same address and with the same behaviour as choosing its tile, keeping `?page`. Closing the dialog SHALL return to the grid as it does for a tile. While an item's dialog is open, its name SHALL be highlighted and marked as the current entry. A list with no item SHALL say "No pieces yet" or "No rooms yet" in the sub-menu. A name too long for the column SHALL be cut short with an ellipsis, and its full name SHALL be shown on hover. A sub-menu longer than the screen SHALL scroll on its own, with the page and the rail staying in place. The names SHALL follow the lists without a reload: a piece or room that is created or deleted SHALL appear in or disappear from the sub-menu as its tile does.

"Uploaded models" SHALL be the Model Library's first view and its address (`/studio/models`), and "Prices" the Pricing tab's (`/studio/pricing`). "Upload model" SHALL open the upload dialog of the Model Library requirement over Uploaded models, and SHALL be highlighted while that dialog is open. In the Workspace sub-menu, "New conversation" SHALL start a conversation and open it, and a conversation's entry SHALL open it at `/studio/workspace/<thread-id>`, highlighted while it is open. On a screen 768 CSS px wide or wider the sub-menu SHALL be a column between the rail and the content, with a close button ("Close <sub-menu name>", an "x") at its top. The column SHALL close when the owner chooses one of its entries, including "New conversation", or presses its close button, and the content SHALL then use the freed width. Choosing a tab on the rail, including the tab already chosen, SHALL open the column again. Opening a Design Studio address directly, or reloading it, SHALL show the column open. Narrower, it SHALL be one row across the top of the content, below the page title, that scrolls sideways when the names do not fit, and the rail SHALL stay at the left edge as it is.

Each tab SHALL show what its page showed: wherever another requirement names the Pieces page, the Measured Rooms page (or the Rooms page) or the Model Library page, it SHALL mean that tab, and where it gives that page a heading row with its page title, no title is shown and the tab keeps the rest of its heading row. The old addresses `/pieces`, `/rooms` and `/models` SHALL open the matching tab; a piece version's inspector SHALL keep its address `/pieces/<id>/versions/<n>`. The Studio navigation SHALL NOT show a "Design Studio" entry, nor "Pieces", "Measured Rooms", "Model Library", "Pricing Overview" or "AI & Agent Settings" entries; the Design Studio is reached as the home page. The routes SHALL require sign-in, and a signed-out visit SHALL go to the sign-in page. The owner tabs SHALL NOT show model names, prompts, token counts or costs of model calls. The page SHALL pass a recorded browser check, at 1280 × 800 and at 360 × 780, before it counts as done.

#### Scenario: Pieces first
- **WHEN** the owner chooses "Pieces" on the Design Studio rail
- **THEN** the Pieces tab opens with the piece tiles shown, and the pieces listed by name in the sub-menu with none highlighted

#### Scenario: No page title
- **WHEN** the owner opens any Design Studio tab
- **THEN** no "Design Studio" title is shown above the tab's content, and a screen reader still finds the level-1 heading "Design Studio"

#### Scenario: Labels shown and hidden
- **WHEN** the owner chooses "Show labels" on the Design Studio rail
- **THEN** each tab shows its label beside its icon, and the Workspace chat pane's panel icons show their labels too until the owner hides them

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
- **THEN** it shows no "Design Studio", "Pieces", "Measured Rooms", "Model Library", "Pricing Overview" or "AI & Agent Settings" entry

#### Scenario: Signed out
- **WHEN** a signed-out visitor opens `/studio/pricing/remnants`
- **THEN** they are sent to the sign-in page

#### Scenario: Owner rail
- **WHEN** the owner is signed in without the developer gate and opens the Design Studio
- **THEN** the rail shows "Workspace", "Pieces", "Measured Rooms", "Model Library" and "Pricing", in that order, and no divider and no "AI & Agent Settings" tab

#### Scenario: Developer rail
- **WHEN** the developer is signed in and opens the Design Studio
- **THEN** the rail shows "Workspace", "Pieces", "Measured Rooms", "Model Library" and "Pricing", then a divider and "AI & Agent Settings"

#### Scenario: Pieces listed by name
- **WHEN** the owner opens the Pieces tab and the pieces are `bench`, `hall-bench` and `shelf`
- **THEN** the sub-menu lists `bench`, `hall-bench` and `shelf` in the grid's order, and no "All pieces" entry

#### Scenario: Rooms and apartment listed
- **WHEN** the house file holds `Hall` and `Küche`, and apartment `Wohnung` has a composition
- **THEN** the Measured Rooms sub-menu lists `Hall`, `Küche`, then `Wohnung`, and no "All rooms" entry

#### Scenario: Name opens the dialog
- **WHEN** the owner, on page 2 of Pieces, chooses `shelf` in the sub-menu
- **THEN** the address is `/studio/pieces/shelf?page=2`, the `shelf` dialog opens over the grid, and `shelf` is highlighted in the sub-menu

#### Scenario: Dialog closed
- **WHEN** the owner closes the `shelf` dialog
- **THEN** the address is `/studio/pieces?page=2`, the grid is shown, and no name is highlighted

#### Scenario: Composition name opens its dialog
- **WHEN** the owner chooses `Wohnung` in the Measured Rooms sub-menu
- **THEN** the address is `/studio/rooms/compositions/wohnung` and the `Wohnung` dialog opens

#### Scenario: No pieces
- **WHEN** there are no pieces
- **THEN** the Pieces sub-menu says "No pieces yet"

#### Scenario: Deleted room leaves the sub-menu
- **WHEN** the owner deletes `Hall` from its dialog
- **THEN** `Hall` is gone from the sub-menu and from the grid without a reload

#### Scenario: Names on a phone
- **WHEN** the owner opens Pieces with 18 pieces on a 360 × 780 screen
- **THEN** the names are one row above the grid that scrolls sideways, the page does not scroll sideways, and the rail is still at the left edge

#### Scenario: Sub-menu closes after a choice
- **WHEN** the screen is 1280 px wide and the owner chooses "Remnants" in the Pricing sub-menu column
- **THEN** the Remnants view is shown and the sub-menu column is closed

#### Scenario: Sub-menu closed with its x
- **WHEN** the owner presses "Close Conversations" at the top of the Workspace sub-menu column
- **THEN** the column closes and the conversation uses the freed width

#### Scenario: Sub-menu reopened from the rail
- **WHEN** the Pieces sub-menu column is closed and the owner chooses the Pieces tab on the rail
- **THEN** the Pieces sub-menu column is shown again

#### Scenario: Row unchanged on a phone
- **WHEN** the screen is 360 px wide and the owner chooses a conversation in the Workspace sub-menu row
- **THEN** the conversation opens and the sub-menu row stays shown above the content

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
- its screenshot or still. The dialog SHALL NOT show a link to the turntable viewer outside the 3D view;
- when the version has `model.glb`, a 3D view of the composition, loaded only when the owner opens it; choosing another version in the dropdown SHALL show that version in the open view. It SHALL use the piece inspector's camera controls (free rotate and zoom, Iso, Front, Side and Plan) and its Workshop and Blueprint modes. It SHALL offer one switch per surface of the version's surface map: each wall, the floor, the ceiling and the items, plus "All walls". Switching a surface off SHALL hide exactly the meshes the map lists under it, and a mesh the map does not name stays visible. All surfaces SHALL start switched on, except the ceiling, which starts off so the room can be seen from above. The view SHALL offer a "dimensions" switch, off at first. Switched on, it SHALL label every unique wall of the version's room plan with its length in millimetres, on that wall (a wall two rooms of an apartment share is labelled once), and each room's ceiling height in millimetres once per room (so an apartment whose rooms differ shows each height). The figures SHALL be the chosen version's own. While the 3D view is open and the chosen version has a turntable, the view SHALL offer "Open the turntable viewer of <name>", opening the viewer in a new tab; this is the only place on the page that offers it. A version without `model.glb` SHALL show its screenshot or still and say that composing the room again adds the 3D view.

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

#### Scenario: Turntable viewer only in the 3D view
- **WHEN** composition `Wohnen` version 11 has a turntable and the owner opens the `Wohnen` dialog
- **THEN** no "Open the turntable viewer of Wohnen" link is shown until the owner opens the 3D view, and the open 3D view offers it

### Requirement: A build notice is shown with an Inspect button
The conversation view SHALL show each build notice in its place among the messages, framed like a render notice. A finished build's notice SHALL show an "Inspect version N" button that opens the inspector for that piece version beside the chat. A failed build's notice, and a notice whose version was deleted, SHALL show no button. A build notice posted while the view is open SHALL appear without a reload while the Project panel is following a build. A revision SHALL NOT add a second notice with its own button: the build notice and its "Inspect version N" button are the one notice of a revision. A revision notice already in a thread's history SHALL be shown as its text with no button. It SHALL NOT show a model name, prompt, token count or cost.

#### Scenario: Built while open
- **WHEN** `hall-bench` version 2 finishes building while its conversation is open
- **THEN** a notice saying version 2 is built appears without a reload, with an "Inspect version 2" button

#### Scenario: Inspect from the notice
- **WHEN** the owner presses "Inspect version 2" on that notice
- **THEN** the inspector for `hall-bench` version 2 is shown beside the chat and the composer is still usable

#### Scenario: Failed build
- **WHEN** the build of `hall-bench` version 3 fails
- **THEN** its notice says it did not build and shows no button

#### Scenario: One notice per revision
- **WHEN** the owner confirms a revision of `hall-bench` and version 2 builds
- **THEN** the conversation shows one notice for version 2, saying it is built, with an "Inspect version 2" button and no "Open version 2" button

#### Scenario: Old revision notice
- **WHEN** a thread's history holds a revision notice "hall-bench version 2 is created." from before this change
- **THEN** it is shown as text with no button

## ADDED Requirements

### Requirement: Conversation pages show no model internals
No conversation page SHALL show model names, token counts or costs. Delete of a conversation SHALL be offered on the conversation view as set out in "Conversations are deleted from the list". A conversation SHALL use every plugin that is enabled for the whole service on the developer's Plugins page.

#### Scenario: No internals
- **WHEN** the owner opens any conversation
- **THEN** no model name, token count or cost is shown

#### Scenario: Delete with confirmation
- **WHEN** the owner chooses delete on the open conversation "Listening wall" and confirms
- **THEN** the conversation is gone, and when the owner cancels instead, nothing changes

## REMOVED Requirements

### Requirement: Conversations show their tool toggles
**Reason**: The owner decided on 2026-10-18 to drop per-conversation tool switches. Plugins are switched only for the whole service from AI & Agent Settings → Plugins. The requirement's remaining rules (no model internals, delete) move to "Conversation pages show no model internals". Its rules on starting conversations from the Pieces page were already replaced by the Workspace requirements.
**Migration**: Switch a plugin off for every conversation on the developer's Plugins page (`/admin/plugins`).
