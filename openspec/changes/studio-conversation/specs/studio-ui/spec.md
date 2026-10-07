## MODIFIED Requirements

### Requirement: Conversations show their tool toggles
The Studio SHALL list the owner's conversations with their title, the piece each is about when one is bound, and when each last had a turn, newest activity first, and SHALL open a conversation on its own route. The conversation view SHALL show the conversation's toggleable tools by plain name and description with their on/off state, letting the owner switch them; tools that cannot be toggled SHALL be shown as always on. No conversation page SHALL show model names, token counts or costs.

#### Scenario: Toggle a tool
- **WHEN** the owner switches off the room check in one conversation
- **THEN** the page shows it off for that conversation and the next turn there binds no `room_fit`

#### Scenario: List entry
- **WHEN** a conversation is about `hall-bench` and last had a turn today
- **THEN** its list entry shows the title, `hall-bench` and today's time, and clicking it opens the conversation

## ADDED Requirements

### Requirement: The conversation view is the homeowner's chat
The conversation view SHALL show the owner's messages and the replies in order, a composer that sends one message as one turn and shows the reply when it arrives, and the turn's refusal in words next to the composer when the service refuses it. While a turn is running the composer SHALL be disabled and say so. A reply's specialist SHALL be shown by role name only.

#### Scenario: Send and read
- **WHEN** the owner types "I want a bench for the hall" and sends it
- **THEN** the message appears at once, the composer is disabled until the reply arrives, and the reply appears under it labelled by the specialist's role

#### Scenario: Refused turn
- **WHEN** the service answers the turn with 503 and the memory reason
- **THEN** the reason is shown next to the composer and the owner's message is not kept in the list

### Requirement: A pending confirmation is answered in the view
When a reply carries a pending confirmation the view SHALL show it as a card with its subject, summary and proposal, a **Yes** and a **No** button and an optional reason, and SHALL hide the composer until it is answered. Answering SHALL send the owner's answer on the thread and show the reply that follows. Reopening a conversation with a confirmation still pending SHALL show the card again.

#### Scenario: Yes
- **WHEN** the Designer proposes a revision and the owner clicks Yes
- **THEN** the view shows the reply that reports the new version and the composer returns

#### Scenario: No with a reason
- **WHEN** the owner clicks No with "make it 4 shelves"
- **THEN** the reason is sent with the answer and the next reply is shown

#### Scenario: Reopened while pending
- **WHEN** the owner reloads a conversation that has a pending brief confirmation
- **THEN** the card is shown and the composer is hidden

### Requirement: Plans and photos are attached from the view
The conversation view SHALL let the owner add PNG or JPEG images to the conversation and attach them to the next message; attached images SHALL be shown as thumbnails on the composer and in the sent message, and a refused upload (type, size, count) SHALL be reported in the service's words.

#### Scenario: Attach a blueprint
- **WHEN** the owner adds `blueprint.jpeg` and sends "This is my flat"
- **THEN** the turn carries the upload and the sent message shows the thumbnail

#### Scenario: Too large
- **WHEN** the owner adds an image over the configured size
- **THEN** the refusal's reason is shown and nothing is attached

### Requirement: The conversation view shows the project's progress
The conversation view SHALL show a project panel with the bound piece, its latest version and build state, the progress steps (brief confirmed, piece created, built, draft or preview rendered, reviewed with open items, detail pass, final) each marked done or not, the next step the owner can ask for, the latest screenshot or still when one exists, and the piece's open generator-extension requests. The panel SHALL refresh while a build is queued or running and after every turn. It SHALL show nothing when the service's progress read is refused other than the refusal's reason.

#### Scenario: After the first build
- **WHEN** the Builder's build of version 1 finishes while the view is open
- **THEN** the panel shows version 1 built with its screenshot, "built" done, and the next step as a draft render, without a reload

#### Scenario: Open review items
- **WHEN** the latest review of the piece has two open items
- **THEN** the panel shows "reviewed, 2 open" and links to the piece's page
