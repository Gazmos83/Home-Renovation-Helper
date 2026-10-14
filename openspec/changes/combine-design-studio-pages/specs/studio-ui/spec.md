## ADDED Requirements

### Requirement: Pieces, measured rooms and the model library are tabs of one Design Studio page
The Studio SHALL have a Design Studio page for the owner at `/studio` with the page title "Design Studio" and three tabs, in this order: "Pieces", "Measured Rooms" and "Model Library". Each tab SHALL have its own address — `/studio/pieces`, `/studio/rooms`, `/studio/models` — and opening that address SHALL show the page with that tab chosen. `/studio`, and a `/studio/` address naming no known tab, SHALL show the Pieces tab. The tabs SHALL be a rail at the screen's left edge below the header, with the same font, icon style, colour scheme and "Hide labels" switch as the conversation page's panel rail: each tab an icon, with its label beside it while labels are shown, the chosen tab highlighted, and the switch at the rail's foot. The label choice SHALL be remembered in the browser and shared with the other rails; a browser that cannot store it SHALL show the labels hidden. The tabs SHALL be exposed as a vertical tab list with the chosen tab marked selected, and only the chosen tab's content SHALL be shown.

Each tab SHALL show what its page showed: wherever another requirement names the Pieces page, the Measured Rooms page (or the Rooms page) or the Model Library page, it SHALL mean that tab, and where it gives that page a heading row with its page title, the page title is "Design Studio" and the tab keeps the rest of its heading row. The old addresses `/pieces`, `/rooms` and `/models` SHALL open the matching tab; a piece version's inspector SHALL keep its address `/pieces/<id>/versions/<n>`. The Studio navigation SHALL show one "Design Studio" entry, first, marked current on every tab, and SHALL NOT show "Pieces", "Measured Rooms" or "Model Library" entries. The routes SHALL require sign-in, and a signed-out visit SHALL go to the sign-in page. The page SHALL NOT show model names, prompts, token counts or costs of model calls. The page SHALL pass a recorded browser check before it counts as done.

#### Scenario: Pieces first
- **WHEN** the owner chooses "Design Studio" in the navigation
- **THEN** the Design Studio page opens with the Pieces tab chosen and the pieces shown

#### Scenario: Labels shown and hidden
- **WHEN** the owner chooses "Show labels" on the Design Studio rail
- **THEN** each tab shows its label beside its icon, and the Pricing Overview and conversation rails show their labels too until the owner hides them

#### Scenario: Tab chosen
- **WHEN** the owner chooses the Model Library tab
- **THEN** the address is `/studio/models`, the models and the upload form are shown, and the pieces and measured rooms are not

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

## MODIFIED Requirements

### Requirement: Conversations are not listed in the Studio navigation
The Studio navigation SHALL NOT include a Conversations item. Routes `/conversations` and `/conversations/:threadId` SHALL remain reachable by deep link and from the Pieces tab's conversation links. After sign-in the owner SHALL land on the Design Studio page's Pieces tab.

#### Scenario: Nav without Conversations
- **WHEN** the owner is signed in and looks at the Studio navigation
- **THEN** there is no Conversations item, and Design Studio is present

#### Scenario: Sign-in lands on Pieces
- **WHEN** the owner signs in successfully
- **THEN** the Studio opens on the Design Studio page with the Pieces tab chosen

#### Scenario: Deep link still works
- **WHEN** the owner opens `/conversations/<thread-id>` for an existing conversation
- **THEN** that conversation view opens

## REMOVED Requirements

### Requirement: The Studio navigation offers Measured Rooms and Model Library
**Reason**: The owner asked (2026-10-14) for Pieces, Measured Rooms and Model Library as tabs of one Design Studio page with one navigation entry.
**Migration**: See "Pieces, measured rooms and the model library are tabs of one Design Studio page". `/rooms` and `/models` redirect to their tab. No API changes.
