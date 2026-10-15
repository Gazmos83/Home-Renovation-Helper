## RENAMED Requirements

- FROM: `### Requirement: Pieces, measured rooms and the model library are tabs of one Design Studio page`
- TO: `### Requirement: The workspace, pieces, measured rooms, the model library, pricing and agent settings are tabs of one Design Studio page
The Studio SHALL have a Design Studio page for the owner at `/studio` with the page title "Design Studio" on every tab, and five owner tabs, in this order: "Workspace", "Pieces", "Measured Rooms", "Model Library" and "Pricing". When the developer gate answers, a sixth tab, "AI & Agent Settings", SHALL follow them below a divider. Without the developer gate, that tab and the divider SHALL NOT be shown. Each owner tab SHALL have its own address (`/studio/workspace`, `/studio/pieces`, `/studio/rooms`, `/studio/models`, `/studio/pricing`), and opening that address SHALL show the page with that tab chosen. The AI & Agent Settings tab SHALL keep the developer route tree's addresses, as its requirement states. `/studio`, and a `/studio/` address naming no known tab, SHALL show the Pieces tab. The tabs SHALL be a rail at the screen's left edge below the header, with the same font, icon style, colour scheme and "Hide labels" switch as the conversation page's panel rail: each tab an icon, with its label beside it while labels are shown, the chosen tab highlighted, and the switch at the rail's foot. The label choice SHALL be remembered in the browser and shared with the other rails; a browser that cannot store it SHALL show the labels hidden. The tabs SHALL be exposed as a vertical tab list with the chosen tab marked selected, and only the chosen tab's content SHALL be shown.

**Sub-menu.** Beside the rail, the chosen tab SHALL show a sub-menu, each entry with its label always shown:
- Workspace: "New conversation", then the conversations by title, newest first;
- Pieces: the name (id) of every piece, in the order of the Pieces grid;
- Measured Rooms: the name of every measured room, then the name of every composition that has a tile of its own (an apartment composition, or a room composition whose room is not in the house file), in the order of the Measured Rooms grid;
- Model Library: "Uploaded models" and "Upload model";
- Pricing: "Prices", "Snapshots" and "Remnants";
- AI & Agent Settings: "Agent Memory", "Agent Workflow", "Agent Calls", "Render Offload", "Agent Score", "Token Usage", "Plugins" and "Models and Routing".

There SHALL be no "All pieces" or "All rooms" entry. With no dialog open, each tab's address (`/studio/pieces`, `/studio/rooms`) SHALL show its tile grid, and no Pieces or Measured Rooms entry SHALL be highlighted. Choosing a piece's, room's or composition's name SHALL open that item's dialog over the grid, at the same address and with the same behaviour as choosing its tile, keeping `?page`. Closing the dialog SHALL return to the grid as it does for a tile. While an item's dialog is open, its name SHALL be highlighted and marked as the current entry. A list with no item SHALL say "No pieces yet" or "No rooms yet" in the sub-menu. A name too long for the column SHALL be cut short with an ellipsis, and its full name SHALL be shown on hover. A sub-menu longer than the screen SHALL scroll on its own, with the page and the rail staying in place. The names SHALL follow the lists without a reload: a piece or room that is created or deleted SHALL appear in or disappear from the sub-menu as its tile does.

"Uploaded models" SHALL be the Model Library's first view and its address (`/studio/models`), and "Prices" the Pricing tab's (`/studio/pricing`). "Upload model" SHALL open the upload dialog of the Model Library requirement over Uploaded models, and SHALL be highlighted while that dialog is open. In the Workspace sub-menu, "New conversation" SHALL start a conversation and open it, and a conversation's entry SHALL open it at `/studio/workspace/<thread-id>`, highlighted while it is open. On a screen 768 CSS px wide or wider the sub-menu SHALL be a column between the rail and the content. Narrower, it SHALL be one row across the top of the content, below the page title, that scrolls sideways when the names do not fit, and the rail SHALL stay at the left edge as it is.

Each tab SHALL show what its page showed: wherever another requirement names the Pieces page, the Measured Rooms page (or the Rooms page) or the Model Library page, it SHALL mean that tab, and where it gives that page a heading row with its page title, the page title is "Design Studio" and the tab keeps the rest of its heading row. The old addresses `/pieces`, `/rooms` and `/models` SHALL open the matching tab; a piece version's inspector SHALL keep its address `/pieces/<id>/versions/<n>`. The Studio navigation SHALL show one "Design Studio" entry, first, marked current on every tab including AI & Agent Settings, and SHALL NOT show "Pieces", "Measured Rooms", "Model Library", "Pricing Overview" or "AI & Agent Settings" entries. The routes SHALL require sign-in, and a signed-out visit SHALL go to the sign-in page. The owner tabs SHALL NOT show model names, prompts, token counts or costs of model calls. The page SHALL pass a recorded browser check, at 1280 × 800 and at 360 × 780, before it counts as done.

#### Scenario: Pieces first
- **WHEN** the owner chooses "Design Studio" in the navigation
- **THEN** the Design Studio page opens with the Pieces tab chosen, the piece tiles shown, and the pieces listed by name in the sub-menu with none highlighted

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
- **THEN** it shows "Design Studio" first and no "Pieces", "Measured Rooms", "Model Library", "Pricing Overview" or "AI & Agent Settings" entry

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

### Requirement: Tools and Project open from a rail
In the Workspace, the chat pane SHALL show a header row with the conversation's title, its delete action and a row of panel icons: "Tools", "Decisions so far", "Brief", "Project", "Piece" and "Room", each with an accessible name and a tooltip naming it. While the Design Studio rail shows its labels, each icon SHALL show its label beside it. Choosing an icon SHALL open its panel as a flyout over the chat pane. Choosing it again, choosing another icon, pressing Escape or closing the flyout SHALL close it or switch to the other panel. The messages SHALL NOT reflow when a flyout opens. The header row SHALL stay visible while the messages scroll. The Project flyout SHALL carry the project panel unchanged, including its refresh while a build or render is queued or running.

#### Scenario: Open and close
- **WHEN** the owner clicks the Project icon in the chat pane header and then presses Escape
- **THEN** the project panel opens over the chat and then closes, and the messages were not reflowed

#### Scenario: Switch
- **WHEN** the Tools flyout is open and the owner clicks the Project icon
- **THEN** the Tools flyout closes and the project panel opens

#### Scenario: Scrolled conversation
- **WHEN** the owner scrolls a long conversation to its end
- **THEN** the chat pane header and its icons are still shown, and the icons still open their panels

#### Scenario: Icons named
- **WHEN** the owner rests the pointer on the Brief icon
- **THEN** a tooltip shows "Brief"

#### Scenario: Expanded
- **WHEN** the owner chooses "Show labels" on the Design Studio rail
- **THEN** the chat pane header shows each panel's label beside its icon, and choosing "Hide labels" shows the icons only

### Requirement: A piece version is reviewed beside the conversation
The Workspace's piece pane SHALL show the inspector for one piece version, with its version dropdown, in every layout that has a piece pane. It SHALL show the version named in the address (`?inspect=<package-id>/<n>`), or otherwise the latest version of the conversation's bound piece. When the conversation has no bound piece, the pane SHALL say in plain words that no piece has been designed yet in this conversation. While the inspector is shown, the owner SHALL still be able to read, scroll and send messages, and opening the inspector SHALL NOT start a turn. Opening another version, from the dropdown, a notice or the Project panel, SHALL replace the shown one and write it to the address, so a reload shows it again. When the current layout has no piece pane, opening a version SHALL switch to the "Chat and piece" layout. A version that is not built, or a file it lacks, SHALL be named in plain words as on the inspector page.

#### Scenario: Review from a notice
- **WHEN** the owner presses "Review draft v1" on a notice for `hall-bench` version 1
- **THEN** the piece pane shows the inspector for `hall-bench` version 1 and the composer is still usable

#### Scenario: Ask about a detail
- **WHEN** the piece pane shows a version and the owner sends "the left shelf looks too thin"
- **THEN** the message is sent as a normal turn and the piece pane still shows that version

#### Scenario: Bound piece by default
- **WHEN** the owner opens a conversation bound to `hall-bench`, whose latest version is 3, with no `?inspect=` in the address, in the "Chat and piece" layout
- **THEN** the piece pane shows `hall-bench` version 3

#### Scenario: No piece yet
- **WHEN** the owner opens a new conversation with no bound piece in the "Chat and piece" layout
- **THEN** the piece pane says no piece has been designed yet in this conversation

#### Scenario: Opened from the room layout
- **WHEN** the layout is "Chat and room" and the owner presses "Review draft v2" on a notice
- **THEN** the layout switches to "Chat and piece" and the piece pane shows version 2

#### Scenario: Close
- **WHEN** the piece pane is shown in "Chat and piece" and the owner chooses the "Chat and room" layout
- **THEN** the piece pane is no longer shown, and the room pane takes its place beside the chat

#### Scenario: Reload
- **WHEN** the owner reloads the conversation while the piece pane shows `hall-bench` version 2
- **THEN** the conversation and the inspector for version 2 are shown again, in the same layout

### Requirement: The Project panel opens the conversation's room in 3D beside the chat
The Project panel SHALL show, under the piece, a "Selected room" heading and below it the conversation's confirmed room or apartment by name. When its composition has a 3D model, the panel SHALL offer a button to inspect it. Pressing it SHALL show the room's 3D view in the Workspace's room pane, and SHALL switch to the "Chat and room" layout when the current layout has no room pane. In every layout with a room pane, the pane SHALL show the room named in the address (`?room=<slug>[/<n>]`), or otherwise the conversation's confirmed room at its composition's latest version. The view SHALL be the Rooms page's 3D view of the composition, with the same cameras, modes, surface switches and dimensions switch, and the ceiling starting off. The pane SHALL show the room's name and offer the same version dropdown as the Rooms page (the newest five versions, the latest chosen). Choosing a version SHALL show it, and a version without a 3D model SHALL be named in plain words. Opening it SHALL NOT start a turn, and the owner SHALL still be able to read, scroll and send messages. The shown room and its chosen version SHALL be part of the page's address, so a reload shows them again.

When the room or apartment has no composition, the panel and the room pane SHALL say in plain words that it has no 3D view yet and that the Designer can compose it. When the composition's latest version has no 3D model, they SHALL say that composing it again adds the 3D view. When the conversation has confirmed no room or apartment, the panel SHALL show no room section and the room pane SHALL say that no room is confirmed yet. An address naming a room that is not the conversation's current room SHALL be ignored, and the pane SHALL show the current room.

The piece pane and the room pane SHALL be shown together in the "Piece and room, chat below" layout. Opening one SHALL NOT close the other.

The panel and the panes SHALL NOT show model names of language models, prompts, token counts or costs. The room section SHALL pass a recorded browser check before it counts as done.

#### Scenario: Inspect the room
- **WHEN** the layout is "Chat and piece", the conversation has confirmed `Hall`, composition `Hall` has a 3D model, and the owner presses "Inspect Hall" in the Project panel under "Selected room"
- **THEN** the layout switches to "Chat and room", the 3D view of `Hall` is shown with its surface switches and the ceiling off, and the composer is still usable

#### Scenario: Another version beside the chat
- **WHEN** the room pane shows `Hall` version 3 and the owner chooses version 2 in its dropdown
- **THEN** version 2's model is shown, and a reload shows version 2 again

#### Scenario: Dimensions beside the chat
- **WHEN** the owner switches dimensions on in the room view of `Hall`
- **THEN** each wall of `Hall` is labelled with its length and the ceiling height is shown once

#### Scenario: No 3D view yet
- **WHEN** the conversation has confirmed `Hall` and `Hall` has no composition
- **THEN** the Project panel and the room pane say `Hall` has no 3D view yet and that the Designer can compose the room, and the panel offers no inspect button

#### Scenario: No room confirmed
- **WHEN** the conversation has confirmed no room or apartment
- **THEN** the Project panel shows no room section and the room pane says no room is confirmed yet

#### Scenario: Reload
- **WHEN** the owner reloads the conversation while the room pane shows `Hall`
- **THEN** the conversation and the room view of `Hall` are shown again

#### Scenario: Close the room view
- **WHEN** the room pane is shown in "Chat and room" and the owner chooses the "Chat and piece" layout
- **THEN** the room pane is no longer shown, and the piece pane takes its place beside the chat

#### Scenario: One pane at a time
- **WHEN** the layout is "Chat and room" and the owner presses "Inspect version 2" in the Project panel
- **THEN** the layout switches to "Chat and piece" with version 2 shown; pressing "Inspect Hall" then switches back to "Chat and room" with `Hall` shown

#### Scenario: Piece and room together
- **WHEN** the layout is "Piece and room, chat below" and the owner presses "Inspect version 2" and then "Inspect Hall" in the Project panel
- **THEN** the piece pane shows version 2, the room pane shows `Hall`, and neither closes the other

### Requirement: Conversations are not listed in the Studio navigation
The Studio header navigation SHALL NOT include a Conversations item. Conversations SHALL be listed in the Workspace tab's sub-menu. `/conversations` SHALL open the Workspace, and `/conversations/<thread-id>` SHALL open `/studio/workspace/<thread-id>`, keeping its `?inspect=` and `?room=` values. The Pieces tab's conversation links SHALL open `/studio/workspace/<thread-id>`. After sign-in the owner SHALL land on the Design Studio page's Pieces tab.

#### Scenario: Nav without Conversations
- **WHEN** the owner is signed in and looks at the Studio navigation
- **THEN** there is no Conversations item, and Design Studio is present

#### Scenario: Sign-in lands on Pieces
- **WHEN** the owner signs in successfully
- **THEN** the Studio opens on the Design Studio page with the Pieces tab chosen

#### Scenario: Deep link still works
- **WHEN** the owner opens `/conversations/<thread-id>?inspect=hall-bench/2` for an existing conversation
- **THEN** the address becomes `/studio/workspace/<thread-id>?inspect=hall-bench/2`, and that conversation opens with version 2 in the piece pane

## REMOVED Requirements

### Requirement: Prices, snapshots and remnants are tabs of one Pricing Overview page
**Reason**: The owner folded the Pricing Overview page into the Design Studio (2026-10-14). Its three tabs become the views of the Design Studio's Pricing tab.
**Migration**: See "Prices, snapshots and remnants are views of the Design Studio's Pricing tab". `/pricing`, `/pricing/<tab>`, `/price-list`, `/snapshots` and `/remnants` forward to the matching `/studio/pricing/<view>` address.

## ADDED Requirements

### Requirement: The Workspace shows a conversation in a chosen layout
The Design Studio's Workspace tab SHALL show one conversation at `/studio/workspace/<thread-id>` in one of three layouts:
- "Chat and piece": the chat pane on the left, the piece pane on the right;
- "Chat and room": the chat pane on the left, the room pane on the right;
- "Piece and room, chat below": the piece pane on the left and the room pane on the right, across the top, with the chat pane across the bottom.

A layout button with an accessible name "Layout" SHALL sit at the right end of the "Design Studio" title row while the Workspace tab is chosen. It SHALL open a menu of the three layouts, each with a small picture of its arrangement and its name, with the current one marked. Choosing one SHALL switch the layout without reloading the conversation and without starting a turn. The default layout SHALL be "Chat and piece".

Between every two neighbouring panes there SHALL be a resize handle: between the chat and the piece or room left and right, between the piece and the room left and right, and between the top panes and the chat up and down. Dragging a handle SHALL resize the panes on both sides. Double-clicking it SHALL restore that layout's default sizes. With the handle focused, the arrow keys SHALL move it. No pane SHALL be made smaller than 20 % of its group. The default sizes SHALL be half and half for each left and right split, and 60 % for the top panes and 40 % for the chat in "Piece and room, chat below". The chosen layout and each layout's sizes SHALL be remembered in the browser. A browser that cannot store them SHALL use the defaults. The panes SHALL fill the height of the screen below the title row, and each pane SHALL scroll on its own.

`/studio/workspace` SHALL open the newest conversation. When there is none, it SHALL say so in plain words and offer "New conversation". A `/studio/workspace/` address naming an unknown conversation SHALL say the conversation was not found, and SHALL keep the sub-menu.

Below 1024 CSS px wide, the Workspace SHALL show one pane at a time, chosen from a row of "Chat", "Piece" and "Room" tabs above it, and SHALL NOT show the layout button. Opening a piece version or the room from the chat SHALL choose that pane's tab.

Wherever another requirement names the conversation view or the conversation page, it SHALL mean the Workspace with that conversation open. Where it says "beside the chat", it SHALL mean in the piece or room pane. The Workspace SHALL NOT show model names, prompts, token counts or costs of model calls. The tab SHALL pass a recorded browser check, at 1280 × 800 and at 360 × 780, before it counts as done.

#### Scenario: Default layout
- **WHEN** the owner opens a conversation in the Workspace for the first time in this browser
- **THEN** the chat is on the left and the piece pane on the right, each half the width

#### Scenario: Choose a layout
- **WHEN** the owner presses "Layout" and chooses "Piece and room, chat below"
- **THEN** the piece pane is on the top left, the room pane on the top right, the chat across the bottom, and no turn starts

#### Scenario: Drag a handle
- **WHEN** in "Chat and piece" the owner drags the handle between the chat and the piece to the right
- **THEN** the chat grows and the piece pane shrinks, and neither becomes smaller than 20 %

#### Scenario: Chat expanded upwards
- **WHEN** in "Piece and room, chat below" the owner drags the handle above the chat upwards
- **THEN** the chat grows taller and the piece and room panes grow shorter

#### Scenario: Double-click resets
- **WHEN** the owner double-clicks a handle after dragging it
- **THEN** the panes on both sides return to that layout's default sizes

#### Scenario: Keyboard
- **WHEN** the owner focuses the handle between the piece and the room and presses the left arrow
- **THEN** the piece pane shrinks and the room pane grows

#### Scenario: Remembered
- **WHEN** the owner chooses "Chat and room", drags its handle, and reloads the page
- **THEN** the layout is "Chat and room" with the dragged sizes

#### Scenario: Storage unavailable
- **WHEN** the browser cannot store the layout
- **THEN** the Workspace opens in "Chat and piece" at the default sizes, and switching and resizing still work until the page is left

#### Scenario: Newest conversation
- **WHEN** the owner chooses "Workspace" on the rail and conversations exist
- **THEN** the newest conversation opens and is highlighted in the sub-menu

#### Scenario: New conversation
- **WHEN** the owner chooses "New conversation" in the Workspace sub-menu
- **THEN** a conversation is started, it opens at its `/studio/workspace/<thread-id>` address, and it is listed first in the sub-menu

#### Scenario: Phone tabs
- **WHEN** the owner opens a conversation on a 360 × 780 screen
- **THEN** "Chat", "Piece" and "Room" tabs are shown with "Chat" chosen, only the chat is shown, and there is no layout button

#### Scenario: Phone review
- **WHEN** on a 360 × 780 screen the owner presses "Review draft v1" on a notice
- **THEN** the "Piece" tab is chosen and shows version 1

### Requirement: Prices, snapshots and remnants are views of the Design Studio's Pricing tab
The Design Studio's Pricing tab SHALL have three views, in this order: "Prices", "Snapshots" and "Remnants", chosen from its sub-menu. Each view SHALL have its own address (`/studio/pricing/prices`, `/studio/pricing/snapshots`, `/studio/pricing/remnants`), and opening that address SHALL show the Design Studio with the Pricing tab and that view chosen. `/studio/pricing`, and a `/studio/pricing/` address naming no known view, SHALL show the Prices view. Only the chosen view's content SHALL be shown. Each view SHALL show what the matching Pricing Overview tab showed: wherever another requirement names the Pricing Overview page or its Prices, Snapshots or Remnants tab, it SHALL mean the Pricing tab or that view. The old addresses `/pricing`, `/pricing/prices`, `/pricing/snapshots`, `/pricing/remnants`, `/price-list`, `/snapshots` and `/remnants` SHALL open the matching view, and a `/pricing/` address naming no known tab SHALL open the Prices view. The tab SHALL NOT show model names, prompts, token counts or costs of model calls. The tab SHALL pass a recorded browser check, at 1280 × 800 and at 360 × 780, before it counts as done.

#### Scenario: Prices first
- **WHEN** the owner chooses "Pricing" on the Design Studio rail
- **THEN** the address is `/studio/pricing`, the sub-menu shows "Prices" (chosen), "Snapshots" and "Remnants", and the price list is shown

#### Scenario: View chosen
- **WHEN** the owner chooses "Remnants" in the Pricing sub-menu
- **THEN** the address is `/studio/pricing/remnants`, the rack is shown, and the price list and snapshots are not

#### Scenario: View address reloaded
- **WHEN** the owner reloads `/studio/pricing/snapshots`
- **THEN** the Design Studio opens with the Pricing tab and its Snapshots view chosen

#### Scenario: Old address
- **WHEN** the owner opens a bookmark to `/snapshots` or to `/pricing/snapshots`
- **THEN** the Design Studio opens at `/studio/pricing/snapshots` with the Snapshots view chosen

#### Scenario: Pricing on a phone
- **WHEN** the owner opens `/studio/pricing/prices` on a 360 × 780 screen
- **THEN** "Prices", "Snapshots" and "Remnants" are a row of tabs above the price list, and the page does not scroll sideways
