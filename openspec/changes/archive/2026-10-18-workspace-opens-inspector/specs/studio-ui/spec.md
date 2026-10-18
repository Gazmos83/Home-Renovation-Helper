## MODIFIED Requirements

### Requirement: Tools and Project open from a rail
In the Workspace, the chat pane SHALL show one header row with, from the left, the conversation's title, its rename button, its delete action ("Delete <title>") directly to the right of the title, and at the right end a row of panel icons followed by the "Layout" button: "Tools", "Decisions so far", "Brief", "Project", "Piece" and "Room", each with an accessible name and a tooltip naming it. While the Design Studio rail shows its labels, each icon SHALL show its label beside it. Choosing the Tools, Decisions so far, Brief or Project icon SHALL open its panel as a flyout over the chat pane. Choosing it again, choosing another flyout icon, pressing Escape or closing the flyout SHALL close it or switch to the other panel. The Piece and Room icons SHALL NOT open a flyout: choosing one SHALL close any open flyout and show the Workspace's piece pane or room pane, as the requirement "The Workspace's Piece and Room icons open their panes" sets out. The messages SHALL NOT reflow when a flyout opens. The header row SHALL stay visible while the messages scroll. Asking to delete SHALL show the confirmation on its own line below the header row. The Project flyout SHALL show the progress steps, the next step and the open review items, and SHALL refresh while a build or render is queued or running.

#### Scenario: Open and close
- **WHEN** the owner clicks the Project icon in the chat pane header and then presses Escape
- **THEN** the project panel opens over the chat and then closes, and the messages were not reflowed

#### Scenario: Switch
- **WHEN** the Tools flyout is open and the owner clicks the Project icon
- **THEN** the Tools flyout closes and the project panel opens

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

### Requirement: The Workspace's piece and room panes approve the version they show
The Workspace's piece pane SHALL show, for the piece version it shows, whether that version is approved, and the room pane SHALL do the same for the composition version it shows. The approval control SHALL sit at the top of the pane, above the 3D view. Each pane SHALL offer "Approve version N" when the shown version's build succeeded and it is not approved, and "Unapprove version N" when the shown version is the approved one. Neither control SHALL be offered for a version that is not built. Approving the shown version SHALL replace any other approved version of the same piece or composition. An API refusal SHALL be shown next to the control in the service's plain words, never as a status code or an internal code, and the version's state SHALL stay as it was. After a change, the pane, its version dropdown, the Pieces page and the Measured Rooms page SHALL show the new state without a reload.

While the room's latest composition version is queued or running, the conversation's progress SHALL be read again every few seconds, as it is for a piece build. Once that version's build succeeds, the room pane SHALL offer "Approve version N" without a reload.

**Piece pane.** Besides approval, the piece pane SHALL show:
- the piece's build state;
- "N of 15 versions" once the piece holds 13 or more;
- "Delete version N" for the shown version when it is neither approved nor queued or building, with the "Are you sure?" flow of "A version is deleted from the Pieces page and the Project panel after 'Are you sure?'";
- the shown version's restyle looks with "Keep this look", which sends the owner's request to the conversation;
- the piece's open generator-extension requests.

**Room pane.** Besides approval, the room pane SHALL show:
- "Delete version N" for the shown composition version when it is not approved, with the "Are you sure?" flow of "A composition version is deleted from the Rooms page and the Project panel after 'Are you sure?'";
- the shown version's restyle looks.

Wherever another requirement gives the Project panel, or the Piece or Room flyout, a piece's or room's approval, delete, looks, version-limit notice, picture or "Inspect" control, it SHALL mean these panes. Neither pane SHALL show a model name, prompt, token count or cost. Approving, unapproving or deleting SHALL NOT start a turn. The flow SHALL pass a recorded browser check before it counts as done.

#### Scenario: Approve the shown piece version
- **WHEN** the piece pane shows `hall-bench` version 2, which is built and not approved, and the owner presses "Approve version 2"
- **THEN** the pane shows version 2 as approved and the version dropdown labels version 2 "approved"

#### Scenario: Approve an older piece version from the dropdown
- **WHEN** `hall-bench` version 3 is approved, the owner chooses version 2 in the piece pane's dropdown and presses "Approve version 2"
- **THEN** version 2 is approved and version 3 is no longer approved

#### Scenario: Unapprove the shown piece version
- **WHEN** the piece pane shows approved `hall-bench` version 2 and the owner presses "Unapprove version 2"
- **THEN** the pane shows that version 2 is not approved and offers "Approve version 2"

#### Scenario: Unbuilt version offers no control
- **WHEN** the piece pane shows `hall-bench` version 4 while it is still building
- **THEN** the pane offers neither "Approve version 4" nor "Unapprove version 4", and no "Delete version 4"

#### Scenario: Approve the shown room version
- **WHEN** the room pane shows `Hall` version 2, which is built and not approved, and the owner presses "Approve version 2"
- **THEN** the pane shows version 2 as approved and its dropdown labels version 2 "(approved)"

#### Scenario: Room approval refused
- **WHEN** the owner approves `Hall` version 2 from the room pane while it places a piece version that is not approved
- **THEN** the service's reason naming that piece is shown next to the control, with no status code, and version 2 stays unapproved

#### Scenario: Approval does not start a turn
- **WHEN** the owner approves a version from either pane
- **THEN** no message is sent to the conversation and the composer stays usable

#### Scenario: Fresh room version becomes approvable
- **WHEN** the Designer composes `Wohnen` version 3 in the conversation while the room pane shows `Wohnen`, and its build succeeds
- **THEN** the room pane shows version 3 and offers "Approve version 3" without a reload

#### Scenario: Delete from the piece pane
- **WHEN** the piece pane shows unapproved, built `hall-bench` version 3 and the owner presses "Delete version 3", then "Yes, delete version 3"
- **THEN** version 3 is deleted and the pane shows the piece's latest remaining version

#### Scenario: Keep a look from the piece pane
- **WHEN** the piece pane shows `hall-bench` version 2 with a restyle look "Oak" and the owner presses "Keep this look"
- **THEN** the conversation receives the owner's request to keep that look, as the flyout sent it before

#### Scenario: Near the limit
- **WHEN** the conversation's piece holds 14 versions
- **THEN** the piece pane shows "14 of 15 versions"

## ADDED Requirements

### Requirement: The Workspace's Piece and Room icons open their panes
In the Workspace's chat pane header, choosing the Piece icon SHALL show the piece pane at the bound piece's latest version, as "Inspect version N" does: the address SHALL name that version, and the layout SHALL switch to "Chat and piece" when the current layout has no piece pane. Choosing the Room icon SHALL show the room pane at the conversation's room, at its composition's latest version, as "Inspect <room>" does: the address SHALL name the room, and the layout SHALL switch to "Chat and room" when the current layout has no room pane. On a screen narrower than the Workspace's wide layout, each icon SHALL choose its pane's tab. In "Piece, room and chat above", choosing one icon SHALL NOT close the other pane.

When the conversation has no piece yet, the Piece icon SHALL show the piece pane, which says in plain words that no piece has been designed yet. When it has no confirmed room, the Room icon SHALL show the room pane, which says that no room is confirmed yet. When the room has no 3D view, the pane SHALL say so as it does today. Choosing an icon SHALL NOT start a turn, and the composer SHALL stay usable.

#### Scenario: Piece icon opens the inspector
- **WHEN** the layout is "Chat and room", the conversation's piece is `hall-bench` at version 3, and the owner clicks the Piece icon
- **THEN** the layout switches to "Chat and piece", the inspector shows `hall-bench` version 3 with its approval control above the 3D view, and no flyout is open

#### Scenario: Room icon opens the room view
- **WHEN** the layout is "Chat and piece", the conversation has confirmed `Hall` whose composition has a 3D model, and the owner clicks the Room icon
- **THEN** the layout switches to "Chat and room" and the room pane shows `Hall` at its latest version with its approval control, and no flyout is open

#### Scenario: No piece yet
- **WHEN** the conversation has no piece and the owner clicks the Piece icon
- **THEN** the piece pane is shown and says that no piece has been designed yet

#### Scenario: No room confirmed
- **WHEN** the conversation has confirmed no room and the owner clicks the Room icon
- **THEN** the room pane is shown and says that no room is confirmed yet

#### Scenario: Phone
- **WHEN** the screen is 360 px wide and the owner clicks the Room icon
- **THEN** the Room tab is chosen and the room pane is shown

## REMOVED Requirements

### Requirement: Opening an inspector from the Project flyout closes the flyout
**Reason**: The Project flyout no longer holds an "Inspect" control, and the Piece and Room icons open their panes directly, so no flyout has to close when an inspector opens.
**Migration**: Use the Piece or Room icon, a build notice's "Inspect version N", or the version dropdown in the pane.
