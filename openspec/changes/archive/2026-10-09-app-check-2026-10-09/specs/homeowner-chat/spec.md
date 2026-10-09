## ADDED Requirements

### Requirement: A running turn can be stopped
The owner SHALL be able to stop the thread's running turn through an owner-gated route. A stopped turn SHALL end at the next step boundary: before the next model call or tool call. It SHALL end the stream with a `stopped` event. A stopped turn SHALL be discarded: reading the thread afterwards shows the history as it was before the owner's message. A tool call that completed before the stop SHALL NOT be undone. If one completed, the `stopped` event SHALL say so in plain words (for example "a build was already started"). A stop SHALL be answered with 409 when no turn is running, 404 for an unknown thread and 401 without the session cookie. A confirmation that is pending is not a running turn; it is answered as before.

#### Scenario: Stopped before any tool
- **WHEN** the owner sends "make it wider" and stops the turn while the Foreman is choosing
- **THEN** the stream ends with `stopped`, and reading the thread shows neither "make it wider" nor a reply

#### Scenario: Stopped after a build started
- **WHEN** the owner stops a turn after the Builder's build tool has started a build
- **THEN** the stream ends with `stopped` saying a build was already started, the build continues, and the turn is not in the thread's history

#### Scenario: Nothing running
- **WHEN** the owner stops a thread with no running turn
- **THEN** the answer is 409 and the thread is unchanged

### Requirement: The owner's latest message can be edited and sent again
The owner SHALL be able to replace the thread's latest owner message with new text through an owner-gated route, when no turn is running and no confirmation is pending. The thread SHALL be rewound to just before that message, removing it and every reply after it. The new text SHALL then run as a turn, streamed like any turn. Only the latest owner message SHALL be editable. Pieces, versions, renders, compositions and house-file writes made by the rewound turn SHALL stay. A rewound turn that confirmed one of them SHALL be named in the edit response, so the owner is told. Uploads attached to the replaced message SHALL be attached to the new one.

#### Scenario: Message corrected
- **WHEN** the owner's latest message was "make it 60 cm deep", the reply asked a question, and the owner edits it to "make it 45 cm deep"
- **THEN** the thread shows "make it 45 cm deep" and its new reply, and neither the old message nor the old reply

#### Scenario: Version already created
- **WHEN** the latest owner message's turn created `bench` v3 after a confirmed `yes` and the owner edits that message
- **THEN** the response names `bench` v3 as staying, and v3 still exists after the edited turn

#### Scenario: Older message
- **WHEN** the owner tries to edit a message that is not the latest owner message
- **THEN** the answer is 409 and the thread is unchanged

#### Scenario: Confirmation pending
- **WHEN** a confirmation is pending and the owner tries to edit the latest message
- **THEN** the answer is 409 naming the pending subject
