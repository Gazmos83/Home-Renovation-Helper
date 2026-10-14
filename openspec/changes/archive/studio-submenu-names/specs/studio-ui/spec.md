## MODIFIED Requirements

### Requirement: Pieces, measured rooms and the model library are tabs of one Design Studio page
The Studio SHALL have a Design Studio page for the owner at `/studio` with the page title "Design Studio" and three tabs, in this order: "Pieces", "Measured Rooms" and "Model Library". Each tab SHALL have its own address — `/studio/pieces`, `/studio/rooms`, `/studio/models` — and opening that address SHALL show the page with that tab chosen. `/studio`, and a `/studio/` address naming no known tab, SHALL show the Pieces tab. The tabs SHALL be a rail at the screen's left edge below the header, with the same font, icon style, colour scheme and "Hide labels" switch as the conversation page's panel rail: each tab an icon, with its label beside it while labels are shown, the chosen tab highlighted, and the switch at the rail's foot. The label choice SHALL be remembered in the browser and shared with the other rails; a browser that cannot store it SHALL show the labels hidden. The tabs SHALL be exposed as a vertical tab list with the chosen tab marked selected, and only the chosen tab's content SHALL be shown.

**Sub-menu.** Beside the rail, the chosen tab SHALL show a sub-menu, each entry with its label always shown:
- Pieces: the name (id) of every piece, in the order of the Pieces grid;
- Measured Rooms: the name of every measured room, then the name of every composition that has a tile of its own (an apartment composition, or a room composition whose room is not in the house file), in the order of the Measured Rooms grid;
- Model Library: "Uploaded models" and "Upload model".

There SHALL be no "All pieces" or "All rooms" entry. With no dialog open, each tab's address (`/studio/pieces`, `/studio/rooms`) SHALL show its tile grid, and no Pieces or Measured Rooms entry SHALL be highlighted. Choosing a piece's, room's or composition's name SHALL open that item's dialog over the grid, at the same address and with the same behaviour as choosing its tile, keeping `?page`. Closing the dialog SHALL return to the grid as it does for a tile. While an item's dialog is open, its name SHALL be highlighted and marked as the current entry. A list with no item SHALL say "No pieces yet" or "No rooms yet" in the sub-menu. A name too long for the column SHALL be cut short with an ellipsis, and its full name SHALL be shown on hover. A sub-menu longer than the screen SHALL scroll on its own, with the page and the rail staying in place. The names SHALL follow the lists without a reload: a piece or room that is created or deleted SHALL appear in or disappear from the sub-menu as its tile does.

"Uploaded models" SHALL be the Model Library's first view and its address (`/studio/models`). "Upload model" SHALL open the upload dialog of the Model Library requirement over Uploaded models, and SHALL be highlighted while that dialog is open. On a screen 768 CSS px wide or wider the sub-menu SHALL be a column between the rail and the content. Narrower, it SHALL be one row across the top of the content, below the page title, that scrolls sideways when the names do not fit, and the rail SHALL stay at the left edge as it is.

Each tab SHALL show what its page showed: wherever another requirement names the Pieces page, the Measured Rooms page (or the Rooms page) or the Model Library page, it SHALL mean that tab, and where it gives that page a heading row with its page title, the page title is "Design Studio" and the tab keeps the rest of its heading row. The old addresses `/pieces`, `/rooms` and `/models` SHALL open the matching tab; a piece version's inspector SHALL keep its address `/pieces/<id>/versions/<n>`. The Studio navigation SHALL show one "Design Studio" entry, first, marked current on every tab, and SHALL NOT show "Pieces", "Measured Rooms" or "Model Library" entries. The routes SHALL require sign-in, and a signed-out visit SHALL go to the sign-in page. The page SHALL NOT show model names, prompts, token counts or costs of model calls. The page SHALL pass a recorded browser check, at 1280 × 800 and at 360 × 780, before it counts as done.

#### Scenario: Pieces first
- **WHEN** the owner chooses "Design Studio" in the navigation
- **THEN** the Design Studio page opens with the Pieces tab chosen, the piece tiles shown, and the pieces listed by name in the sub-menu with none highlighted

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
