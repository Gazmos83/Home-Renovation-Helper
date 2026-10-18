## MODIFIED Requirements

### Requirement: A render notice is shown in the conversation
The conversation view SHALL show each notice in the thread's history in its place among the messages, centred and framed like a confirmation, with its text. A finished render of a piece version SHALL show a Review button that names the render's tier: "Review <tier> v1" when the version is 1, and "Review <tier> revision <n>" for version n above 1, where the tier is `draft` or `final`. Pressing it SHALL open the inspector for that piece version in the split view, on its Renders tab, with the most recently finished render of that tier selected. A finished room render's notice SHALL show its link ("Open the turntable viewer" or "Open the still"), opening the result in a new tab. A failed render's notice, a shell's notice, and a room notice without a link SHALL show no button or link. A notice posted while the view is open SHALL appear without a reload while the thread's progress is following a render, including a room render started in the thread. A notice SHALL NOT show a model name, prompt, token count or cost.

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

#### Scenario: Room render link
- **WHEN** the draft turntable of `wohnen` version 11 finishes while the Murphy bed conversation is open
- **THEN** its notice appears without a reload, with an "Open the turntable viewer" link that opens the viewer in a new tab and no Review button
