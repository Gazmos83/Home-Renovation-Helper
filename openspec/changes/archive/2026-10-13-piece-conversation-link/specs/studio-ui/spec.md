## ADDED Requirements

### Requirement: The Pieces page opens or starts each piece's conversation
The Pieces page SHALL place a conversation link directly under each piece card's header (the piece's id or name). When that piece already has a conversation, the link SHALL open it. When it has none, the link SHALL start a conversation bound to that piece and open it. The link SHALL NOT show a model name, prompt, token count or cost. The flow SHALL pass a recorded browser check before it counts as done.

#### Scenario: Open the existing conversation
- **WHEN** `hall-bench` has a conversation and the owner chooses the conversation link under its header
- **THEN** that conversation opens

#### Scenario: Start when the piece has none
- **WHEN** `shoe-rack` has no conversation and the owner chooses the conversation link under its header
- **THEN** a conversation bound to `shoe-rack` is started and opens with the composer ready

### Requirement: The Pieces page starts a conversation for a new piece
The Pieces page SHALL show a "Create A New Piece" button at the top of the page. Choosing it SHALL start an unbound conversation and open it so the owner can describe a new piece. The button SHALL NOT show a model name, prompt, token count or cost. The flow SHALL pass a recorded browser check before it counts as done.

#### Scenario: Create A New Piece
- **WHEN** the owner clicks "Create A New Piece"
- **THEN** an untitled conversation with no bound piece opens with the composer ready

#### Scenario: Button at the top
- **WHEN** the owner opens the Pieces page with two pieces listed
- **THEN** "Create A New Piece" is shown above the piece cards

### Requirement: Conversations are not listed in the Studio navigation
The Studio navigation SHALL NOT include a Conversations item. Routes `/conversations` and `/conversations/:threadId` SHALL remain reachable by deep link and from the Pieces page conversation links. After sign-in the owner SHALL land on the Pieces page.

#### Scenario: Nav without Conversations
- **WHEN** the owner is signed in and looks at the Studio navigation
- **THEN** there is no Conversations item, and Pieces is present

#### Scenario: Sign-in lands on Pieces
- **WHEN** the owner signs in successfully
- **THEN** the Studio opens on the Pieces page

#### Scenario: Deep link still works
- **WHEN** the owner opens `/conversations/<thread-id>` for an existing conversation
- **THEN** that conversation view opens

## MODIFIED Requirements

### Requirement: Conversations show their tool toggles
The conversation view SHALL show the conversation's toggleable tools by plain name and description with their on/off state in the Tools flyout, letting the owner switch them; tools that cannot be toggled SHALL be shown as always on. No conversation page SHALL show model names, token counts or costs. Starting a conversation and opening an existing one for navigation SHALL happen from the Pieces page as set out in the Pieces conversation requirements; the Conversations list page is not part of the Studio navigation. Delete of a conversation SHALL be offered on the conversation view as set out in "Conversations are deleted from the list".

#### Scenario: Toggle a tool
- **WHEN** the owner opens the Tools flyout and switches off the room check in one conversation
- **THEN** the flyout shows it off for that conversation and the next turn there binds no `room_fit`

#### Scenario: List entry
- **WHEN** a conversation is about `hall-bench` and last had a turn today
- **THEN** the Pieces page conversation link for `hall-bench` opens that conversation

#### Scenario: Start without a title
- **WHEN** the owner clicks "Create A New Piece"
- **THEN** an untitled conversation opens with the composer ready, and after the first reply its heading shows the generated title

#### Scenario: Delete with confirmation
- **WHEN** the owner chooses delete on the open conversation "Listening wall" and confirms
- **THEN** the conversation is gone and the owner is on the Pieces page; when the owner cancels instead, nothing changes

### Requirement: Conversations are deleted from the list
The conversation view SHALL offer a delete action. It asks for confirmation, naming the conversation and stating that its pieces and renders are kept and that the conversation cannot be restored. A confirmed delete SHALL remove the conversation and return the owner to the Pieces page; a cancel changes nothing. A refusal (a reply still being written, or memory unavailable) SHALL be shown in words on the conversation view, which stays open. The delete flow SHALL pass a recorded browser check before it counts as done.

#### Scenario: Delete with confirmation
- **WHEN** the owner chooses delete on the open conversation "Hall shoe bench" and confirms
- **THEN** the conversation is gone, the owner is on the Pieces page, and the piece is still listed there

#### Scenario: Cancel
- **WHEN** the owner chooses delete and then cancels
- **THEN** nothing is sent and the conversation stays open

#### Scenario: Refused while a reply is written
- **WHEN** the owner confirms a delete while that conversation's turn is running
- **THEN** the conversation stays open and the refusal is shown on the view
