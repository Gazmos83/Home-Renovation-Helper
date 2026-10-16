## MODIFIED Requirements

### Requirement: The Workspace shows a conversation in a chosen layout
The Design Studio's Workspace tab SHALL show one conversation at `/studio/workspace/<thread-id>` in one of three layouts:
- "Chat and piece": the chat pane on the left, the piece pane on the right;
- "Chat and room": the chat pane on the left, the room pane on the right;
- "Piece, room and chat above": the chat pane across the top, with the piece pane on the left and the room pane on the right below it.

A layout button with an accessible name "Layout" SHALL sit in the chat pane's header row, after its panel icons, at the row's right end. It SHALL open a menu of the three layouts, each with a small picture of its arrangement and its name, with the current one marked. Choosing one SHALL switch the layout without reloading the conversation and without starting a turn, and SHALL show the chat scrolled to its last message. The default layout SHALL be "Chat and piece". There SHALL be no "Piece and room, chat below" layout; a browser that remembered it SHALL open in "Piece, room and chat above" at that layout's default sizes.

Between every two neighbouring panes there SHALL be a resize handle: between the chat and the piece or room left and right, between the piece and the room left and right, and between the chat and the panes below it up and down. Dragging a handle SHALL resize the panes on both sides. Double-clicking it SHALL restore that layout's default sizes. With the handle focused, the arrow keys SHALL move it. No pane SHALL be made smaller than 20 % of its group. The default sizes SHALL be half and half for each left and right split, and 40 % for the chat and 60 % for the panes below it in "Piece, room and chat above". The chosen layout and each layout's sizes SHALL be remembered in the browser. A browser that cannot store them SHALL use the defaults. The panes SHALL fill the height of the screen below the header (and, on a phone, the sub-menu row), and each pane SHALL scroll on its own.

`/studio/workspace` SHALL open the newest conversation. When there is none, it SHALL say so in plain words and offer "New conversation". A `/studio/workspace/` address naming an unknown conversation SHALL say the conversation was not found, and SHALL keep the sub-menu.

Below 1024 CSS px wide, the Workspace SHALL show one pane at a time, chosen from a row of "Chat", "Piece" and "Room" tabs above it, and SHALL NOT show the layout button. Opening a piece version or the room from the chat SHALL choose that pane's tab.

Wherever another requirement names the conversation view or the conversation page, it SHALL mean the Workspace with that conversation open. Where it says "beside the chat", it SHALL mean in the piece or room pane. The Workspace SHALL NOT show model names, prompts, token counts or costs of model calls. The tab SHALL pass a recorded browser check, at 1280 × 800 and at 360 × 780, before it counts as done.

#### Scenario: Default layout
- **WHEN** the owner opens a conversation in the Workspace for the first time in this browser
- **THEN** the chat is on the left and the piece pane on the right, each half the width

#### Scenario: Choose a layout
- **WHEN** the owner presses "Layout" and chooses "Piece, room and chat above"
- **THEN** the chat is across the top, the piece pane on the bottom left, the room pane on the bottom right, and no turn starts

#### Scenario: Last message after a switch
- **WHEN** a long conversation is shown scrolled to its end in "Chat and piece" and the owner chooses "Piece, room and chat above"
- **THEN** the chat shows its last message, scrolled to the bottom of the messages box

#### Scenario: Layout button in the chat header
- **WHEN** the owner opens a conversation in the Workspace on a 1280 × 800 screen
- **THEN** the "Layout" button is at the right end of the chat pane's header row, after the Room icon, and no "Design Studio" title is shown above the Workspace

#### Scenario: Old layout remembered
- **WHEN** the browser remembered "Piece and room, chat below" and the owner opens a conversation
- **THEN** the Workspace opens in "Piece, room and chat above" with the chat at 40 % and the piece and room at half and half

#### Scenario: Drag a handle
- **WHEN** in "Chat and piece" the owner drags the handle between the chat and the piece to the right
- **THEN** the chat grows and the piece pane shrinks, and neither becomes smaller than 20 %

#### Scenario: Chat expanded downwards
- **WHEN** in "Piece, room and chat above" the owner drags the handle below the chat downwards
- **THEN** the chat grows taller and the piece and room panes grow shorter

#### Scenario: Chat expanded upwards
- **WHEN** in "Piece, room and chat above" the owner drags the handle below the chat upwards
- **THEN** the chat grows shorter and the piece and room panes grow taller, and the chat never becomes smaller than 20 %

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

### Requirement: The Project panel opens the conversation's room in 3D beside the chat
The Project panel SHALL show, under the piece, a "Selected room" heading and below it the conversation's confirmed room or apartment by name. When its composition has a 3D model, the panel SHALL offer a button to inspect it. Pressing it SHALL show the room's 3D view in the Workspace's room pane, and SHALL switch to the "Chat and room" layout when the current layout has no room pane. In every layout with a room pane, the pane SHALL show the room named in the address (`?room=<slug>[/<n>]`), or otherwise the conversation's confirmed room at its composition's latest version. The view SHALL be the Rooms page's 3D view of the composition, with the same cameras, modes, surface switches and dimensions switch, and the ceiling starting off. The pane SHALL show the room's name and offer the same version dropdown as the Rooms page (the newest five versions, the latest chosen). Choosing a version SHALL show it, and a version without a 3D model SHALL be named in plain words. Opening it SHALL NOT start a turn, and the owner SHALL still be able to read, scroll and send messages. The shown room and its chosen version SHALL be part of the page's address, so a reload shows them again.

When the room or apartment has no composition, the panel and the room pane SHALL say in plain words that it has no 3D view yet and that the Designer can compose it. When the composition's latest version has no 3D model, they SHALL say that composing it again adds the 3D view. When the conversation has confirmed no room or apartment, the panel SHALL show no room section and the room pane SHALL say that no room is confirmed yet. An address naming a room that is not the conversation's current room SHALL be ignored, and the pane SHALL show the current room.

The piece pane and the room pane SHALL be shown together in the "Piece, room and chat above" layout. Opening one SHALL NOT close the other.

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
- **WHEN** the layout is "Piece, room and chat above" and the owner presses "Inspect version 2" and then "Inspect Hall" in the Project panel
- **THEN** the piece pane shows version 2, the room pane shows `Hall`, and neither closes the other

### Requirement: The conversation view is the homeowner's chat
The conversation view SHALL show the owner's messages and the replies in order as chat bubbles: replies aligned to the left, the owner's messages to the right, and forms, confirmations and question sets centred. Reply text SHALL be set in Commissioner and headings and speaker names in Oswald, served with the app, with a line height of at least 1.6 and space between paragraphs. A reply SHALL be rendered as formatted text — headings, bullet and numbered lists, tables, emphasis, inline code — with raw HTML shown as text and never rendered, and an image shown only when it points at one of the app's own routes. A fenced block marked `calc` SHALL be shown in a framed box set apart from the reply's text. A file route of a piece, a composition or an apartment shell in a reply, written bare or as a link, SHALL be shown as a link that opens in a new tab; no other address in a reply SHALL be linked. A composer SHALL send one message as one turn, and the turn's refusal SHALL be shown in words next to the composer when the service refuses it. While a turn is running the composer SHALL be disabled and a waiting bubble SHALL stand in the reply position: left-aligned, rounded, with a 2 px border and animated dots, naming the specialist currently working ("Designer is working…") and updating as the turn moves on, or "The Foreman is working…" before a specialist is chosen. Under each reply the specialists that ran in that turn SHALL be listed by role name only. A reply's title event SHALL update the heading without a reload. The heading SHALL be editable in place; saving sends the new title and an empty title is refused in words.

**Compact chat.** In the "Piece, room and chat above" layout, and only there, the chat SHALL be a compact transcript instead:
- every message, reply, notice, confirmation, question set, the waiting bubble and a pending confirmation card SHALL be aligned to the left;
- each reply and each of the owner's messages SHALL be a light bubble (a thin border, no filled colour) with its speaker inline before the text on the same line — "Foreman:" before a reply and "You:" before the owner's message — and the text wrapping beside the speaker, not below it;
- the vertical gap between two messages SHALL be at most 8 px;
- the composer's first row SHALL hold, in this order, a "You:" label, the message box with the placeholder "Describe what you want…", and Send (Stop while a turn runs, "Send edit" while editing); the attach control, the edit warning and pending attachments SHALL be on rows below it.

A message's formatting, links, attachments, "Edit", "Add to decisions" and the specialists listed under a reply SHALL be the same in both styles. "Chat and piece", "Chat and room" and the phone view SHALL keep the left and right bubbles.

#### Scenario: Send and read
- **WHEN** the owner types "I want a bench for the hall" and sends it
- **THEN** the message appears at once on the right, the composer is disabled, a waiting bubble on the left names the Foreman and then Intake, and the reply replaces it on the left with "Intake" listed under it

#### Scenario: Refused turn
- **WHEN** the service answers the turn with 503 and the memory reason
- **THEN** the reason is shown next to the composer, the waiting bubble is gone and the owner's message is not kept in the list

#### Scenario: Table in a reply
- **WHEN** a reply contains a Markdown table of five cut-list rows
- **THEN** it is shown as a table with a header row and five rows, not as text with `|` characters

#### Scenario: Calculation box
- **WHEN** a reply contains a `calc` block "430 + 430 + 400 + 100 + 100 = 1460"
- **THEN** the calculation is shown in a framed box between the paragraphs around it

#### Scenario: HTML in a reply
- **WHEN** a reply contains `<img src=x onerror=alert(1)>`
- **THEN** the text is shown literally and no element is created from it

#### Scenario: Render route in a reply
- **WHEN** a reply says the turntable "will be at /packages/hall-bench/versions/1/files/viewer.html."
- **THEN** that route is a link opening in a new tab, without the full stop, and an `https://` address in a reply stays plain text

#### Scenario: Rename in place
- **WHEN** the owner edits the heading to "Listening wall" and saves
- **THEN** the heading and the conversation list show "Listening wall"

#### Scenario: Compact transcript
- **WHEN** the layout is "Piece, room and chat above" and the conversation holds the owner's "Make it 10 cm narrower" followed by a reply
- **THEN** both are on the left, the owner's message reads "You: Make it 10 cm narrower" on one line in a light bubble, the reply starts with "Foreman:" on its first line, and the gap between them is at most 8 px

#### Scenario: Compact composer
- **WHEN** the layout is "Piece, room and chat above"
- **THEN** "You:", the "Describe what you want…" box and Send are on one row, and "Add a plan, photo, design or note" is below it

#### Scenario: Other layouts unchanged
- **WHEN** the owner switches from "Piece, room and chat above" to "Chat and piece"
- **THEN** the owner's messages are on the right again with "You" above them, and the half-typed message in the composer is kept

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

"Uploaded models" SHALL be the Model Library's first view and its address (`/studio/models`), and "Prices" the Pricing tab's (`/studio/pricing`). "Upload model" SHALL open the upload dialog of the Model Library requirement over Uploaded models, and SHALL be highlighted while that dialog is open. In the Workspace sub-menu, "New conversation" SHALL start a conversation and open it, and a conversation's entry SHALL open it at `/studio/workspace/<thread-id>`, highlighted while it is open. On a screen 768 CSS px wide or wider the sub-menu SHALL be a column between the rail and the content. Narrower, it SHALL be one row across the top of the content, below the page title, that scrolls sideways when the names do not fit, and the rail SHALL stay at the left edge as it is.

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

### Requirement: Tools and Project open from a rail
In the Workspace, the chat pane SHALL show one header row with, from the left, the conversation's title, its rename button, its delete action ("Delete <title>") directly to the right of the title, and at the right end a row of panel icons followed by the "Layout" button: "Tools", "Decisions so far", "Brief", "Project", "Piece" and "Room", each with an accessible name and a tooltip naming it. While the Design Studio rail shows its labels, each icon SHALL show its label beside it. Choosing an icon SHALL open its panel as a flyout over the chat pane. Choosing it again, choosing another icon, pressing Escape or closing the flyout SHALL close it or switch to the other panel. The messages SHALL NOT reflow when a flyout opens. The header row SHALL stay visible while the messages scroll. Asking to delete SHALL show the confirmation on its own line below the header row. The Project flyout SHALL carry the project panel unchanged, including its refresh while a build or render is queued or running.

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

#### Scenario: Delete beside the title
- **WHEN** the owner opens the conversation "Murphy bed" in the Workspace
- **THEN** "Delete Murphy bed" is on the header row directly right of the title and its rename button, and no separate line holds it

## REMOVED Requirements

### Requirement: Conversations are not listed in the Studio navigation
**Reason**: The owner made the Workspace the home page (2026-10-16): sign-in no longer lands on Pieces, and the header no longer has a "Design Studio" entry for the old scenario to look for.
**Migration**: See "The Workspace is the home page". The redirects from `/conversations` and `/conversations/<thread-id>` and the Pieces tab's conversation links are unchanged.

## ADDED Requirements

### Requirement: The Workspace is the home page
After sign-in the owner SHALL land on the Workspace tab, which opens the newest conversation. `/`, `/studio`, any address the Studio does not know, and a developer address opened without the developer gate SHALL open the Workspace for a signed-in owner. The header's "Home Renovation" name SHALL be a link to the Workspace. The header navigation SHALL NOT include a Conversations item; conversations SHALL be listed in the Workspace tab's sub-menu. `/conversations` SHALL open the Workspace, and `/conversations/<thread-id>` SHALL open `/studio/workspace/<thread-id>`, keeping its `?inspect=` and `?room=` values. The Pieces tab's conversation links SHALL open `/studio/workspace/<thread-id>`.

#### Scenario: Sign-in lands on the Workspace
- **WHEN** the owner signs in successfully and conversations exist
- **THEN** the Design Studio opens with the Workspace tab chosen and the newest conversation open

#### Scenario: Home address
- **WHEN** the signed-in owner opens `/` or `/studio`
- **THEN** the Workspace tab opens

#### Scenario: Name in the header
- **WHEN** the owner is on the Help page and clicks "Home Renovation" in the header
- **THEN** the Workspace tab opens

#### Scenario: Nav without Conversations
- **WHEN** the owner is signed in and looks at the Studio navigation
- **THEN** there is no Conversations item and no "Design Studio" item

#### Scenario: Deep link still works
- **WHEN** the owner opens `/conversations/<thread-id>?inspect=hall-bench/2` for an existing conversation
- **THEN** the address becomes `/studio/workspace/<thread-id>?inspect=hall-bench/2`, and that conversation opens with version 2 in the piece pane

### Requirement: The header offers sign-out
While the owner is signed in, the header SHALL show a "Sign out" button at its right end. Pressing it SHALL end the session (the sign-out of the owner-auth capability) and show the sign-in page, with no header. If the sign-out request fails, the owner SHALL stay signed in and the reason SHALL be shown in words beside the button.

#### Scenario: Sign out
- **WHEN** the signed-in owner presses "Sign out"
- **THEN** the session is ended, the sign-in page is shown, and opening `/studio/workspace` afterwards shows the sign-in page

#### Scenario: Sign-out fails
- **WHEN** the owner presses "Sign out" and the service cannot be reached
- **THEN** the owner stays on the page, still signed in, and the reason is shown beside the button
