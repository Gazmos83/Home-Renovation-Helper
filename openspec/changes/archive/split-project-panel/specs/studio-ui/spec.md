## MODIFIED Requirements

### Requirement: Tools and Project open from a rail
The conversation view SHALL show a narrow rail with a Tools icon, a Decisions icon, a Brief icon, a Project icon, a Piece icon and a Room icon, each with an accessible name. The rail SHALL sit at the left edge of the screen, below the header, outside the centred page, and SHALL stay visible while the page scrolls. The rail SHALL have an expand control: expanded, each icon is shown with its label ("Tools", "Decisions so far", "Brief", "Project", "Piece", "Room"); collapsed, only the icons are shown. The control SHALL say which it does and whether the rail is expanded. Choosing an icon SHALL open its panel as a flyout beside the rail, over the chat; choosing it again, choosing another, pressing Escape or closing the flyout SHALL close or switch it. The chat SHALL use the full width beside the rail when no flyout is open.

The Brief flyout SHALL list the conversation's brief settings (room, purpose, highest the piece may be, style, budget), each editable, with a Save button; saving SHALL show the saved values, and a refusal SHALL be shown with its reason next to the form. It SHALL NOT show a model name, prompt, token count or cost. The Project flyout SHALL show the progress steps, the next step and the open review items. The Piece flyout SHALL show the bound piece's name, id and build state, its approval controls, its version count and delete control, its latest picture, "Inspect version N", its looks, and its open generator-extension requests; with no piece it SHALL say "No piece yet." The Room flyout SHALL show the conversation's selected room as the project panel showed it (approval, delete version, looks, inspect); with no room it SHALL say "No room selected yet." Each flyout SHALL refresh while a build or render is queued or running and after every turn.

#### Scenario: Open and close
- **WHEN** the owner clicks the Project icon and then presses Escape
- **THEN** the project panel opens over the chat and then closes, and the messages were not reflowed

#### Scenario: Switch
- **WHEN** the Tools flyout is open and the owner clicks the Piece icon
- **THEN** the Tools flyout closes and the Piece panel opens

#### Scenario: Piece and room apart
- **WHEN** the owner opens the Piece panel in a conversation with a piece and a selected room
- **THEN** it shows the piece's approval and "Inspect version N" and does not show the room's approval or "Inspect <room>"; the Room panel shows the reverse

#### Scenario: Edit the brief
- **WHEN** the owner opens the Brief panel, changes the budget to 900 and presses Save
- **THEN** the panel shows budget 900, and the conversation's and the bound piece's briefs hold 900

#### Scenario: Invalid brief
- **WHEN** the owner clears the purpose and presses Save
- **THEN** nothing is saved and the panel says the purpose is required

#### Scenario: Progress in Project
- **WHEN** the owner opens the Project panel
- **THEN** it shows the progress steps and the next step, and not the piece's approval or the room's controls

#### Scenario: Scrolled conversation
- **WHEN** the owner scrolls a long conversation to its end
- **THEN** the rail is still shown at the left edge of the screen and its icons still open their panels

#### Scenario: Expanded
- **WHEN** the owner presses the expand control
- **THEN** the rail shows "Tools", "Decisions so far", "Brief", "Project", "Piece" and "Room" beside their icons; pressing it again shows the icons only

### Requirement: Approval is shown and set from the Studio
The Studio SHALL show, on the Pieces page for each version and in a conversation's Piece panel for the bound piece, whether a version is approved, and SHALL let the owner approve a built version and unapprove an approved one there. The control SHALL be offered only for a version whose build succeeded; an API refusal SHALL be shown next to the version it names. After a change the page and the panel SHALL show the new state without a reload. Neither SHALL show a model name, prompt, token count or cost. The approve and unapprove flow SHALL pass a recorded browser check before it counts as done.

#### Scenario: Approve from the Pieces page
- **WHEN** the owner opens `listening-wall` on the Pieces page and approves version 4
- **THEN** version 4 shows "Approved" and a reload shows the same

#### Scenario: Approval in the project panel
- **WHEN** the conversation is bound to `listening-wall`, version 4 is approved and version 5 is the latest
- **THEN** the Piece panel shows version 5 as latest and version 4 as approved, with a control to approve version 5 once it is built

#### Scenario: Unapprove
- **WHEN** the owner unapproves version 4 from the panel
- **THEN** the panel and the Pieces page show no approved version

### Requirement: The inspector is reachable from the Pieces page and the conversation
The Pieces page SHALL offer an "Inspect version N" button for the version shown once it is built, opening the inspector page for that version. It SHALL be a framed button with rounded corners in the Studio's button style, not a text link, and SHALL stand with the approval control, apart from the downloads. A conversation's Piece panel SHALL offer an "Inspect version N" button for the bound piece's latest version once it is built, in the same style. It SHALL open the inspector for that version in the conversation's split view. A render notice's Review button SHALL open the same split view.

#### Scenario: Inspect from the Pieces page
- **WHEN** the owner opens a piece whose version 2 is built and version 3 is building
- **THEN** version 2 offers an "Inspect version 2" button and version 3 does not

#### Scenario: Inspect button opens the inspector
- **WHEN** the owner presses "Inspect version 2" on the Pieces page
- **THEN** the inspector page for version 2 is shown

#### Scenario: Inspect from the conversation
- **WHEN** the bound piece's version 1 has just been built
- **THEN** the panel shows an "Inspect version 1" button, and pressing it shows the inspector for version 1 beside the chat

### Requirement: A render notice is shown in the conversation
The conversation view SHALL show each notice in the thread's history in its place among the messages, centred and framed like a confirmation, with its text. A finished render of a piece version SHALL show a Review button that names the render's tier: "Review <tier> v1" when the version is 1, and "Review <tier> revision <n>" for version n above 1, where the tier is `draft`, `preview` or `final`. Pressing it SHALL open the inspector for that piece version in the split view. A failed render's notice, and a notice for a shell or composition, SHALL show no button. A notice posted while the view is open SHALL appear without a reload while the Piece panel is following a render. A notice SHALL NOT show a model name, prompt, token count or cost.

#### Scenario: First draft ready
- **WHEN** the draft turntable of `hall-bench` version 1 finishes while the conversation is open
- **THEN** a notice appears without a reload, saying it is ready and can also be checked in the Piece panel, with a "Review draft v1" button

#### Scenario: Later version
- **WHEN** a notice is shown for a finished draft render of `hall-bench` version 3
- **THEN** its button reads "Review draft revision 3"

#### Scenario: Preview and final
- **WHEN** notices are shown for a finished preview of `hall-bench` version 1 and a finished final of version 4
- **THEN** their buttons read "Review preview v1" and "Review final revision 4"

#### Scenario: Failed render
- **WHEN** a preview turntable of `hall-bench` version 2 fails
- **THEN** a notice says it did not finish and shows no button

### Requirement: A version is deleted from the Pieces page and the Project panel after "Are you sure?"
The Pieces page SHALL offer "Delete version N" for the version shown. The Piece panel SHALL offer "Delete version N" for the latest version. Neither SHALL offer it for an approved version.

Pressing it SHALL NOT delete anything yet. It SHALL show, in place, "Are you sure? Version N and its renders, reviews and pricings will be deleted. This cannot be undone." with "Yes, delete version N" and "Cancel" buttons. When N is the piece's only version, the question SHALL say that the whole piece will be deleted.

Only "Yes" SHALL send the delete. Afterwards:
- the Pieces page SHALL show the piece's remaining versions, or drop the piece when it has none left;
- the Piece panel SHALL refresh;
- an inspector showing the deleted version SHALL close.

A refusal SHALL be shown with its reason next to the control. The Piece panel SHALL show "N of 15 versions" once the piece holds 13 or more.

#### Scenario: Confirmed delete on the Pieces page
- **WHEN** the owner shows `hall-bench` version 2, presses "Delete version 2", then "Yes, delete version 2"
- **THEN** version 2 is no longer in the piece's version dropdown and the page shows another version

#### Scenario: Cancelled
- **WHEN** the owner presses "Delete version 2" and then "Cancel"
- **THEN** nothing is deleted and the delete control is shown again

#### Scenario: Approved version has no delete
- **WHEN** the owner shows `hall-bench` version 4, which is approved
- **THEN** no "Delete version 4" control is shown

#### Scenario: Refusal shown
- **WHEN** the owner confirms deleting a version that a composition places
- **THEN** the refusal naming the composition is shown next to the control and the version stays listed

#### Scenario: Near the limit
- **WHEN** the conversation's piece holds 14 versions
- **THEN** the Piece panel shows "14 of 15 versions"

### Requirement: Piece titles do not carry the version
The Piece panel's header line SHALL show the piece's name, its id and its build state, without "version N". The heading of the inspector beside the chat SHALL show the piece's name, or its id when the name cannot be read, without the version. Its version buttons already show which version is open. Lines and buttons that act on one version SHALL keep its number, such as "Approve version 14", "Inspect version 14" and "Delete version 14".

#### Scenario: Project panel header
- **WHEN** the conversation's piece is `listening-wall`, named "Listening wall", at version 14
- **THEN** the panel's header reads "Listening wall" with the id `listening-wall` and contains no "version 14"

#### Scenario: Inspector heading
- **WHEN** the inspector beside the chat shows `listening-wall` version 14
- **THEN** its heading reads "Listening wall" and the version buttons mark version 14 as shown

### Requirement: A build notice is shown with an Inspect button
The conversation view SHALL show each build notice in its place among the messages, framed like a render notice. A finished build's notice SHALL show an "Inspect version N" button that opens the inspector for that piece version beside the chat. A failed build's notice, and a notice whose version was deleted, SHALL show no button. A build notice posted while the view is open SHALL appear without a reload while the Piece panel is following a build. It SHALL NOT show a model name, prompt, token count or cost.

#### Scenario: Built while open
- **WHEN** `hall-bench` version 2 finishes building while its conversation is open
- **THEN** a notice saying version 2 is built appears without a reload, with an "Inspect version 2" button

#### Scenario: Inspect from the notice
- **WHEN** the owner presses "Inspect version 2" on that notice
- **THEN** the inspector for `hall-bench` version 2 is shown beside the chat and the composer is still usable

#### Scenario: Failed build
- **WHEN** the build of `hall-bench` version 3 fails
- **THEN** its notice says it did not build and shows no button

### Requirement: Room-version approval is shown and set from the Studio
The Studio SHALL show, on the Rooms page for the chosen composition version and in a conversation's Room panel for the confirmed room's composition, whether a version is approved, and SHALL let the owner approve a built version and unapprove an approved one there. The control SHALL be offered only for a version whose build succeeded; an API refusal SHALL be shown next to the version it names. After a change the page and the panel SHALL show the new state without a reload. Neither SHALL show a model name, prompt, token count or cost. The approve and unapprove flow SHALL pass a recorded browser check before it counts as done.

#### Scenario: Approve from the Rooms page
- **WHEN** the owner opens composition `Wohnen` on the Rooms page, chooses version 2, and approves it
- **THEN** version 2 shows "Approved" and a reload shows the same

#### Scenario: Approval in the project panel
- **WHEN** the conversation's confirmed room is `Hall`, version 1 is approved and version 2 is the latest built version
- **THEN** the Room panel shows version 2 as latest and version 1 as approved, with a control to approve version 2

#### Scenario: Unapprove
- **WHEN** the owner unapproves `Wohnen` version 2 from the Rooms page
- **THEN** the page and the Room panel show no approved version of `Wohnen`

#### Scenario: Unapprove of a placed piece is explained
- **WHEN** the owner unapproves `listening-wall` v4 from the Pieces page or the Room panel while approved `Wohnen` version 2 places it
- **THEN** the refusal naming `Wohnen` version 2 is shown next to the control and v4 stays approved

### Requirement: A composition version is deleted from the Rooms page and the Project panel after "Are you sure?"
The Rooms page SHALL offer "Delete version N" for the version shown. The Room panel SHALL offer "Delete version N" for the latest composition version. Neither SHALL offer it for an approved version.

Pressing it SHALL NOT delete anything yet. It SHALL show, in place, "Are you sure? Version N and its model and renders will be deleted. This cannot be undone." with "Yes, delete version N" and "Cancel" buttons. When N is the composition's only version, the question SHALL say that the composition will be deleted and the measured room kept.

Only "Yes" SHALL send the delete. Afterwards the Rooms page SHALL show the remaining versions, or drop the composition when it has none left, and the Room panel SHALL refresh. A refusal SHALL be shown with its reason next to the control.

#### Scenario: Confirmed delete on the Rooms page
- **WHEN** the owner shows `Wohnen` version 2, presses "Delete version 2", then "Yes, delete version 2"
- **THEN** version 2 is no longer among the composition's versions and the page shows another version

#### Scenario: Cancelled
- **WHEN** the owner presses "Delete version 2" and then "Cancel"
- **THEN** nothing is deleted and the delete control is shown again

#### Scenario: Approved version has no delete
- **WHEN** the owner shows `Wohnen` version 4, which is approved
- **THEN** no "Delete version 4" control is shown

#### Scenario: Refusal shown
- **WHEN** the owner confirms deleting a composition version that is still building
- **THEN** the refusal is shown next to the control and the version stays listed

### Requirement: The Project panel opens the conversation's room in 3D beside the chat
The Room panel SHALL show a "Selected room" heading and below it the conversation's confirmed room or apartment by name. When the composition has an approved version, the panel SHALL show that version's picture (its still, else its screenshot) as the Piece panel shows a piece's latest picture, named "Approved picture of <room>, version N"; with no approved version, or an approved version with no picture, it SHALL show no picture. The approved version's picture SHALL be shown even when that version is older than the listed newest five. When its composition has a 3D model the panel SHALL offer a button to inspect it. Pressing it SHALL show the room's 3D view beside the chat in the same split screen as the piece inspector: on a wide screen the chat on one side and the room on the other, on a narrow screen the room below the chat. The view SHALL be the Rooms page's 3D view of the composition, with the same cameras, modes, surface switches and dimensions switch, the ceiling starting off. The pane SHALL offer the same version dropdown as the Rooms page (the newest five versions, the latest chosen); choosing a version SHALL show it, and a version without a 3D model SHALL be named in plain words. Opening it SHALL NOT start a turn, and the owner SHALL still be able to read, scroll and send messages. The pane SHALL show the room's name and a control to close it, after which the chat takes the width again. The open room view and its chosen version SHALL be part of the page's address, so a reload shows them again.

When the room or apartment has no composition, the panel SHALL say in plain words that it has no 3D view yet and that the Designer can compose it. When the composition's latest version has no 3D model, the panel SHALL say that composing it again adds the 3D view. When the conversation has confirmed no room or apartment, the panel SHALL show no room section. An address naming a room view that is not the conversation's current room SHALL show no room pane.

Only one side pane SHALL be shown at a time: opening the room view SHALL close an open piece inspector, and opening a piece version (from the panel or a notice) SHALL close an open room view.

The Room panel and the pane SHALL NOT show model names of language models, prompts, token counts or costs. The room section SHALL pass a recorded browser check before it counts as done.

#### Scenario: Approved room picture
- **WHEN** composition `Hall` has version 2 approved and version 3 is the latest, and the owner opens the Room panel
- **THEN** the panel shows version 2's picture named "Approved picture of Hall, version 2"

#### Scenario: No approved version
- **WHEN** no version of composition `Hall` is approved
- **THEN** the Room panel shows no picture

#### Scenario: Inspect the room
- **WHEN** the conversation has confirmed `Hall`, composition `Hall` has a 3D model, and the owner presses "Inspect Hall" in the Room panel under "Selected room"
- **THEN** the 3D view of `Hall` is shown beside the chat with its surface switches and the ceiling off, and the composer is still usable

#### Scenario: Another version beside the chat
- **WHEN** the room view of `Hall` shows version 3 and the owner chooses version 2 in its dropdown
- **THEN** version 2's model is shown, and a reload shows version 2 again

#### Scenario: Dimensions beside the chat
- **WHEN** the owner switches dimensions on in the room view of `Hall`
- **THEN** each wall of `Hall` is labelled with its length and the ceiling height is shown once

#### Scenario: No 3D view yet
- **WHEN** the conversation has confirmed `Hall` and `Hall` has no composition
- **THEN** the Room panel says `Hall` has no 3D view yet and that the Designer can compose the room, and offers no inspect button

#### Scenario: No room confirmed
- **WHEN** the conversation has confirmed no room or apartment
- **THEN** the Room panel shows no room section

#### Scenario: Close the room view
- **WHEN** the owner closes the room pane
- **THEN** the chat takes the full width beside the rail again

#### Scenario: Reload
- **WHEN** the owner reloads the conversation while the room view of `Hall` is shown
- **THEN** the conversation and the room view of `Hall` are shown again

#### Scenario: One pane at a time
- **WHEN** the room view of `Hall` is shown and the owner presses "Inspect version 2" in the Piece panel
- **THEN** the piece inspector for version 2 is shown beside the chat and the room view is closed; pressing "Inspect Hall" then shows the room and closes the inspector

### Requirement: The conversation view shows the project's progress
The conversation view SHALL show a Project panel with the progress steps (brief confirmed, piece created, built, draft or preview rendered, reviewed with open items, detail pass, final) each marked done or not, the next step the owner can ask for, and the number of open review items. The bound piece's name, latest version and build state, its latest still when one exists and otherwise the screenshot, and its open generator-extension requests SHALL be shown in the Piece panel. Neither panel SHALL offer a link to a turntable viewer. Both panels SHALL refresh while a build is queued or running, while a render of the latest version is queued or running, and after every turn. Each SHALL show nothing when the service's progress read is refused other than the refusal's reason.

#### Scenario: After the first build
- **WHEN** the Builder's build of version 1 finishes while the view is open
- **THEN** the Piece panel shows version 1 built with its screenshot, and the Project panel shows "built" done and the next step as a draft render, without a reload

#### Scenario: Open review items
- **WHEN** the latest review of the piece has two open items
- **THEN** the Project panel shows "reviewed, 2 open" and links to the piece's page

#### Scenario: Turntable finished
- **WHEN** the draft turntable of version 1 finishes while the view is open
- **THEN** the Piece panel shows the still and the Project panel "draft" rendered, without a reload, and shows no "Open the turntable viewer" link
