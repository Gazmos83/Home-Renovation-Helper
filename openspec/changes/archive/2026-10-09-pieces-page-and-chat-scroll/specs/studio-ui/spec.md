## ADDED Requirements

### Requirement: The Pieces page lists a piece's versions in a dropdown
The Pieces page SHALL show a piece's versions in one dropdown, not as a row of buttons, newest first. Each entry SHALL read "Version N", followed by the version's state when it has one:
- "(approved)" for the approved version;
- "(failed)" for a version whose build failed;
- "(building)" for a version whose build is queued or running.

A built version that is not approved SHALL show no state. The page SHALL open each piece on its newest version. Choosing an entry SHALL show that version's approval, Inspect button, downloads, pricing, delete control and renders, without a reload. After the version shown is deleted, the dropdown SHALL show the newest version left.

#### Scenario: Entries with their state
- **WHEN** `listening-wall` has versions 11 to 14, version 14 is approved, version 12 failed and version 13 is built
- **THEN** the dropdown lists "Version 14 (approved)", "Version 13", "Version 12 (failed)" and "Version 11", in that order

#### Scenario: Opens on the newest
- **WHEN** the owner opens the Pieces page and `listening-wall`'s newest version is 14
- **THEN** the dropdown shows "Version 14" and the card shows version 14

#### Scenario: Choose another version
- **WHEN** the owner chooses "Version 11" in the dropdown
- **THEN** the card shows version 11's approval, downloads and renders without a reload

#### Scenario: Building
- **WHEN** version 15 of `listening-wall` is still building
- **THEN** its entry reads "Version 15 (building)"

### Requirement: Each piece card shows a picture of the piece
At the top of each piece card, the Pieces page SHALL show the build screenshot of one version:
- the approved version, when it has a screenshot;
- otherwise the newest version that has a screenshot.

A caption under the picture SHALL name the version, followed by "(approved)" when it is the approved one, e.g. "Version 14 (approved)". The picture SHALL NOT follow the dropdown. It SHALL be the build screenshot only, never a render. A piece with no screenshot in any version SHALL show no picture and no error. After an approval changes or a version is deleted, the picture SHALL show the version these rules now choose, without a reload.

#### Scenario: Approved version shown
- **WHEN** `listening-wall` has versions 1 to 14, all built, and version 9 is approved
- **THEN** the card shows version 9's screenshot captioned "Version 9 (approved)", whichever version the dropdown shows

#### Scenario: None approved
- **WHEN** no version of `murphy-bed` is approved and versions 1 to 4 are built
- **THEN** the card shows version 4's screenshot captioned "Version 4"

#### Scenario: Newest has not built
- **WHEN** no version of `murphy-bed` is approved, version 5 failed and version 4 is built
- **THEN** the card shows version 4's screenshot captioned "Version 4"

#### Scenario: No screenshot at all
- **WHEN** `hall-bench` has only version 1 and it is still building
- **THEN** the card shows no picture and no error

#### Scenario: Render not used
- **WHEN** the approved version has a rendered still and a build screenshot
- **THEN** the card shows the build screenshot

### Requirement: The conversation's messages scroll in their own box and open at the last message
The conversation view SHALL show the messages in a box that takes the window height left under the header and the title, with its own scroll bar. The composer, a pending confirmation card or a question form SHALL stay visible below the box without scrolling the page. When the inspector is open beside the chat, the same SHALL hold for the chat column.

Opening a conversation SHALL show the last message, scrolled to the bottom of the box. When a message, a reply, a notice or the waiting bubble is added:
- the box SHALL scroll to the bottom when the owner was already at the bottom;
- the box SHALL stay where it is when the owner had scrolled up.

Sending a message, or answering a confirmation or question form, SHALL always scroll the box to the bottom. An empty conversation SHALL show its "Nothing said yet" line in the box.

#### Scenario: Opens at the last message
- **WHEN** the owner opens a conversation with 60 messages
- **THEN** the last message is visible at the bottom of the box, the box has a scroll bar, and the composer is visible below it

#### Scenario: Follows while at the bottom
- **WHEN** the owner is at the bottom of the box and a reply arrives
- **THEN** the box scrolls so the reply is visible

#### Scenario: Stays while reading older messages
- **WHEN** the owner has scrolled up to read an older message and a build notice arrives
- **THEN** the box stays at the message the owner is reading

#### Scenario: Sending jumps to the bottom
- **WHEN** the owner has scrolled up and sends a message
- **THEN** the box scrolls to the bottom and shows the message and the waiting bubble

## MODIFIED Requirements

### Requirement: Designs are imported and exported from the Studio
The conversation view SHALL let the owner attach a design file (`.json`) as well as images. An attached design SHALL be shown by its file name, not as a thumbnail. A refusal of the file SHALL be shown in plain words.

The Pieces page SHALL offer:
- a download of the import template, with one line saying to give it to another AI chat and attach the returned file in a conversation;
- for each version, a design download;
- for a built version, a bundle download.

The version downloads SHALL stand on a line of their own, reading "Downloads:" followed by "Design (JSON)" and, for a built version, "Bundle (ZIP)". That line SHALL NOT hold the Inspect button or any other action.

Neither view SHALL show a model name, prompt, token count or cost. The import and export flow SHALL pass a recorded browser check before it counts as done.

#### Scenario: Design attached
- **WHEN** the owner picks `wall-unit.json` in a conversation
- **THEN** a chip named `wall-unit.json` is shown and is sent with the next message

#### Scenario: Downloads on the Pieces page
- **WHEN** the owner opens a piece whose version 2 is built and version 3 is building
- **THEN** version 2 offers the design and the bundle downloads, and version 3 offers only the design

#### Scenario: Downloads on their own line
- **WHEN** the owner shows a built version 2 on the Pieces page
- **THEN** a line reads "Downloads: Design (JSON) · Bundle (ZIP)", and "Inspect version 2" is not on that line

#### Scenario: Template offered
- **WHEN** the owner opens the Pieces page
- **THEN** a link downloads the import template, with the line on how to use it

### Requirement: The inspector is reachable from the Pieces page and the conversation
The Pieces page SHALL offer an "Inspect version N" button for the version shown once it is built, opening the inspector page for that version. It SHALL be a framed button with rounded corners in the Studio's button style, not a text link, and SHALL stand with the approval control, apart from the downloads. A conversation's project panel SHALL offer an "Inspect version N" button for the bound piece's latest version once it is built, in the same style. It SHALL open the inspector for that version in the conversation's split view. A render notice's Review button SHALL open the same split view.

#### Scenario: Inspect from the Pieces page
- **WHEN** the owner opens a piece whose version 2 is built and version 3 is building
- **THEN** version 2 offers an "Inspect version 2" button and version 3 does not

#### Scenario: Inspect button opens the inspector
- **WHEN** the owner presses "Inspect version 2" on the Pieces page
- **THEN** the inspector page for version 2 is shown

#### Scenario: Inspect from the conversation
- **WHEN** the bound piece's version 1 has just been built
- **THEN** the panel shows an "Inspect version 1" button, and pressing it shows the inspector for version 1 beside the chat

### Requirement: A version is deleted from the Pieces page and the Project panel after "Are you sure?"
The Pieces page SHALL offer "Delete version N" for the version shown. The Project panel SHALL offer "Delete version N" for the latest version. Neither SHALL offer it for an approved version.

Pressing it SHALL NOT delete anything yet. It SHALL show, in place, "Are you sure? Version N and its renders, reviews and pricings will be deleted. This cannot be undone." with "Yes, delete version N" and "Cancel" buttons. When N is the piece's only version, the question SHALL say that the whole piece will be deleted.

Only "Yes" SHALL send the delete. Afterwards:
- the Pieces page SHALL show the piece's remaining versions, or drop the piece when it has none left;
- the Project panel SHALL refresh;
- an inspector showing the deleted version SHALL close.

A refusal SHALL be shown with its reason next to the control. The Project panel SHALL show "N of 15 versions" once the piece holds 13 or more.

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
- **THEN** the Project panel shows "14 of 15 versions"
