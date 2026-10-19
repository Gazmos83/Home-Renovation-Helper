## MODIFIED Requirements

### Requirement: A render notice is shown in the conversation
The conversation view SHALL show each notice in the thread's history in its place among the messages, centred and framed like a confirmation, with its text. A piece render's notice SHALL show its text only, with no button: renders are viewed in the room inspector's Renders tab, and the piece inspector has none. A finished room render's notice SHALL show its link ("Open the turntable viewer" or "Open the still"), opening the result in a new tab. A failed render's notice, a shell's notice, and a room notice without a link SHALL show no button or link. A notice posted while the view is open SHALL appear without a reload while the thread's progress is following a render, including a room render started in the thread. A notice SHALL NOT show a model name, prompt, token count or cost.

#### Scenario: First draft ready
- **WHEN** a notice for a finished draft turntable of `hall-bench` version 1 is shown, posted before renders moved to rooms
- **THEN** it shows its text and no Review button

#### Scenario: Review opens the render
- **WHEN** the owner wants to look at a finished render of room `Hall` version 3
- **THEN** the room notice's link opens it, and the room pane's Renders tab for version 3 lists it

#### Scenario: Later version
- **WHEN** a notice is shown for a finished draft render of `hall-bench` version 3
- **THEN** it shows its text and no button

#### Scenario: Preview and final
- **WHEN** notices are shown for a finished final of `hall-bench` version 4 and for a version-1 render recorded at the removed tier `preview`
- **THEN** both show their text and no button

#### Scenario: Failed render
- **WHEN** a draft turntable of `hall-bench` version 2 fails
- **THEN** a notice says it did not finish and shows no button

#### Scenario: Room render link
- **WHEN** the draft turntable of `wohnen` version 11 finishes while the Murphy bed conversation is open
- **THEN** its notice appears without a reload, with an "Open the turntable viewer" link that opens the viewer in a new tab and no Review button

### Requirement: A piece version is reviewed beside the conversation
The Workspace's piece pane SHALL show the inspector for one piece version, with its version dropdown, in every layout that has a piece pane. It SHALL show the version named in the address (`?inspect=<package-id>/<n>`), or otherwise the latest version of the conversation's bound piece. When the conversation has no bound piece, the pane SHALL say in plain words that no piece has been designed yet in this conversation. While the inspector is shown, the owner SHALL still be able to read, scroll and send messages, and opening the inspector SHALL NOT start a turn. Opening another version, from the dropdown, a notice or the Project panel, SHALL replace the shown one and write it to the address, so a reload shows it again. When the current layout has no piece pane, opening a version SHALL switch to the "Chat and piece" layout. A version that is not built, or a file it lacks, SHALL be named in plain words as on the inspector page.

#### Scenario: Review from a notice
- **WHEN** the owner presses "Inspect version 1" on a build notice for `hall-bench` version 1
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
- **WHEN** the layout is "Chat and room" and the owner presses "Inspect version 2" on a build notice
- **THEN** the layout switches to "Chat and piece" and the piece pane shows version 2

#### Scenario: Close
- **WHEN** the piece pane is shown in "Chat and piece" and the owner chooses the "Chat and room" layout
- **THEN** the piece pane is no longer shown, and the room pane takes its place beside the chat

#### Scenario: Reload
- **WHEN** the owner reloads the conversation while the piece pane shows `hall-bench` version 2
- **THEN** the conversation and the inspector for version 2 are shown again, in the same layout

### Requirement: The Pieces page shows renders and takes feedback
The Studio SHALL show the owner a Pieces page that lists the pieces, then each piece's versions, then each version's published stills (the version's own, in the room, and detailed), showing for each:
- its kind and tier;
- its picture;
- its current rating and comment, with controls to rate up, rate down, edit the comment and clear.

Turntables and restyle variants SHALL NOT be listed on the Pieces page, and the piece inspector has no Renders tab. The page SHALL NOT offer a link to a render's viewer. The page SHALL show an API refusal next to the render it names. It SHALL NOT show model names, prompts, token counts or costs. It SHALL pass a recorded browser check before it counts as done.

#### Scenario: Rate a turntable
- **WHEN** the owner looks for a piece turntable to rate
- **THEN** the Pieces page lists stills only, and the piece inspector offers no Renders tab

#### Scenario: Rate a still
- **WHEN** the owner rates the `draft` still of `hall-bench` v2 down with "too dark" on the Pieces page
- **THEN** the page shows the down rating and the comment, and a reload shows the same

#### Scenario: No internals
- **WHEN** the Pieces page shows a render the Builder started
- **THEN** no model slug, prompt text or token figure appears on the page

#### Scenario: No viewer link
- **WHEN** a version has a published draft turntable and a still
- **THEN** the Pieces page shows the still with its rating controls, no card for the turntable, and no "Open the turntable viewer" link

### Requirement: The inspector shows and sets the version's verdict
The inspector, both its page and the conversation's split view, SHALL show the shown version's verdict above its tabs as one compact row, on every tab, whether or not the version is built or rendered. The row SHALL hold a thumbs up ("Matches what I confirmed") and a thumbs down ("Doesn't match what I confirmed"), each with that accessible name and tooltip, the chosen one shown as pressed. With no verdict, only the two thumbs SHALL be shown. A note field SHALL appear only once a thumb is chosen. A thumbs up SHALL be saved at once, with an optional note. A thumbs down SHALL be saved only with a note that is not blank; until then nothing is saved. Pressing the chosen thumb again SHALL clear the verdict.

While the note in the field differs from the saved note, the row SHALL show a **Save** button, for either thumb. Pressing Enter or Save SHALL save the note once; a second save SHALL NOT be sent while one is in flight, and leaving the field SHALL NOT save. A saved note SHALL be shown as text with a "Saved" mark and an **Edit** button; Edit SHALL open the field with that note, and Escape SHALL cancel the edit without saving. For a thumbs down, the row SHALL show whether it is open, resolved or dismissed, and offer "Mark resolved" and "Dismiss" while it is open. Switching versions SHALL show that version's verdict. A refusal SHALL be shown with its reason next to the row. The row SHALL NOT show a model name, prompt, token count or cost, and it SHALL pass a recorded browser check before it counts as done.

#### Scenario: Blockout marked wrong in the inspector
- **WHEN** the owner opens `amesbury-wardrobe` v4, presses thumbs down, writes "the side sections lost their 5 drawers" and presses Enter
- **THEN** thumbs down is shown pressed with the note, "Saved" and "open", and a reload shows the same

#### Scenario: Note on a thumbs up saved with Enter
- **WHEN** the owner presses thumbs up on `hall-bench` v3, writes "drawer heights are right" and presses Enter
- **THEN** the note is saved once, shown as text with "Saved" and an Edit button, and a reload shows the same

#### Scenario: Note edited
- **WHEN** the owner presses Edit on a saved note, changes it and presses Save
- **THEN** the new note replaces the old one and is shown as saved

#### Scenario: Edit cancelled
- **WHEN** the owner presses Edit, changes the text and presses Escape
- **THEN** nothing is saved and the saved note is shown again

#### Scenario: Note required
- **WHEN** the owner presses thumbs down and saves with an empty note
- **THEN** nothing is saved and the row asks for what does not match

#### Scenario: No note field before a choice
- **WHEN** the owner opens a version with no verdict
- **THEN** only the two thumbs are shown

#### Scenario: Cleared by pressing again
- **WHEN** the owner presses thumbs up on a version whose verdict is thumbs up
- **THEN** the verdict is cleared and the note field is gone

#### Scenario: Resolved
- **WHEN** the owner marks v4's open thumbs down resolved
- **THEN** the row shows it as resolved and no longer offers resolve or dismiss

## ADDED Requirements

### Requirement: The room inspector has a Renders tab
The Workspace's room pane, the room inspector beside the chat, SHALL offer two tabs for the composition version it shows: "3D view", the room's 3D view, and "Renders". The Renders tab SHALL list the version's published renders, newest first: its turntable and its still. A selected turntable SHALL play in the frame scrubber, showing frame 1 at once, and a selected still SHALL show its picture. Frames and pictures SHALL be loaded only from the version's file routes and only when the tab is shown. A version with no renders SHALL say so in plain words.

A built room version with no renders SHALL offer a "Render version <n> now" button. Pressing it SHALL first show, in one plain sentence, that this makes a quick turn-around preview of the room on this computer and about how long it takes, using the render guard's estimate, with a **Start** and a **Cancel** button. The sentence SHALL NOT mention frames, resolution or the engine. Start SHALL request a `draft` turntable of that room version through the render guard; no other tier SHALL be offered, and a `final` stays a request in the conversation. While that render is queued or running the tab SHALL say that version <n> is rendering, with the estimate, and SHALL show the finished turntable, selected, without a reload. A refusal SHALL be shown in plain words and nothing SHALL be started. A version that is not built SHALL NOT offer the button. The tab SHALL NOT show a model name, prompt, token count or cost.

#### Scenario: No renders yet
- **WHEN** the owner opens the Renders tab of a built room version with no renders
- **THEN** the tab says there are no renders of this version yet and offers "Render version <n> now"

#### Scenario: Render now
- **WHEN** the owner presses "Render version 3 now" on `Hall` v3 and then Start
- **THEN** the tab first said the preview takes about the guard's estimate, a `draft` turntable of the room is started, the tab says version 3 is rendering, and once it finishes the turntable is shown selected

#### Scenario: Cancel before starting
- **WHEN** the owner presses "Render version 3 now" and then Cancel
- **THEN** nothing is started and the tab shows the button again

#### Scenario: No benchmark yet
- **WHEN** no benchmark is stored and the owner presses "Render version 3 now"
- **THEN** the tab says in plain words that the benchmark must be run first, and offers no Start

#### Scenario: Turntable played
- **WHEN** the room version has a 12-frame draft turntable and the owner selects it
- **THEN** frame 1 of 12 is shown at once and the frames can be stepped through

### Requirement: The Measured Rooms page offers a room's blueprints
The Measured Rooms page SHALL show, for each measured room that belongs to an apartment with stored blueprints, one "Download blueprint <original name>" link per blueprint, newest first. Each link SHALL download the file as stored. A room with no blueprints SHALL show no blueprint line. The links SHALL NOT show a file-system path, model name, prompt, token count or cost. The page SHALL pass a recorded browser check before it counts as done.

#### Scenario: Blueprint downloaded
- **WHEN** the plan of the apartment holding `Wohnen` was confirmed from `grundriss.png`, and the owner opens `Wohnen` on the Measured Rooms page
- **THEN** "Download blueprint grundriss.png" is shown, and pressing it downloads that image

#### Scenario: Room measured by hand
- **WHEN** a room was recorded from typed measurements only
- **THEN** its card shows no blueprint line

## REMOVED Requirements

### Requirement: The inspector has a Renders tab
**Reason**: The owner decided on 2026-10-18 that renders belong to room versions, not pieces: the piece inspector's 3D view is enough for a piece, and its existing renders were deleted. The Renders tab moves to the room inspector ("The room inspector has a Renders tab").
**Migration**: A piece version is looked at in the inspector's Model tab. An old `?tab=renders` address opens the Model tab.
