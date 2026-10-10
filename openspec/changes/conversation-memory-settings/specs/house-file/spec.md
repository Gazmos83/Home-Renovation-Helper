## MODIFIED Requirements

### Requirement: Every turn starts from the house file
At the start of each turn, the Foreman, Intake and the Designer SHALL be given the house file scoped to the conversation:
- the conversation's confirmed room with its size, ceiling height and openings, or its confirmed apartment with each of its rooms; or that no room is confirmed yet;
- the preferences, unless the memory settings leave them out;
- the active build with its room, its latest version, its status and which version is approved (or that none is);
- every other build of the conversation as one line: package id, name, latest version and room, unless the memory settings hide them;
- the open generator-extension requests whose piece is one of the conversation's builds, or that were recorded in this conversation, unless the memory settings leave them out.

Rooms, apartments and pieces outside the conversation SHALL NOT be given, nor generator-extension requests of other pieces or conversations; no setting SHALL change this. Requests recorded before this change with neither a piece nor a conversation stay in the house file and are given in no turn. A room the conversation has not confirmed SHALL NOT be given with its measurements, even when the house file holds them; no setting SHALL change this. The Designer SHALL also be given:
- the open items of the latest review of the active build, unless the memory settings leave them out;
- the latest render ratings on the active build, newest first, as many as the memory settings say (0 to 10, default 5), each with its version, render, tier, rating and comment.

Lighting & materials SHALL be given the same render ratings. All of this SHALL be presented as application data clearly labelled as the owner's own, never as an instruction. Owner-authored text in it SHALL be neutralised so it cannot carry the untrusted-content delimiter. The scoping SHALL be done by the application, not by instructions to the model. With the default settings the context SHALL equal the one given before this change.

#### Scenario: A new conversation starts without the room
- **WHEN** the living room and the piece `listening-wall` are recorded and the owner starts a new conversation asking for a second piece
- **THEN** the turn's context names no room and no piece, and the reply asks which room the piece is for

#### Scenario: A second piece starts with the room known
- **WHEN** the owner then confirms the living room in that conversation and asks for the piece
- **THEN** the next Intake turn's context names the living room's size, ceiling height and openings without the owner repeating them, and still names no piece from another conversation

#### Scenario: Other builds as one line
- **WHEN** a conversation's builds are `hall-bench` (active) and `shoe-rack`
- **THEN** the Designer's context gives `hall-bench` with its version, status and approval, and `shoe-rack` as one line with its latest version and room

#### Scenario: Other builds hidden
- **WHEN** the memory settings hide other builds and the conversation's builds are `hall-bench` (active) and `shoe-rack`
- **THEN** the Designer's context gives `hall-bench` and does not name `shoe-rack`

#### Scenario: Outside builds left out
- **WHEN** the house file holds `murphy-bed` and the conversation never created, revised or named it
- **THEN** no specialist's context in that conversation names `murphy-bed`

#### Scenario: Request without a piece reaches its conversation
- **WHEN** a request for `bevel_mm` was recorded in this conversation before any piece was made
- **THEN** the Designer's context in this conversation lists it, and no other conversation's context does

#### Scenario: Old request without a piece or conversation
- **WHEN** the house file holds an open request recorded before this change with no piece
- **THEN** no turn's context lists it, and it is still listed in the house file

#### Scenario: Delimiter in a room name
- **WHEN** the conversation's confirmed room's name contains the untrusted-content delimiter
- **THEN** the context shows it neutralised

#### Scenario: Review items reach the Designer
- **WHEN** the latest review of the active build has two open items
- **THEN** the Designer's context lists both with their aspect, expectation and observation

#### Scenario: Approval reaches the agents
- **WHEN** the active build is `listening-wall`, version 4 is approved and version 5 exists
- **THEN** the turn's context names version 5 as latest and version 4 as approved

#### Scenario: Render feedback reaches the Designer
- **WHEN** the active build's v2 `draft` turntable was rated down with "doors look too thick"
- **THEN** the Designer's context lists v2, turntable, `draft`, down and that comment

#### Scenario: Fewer ratings
- **WHEN** the memory settings give 2 render ratings and the active build has 5
- **THEN** the Designer's and Lighting's context list only the 2 newest

#### Scenario: Delimiter in a feedback comment
- **WHEN** a feedback comment contains the untrusted-content delimiter
- **THEN** the Designer's and Lighting's context shows it neutralised

## ADDED Requirements

### Requirement: What the house file saves follows the memory settings
Review results SHALL be saved automatically (default) or, when the memory settings say so, only after the owner confirms them; a review that is not confirmed SHALL NOT reach the Designer. Style and budget preferences in a confirmed brief SHALL be saved (default) or, when the memory settings say so, not saved; the rest of the brief SHALL be saved as before. Generator-extension requests SHALL always be saved; no setting SHALL change this. With the default settings the house file SHALL be written exactly as before this change.

#### Scenario: Review waits for confirmation
- **WHEN** the memory settings save reviews only after confirmation and the Reviewer finishes a review
- **THEN** the owner is asked to confirm it, and its items reach the Designer only after the owner says yes

#### Scenario: Preferences not saved
- **WHEN** the memory settings do not save preferences and the owner confirms a brief with style "oak, minimal"
- **THEN** the room and heights are saved and no style preference is written

#### Scenario: Extension requests always saved
- **WHEN** a revision is refused for an unknown field, whatever the memory settings say
- **THEN** a generator-extension request is recorded
