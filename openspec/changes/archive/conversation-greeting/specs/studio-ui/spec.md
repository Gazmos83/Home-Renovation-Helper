## MODIFIED Requirements

### Requirement: The conversation's messages scroll in their own box and open at the last message
The conversation view SHALL show the messages in a box that takes the window height left under the header and the title, with its own scroll bar. The composer, a pending confirmation card or a question form SHALL stay visible below the box without scrolling the page. When the inspector is open beside the chat, the same SHALL hold for the chat column.

Opening a conversation SHALL show the last message, scrolled to the bottom of the box. When a message, a reply, a notice or the waiting bubble is added:
- the box SHALL scroll to the bottom when the owner was already at the bottom;
- the box SHALL stay where it is when the owner had scrolled up.

Sending a message, or answering a confirmation or question form, SHALL always scroll the box to the bottom. An empty conversation SHALL show, in the box, a reply bubble signed "Little Homey" that reads "Little Homey here, how can I help?". The greeting SHALL be shown on the screen only: it SHALL NOT be saved in the thread's history, SHALL NOT need a model call, and SHALL NOT be shown once the conversation has a message.

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

#### Scenario: Greeting in a new conversation
- **WHEN** the owner opens a conversation with no messages
- **THEN** the box shows a bubble signed "Little Homey" reading "Little Homey here, how can I help?", and the "Nothing said yet" line is not shown

#### Scenario: Greeting is not part of the history
- **WHEN** the owner sends the first message in a new conversation
- **THEN** the greeting is no longer shown, and the thread's history holds only the owner's message and the replies
