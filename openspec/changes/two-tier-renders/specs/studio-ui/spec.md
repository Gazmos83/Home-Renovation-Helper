## MODIFIED Requirements

### Requirement: The conversation view shows the project's progress
The conversation view SHALL show a project panel with the bound piece, its latest version and build state, the progress steps (brief confirmed, piece created, built, draft rendered, reviewed with open items, detail pass, final) each marked done or not, the next step the owner can ask for, the latest still when one exists and otherwise the screenshot, and the piece's open generator-extension requests. The panel SHALL NOT offer a link to a turntable viewer. The panel SHALL refresh while a build is queued or running, while a render of the latest version is queued or running, and after every turn. It SHALL show nothing when the service's progress read is refused other than the refusal's reason.

#### Scenario: After the first build
- **WHEN** the Builder's build of version 1 finishes while the view is open
- **THEN** the panel shows version 1 built with its screenshot, "built" done, and the next step as a draft render, without a reload

#### Scenario: Open review items
- **WHEN** the latest review of the piece has two open items
- **THEN** the panel shows "reviewed, 2 open" and links to the piece's page

#### Scenario: Turntable finished
- **WHEN** the draft turntable of version 1 finishes while the view is open
- **THEN** the panel shows the still and "draft" rendered without a reload, and shows no "Open the turntable viewer" link

### Requirement: A render notice is shown in the conversation
The conversation view SHALL show each notice in the thread's history in its place among the messages, centred and framed like a confirmation, with its text. A finished render of a piece version SHALL show a Review button that names the render's tier: "Review <tier> v1" when the version is 1, and "Review <tier> revision <n>" for version n above 1, where the tier is `draft` or `final`. Pressing it SHALL open the inspector for that piece version in the split view, on its Renders tab, with the most recently finished render of that tier selected. A failed render's notice, and a notice for a shell or composition, SHALL show no button. A notice posted while the view is open SHALL appear without a reload while the project panel is following a render. A notice SHALL NOT show a model name, prompt, token count or cost.

#### Scenario: First draft ready
- **WHEN** the draft turntable of `hall-bench` version 1 finishes while the conversation is open
- **THEN** a notice appears without a reload, saying it is ready and can also be checked in the Project panel, with a "Review draft v1" button

#### Scenario: Review opens the render
- **WHEN** the owner presses "Review final revision 4" after a final detail turntable of version 4 finished
- **THEN** the inspector for version 4 opens beside the chat on its Renders tab with the detailed turntable selected and playable

#### Scenario: Later version
- **WHEN** a notice is shown for a finished draft render of `hall-bench` version 3
- **THEN** its button reads "Review draft revision 3"

#### Scenario: Preview and final
- **WHEN** notices are shown for a finished final of `hall-bench` version 4 and for a version-1 render recorded at the removed tier `preview`
- **THEN** their buttons read "Review final revision 4" and "Review draft v1"

#### Scenario: Failed render
- **WHEN** a draft turntable of `hall-bench` version 2 fails
- **THEN** a notice says it did not finish and shows no button

### Requirement: The Pieces page shows renders and takes feedback
The Studio SHALL show the owner a Pieces page that lists the pieces, then each piece's versions, then each version's published stills (the version's own, in the room, and detailed), showing for each:
- its kind and tier;
- its picture;
- its current rating and comment, with controls to rate up, rate down, edit the comment and clear.

Turntables and restyle variants SHALL NOT be listed on the Pieces page; they are viewed and rated on the inspector's Renders tab, which the version's "Inspect version N" button opens. The page SHALL NOT offer a link to a render's viewer. The page SHALL show an API refusal next to the render it names. It SHALL NOT show model names, prompts, token counts or costs. It SHALL pass a recorded browser check before it counts as done.

#### Scenario: Rate a turntable
- **WHEN** the owner opens `hall-bench` v2 from the Pieces page in the inspector, chooses the Renders tab and rates the `draft` turntable down with "too dark"
- **THEN** the tab shows the down rating and the comment, and a reload shows the same

#### Scenario: No internals
- **WHEN** the Pieces page shows a render the Builder started
- **THEN** no model slug, prompt text or token figure appears on the page

#### Scenario: No viewer link
- **WHEN** a version has a published draft turntable and a still
- **THEN** the Pieces page shows the still with its rating controls, no card for the turntable, and no "Open the turntable viewer" link

## ADDED Requirements

### Requirement: The inspector has a Renders tab
The inspector, both its page and the conversation's split view, SHALL have a Renders tab beside its Model and Cut list tabs. The tab SHALL list every published render of the version, newest first:
- the still and the turntable;
- the still and the turntable in the room;
- the detailed still and the detailed turntable;
- each restyle variant.

Each item SHALL show its label and tier, and its current rating and comment with controls to rate up, rate down, edit the comment and clear, as on the Pieces page.

A selected turntable SHALL play in the tab as a frame scrubber:
- it shows the first frame at once;
- the owner moves through the frames with a slider, by dragging across the picture, and with the arrow keys;
- it wraps at both ends;
- it shows the frame number and the frame count.

A selected still SHALL show its picture. Frames and pictures SHALL be loaded only from the version's file routes and only when the tab is shown. The images SHALL stay files under the render root and SHALL NOT be stored in the database. The open tab and the selected render SHALL be part of the page's address, so a reload shows them again. A version with no renders SHALL say so in plain words. The tab SHALL NOT show a viewer link, a model name, prompt, token count or cost.

#### Scenario: Remote detail turntable played
- **WHEN** an approved `final` detail turntable of `hall-bench` v4 rendered on the render server has been published, and the owner opens the Renders tab and selects "Detailed turntable"
- **THEN** frame 1 of 36 is shown at once, and dragging or pressing the right arrow steps through the frames and wraps from 36 to 1

#### Scenario: Variant played and rated
- **WHEN** the owner selects the `walnut` variant on the Renders tab and rates it up
- **THEN** its 12 draft frames play in the scrubber, and the up rating is shown and kept after a reload

#### Scenario: Address keeps the selection
- **WHEN** the owner reloads while the Renders tab shows the detailed turntable
- **THEN** the Renders tab opens again with the detailed turntable selected

#### Scenario: Tab not opened
- **WHEN** the owner inspects a version and stays on the Model tab
- **THEN** no render frame is fetched

#### Scenario: No renders yet
- **WHEN** the owner opens the Renders tab of a built version with no renders
- **THEN** the tab says there are no renders of this version yet
