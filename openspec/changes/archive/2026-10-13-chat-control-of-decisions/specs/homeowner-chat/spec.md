## ADDED Requirements

### Requirement: The owner changes the decisions note by asking in the chat
The owner SHALL be able to add, change or delete one row of the active "decisions so far" note by asking an assistant in the chat. An assistant SHALL change a row only when the owner's own message explicitly asks for it; it MAY offer to, but SHALL NOT change the note unprompted or as a side effect of another request. Before anything is written the chat SHALL show the row as it is now and as it will be, and SHALL wait for the owner's "yes"; any other answer SHALL change nothing. The write SHALL be the panel's save: text neutralised, within the note's size limit, never leaving the note empty, and marked as the owner's. The note's thread and active build SHALL come from the session, never from a value the model supplies. A row SHALL be named by its topic, with its position when two rows share a topic; an unknown or ambiguous name SHALL be refused with the matching rows listed, and nothing SHALL be written. Deleting the only row SHALL be refused. The tool SHALL be switchable per conversation like other plugins. The panel SHALL show the changed note when the turn ends. A change made this way SHALL NOT change any spec, figure, price or house-file record.

#### Scenario: Nothing changes unprompted
- **WHEN** the owner states a decision or asks something else without asking for the note to change
- **THEN** no confirmation is shown and the note is unchanged, though the assistant may offer to add the decision

#### Scenario: A row is deleted on request
- **WHEN** the owner asks the assistant to remove the "Doors" decision and answers "yes" to the shown change
- **THEN** that row is removed from the note, the note is marked as the owner's, and the panel shows the note without that row

#### Scenario: The owner declines
- **WHEN** the owner answers anything but "yes" to the shown change
- **THEN** the note is unchanged and the assistant says nothing was changed

#### Scenario: A row is changed or added
- **WHEN** the owner asks to note that the shelves are 18 mm and confirms
- **THEN** the row for the shelves is changed, or a new "Shelves" row is added when none exists, and no other row changes

#### Scenario: A name matches several rows
- **WHEN** the owner names a topic that two rows share and gives no position
- **THEN** the call is refused before any confirmation, listing the matching rows with their positions, and the note is unchanged

#### Scenario: A last row or an empty edit is refused
- **WHEN** the request would delete the only row, or leave a row's topic or decision empty
- **THEN** the call is refused with the reason and the note is unchanged

#### Scenario: Another conversation's note is out of reach
- **WHEN** the model names another thread or another build in the call
- **THEN** the value is ignored or refused, and only the session's active note can be changed

#### Scenario: The tool is switched off
- **WHEN** the owner has switched the tool off for the conversation
- **THEN** the assistant cannot call it and says the tool is off

### Requirement: The owner records a decision from a chat message
Each message in the chat SHALL offer an "Add to decisions" action, shown as a bold, framed, light-green button. It SHALL make one model call that compresses the message into a one-line decision and a suggested topic, and open a new row in the "decisions so far" table with only those two values (never the full message text), for the owner to edit, save or cancel. Saving SHALL add the row as the panel's "Add Topic Decision" does, with the same checks and the owner's mark, and without a model call. Nothing SHALL be saved before the owner saves. If the compression call fails or is refused, the row SHALL open empty with a plain-words message.

#### Scenario: A compressed decision is recorded from a message
- **WHEN** the owner chooses "Add to decisions" on a long message
- **THEN** the new row opens with a one-line decision and a suggested topic, not the full message; after the owner saves, that row is added to the end of the active note and the panel shows it

#### Scenario: The compression fails
- **WHEN** the compression call fails or a token ceiling refuses it
- **THEN** the row opens empty, a plain-words message is shown, and the note is unchanged

#### Scenario: The owner cancels
- **WHEN** the owner chooses "Add to decisions" and then cancels
- **THEN** the note is unchanged

#### Scenario: The button's look
- **WHEN** a chat message shows "Add to decisions"
- **THEN** the button is bold, framed and light green
